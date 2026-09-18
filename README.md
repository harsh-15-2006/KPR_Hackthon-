# Industrial Carbon Intelligence & Budget-Constrained Reduction Optimization

**SU-04 — Industrial Carbon Intelligence & Reduction Engine**

Measuring total emissions does not tell an organization *which* reduction actions to fund.
This application turns carbon measurement into an actionable allocation decision: it ingests
operational data, calculates CO₂e, identifies hotspots, validates data quality, and then uses
**Google OR-Tools CP-SAT** to decide how a fixed sustainability budget should be spent to
maximise CO₂e reduction under real business constraints.

> **The optimizer is authoritative.** Gemini explains results; it never makes or overrides the
> allocation decision.

---

## 1. Quick start

Two terminals. Backend first.

### Backend

```bat
cd D:\KPR_Hackthon-\backend
.\venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Runs on `http://127.0.0.1:8000` · interactive docs at `http://127.0.0.1:8000/docs`

> Calling `venv\Scripts\python.exe` directly avoids PowerShell's execution-policy block on
> `Activate.ps1`. If the venv does not exist yet, see [First-time setup](#2-first-time-setup).

### Frontend

```bat
cd D:\KPR_Hackthon-\frontend
npm run dev
```

Runs on `http://localhost:5173` (Vite picks the next free port if busy).
Vite proxies `/api` to `127.0.0.1:8000`, so no CORS setup is needed in development.

**Start the backend first**, or the UI shows "Cannot reach the backend".

---

## 2. First-time setup

```bat
cd D:\KPR_Hackthon-\backend
python -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements.txt
```

Then create `.env` **only if it does not already exist**:

```bat
if not exist .env copy .env.example .env
```

> ⚠️ **Never run a bare `copy .env.example .env`.** It silently overwrites an existing `.env`
> and destroys every key in it, with no backup and no warning. The guarded form above is safe
> to re-run. If you already have a working `.env`, back it up before touching it:
> `copy .env .env.backup`

```bat
cd D:\KPR_Hackthon-\frontend
npm install
```

Then fill in `backend\.env` (see [Environment variables](#5-environment-variables)).

---

## 3. The 10 modules

| Route | Module | What it does |
|---|---|---|
| `/dashboard` | Dashboard | Totals, hotspots, action count, live data-source status |
| `/operational-data` | Operational Data | Manual entry + CSV upload with per-row validation and preview |
| `/carbon-analysis` | Carbon Analysis | Deterministic totals, contribution %, provenance per record |
| `/data-quality` | **Data Quality Review** | 6 trust checks, trust score, human Approve/Reject |
| `/reduction-actions` | Reduction Actions | Full CRUD action library, every value carries its evidence source |
| `/optimization` | **Optimization** | Budget + constraints → OR-Tools CP-SAT allocation |
| `/ai-agent` | AI Agent | Gemini explains stored results from a backend-built context |
| `/what-if` | What-If Simulator | Independent scenario runs; baseline never modified |
| `/re-optimization` | Re-optimization | Re-run on new inputs, with a full change history |
| `/reports` | Reports | CSV + printable HTML from authoritative database values |

---

## 4. Architecture

```
React 19 + TypeScript + Vite + Tailwind + Recharts
        │  Axios  (the browser talks ONLY to FastAPI — never to a vendor API)
        ▼
FastAPI  ──►  EPA CAMPD          (optional, US power-sector, MEASURED)
        │     Electricity Maps   (GRID carbon intensity, api_derived)
        │     Climatiq           (activity data → CO₂e, calculated)
        │     Gemini             (explanation only)
        ▼
Fault tolerance ──► Data trust ──► Supabase PostgreSQL
                                        │
                                        ▼
                     Carbon analysis → Hotspots → OR-Tools CP-SAT → Allocation
```

**Backend layout**

```
backend/app/
  core/          config.py (settings + secret flags), logging.py (JSON + redaction),
                 fault_tolerance.py (retries, circuit breaker, stale cache)
  integrations/  base.py, epa_client.py, electricity_maps_client.py, climatiq_client.py
  ai/            gemini_client.py
  optimization/  models.py, constraints.py, optimizer.py   ← CP-SAT lives here
  services/      emission_service, hotspot_service, action_service,
                 optimization_service, trust_service
  routes/        emissions, hotspots, actions, optimization, ai, reports, trust
  models/        emission, action, operational, optimization
```

---

## 5. Environment variables

All server-side. **Never** create `VITE_` copies of these — they would reach the browser.

| Variable | Required | Notes |
|---|---|---|
| `DATABASE_URL` | for persistence | Supabase Postgres. **Use the Session pooler**, see below |
| `CLIMATIQ_API_KEY` | for real factors | Blank ⇒ Demo Mode |
| `CLIMATIQ_DATA_VERSION` | no | `^37` (current; verified via `/data/v1/data-versions`) |
| `ELECTRICITY_MAPS_API_KEY` | for grid intensity | |
| `ELECTRICITY_MAPS_DEFAULT_ZONE` | no | e.g. `IN-SO` (Southern India) |
| `GEMINI_API_KEY` + `GEMINI_ENABLED=true` + `GEMINI_MODEL` | for AI | `gemini-2.5-flash` works reliably |
| `EPA_API_KEY` | optional | EPA's public `DEMO_KEY` works for testing |
| `SUPABASE_URL` / `SUPABASE_PUBLISHABLE_KEY` / `SUPABASE_SECRET_KEY` | optional | Only for the PostgREST Data API |
| `CORS_ORIGINS` | no | Defaults to localhost dev ports |

`.env` is gitignored. Never commit it.

### ⚠️ Two Supabase gotchas that cost real time

**1. The Direct connection is IPv6-only.** `db.<ref>.supabase.co` publishes only an AAAA record.
On an IPv4 network it can never resolve. Use **Project Settings → Database → Connection string →
Session pooler** (port `5432`, user `postgres.<project-ref>`, host `aws-N-<region>.pooler.supabase.com`).
Avoid the Transaction pooler on `6543` — it breaks SQLAlchemy's prepared statements.

**2. A password containing `@ : / #` breaks URL parsing.** The app now percent-encodes the
password automatically, so **paste the connection string verbatim** — do not hand-edit it, and
do not delete the special character (that changes the password).

If the database is unreachable the app **does not crash**: it falls back to local SQLite, keeps
working, and reports the reason in `/api/health` and in the UI header.

---

## 6. Data provenance — the core honesty rule

Every stored value carries a `data_class`:

| Class | Meaning |
|---|---|
| `measured` | Reported/measured by an external regulated source (EPA CAMPD) |
| `api_derived` | Returned by an external API (Electricity Maps grid intensity) |
| `calculated` | Computed by this system (activity × emission factor) |
| `demo_assumption` | A prototype assumption — **not a measurement** |

Enforced in code:

- A failed API call **never** becomes a fabricated value — it returns an error or clearly-labelled STALE cache.
- A missing measurement stays missing. **It is never zero-filled.**
- An unrecognised CO₂e unit **raises** rather than being assumed to be kilograms.
- Demo Mode results are stamped `demo` and badged **DEMO DATA** in the UI.
- All reduction-action costs/reductions are `is_demo_assumption = true` unless given an evidence source.

---

## 7. Data Trust layer

Six deterministic checks run on every record. **No AI is involved.**

1. Schema/range · 2. Intensity benchmark · 3. Historical trend · 4. Cross-source consistency ·
5. Provenance · 6. Duplicate detection

Trust score starts at 100; each failed rule subtracts. States: `verified` → `plausible` →
`needs_review` → `anomalous`. Records in the last two are **held back from carbon analysis**
until a human clears them at `/data-quality`.

> **This is not fraud detection.** It flags records that are inconsistent, implausible or
> unattributed and routes them to a person. It cannot prove a value is true and never alleges
> wrongdoing. Approve/Reject are human decisions — the AI cannot make them.

---

## 8. Optimization model

```
maximize    Σ  expected_reduction_i · x_i
subject to  Σ  cost_i · x_i  ≤  budget
            0 ≤ x_i ≤ capacity_i
            + configured business constraints
```

- Solved by **Google OR-Tools CP-SAT**, pinned to a fixed seed and one worker so runs are reproducible.
- Costs scale with `ceil`, reductions with `floor`, so integer rounding can never cause a real-money overspend.
- Boolean indicators track "is this action funded at all", so counting constraints count **distinct actions**, not units.
- Statuses: `OPTIMAL` · `FEASIBLE` · `INFEASIBLE` · `UNKNOWN` · `MODEL_INVALID`, each with a plain-English explanation.
- `objective_value == best_bound` ⇒ proven optimal, shown in the UI.
- Every run stores a **snapshot** of the actions and constraints used, so old results stay reproducible after the library is edited.

Business constraint types: `max_actions_per_source`, `max_total_actions`, `max_spend_per_source`,
`mutually_exclusive`, `required_action`.

---

## 9. API endpoints

```
GET    /api/health                        service + database + integration status

GET    /api/emissions/sources             per-source units and activity types
POST   /api/emissions/calculate?demo=     calculate and store one record
GET    /api/emissions                     list records
GET    /api/emissions/summary             totals, per-source, contribution %
POST   /api/emissions/preview-csv         validate a CSV, per-row errors
POST   /api/emissions/import              import confirmed rows

GET    /api/trust/summary                 trust states + average score
GET    /api/trust/records?status=         flagged records with triggered rules
POST   /api/trust/revalidate              re-run all checks
POST   /api/trust/records/{id}/approve    HUMAN decision
POST   /api/trust/records/{id}/reject     HUMAN decision

GET/POST/PUT/DELETE  /api/actions         reduction-action library CRUD
GET/POST/PUT/DELETE  /api/constraints     business constraints

POST   /api/optimization/run              solve and persist
GET    /api/optimization/latest           current baseline
GET    /api/optimization/{run_id}

POST   /api/scenarios                     what-if (baseline untouched)
POST   /api/reoptimization/run            re-run + change summary
GET    /api/reoptimization/history

POST   /api/ai/chat                       Gemini explanation
GET    /api/ai/context                    exactly what the AI is given

GET    /api/reports/latest                full report as JSON
GET    /api/reports/csv                   CSV export
GET    /api/reports/html                  printable report (browser → Save as PDF)
```

---

## 10. Testing

```bat
cd D:\KPR_Hackthon-\backend
.\venv\Scripts\python.exe -m pytest tests\ -q
```

```bat
cd D:\KPR_Hackthon-\frontend
npm run build
```

> **If tests fail with `no such column`**, delete the dev database and restart.
> `create_all()` only CREATEs tables — it never ALTERs them — so a database file from an older
> model silently keeps the old columns.

---

## 11. Known limitations

- **Reduction-action costs and reductions are configured project assumptions**, not industrial measurements. Labelled `DEMO ASSUMPTION` everywhere.
- **Demo Mode emission factors are illustrative.** Not measurements, not from Climatiq.
- **Data trust flags, it does not prove.** No fraud claim is made or implied.
- **EPA CAMPD covers US power-sector facilities only.** It is an optional reference connector; no core workflow depends on it, on a facility ID, or on geolocation.
- **Electricity Maps returns GRID carbon intensity**, not a facility's own consumption. The two are stored separately.
- **Intensity benchmark bands in the trust layer are order-of-magnitude sanity ranges defined for this prototype**, not published industry benchmarks.
- **Reports export CSV and printable HTML.** No native PDF engine is bundled — use the browser's Print → Save as PDF.
- **No authentication.** Anyone who can reach the backend can read and write.
- Schema changes are applied via `supabase/migrations/*.sql`; there is no automatic migration runner.

---

## 12. Not yet done

- Automated background polling / scheduled refresh (`REFRESH_INTERVAL_SECONDS` exists but no scheduler runs)
- Deployment configuration (Vercel + a Python host)
- Frontend unit tests
