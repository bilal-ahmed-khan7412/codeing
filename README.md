# Intern Learning Tracker

A web application (with CLI companions) for managing intern learning plans and progress inside a structured Excel workbook — role-based access, a conversational chat assistant, an intern evaluation wizard, and full audit logging, all built on top of a command layer that keeps every mutation consistent and re-renderable.

> This is the overview. For deep internal design, see [`ARCHITECTURE.md`](ARCHITECTURE.md). For step-by-step usage walkthroughs, see [`WORKFLOW.md`](WORKFLOW.md). For the patch-by-patch version history, see [`CHANGELOG.md`](CHANGELOG.md).

---

## Table of contents

- [What this is](#what-this-is)
- [Feature overview](#feature-overview)
- [Architecture](#architecture)
- [The Excel workbook contract](#the-excel-workbook-contract)
- [The 19-command layer](#the-19-command-layer)
- [Roles and permissions](#roles-and-permissions)
- [Chat assistant](#chat-assistant)
- [Evaluation workflow](#evaluation-workflow)
- [Setup](#setup)
- [Configuration (.env)](#configuration-env)
- [Running it](#running-it)
- [Web routes](#web-routes)
- [CLI usage](#cli-usage)
- [Project layout](#project-layout)

---

## What this is

Interns get tracked in an Excel workbook: one sheet per intern (daily tasks, weekly updates, a main/capstone project, a real-world scenario, small projects) plus a Dashboard sheet with rollup formulas, plus reusable "Plan" sheets (week-by-week curricula) that can be applied to any intern. Everything an admin does — creating a workbook, adding an intern, extending a deadline, editing a task — goes through one of 19 well-defined commands that read the workbook, mutate an in-memory representation, and re-render the whole file. That means the workbook never gets hand-edited into an inconsistent state, and every action is auditable.

On top of that command layer sits:
- A **web UI** (FastAPI + server-rendered HTML) for forms-based operation, chat, evaluation, and governance.
- A **chat assistant** that turns natural language into the same commands, with an LLM (Groq, or any OpenAI-compatible endpoint) doing intent/field extraction and a deterministic regex layer as fallback.
- Two **CLIs** (`tracker_cli.py` for direct commands, `llm_cli.py` for natural language) that call the exact same services as the web UI.
- An **evaluation wizard** for turning a tracker workbook + a separate evaluation-framework workbook into a scored, finalized evaluation output.
- **Governance**: signup/approval, three roles, password reset, deactivation/reactivation, and an activity log of everything.

---

## Feature overview

**Workbook operations** (via forms, chat, or CLI — same 19 commands underneath):
- Create a fresh blank workbook, or render/clean an uploaded one
- Add an intern (from a JSON spec, from plain form fields, or combined with applying a plan in one step)
- Create, edit, and apply reusable learning **plans** (week-by-week curricula)
- Extend an intern's end date — either with placeholder rows to fill in later, or by applying a second plan to generate real content for the extension period
- Edit/update daily tasks, task status, the main/capstone project, the real-world scenario, and weekly/small projects
- Add holidays (global or per-intern) — excluded from pending-task counts
- Generate a progress summary (task counts, completion %) for one intern or the whole workbook

**Chat assistant** (`/chat`):
- Natural-language requests get turned into a proposed command with an editable **Approve / Edit / Cancel** flow — nothing is written to the workbook until you approve
- Free-form AI-drafted learning plans ("create an 8 week Kubernetes plan focused on GitOps and Helm") with a topic-aware deterministic fallback if no LLM is configured
- Read-only requests (progress summaries) execute immediately, no approval step
- Per-user file browser (your uploads/outputs), with admins able to see every user's files

**Evaluation** (`/evaluation`, Admin/Super Admin only):
- Upload a tracker workbook + a separate evaluation-framework workbook
- Fuzzy-matches tracker interns to `SC - <name>` scorecard sheets
- Two auto-computed delivery-completion scores (from real task/project completion data) plus 16 fixed subjective criteria, each with an AI-suggested (or heuristic-fallback) 0–5 score and rationale
- Admin can accept or override every score before finalizing
- Choose scoring basis: "as of" a given date, or the full internship overall
- Finalized workbook is saved with all scores + rationale written into the original scorecard layout

**Governance** (`/users`, `/logs`, `/tasks`, `/profile`):
- Signup → Pending → Admin/Super Admin approval
- Three roles: Super Admin, Admin, User (see [Roles](#roles-and-permissions))
- Password reset requests, admin-issued temporary passwords
- Deactivate/reactivate accounts
- Per-user upload/output folders, with Admin/Super Admin able to see and manage every user's files
- Full activity log (who did what, when, on which workbook), filterable and CSV-exportable
- A small internal task tracker for the team's own workflow (not intern-related)

---

## Architecture

```
web/*.html               ← browser UI: plain HTML + vanilla JS, no build step
   │  fetch() calls
   ▼
web_app.py                ← FastAPI, every route lives here
   │
   ├── tracker_auth/       JWT session cookie, PBKDF2 password hashing, role permissions
   ├── tracker_audit/      SQLite: users, activity_logs, task_tracker, password_reset_requests
   ├── tracker_chat/       chat_service (LLM-first, regex fallback), intern_sheet_drafter
   ├── tracker_commands/   registry (19 command schemas) + validator + executor
   ├── tracker_services/   one service class per command family (intern/plan/workbook/render/summary/version)
   ├── tracker_excel/      renderer/parser.py (read) + renderer/*.py (write) for the .xlsx contract
   ├── tracker_evaluation/ the 5-step evaluation wizard backend
   ├── tracker_tasks/      internal task-tracker CRUD
   ├── tracker_llm/        pluggable LLM provider (Mock / Groq / OpenAI-compatible)
   └── tracker_core/       shared constants/models

tracker_cli.py  / llm_cli.py   ← same service layer, no web server involved
```

**A typical mutating request** (e.g. approving a chat-proposed "add intern"):

```
Browser → POST /api/chat/approve {draft_id}
    │
require_login(request)           ← decodes JWT cookie, re-fetches role/status from
    │                               SQLite on every request (not trusted from the
    │                               token) — a deactivation takes effect immediately
    ▼
CommandExecutor.execute({command, args})
    │
CommandValidator.validate()       ← required-field + status-value checks
    ▼
dispatch → tracker_services/*.py
    │
parse_workbook(source) → WorkbookData     (tracker_excel.renderer.parser)
    │   mutate the in-memory dataclasses
    ▼
RenderService.render_data(data, output)   (tracker_excel.renderer.*)
    │   rewrites visible sheets + hidden audit sheets
    ▼
CommandResult{ok, message, output_path} → AuditService.log(...) → JSON response
```

Read-only requests (a progress summary) skip the proposal/approval step entirely and execute immediately — see [Chat assistant](#chat-assistant).

---

## The Excel workbook contract

Each intern gets one sheet with fixed-position sections:

| Section | Rows |
|---|---|
| Title / subtitle | 1–2 |
| Main project / capstone | 4–6 |
| Real-world scenario | 8–10 |
| Daily tasks | 12–14+ (variable length) |

Two sections are **found dynamically** (their start row shifts with how many daily tasks exist above them):
- Weekly updates — located by scanning for the marker text `"Week #"`
- Small/weekly projects — located by scanning for the header pair `("#", "Title")`

A `Dashboard` sheet aggregates rollup formulas across all intern sheets. **Hidden system sheets** (`_Config`, `_Interns`, `_Plans`, `_PlanItems`, `_Tasks`, `_Projects`, `_WeeklyReports`, `_Holidays`, `_Versions`) are a write-only structured mirror of everything on the visible sheets — a queryable audit trail that the parser never reads back from (only the visible sheets are the source of truth on read).

Because every command re-parses the whole workbook, mutates the in-memory dataclasses, and re-renders the entire file, the workbook is always internally consistent — there's no partial-edit state to worry about.

---

## The 19-command layer

Every mutation — whether it comes from a web form, the chat assistant, or a CLI invocation — goes through one of these, defined in `tracker_commands/registry.py`:

| Command | Purpose |
|---|---|
| `create_workbook` | Create a fresh blank workbook |
| `render_workbook` | Re-render/clean an uploaded workbook |
| `summary` | Progress summary (task counts, completion %) |
| `add_intern` | Add an intern from a raw JSON spec |
| `add_intern_basic` | Add an intern from form fields (placeholder schedule) |
| `add_intern_with_plan` | Add an intern **and** apply a plan in one step (real, plan-derived content) |
| `extend_intern` | Extend end date with placeholder rows to fill in later |
| `extend_intern_with_plan` | Extend end date using a second plan as context for the extension period |
| `edit_task` | Edit a daily task row (no add/delete) |
| `update_task_status` | Update a daily task's status |
| `update_capstone` | Update the main project/capstone section |
| `update_scenario` | Update the real-world scenario section |
| `edit_project` | Edit an existing weekly/small project row |
| `update_project_status` | Update a weekly project's status |
| `add_holiday` | Add a global or per-intern holiday |
| `create_plan` | Create a reusable learning plan |
| `create_plan_from_draft` | Create a plan from an LLM-drafted set of weeks |
| `edit_plan` | Edit plan metadata (name/description) |
| `edit_plan_week` | Edit one week's content within a plan |
| `apply_plan_to_intern` | Apply an existing plan's schedule to an intern |

Each has a `required`/`optional` argument schema (`CommandValidator` enforces required fields and status-value membership before `CommandExecutor` dispatches to the matching service method).

---

## Roles and permissions

| Role | Can do |
|---|---|
| **Super Admin** | Everything — approve any signup as User or Admin, promote/demote Admins, deactivate/reactivate anyone (except can't self-lock-out), full logs/evaluation/user-management access. Exactly one is auto-seeded on first run. |
| **Admin** | Approve signups as User (not Admin), manage Users, view logs, run evaluations, use chat/workbook operations. Cannot manage other Admins. |
| **User** | Chat assistant and their own profile only. No access to Users/Logs/Tasks/Evaluation. |

Signup flow: `/signup` → status `Pending` → an Admin or Super Admin approves (or rejects) from `/users` → account becomes `Active`. Server-side route permission checks are the actual security boundary; navigation links are just hidden per-role as a UX nicety on top of that.

**Default bootstrap account** (seeded once, if no Super Admin exists yet):
```
email:    superadmin@example.com
password: superadmin123
```
Change this after first login — see `/profile`.

---

## Chat assistant

Every chat message goes through, roughly:

1. **Deterministic regex fast-paths** for a handful of high-stakes phrasings (extend-with-plan, edit-plan, capstone/scenario updates) — checked first because these have specific enough phrasing that a small LLM can misroute them.
2. **LLM intent parsing** (if a real provider is configured) for everything else — extracts a command + arguments from free text.
3. **Rule-based fallback** (pure regex, no LLM) if no provider is configured or the LLM's answer doesn't fit.

Whichever path fills a field, the result is a **draft**: if required fields are missing, the assistant asks for them; once complete, it becomes a **proposal** shown with Approve / Edit / Cancel — nothing touches the workbook until you click Approve. Read-only requests (progress summaries) skip this and execute immediately, since there's nothing to approve.

A small/cheap LLM (this project uses `llama-3.1-8b-instant` via Groq) will occasionally answer a vague follow-up with an invented value instead of admitting it doesn't have enough information — the chat layer guards against this by only ever accepting a field value that's traceable back to something you actually typed, and by rejecting a small set of internal-only placeholder tokens outright.

---

## Evaluation workflow

Admin/Super Admin only, at `/evaluation`:

1. **Upload** the tracker workbook plus a separate evaluation-framework workbook (one with `SC - <intern name>` scorecard sheets).
2. **Match** — fuzzy name-matching (Python `difflib`) suggests which scorecard sheet belongs to which tracker intern.
3. **Questions** — pick a scoring basis (as-of-date vs. full internship overall), then walk through 16 fixed subjective criteria (Skills Acquired, Main Project, Problem Solving, Communication, Ownership & Initiative, etc.), each with an AI-suggested score + rationale (or a heuristic keyword-based fallback if no LLM is configured).
4. **Review** — accept or manually override any score before finalizing; an override is labeled "Set by user".
5. **Finalize** — writes 2 auto-computed delivery-completion scores (from real completed/planned task and project counts) plus all 16 subjective scores and their rationale into the original scorecard layout, saved as `Evaluated_<name>_<timestamp>.xlsx`.

---

## Setup

**Requirements**: Python 3.11+ (see `requirements.txt`: `fastapi`, `uvicorn`, `openpyxl`, `PyJWT`, `python-multipart`, `requests`).

```bash
pip install -r requirements.txt
```

---

## Configuration (.env)

Copy `.env.example` to `.env` and fill in real values — `.env` itself is gitignored (never commit real secrets).

```env
AI_PROVIDER=groq
GROQ_API_KEY=your_groq_key_here
GROQ_MODEL=llama-3.1-8b-instant
LLM_VERIFY_SSL=false

# Session auth. Left blank, the server generates one on first run and
# writes it back into .env so sessions survive restarts.
JWT_SECRET=
JWT_SESSION_TTL_SECONDS=28800
```

Other supported `AI_PROVIDER` values:
- `mock` — deterministic, no external calls (safe default while testing)
- `local` — any OpenAI-compatible endpoint (Ollama, LM Studio, etc.):
  ```env
  AI_PROVIDER=local
  LLM_BASE_URL=http://localhost:11434/v1
  LLM_MODEL=llama3.1
  LLM_API_KEY=optional
  ```

Without a real LLM provider configured, everything still works — chat and evaluation both fall back to deterministic regex/heuristic logic.

---

## Running it

**Directly:**
```bash
uvicorn web_app:app --host 0.0.0.0 --port 8005
```
Then open `http://127.0.0.1:8005/login`.

**With Docker Compose** (recommended — handles the build, port, `.env`, and persistent volumes in one command):
```bash
sudo docker compose up -d --build
```
This builds the image (`ai-track`), starts the container (`intern-ai-tracker`) on port `9004`, and mounts three named, pinned volumes (`intern_ai_tracker_app_data`, `_app_uploads`, `_app_outputs`) so your database, uploads, and generated workbooks all survive rebuilds/recreates — regardless of what folder the project happens to be checked out into.

```bash
sudo docker compose logs -f      # watch logs
sudo docker compose down         # stop (keeps volumes/data)
sudo docker compose down -v      # stop AND wipe the volumes — only if you actually want a clean slate
```

---

## Web routes

| Route | Who | Purpose |
|---|---|---|
| `/login`, `/signup`, `/pending`, `/forgot-password` | Public | Auth entry points |
| `/`, `/dashboard/{super-admin,admin,user}` | Logged in | Role-specific landing dashboard |
| `/chat` | Logged in | Chat assistant |
| `/profile` | Logged in | Own account details/password |
| `/users` | Admin/Super Admin | User management, approvals, password resets |
| `/logs` | Admin/Super Admin | Activity log, filterable, CSV export |
| `/tasks` | Admin/Super Admin | Internal task tracker |
| `/evaluation` | Admin/Super Admin | Evaluation wizard |
| `/download/{filename}` | Logged in | Download an owned (or, for admins, any) output/upload file |

All mutating actions are also available as JSON APIs under `/api/*` (`/api/chat/*`, `/api/execute`, `/api/users/*`, `/api/evaluation/*`, etc.) — the HTML pages are just thin clients over these.

---

## CLI usage

**Direct command CLI** (`tracker_cli.py`) — one subcommand per registry command:

```bash
python tracker_cli.py create-workbook --output "Blank_Tracker.xlsx"
python tracker_cli.py add-intern-basic --source "Blank_Tracker.xlsx" --name "Ahmed Ali" \
  --start-date 2026-08-01 --end-date 2026-09-30 --output "Tracker_With_Ahmed.xlsx"
python tracker_cli.py extend-intern --source "Tracker_With_Ahmed.xlsx" --intern "Ahmed Ali" \
  --new-end 2026-10-15 --output "Tracker_Extended.xlsx"
python tracker_cli.py summary --workbook "Tracker_Extended.xlsx" --intern "Ahmed Ali"
```

**Natural-language CLI** (`llm_cli.py`) — same command layer, plain-English input:

```bash
# Plan only (prints the proposed command, doesn't execute)
python llm_cli.py "Extend Ahmed Ali to 2026-10-15" --source tracker.xlsx --output tracker_v2.xlsx

# Plan and execute
python llm_cli.py "Extend Ahmed Ali to 2026-10-15" --source tracker.xlsx --output tracker_v2.xlsx --execute
```

---

## Project layout

```
web_app.py                  FastAPI app, all routes
tracker_cli.py               Direct command-line interface
llm_cli.py                   Natural-language command-line interface
docker-compose.yml           Single-service deployment with persistent volumes
Dockerfile / entrypoint.sh    Container build

tracker_core/                 Shared constants/models
tracker_auth/                 JWT sessions, password hashing, permissions, user service
tracker_audit/                SQLite schema + audit log service
tracker_commands/             Command registry, validator, executor
tracker_services/             One service class per command family
tracker_excel/renderer/       parser.py (read) + *.py (write) for the .xlsx contract
tracker_chat/                 Chat assistant service + LLM intent parser
tracker_evaluation/           Evaluation wizard backend
tracker_tasks/                Internal task-tracker service
tracker_llm/                  Pluggable LLM provider (Mock/Groq/OpenAI-compatible)
tracker_config/               .env loading

web/                          Server-rendered HTML pages (one file per route)
examples/                     Sample JSON specs for CLI input
data/, uploads/, outputs/     Runtime data — gitignored, volume-mounted in Docker
```
