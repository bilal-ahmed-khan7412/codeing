# Architecture

Deep technical reference for how this system is built. For a feature overview and setup instructions, see [`README.md`](README.md). For step-by-step usage walkthroughs, see [`WORKFLOW.md`](WORKFLOW.md).

---

## Table of contents

- [System overview](#system-overview)
- [Module map](#module-map)
- [Request lifecycle](#request-lifecycle)
- [The command layer](#the-command-layer)
- [The Excel workbook contract](#the-excel-workbook-contract)
- [Data layer (SQLite)](#data-layer-sqlite)
- [Authentication and session design](#authentication-and-session-design)
- [Chat assistant internals](#chat-assistant-internals)
- [Evaluation internals](#evaluation-internals)
- [LLM provider abstraction](#llm-provider-abstraction)
- [Deployment architecture](#deployment-architecture)

---

## System overview

This is a single-process, single-container application. One FastAPI process serves the HTML pages, the JSON APIs, and (implicitly) the "frontend" — there's no separate frontend build, no SPA framework, no bundler. Every `.html` file under `web/` is read straight off disk and returned as a raw response by a route; the browser then runs whatever inline `<script>` is in that file, which calls back into the same process's `/api/*` routes.

```
Browser
  │  GET /login, /chat, /users, ...        (HTML pages, session cookie)
  │  fetch('/api/...')                      (JSON, same origin)
  ▼
FastAPI process (web_app.py)
  │
  ├─ tracker_auth      JWT session, password hashing, role permissions
  ├─ tracker_audit     SQLite: users / activity_logs / task_tracker / password_reset_requests
  ├─ tracker_commands  registry + validator + executor (the 19-command contract)
  ├─ tracker_services  one service class per command family
  ├─ tracker_excel     parser (read) + renderer (write) for the .xlsx files
  ├─ tracker_chat      chat_service (LLM-first, regex fallback), intern_sheet_drafter
  ├─ tracker_evaluation the evaluation wizard backend
  ├─ tracker_tasks     internal task-tracker CRUD
  ├─ tracker_llm       provider abstraction (Mock / Groq / OpenAI-compatible)
  └─ tracker_core      shared constants/models
  │
  ▼
data/app.db (SQLite file)      uploads/<user_id>/*.xlsx      outputs/<user_id>/*.xlsx
```

Same-origin matters: the JWT session is an `httponly` cookie set on login, and the browser sends it automatically on every subsequent `fetch()` to the same host. This is why the frontend and backend are deliberately **not** split into separate services — doing so would mean either sharing a cookie domain or switching to cross-origin `SameSite=None` cookies plus CORS on every route, real ongoing complexity with no corresponding benefit at this app's scale.

---

## Module map

| Module | Responsibility |
|---|---|
| `web_app.py` | Every FastAPI route. Auth guards, storage-path resolution, and dispatch into the modules below. |
| `tracker_core/` | Shared dataclasses/constants used across modules (avoids import cycles). |
| `tracker_auth/` | `passwords.py` (PBKDF2 hashing), `jwt_service.py` (session tokens), `permissions.py` (role checks), `user_service.py` (CRUD + `ensure_super_admin()` bootstrap). |
| `tracker_audit/` | `audit_db.py` (SQLite schema + connection), `audit_service.py` (writes/reads `activity_logs`, CSV export). |
| `tracker_commands/` | `registry.py` (the 19 command schemas: required/optional args), `validator.py` (required-field + status-value checks), `executor.py` (dispatch table → service methods). |
| `tracker_services/` | `intern_service.py`, `plan_service.py`, `workbook_service.py`, `render_service.py`, `summary_service.py`, `version_service.py` — the actual business logic behind each command. |
| `tracker_excel/renderer/` | `parser.py` (read a workbook into dataclasses), `plan_renderer.py` / `intern_renderer.py` / `dashboard_renderer.py` / `hidden_renderer.py` (write dataclasses back to a workbook), `styles.py`, `utils.py`. |
| `tracker_chat/` | `chat_service.py` (the draft/proposal state machine), `llm_intent_parser.py` (LLM-based command+args extraction), `intern_sheet_drafter.py` (LLM-assisted intern sheet content generation). |
| `tracker_evaluation/` | `evaluation_service.py` — upload handling, name matching, metrics, scoring, workbook finalization. |
| `tracker_tasks/` | `task_service.py` — the internal (non-intern) task tracker. |
| `tracker_llm/` | `providers.py` (Mock/Groq/OpenAI-compatible provider classes), `prompts.py`, `planner.py` (used by `llm_cli.py`). |
| `tracker_config/` | `.env` loading into a `Settings` object. |
| `web/` | One `.html` file per route; each is self-contained (inline `<style>`/`<script>`, no bundler). |

---

## Request lifecycle

**A mutating request** (chat-proposed command, approved):

```
POST /api/chat/approve {draft_id}
  │
require_login(request)
  │   decodes the JWT cookie, then re-fetches the user's current
  │   role/status from SQLite on every single request — never trusts
  │   the token's claims for authorization. This means a Super Admin
  │   deactivating a user takes effect on that user's very next
  │   request, not after their session naturally expires.
  ▼
CommandExecutor.execute({command, args})
  │
CommandValidator.validate()
  │   checks required args are present, and that any status value is
  │   one of the allowed set (Pending/In Progress/Completed)
  ▼
dispatch table → tracker_services/<Something>Service.<method>(...)
  │
parse_workbook(source_path)  → WorkbookData
  │   mutate the relevant intern/plan dataclass in place
  ▼
RenderService.render_data(data, output_path)
  │   rewrites the ENTIRE workbook: visible sheets (Dashboard, Plan
  │   sheets, Intern sheets) + hidden audit-mirror sheets
  ▼
CommandResult(ok, message, output_path, data)
  │
AuditService.log(actor, interface, action, target, status, ...)
  ▼
JSON response → browser renders "Done" + download link
```

**A read-only request** (progress summary) skips the proposal/approval step entirely: `ChatService._execute_readonly_summary()` calls the executor immediately and returns `{"type": "result", "readonly": true}` instead of `{"type": "proposal"}` — the frontend branches on this field explicitly, so there's never a stray "Approve" button left over for something that already ran.

---

## The command layer

The registry/validator/executor split exists so that **every entry point — web forms, chat, both CLIs — funnels through the identical validated path**. None of them are allowed to call a service method directly without going through the validator first; this is what makes the 19 commands the actual security/consistency boundary, not a convention that's easy to accidentally bypass.

`tracker_commands/registry.py` defines each command as:
```python
"add_intern_with_plan": {
    "required": ["source", "name", "start_date", "end_date", "plan_name", "output"],
    "optional": ["manager", "skip_manager", "final_project", "main_title", "objective",
                 "tech_stack", "scenario", "skills", "deliverable"],
    "description": "Add an intern and apply a selected plan in one approved workflow.",
}
```

`CommandValidator.validate(command, args)` raises `CommandValidationError` if a required field is missing, or if a status-like field isn't one of the allowed values. `CommandExecutor.execute({command, args})` looks up the matching service method in a dispatch table and calls it with the validated args, returning a `CommandResult(ok, message, output_path, data)`.

See [`README.md`'s command table](README.md#the-19-command-layer) for the full list of all 19 commands and what each does.

---

## The Excel workbook contract

### Per-intern sheet layout

| Section | Rows | How it's located |
|---|---|---|
| Title / subtitle | 1–2 | Fixed |
| Main project / capstone | 4–6 | Fixed |
| Real-world scenario | 8–10 | Fixed |
| Daily tasks | 12–14+ | Fixed start, variable length |
| Weekly updates | (shifts) | Dynamic — scans for marker text `"Week #"` |
| Small/weekly projects | (shifts) | Dynamic — scans for header pair `("#", "Title")` |

The dynamic sections exist because their start row depends on how many daily task rows are above them — a longer internship has more daily rows, pushing everything below it further down. The parser and renderer share the exact same row-offset assumptions (both live in `tracker_excel/renderer/`), which is what keeps read and write symmetric: parse → mutate → render always round-trips correctly.

### Dashboard sheet

Aggregates rollup formulas across every intern sheet (e.g. `=COUNTA('<intern>'!E<start>:E<end>)` for completed-task counts) — these are real Excel formulas, recalculated by Excel/any spreadsheet viewer, not precomputed values.

### Hidden system sheets

`_Config`, `_Interns`, `_Plans`, `_PlanItems`, `_Tasks`, `_Projects`, `_WeeklyReports`, `_Holidays`, `_Versions` — a structured, write-only mirror of everything on the visible sheets. These exist as a queryable audit trail (e.g. for external tooling that wants structured data without re-parsing the visible layout) and are **never read back by the parser** — the visible sheets remain the single source of truth on read. Every render pass rewrites these from scratch alongside the visible sheets.

### Plans

A "Plan" sheet is a reusable week-by-week curriculum (theme, task, weekly project, notes per week), independent of any specific intern. `apply_plan_to_intern` / `add_intern_with_plan` / `extend_intern_with_plan` all take a plan by name and use its week content (via `tracker_chat/intern_sheet_drafter.py`, which can further ask an LLM to adapt generic plan content into intern-sheet-ready daily tasks) to populate the relevant intern sheet.

---

## Data layer (SQLite)

`tracker_audit/audit_db.py` defines four tables in `data/app.db`:

```sql
users (id, name, email, password, department, role, status, created_at, last_login, last_logout)
activity_logs (id, timestamp, user_name, email, department, role, interface, action,
                target_type, target_name, input_workbook, output_workbook,
                status, approval_status, summary, error_message)
task_tracker (id, title, description, category, priority, status,
               assigned_to, created_by, created_at, due_date, completed_at, remarks)
password_reset_requests (...)
```

SQLite is a file, not a client-server database — there's no separate "database service" to run, which is why this stays a single-container app rather than needing a `db:` service in `docker-compose.yml`. If this ever needed to scale to multiple concurrent app instances, SQLite's file-level locking (fine for one process, contentious across several) and local-disk-only file storage would be the actual blockers — the fix at that point would be migrating to a real client-server database (Postgres) and shared/networked file storage, not splitting frontend from backend.

**Seeding is idempotent by design**: `audit_db.init_db()` only inserts its legacy default account if `SELECT COUNT(*) FROM users` is zero; `UserService.ensure_super_admin()` only inserts the Super Admin bootstrap account if `SELECT COUNT(*) FROM users WHERE role='Super Admin'` is zero. Neither ever wipes or resets existing data — so a persisted `data/app.db` (see [Deployment architecture](#deployment-architecture)) genuinely keeps every user/log/task across restarts.

---

## Authentication and session design

- **Passwords**: PBKDF2-HMAC-SHA256, salted (`tracker_auth/passwords.py`). Legacy plaintext passwords (from a much older seed) are transparently migrated to hashed storage on that account's next successful login.
- **Sessions**: a JWT stored in an `httponly` cookie, 8-hour default TTL (`JWT_SESSION_TTL_SECONDS`). The signing secret is auto-generated on first run and persisted back into `.env` if left blank, so sessions survive process restarts.
- **Authorization is never trusted from the token itself** — every request that needs a role check re-fetches the user's current role/status from SQLite. This is deliberate: it means deactivating a user, or changing their role, takes effect on their very next request rather than only after their session token naturally expires.
- **Route-level permission checks are the real security boundary.** Hiding a nav link for a role (`web/static/js/*` or per-page nav logic) is a UX nicety on top of that, never a substitute for it.

---

## Chat assistant internals

`ChatService.message(text, current_workbook)` tries, roughly in this order:

1. **Deterministic regex fast-paths** for a handful of specific, high-stakes phrasings — extend-with-plan (`extend X to DATE with PLAN`), edit-plan, capstone/scenario updates. Checked first and explicitly *before* general intent detection, because these have specific enough phrasing that a small LLM can misroute them (e.g. classifying "add intern ... main project should be X" as an *update* to an existing intern's capstone, since it doesn't know the intern doesn't exist yet — the deterministic layer has a hard guard: any message containing "add/create/new intern" is barred from ever reaching those builders).
2. **LLM intent parsing** (`llm_intent_parser.py`, if a real provider is configured) — asks the model to return `{command, args}` from free text, restricted to a known schema of supported commands.
3. **Rule-based regex fallback** — used if no LLM provider is configured, or the LLM's answer doesn't match the active command.

Whichever path produces a result becomes a `ChatDraft(draft_id, command, args)`. `_missing()` checks which of the command's required args (from `tracker_commands/registry.py`'s `REQUIRED`) are still unset:
- If anything is missing → `{"type": "needs_more_info", "missing": [...]}`, and the next message goes through `fill_from_text()` instead of `message()`.
- If nothing is missing → `{"type": "proposal", "args": {...}}`, shown with Approve/Edit/Cancel. Nothing is written to any workbook until Approve is clicked.
- If the command is read-only (`summary`) → executes immediately, `{"type": "result", "readonly": true}`, no proposal step at all.

**Grounding checks** — both `_build_llm_intent_draft()` (first message) and `fill_from_text()` (follow-up replies) filter every value the LLM returns: a value is only accepted if it's traceable to something the user actually typed (`_is_grounded()`, a case-insensitive substring check), with an explicit exemption for fields that are a genuine semantic classification rather than a literal extraction (currently just `status` — "mark it done" legitimately becomes "Completed" without that word appearing verbatim). This exists because a small, cheap model (this project defaults to `llama-3.1-8b-instant`) will occasionally answer a vague or underspecified message by inventing a plausible-looking value — observed in practice: asked to fill in two missing fields from the reply "extend intern" (no real information in it at all), the model returned its own few-shot example name from its own instructions, and separately, internal routing sentinel tokens meant only for command dispatch. Grounding, plus outright rejecting anything shaped like an internal placeholder token, closes that class of failure without needing a bigger (slower, more expensive) model.

---

## Evaluation internals

`tracker_evaluation/evaluation_service.py` is stateless per-request; session state (which tracker/evaluation workbook pair is active) lives in an in-memory `EVAL_SESSIONS` dict in `web_app.py`, keyed by a session id returned from `/api/evaluation/upload`.

- **Name matching**: `difflib.SequenceMatcher` ratio between a normalized (lowercased, alphanumeric-only) tracker intern name and each `SC - <name>` scorecard sheet title.
- **Metrics**: `get_tracker_metrics()` re-parses the tracker workbook, counts completed vs. planned daily tasks and weekly projects, computed twice — once filtered to "as of" a given evaluation date, once for the full internship — and the caller picks which one is authoritative via the `basis` argument. Both are always genuinely computed; nothing is silently forced to one or the other.
- **Scoring**: 16 fixed subjective criteria (`SUBJECTIVE_CRITERIA`), each scored 0–5 either by an LLM (given the criterion's rubric, the evaluator's free-text answer, and tracker context) or a heuristic keyword-matcher fallback (`heuristic_score()`) if no LLM is configured. Every suggested score comes with a rationale string, generated by the LLM or a template-based fallback (`_reason_for_score()`).
- **Finalizing**: `finalize_evaluation()` locates each criterion's label cell by scanning all cells for an exact text match (`_find_cell()`), then writes the score 2 columns right and the rationale/evidence comment 5 columns right of that label — this positional-offset convention is what lets the writer work against the evaluation-framework workbook's existing layout without needing to know it in advance or add new fields to it.

---

## LLM provider abstraction

`tracker_llm/providers.py` defines a small common interface (`complete_json(prompt) -> dict`) with three implementations, selected by `AI_PROVIDER` in `.env`:

| Provider | Behavior |
|---|---|
| `mock` | Deterministic, no external calls — used for tests and as a safe default. |
| `groq` | Calls the Groq API (`GROQ_API_KEY`, `GROQ_MODEL`). |
| `local` | Any OpenAI-compatible endpoint (`LLM_BASE_URL`, `LLM_MODEL`) — Ollama, LM Studio, etc. |

Both `tracker_chat/` and `tracker_evaluation/` degrade gracefully to deterministic/heuristic logic if no real provider is configured or a call fails — nothing in the app hard-depends on an LLM being available.

---

## Deployment architecture

Single service, `docker-compose.yml`:

```yaml
services:
  app:
    build: .
    image: ai-track
    container_name: intern-ai-tracker
    ports: ["9004:8005"]
    env_file: [.env]
    volumes:
      - app_data:/app/data
      - app_uploads:/app/uploads
      - app_outputs:/app/outputs
    restart: unless-stopped
volumes:
  app_data: {name: intern_ai_tracker_app_data}
  app_uploads: {name: intern_ai_tracker_app_uploads}
  app_outputs: {name: intern_ai_tracker_app_outputs}
```

- **`entrypoint.sh`** ensures `data/`, `uploads/`, `outputs/` exist before `uvicorn` starts (defensive, in case a freshly-mounted empty volume needs those directories created), then execs the real `CMD`.
- **Volume names are pinned explicitly** rather than left to Compose's default (which derives a name from the containing folder) — this specifically avoids re-cloning/copying the project into a differently-named folder silently starting a brand-new, empty volume set instead of reusing the persisted one.
- **`.env` is never baked into the image** (`.dockerignore` excludes it) — it's injected at container start via `env_file`, so the JWT secret and any LLM API key never end up in a built image layer.
