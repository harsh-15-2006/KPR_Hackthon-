# Industrial Carbon Intelligence & Budget-Constrained Reduction Optimization

**Problem Statement: SU-04 — Industrial Carbon Intelligence & Reduction Engine**
**Domain 03 — Sustainability**

---

## 1. Problem Statement

> Organizations generate emissions across multiple operational sources including
> electricity, fuel, logistics, production and waste. **Merely calculating total emissions
> does not tell an organization which actions will provide the greatest reduction.** Build a
> carbon-intelligence system that estimates operational emissions and recommends reduction
> strategies under realistic business constraints. A core challenge is the **fixed
> sustainability budget**: given limited resources for sustainability initiatives, determine
> how they should be allocated to maximize carbon reduction.
>
> **Key challenge — Transform carbon measurement into an actionable optimization problem.**

### Why a carbon calculator is not enough

Knowing you emit 620 tonnes tells you your score. It does not tell you your next move.
A plant with ₹1 crore for sustainability has more candidate projects than money, and the
obvious approach — rank actions by cost-per-tonne and buy down the list until the money runs
out — is **provably not optimal** when projects are indivisible.

On our own demo data, that greedy approach spends ₹88L for 1,830 tCO₂e. The optimizer finds
**₹98L for 1,930 tCO₂e** — **+100 tCO₂e from the same budget.** That gap is the entire project.

---

## 2. Proposed Solution

A system that carries an organization all the way from raw activity data to a **funded,
constraint-respecting decarbonisation plan**.

```
Operational data          electricity · fuel · logistics · production · waste
        ↓
Data trust validation     6 deterministic checks; implausible records held for review
        ↓
Emission calculation      activity data × emission factor  (Climatiq)
        ↓
Hotspot identification    source_co2e / total_co2e × 100   (deterministic)
        ↓
Reduction action library  cost + expected reduction + capacity per action
        ↓
Business constraints      max actions per source · mutual exclusion · spend caps
        ↓
Fixed sustainability budget
        ↓
OR-TOOLS CP-SAT           maximize Σ reduction·x  s.t.  Σ cost·x ≤ budget
        ↓
Budget allocation         which actions to fund, and why each was chosen or rejected
        ↓
Expected carbon reduction proven optimal when objective == best bound
```

**The optimizer is authoritative.** Gemini explains the result in words; it never makes or
alters the allocation.

---

## 3. Key Features

Every item below is implemented and working in this repository.

| Feature | What it does |
|---|---|
| **Multi-source emission calculation** | Five sources, each with its own activity unit — no universal kWh assumption |
| **Data trust layer** | 6 checks (schema, duplicate, intensity benchmark, historical trend, cross-source, provenance) → trust score → human Approve/Reject |
| **Hotspot analysis** | Deterministic per-source totals and contribution %, with provenance on every value |
| **Reduction action library** | Full CRUD; every value carries its evidence source and a demo-assumption flag |
| **Budget allocation optimization** | Google OR-Tools CP-SAT, with business constraints and proof of optimality |
| **Explainability** | Per-action reason for every funding decision, including why an action was rejected |
| **What-if simulation** | Independent scenario runs; the baseline is never overwritten |
| **Re-optimization** | Re-run on changed inputs with a full change history |
| **AI-assisted explanation** | Gemini explains stored results from a backend-built context only |
| **Reports** | CSV and printable HTML, generated from database values — never from the AI |
| **Authentication & multi-tenancy** | Company registration, bcrypt passwords, JWT sessions; each company sees only its own data |
| **Administrator console** | Platform-wide view of every company, with audit log |
| **Fault tolerance** | Retries, exponential backoff, circuit breaker, stale-cache fallback, source health |

---

## 4. Architecture

```
React 19 + TypeScript + Vite + Tailwind + Recharts
        │  Axios  (the browser talks ONLY to FastAPI — never to a vendor API)
        ▼
FastAPI  ──►  Climatiq          activity data → CO₂e            (calculated)
        │     Electricity Maps  grid carbon intensity           (api_derived)
        │     EPA CAMPD         US power-sector measured CO₂    (measured, optional)
        │     Gemini            explanation layer only
        ▼
Auth + tenancy ──► Fault tolerance ──► Data trust ──► Supabase PostgreSQL
                                                            │
                                                            ▼
                          Carbon analysis → Hotspots → OR-Tools CP-SAT → Allocation
```

### Layering rule

```
routes/        HTTP only — validate input, call a service, shape the response
services/      business logic — no HTTP, no vendor SDKs
integrations/  vendor APIs — no business logic
optimization/  pure math — no FastAPI, no database, no vendor imports
```

Each layer only calls downward, which is why the optimizer is unit-testable with no server
running and no database.

---

## 5. Technology Stack

| Layer | Technology |
|---|---|
| Frontend | React 19 · TypeScript · Vite 8 · Tailwind CSS 4 · Recharts 3 · React Router 7 · Axios |
| Backend | Python 3.14 · FastAPI · Pydantic v2 · SQLAlchemy 2.0 · httpx |
| Database | Supabase PostgreSQL (psycopg v3) |
| Optimization | **Google OR-Tools CP-SAT** |
| Emission factors | Climatiq API (`data_version 37`) |
| Grid carbon intensity | Electricity Maps API (India zones IN-SO / IN-NO / IN-WE / IN-EA / IN-NE) |
| Measured reference data | EPA Clean Air Markets (CAMPD) — optional connector |
| AI | Gemini (model configurable via `GEMINI_MODEL`) |
| Auth | bcrypt (cost 12) · PyJWT HS256 |

---

## 6. Project Structure

```
KPR_Hackthon-
├── README.md
├── .gitignore
│
├── backend/
│   ├── app/
│   │   ├── main.py                FastAPI entrypoint
│   │   ├── core/                  config · logging · security · deps · fault_tolerance
│   │   ├── optimization/          models · constraints · optimizer   ← CP-SAT lives here
│   │   ├── integrations/          climatiq · electricity_maps · epa · base
│   │   ├── ai/                    gemini_client
│   │   ├── services/              emission · hotspot · action · optimization · trust
│   │   ├── routes/                auth · emissions · hotspots · actions
│   │   │                          optimization · ai · trust · reports
│   │   ├── models/                SQLAlchemy models
│   │   ├── schemas/               Pydantic request/response models
│   │   └── db/                    engine + session
│   ├── tests/
│   ├── sample_data/               CSVs for testing, valid and deliberately invalid
│   ├── requirements.txt
│   └── .env.example
│
├── frontend/
│   ├── src/
│   │   ├── pages/                 Landing · Dashboard · OperationalData · CarbonAnalysis
│   │   │                          DataQuality · ReductionActions · Optimization
│   │   │                          AIAgent · WhatIf · Reoptimization · Reports · AdminPanel
│   │   ├── components/            Layout · ui · charts · optimization · Comparison
│   │   ├── contexts/              AuthContext
│   │   ├── services/              api.ts (single Axios client)
│   │   ├── types/                 TypeScript API types
│   │   └── utils/                 formatting, source labels and colours
│   └── package.json
│
└── supabase/
    └── migrations/                SQL schema migrations
```

---

## 7. Setup

### 7.1 Clone

```bash
git clone https://github.com/harsh-15-2006/KPR_Hackthon-.git
cd KPR_Hackthon-
```

### 7.2 Backend

```bat
cd backend
python -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements.txt
if not exist .env copy .env.example .env
```

> ⚠️ Never run a bare `copy .env.example .env` — it silently overwrites an existing `.env`
> and destroys every key in it. The guarded form above is safe to re-run.

Fill in `backend\.env` (see [Environment Variables](#8-environment-variables)), then:

```bat
.\venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Backend runs at `http://127.0.0.1:8000` · API docs at `http://127.0.0.1:8000/docs`

> Calling `venv\Scripts\python.exe` directly avoids PowerShell's execution-policy block on
> `Activate.ps1`.

### 7.3 Frontend

In a second terminal:

```bat
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`. Vite proxies `/api` to the backend, so no CORS setup is needed
in development. **Start the backend first.**

### 7.4 First use

1. Open the app → **Register a company** → this creates your workspace and owner account.
2. **Operational Data** → add activity data, or upload `backend/sample_data/valid_full.csv`.
3. **Optimization** → set a budget → **Optimize**.

To create the platform administrator, set `ADMIN_SETUP_KEY` in `.env` and POST once to
`/api/auth/bootstrap-admin`. It refuses after the first administrator exists.

---

## 8. Environment Variables

All are **server-side only**. Never create `VITE_` copies — those reach the browser.
`.env` is gitignored; `.env.example` holds placeholders only.

| Variable | Required | Notes |
|---|---|---|
| `DATABASE_URL` | for persistence | Supabase Postgres — **use the Session pooler** (see below) |
| `JWT_SECRET` | yes | Must be ≥ 32 bytes. `python -c "import secrets;print(secrets.token_urlsafe(48))"` |
| `ADMIN_SETUP_KEY` | for admin bootstrap | Gate for creating the first administrator |
| `CLIMATIQ_API_KEY` | for real factors | Blank ⇒ Demo Mode |
| `CLIMATIQ_DATA_VERSION` | no | `^37` |
| `ELECTRICITY_MAPS_API_KEY` | for grid intensity | |
| `ELECTRICITY_MAPS_DEFAULT_ZONE` | no | e.g. `IN-SO` |
| `GEMINI_API_KEY` + `GEMINI_ENABLED=true` + `GEMINI_MODEL` | for AI | |
| `EPA_API_KEY` | optional | EPA's public `DEMO_KEY` works for testing |
| `CORS_ORIGINS` | no | Defaults to the local dev ports |

### Two Supabase gotchas that cost real time

1. **The Direct connection is IPv6-only.** `db.<ref>.supabase.co` publishes only an AAAA
   record, so on an IPv4 network it can never resolve. Use **Project Settings → Database →
   Connection string → Session pooler** (port `5432`). Avoid the Transaction pooler on `6543` —
   it breaks SQLAlchemy's prepared statements.
2. **A password containing `@ : / #` breaks URL parsing.** The app percent-encodes it
   automatically, so paste the connection string **verbatim** — do not hand-edit it, and do not
   delete the special character (that changes the password).

If the database is unreachable the app does **not** crash: it falls back to local SQLite,
keeps working, and reports the reason in `/api/health` and in the UI header.

---

## 9. Data Provenance — the core honesty rule

Every stored value carries a `data_class`:

| Class | Meaning |
|---|---|
| `measured` | Reported/measured by an external regulated source (EPA CAMPD) |
| `api_derived` | Returned by an external API (Electricity Maps grid intensity) |
| `calculated` | Computed by this system (activity × emission factor) |
| `demo_assumption` | A prototype assumption — **not a measurement** |

Enforced in code, not by convention:

- A failed API call **never** becomes a fabricated value — it returns an error, or clearly
  labelled STALE cached data.
- A missing measurement stays missing. **It is never zero-filled.**
- An unrecognised CO₂e unit **raises** rather than being assumed to be kilograms.
- Reduction-action costs are `is_demo_assumption = true` unless given an evidence source.

---

## 10. Optimization Model

```
maximize    Σᵢ  expected_reductionᵢ · xᵢ
subject to  Σᵢ  costᵢ · xᵢ  ≤  budget
            0 ≤ xᵢ ≤ capacityᵢ ,  xᵢ ∈ ℤ
            + configured business constraints
```

This is a **bounded knapsack problem** (NP-hard), solved exactly by CP-SAT.

- Costs scale with `ceil`, reductions with `floor`, so integer rounding can never permit a
  real-money overspend.
- Boolean indicators track "is this action funded at all", so counting constraints count
  **distinct actions**, not units.
- Deterministic: `num_workers=1`, `random_seed=42` — the same inputs always give the same
  allocation, which is what makes a stored run reproducible.
- `objective_value == best_bound` ⇒ **proven optimal**.
- Statuses: `OPTIMAL` · `FEASIBLE` · `INFEASIBLE` · `UNKNOWN` · `MODEL_INVALID`, each with a
  plain-English explanation.

---

## 11. Data Trust Layer

Six deterministic checks run on every record. **No machine learning is involved** — the
repository imports no ML library.

Schema/range · Duplicate · Intensity benchmark · Historical trend (median-ratio) ·
Cross-source consistency · Provenance

Trust score starts at 100; each failed rule subtracts. States: `verified` → `plausible` →
`needs_review` → `anomalous`. The last two are **held back from carbon analysis** until a
human clears them at `/data-quality`.

> **This is not fraud detection.** It flags records that are inconsistent, implausible or
> unattributed and routes them to a person. It cannot prove a value is true and never alleges
> wrongdoing. Approve/Reject are human decisions — the AI cannot make them.

---

## 12. Security

- Passwords are **bcrypt**-hashed (cost 12). Plaintext is never stored, logged or returned.
- JWT HS256; a secret shorter than 32 bytes is refused and replaced at startup.
- Tenancy is enforced **server-side** in one place, so a company account cannot read another
  company's data even by crafting a request with a different `scope_key`.
- Sign-in returns an identical message for an unknown email and a wrong password, so the
  endpoint cannot be used to enumerate accounts.
- Logs redact API keys, bearer tokens, `?api_key=` query strings and exception tracebacks.
- `/api/health` returns booleans and status strings only — never a key.

---

## 13. Testing

```bat
cd backend
.\venv\Scripts\python.exe -m pytest tests\ -q
```

```bat
cd frontend
npm run build
```

`backend/sample_data/` contains CSVs for testing:

| File | Purpose |
|---|---|
| `valid_full.csv` | 12 valid rows across all five sources |
| `invalid_examples.csv` | 5 deliberate errors, one per validation rule |
| `missing_columns.csv` | rejected outright |
| `duplicate_rows.csv` | triggers the data-trust duplicate check |

> If tests fail with `no such column`, delete the dev database and restart. SQLAlchemy's
> `create_all()` only CREATEs tables — it never ALTERs them — so a database file from an older
> model silently keeps the old columns.

---

## 14. Known Limitations

- **Reduction-action costs and reductions are configured project assumptions**, not industrial
  measurements. Labelled `DEMO ASSUMPTION` throughout the UI.
- **Demo Mode emission factors are illustrative.** Not measurements, not from Climatiq.
- **The data-trust layer flags, it does not prove.** No fraud claim is made or implied.
- **Intensity benchmark bands are order-of-magnitude sanity ranges defined for this
  prototype**, not published industry benchmarks.
- **EPA CAMPD covers US power-sector facilities only.** It is an optional reference connector;
  no core workflow depends on it, on a facility ID, or on geolocation.
- **Electricity Maps reports GRID carbon intensity**, not a facility's own consumption.
- **Reports export CSV and printable HTML.** No native PDF engine is bundled — use the
  browser's Print → Save as PDF.
- A company is currently a single owner account; user invites and password reset are not built.
- No background scheduler — re-optimization is manual or triggered by new data.

---

## 15. Team

<!-- Replace the placeholders below with your real team details before the Git checkpoint. -->

**Team name:** _TODO_
**Institution:** _TODO_
**Problem Statement:** SU-04 — Industrial Carbon Intelligence & Reduction Engine (Domain 03 — Sustainability)

| Name | Role | GitHub |
|---|---|---|
| _TODO_ | _TODO_ | _TODO_ |
| _TODO_ | _TODO_ | _TODO_ |
| _TODO_ | _TODO_ | _TODO_ |
| _TODO_ | _TODO_ | _TODO_ |
