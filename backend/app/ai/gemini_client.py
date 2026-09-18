"""Gemini client - EXPLANATION LAYER ONLY.

Gemini never decides anything in this system. It receives a structured,
backend-generated context object and explains it in words. The optimizer
(OR-Tools CP-SAT) is authoritative; the database is authoritative; Gemini
is a narrator.

Guardrails implemented here, not merely requested in a prompt:
  * The model id is read from GEMINI_MODEL - never hardcoded.
  * The context object is built by the backend and serialized as JSON, so
    the model cannot reach past what it was handed.
  * A hard system instruction forbids inventing values or overriding the
    optimizer.
  * If Gemini is unavailable the caller gets an explicit failure. No
    fabricated "AI response" is ever synthesized as a fallback.

API shape verified by introspecting google-genai 2.24.0:
    Client(api_key=...)
    client.models.generate_content(model=..., contents=..., config=...)
    types.GenerateContentConfig(system_instruction=..., temperature=...)
"""
import json
import re
import time
from typing import Any

from app.core.config import get_settings
from app.core.logging import get_logger
from app.integrations.base import IntegrationError, NotConfigured, SourceStatus

logger = get_logger(__name__)

PROVIDER = "Gemini"
SOURCE_NAME = "gemini"
IS_CORE_DEPENDENCY = False   # the product works fully without AI

SYSTEM_INSTRUCTION = """You are an industrial carbon intelligence assistant.

You explain data and optimization results that the backend supplies to you.
You are NOT the optimizer and you are NOT a data source.

RULES - these are absolute:
1. Use ONLY the structured context supplied in the user message. If a value
   is not in that context, say it is not available. Never estimate it.
2. NEVER invent or alter: emissions figures, emission factors, action costs,
   expected reductions, budgets, allocations, timestamps or API results.
3. NEVER change, second-guess or override the optimizer's decision. The
   allocation in `optimization_result` was produced by Google OR-Tools
   CP-SAT and is authoritative. If asked for a different allocation, explain
   that the optimizer must be re-run with different inputs.
4. NEVER declare that data is fraudulent or that a company is lying. You may
   only describe which validation rules were triggered and what they mean.
5. Respect data provenance. Each value carries a data_class:
     measured         - reported/measured by an external regulated source
     api_derived      - returned by an external API
     calculated       - computed by this system from other values
     demo_assumption  - a prototype assumption, NOT a real measurement
   Never describe a calculated or assumed value as measured. When you cite a
   number that is a demo_assumption, say so.
6. If the context shows a source is STALE or UNAVAILABLE, say so plainly
   rather than presenting the figure as current.
7. Be concise and concrete. Quote the actual numbers from the context.

You explain. You do not decide."""


def _client():
    """Build a Gemini client, or raise a truthful error."""
    s = get_settings()
    if not s.gemini_configured:
        missing = []
        if not s.gemini_enabled:
            missing.append("GEMINI_ENABLED=true")
        if not s.gemini_api_key.strip() or s.gemini_api_key.strip() == "your_key_here":
            missing.append("GEMINI_API_KEY")
        if not s.gemini_model.strip():
            missing.append("GEMINI_MODEL")
        raise NotConfigured(PROVIDER, ", ".join(missing) or "GEMINI_API_KEY")
    try:
        from google import genai
    except ImportError as exc:  # pragma: no cover
        raise IntegrationError(
            "The google-genai package is not installed. Run: pip install google-genai",
            SourceStatus.UNAVAILABLE, PROVIDER,
        ) from exc
    return genai.Client(api_key=s.gemini_api_key)


def build_context(
    operational_data: Any = None,
    carbon_analysis: Any = None,
    hotspots: Any = None,
    actions: Any = None,
    constraints: Any = None,
    optimization_result: Any = None,
    scenario: Any = None,
    data_provenance: Any = None,
    source_health: Any = None,
) -> dict[str, Any]:
    """Assemble the ONLY information Gemini is allowed to see.

    Anything omitted here is genuinely unavailable to the model, which is
    what makes rule 1 enforceable rather than aspirational.
    """
    return {
        "operational_data": operational_data,
        "carbon_analysis": carbon_analysis,
        "hotspots": hotspots,
        "actions": actions,
        "constraints": constraints,
        "optimization_result": optimization_result,
        "scenario": scenario,
        "data_provenance": data_provenance,
        "source_health": source_health,
    }


def _error_detail(exc: Exception) -> tuple[int | None, str]:
    """Pull the real HTTP code and message out of an SDK exception.

    Reporting only `type(exc).__name__` ("ServerError") hides whether the
    problem is a bad key, a wrong model id, or transient overload.
    """
    code = getattr(exc, "code", None) or getattr(exc, "status_code", None)
    text = str(exc)
    if code is None:
        m = re.search(r"\b(4\d{2}|5\d{2})\b", text)
        if m:
            code = int(m.group(1))
    m = re.search(r"'message':\s*'([^']+)'", text) or re.search(r'"message":\s*"([^"]+)"', text)
    detail = m.group(1) if m else text.split("\n")[0][:200]
    return (int(code) if code else None), detail


def _user_message(code: int | None, detail: str, model: str) -> str:
    """A message that tells the user what to actually do."""
    if code == 503:
        return (
            f"Gemini model '{model}' is temporarily overloaded (503): {detail} "
            "Retry shortly, or set GEMINI_MODEL to a less busy model such as "
            "gemini-2.5-flash or gemini-flash-latest."
        )
    if code == 404:
        return (
            f"Gemini model '{model}' was not found (404). Check GEMINI_MODEL. "
            "Your key's available models can be listed from the Gemini API."
        )
    if code in (401, 403):
        return f"Gemini rejected the API key ({code}). Check GEMINI_API_KEY in backend/.env."
    if code == 429:
        return f"Gemini rate limit reached (429): {detail}"
    return f"Gemini request failed{f' ({code})' if code else ''}: {detail}"


def explain(
    question: str,
    context: dict[str, Any],
    temperature: float = 0.2,
    max_retries: int = 2,
) -> dict[str, Any]:
    """Ask Gemini to explain the supplied context.

    Raises IntegrationError when Gemini is unavailable. The caller must
    surface that honestly and continue showing backend results.
    """
    s = get_settings()
    client = _client()

    try:
        from google.genai import types
    except ImportError as exc:  # pragma: no cover
        raise IntegrationError(
            "google-genai types unavailable.", SourceStatus.UNAVAILABLE, PROVIDER
        ) from exc

    payload = json.dumps(context, default=str, indent=2)
    prompt = (
        "STRUCTURED BACKEND CONTEXT (this is the only data you may use):\n"
        f"```json\n{payload}\n```\n\n"
        f"QUESTION: {question}\n\n"
        "Answer using only the context above. If the context does not contain "
        "what is needed, say so explicitly."
    )

    cfg = types.GenerateContentConfig(
        system_instruction=SYSTEM_INSTRUCTION, temperature=temperature
    )

    # 503 ("high demand") and 429 are explicitly transient - Google's own
    # message says spikes are usually temporary - so they are worth retrying.
    last_exc: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            resp = client.models.generate_content(
                model=s.gemini_model, contents=prompt, config=cfg
            )
            break
        except Exception as exc:  # noqa: BLE001 - SDK raises varied provider errors
            last_exc = exc
            code, detail = _error_detail(exc)
            if code in (429, 500, 502, 503, 504) and attempt < max_retries:
                time.sleep(1.5 * (2 ** attempt))
                continue
            logger.warning(
                "Gemini call failed", extra={"event": "gemini", "status": str(code or "error")}
            )
            raise IntegrationError(
                _user_message(code, detail, s.gemini_model), SourceStatus.ERROR, PROVIDER, code
            ) from exc
    else:  # pragma: no cover - loop always breaks or raises
        code, detail = _error_detail(last_exc) if last_exc else (None, "")
        raise IntegrationError(
            _user_message(code, detail, s.gemini_model), SourceStatus.ERROR, PROVIDER, code
        )

    text = getattr(resp, "text", None)
    if not text:
        raise IntegrationError(
            f"{PROVIDER} returned an empty response.", SourceStatus.ERROR, PROVIDER
        )

    return {
        "answer": text,
        "model": s.gemini_model,
        "provider": PROVIDER,
        "context_keys": [k for k, v in context.items() if v is not None],
        "disclaimer": (
            "Generated by an AI assistant from backend data. The optimization "
            "decision itself was made by OR-Tools CP-SAT, not by the AI."
        ),
    }


def check_availability() -> dict[str, Any]:
    s = get_settings()
    if not s.gemini_configured:
        return {
            "provider": PROVIDER,
            "status": SourceStatus.UNAVAILABLE.value,
            "message": (
                "Gemini is not configured. Set GEMINI_ENABLED=true, GEMINI_API_KEY "
                "and GEMINI_MODEL in backend/.env."
            ),
            "model": s.gemini_model or None,
        }
    return {
        "provider": PROVIDER,
        "status": "CONFIGURED",
        "message": "Gemini is configured. Availability is confirmed on first use.",
        "model": s.gemini_model,
    }
