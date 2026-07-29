# Workflows

Step-by-step walkthroughs of how each feature is actually used, end to end. For what the system is and how it fits together, see [`README.md`](README.md). For internal design, see [`ARCHITECTURE.md`](ARCHITECTURE.md).

---

## Table of contents

- [Getting an account](#getting-an-account)
- [Password reset](#password-reset)
- [Creating a workbook and adding an intern](#creating-a-workbook-and-adding-an-intern)
- [Applying a plan to an existing intern](#applying-a-plan-to-an-existing-intern)
- [Extending an intern](#extending-an-intern)
- [Editing tasks, status, capstone, scenario, projects](#editing-tasks-status-capstone-scenario-projects)
- [Adding a holiday](#adding-a-holiday)
- [Getting a progress summary](#getting-a-progress-summary)
- [The chat assistant's Approve / Edit / Cancel flow](#the-chat-assistants-approve--edit--cancel-flow)
- [Running an evaluation](#running-an-evaluation)
- [Managing users](#managing-users)
- [Reviewing the activity log](#reviewing-the-activity-log)
- [The internal task tracker](#the-internal-task-tracker)
- [Deploying / updating via Docker Compose](#deploying--updating-via-docker-compose)

---

## Getting an account

1. Go to `/signup`, fill in name/email/password/department. Submitting sets your status to **Pending** and redirects you to `/pending`.
2. An Admin or Super Admin reviews pending requests at `/users` and approves (as **User**, or — Super Admin only — as **Admin**) or rejects.
3. Once approved, log in at `/login`. If your account is later deactivated, your very next request is blocked immediately (permission checks re-read your status from the database on every request — they don't wait for your session to expire).

**Bootstrap Super Admin** (only exists if no Super Admin account exists yet): `superadmin@example.com` / `superadmin123`. Change the password from `/profile` after first login.

---

## Password reset

1. From `/login`, click "Forgot password?" → `/forgot-password` → submit your email. This creates a pending request, visible to Admins/Super Admins.
2. An Admin/Super Admin reviews it at `/users`, and either issues a **temporary password** (shown once, share it through an approved channel) or rejects the request.
3. Log in with the temporary password, then change it from `/profile`.

---

## Creating a workbook and adding an intern

**Via chat** (`/chat`):
```
create a new excel
```
→ proposal → Approve → you now have a blank workbook, automatically set as your "current workbook".

```
add intern Sara from 2026-08-01 to 2026-09-01 with SecOps Foundation
```
→ if `SecOps Foundation` doesn't exist as a plan yet, create it first (see below); otherwise this proposes adding Sara **and** applying that plan's content in one step — main project, real-world scenario, and a full week-by-week schedule preview, all generated from the plan and Sara's dates. Review the preview, Edit anything you want to change, then Approve.

**Via forms/CLI** (equivalent, no chat involved):
```bash
python tracker_cli.py create-workbook --output "Blank_Tracker.xlsx"
python tracker_cli.py add-intern-basic --source "Blank_Tracker.xlsx" --name "Sara" \
  --start-date 2026-08-01 --end-date 2026-09-01 --output "Tracker_With_Sara.xlsx"
```
(`add-intern-basic` creates placeholder rows, not plan-derived content — combining an intern with a plan in one step is currently a chat/web-only workflow, via `add_intern_with_plan`.)

**Creating a plan first**, if you don't already have one:
```
create an 8 week plan for a Kubernetes intern focused on GitOps and Helm
```
Your entire request becomes the topic description handed to the LLM (or, with no LLM configured, a topic-aware deterministic fallback) — it's not limited to a fixed list of plan topics. Review the drafted weeks, Edit if needed, Approve to save the plan.

---

## Applying a plan to an existing intern

If Sara already exists (added without a plan, or you want to layer on a second plan):
```
apply plan SecOps Foundation to intern Sara
```
This applies the plan's schedule starting from Sara's existing dates and fills in main project/scenario defaults, without changing her start/end dates.

---

## Extending an intern

Two ways, and the assistant will ask which one you want if you don't say:

```
extend Sara
```
→ asks for the new end date, then asks whether to apply a specific plan for the extension period or just add placeholder rows ("Task to be assigned") to fill in yourself later. Reply with a plan name, or "no plan" to opt for placeholders.

One-shot, no follow-up needed:
```
extend Sara to 2026-10-01 with SecOps Foundation
```
Generates real, plan-derived content (progressive daily tasks, weekly updates, weekly projects) for just the extension period — the original schedule up to the old end date is untouched.

---

## Editing tasks, status, capstone, scenario, projects

All of these work as direct chat messages, asked as plain sentences:

```
mark Sara's task on 2026-08-04 as completed
update the main project for Sara to Agentic AI platform
update the real-world scenario for Sara to investigating a phishing incident, skills needed are log analysis and incident response
```

If a required field (usually the intern's name) isn't in your message, the assistant asks for it before showing a proposal — reply in plain text, it fills in the draft rather than starting over.

---

## Adding a holiday

```
add a holiday called Eid on 2026-08-19 for all interns
```
Global holidays apply across every intern's schedule; say "for intern <name>" instead of "all interns" to scope it to one person. Holiday rows are excluded from pending-task counts in the dashboard and summaries.

---

## Getting a progress summary

```
generate progress summary for Sara
```
This is **read-only** — it executes immediately with no Approve step, and shows real numbers directly in the chat: total tasks, completed/in-progress/pending counts, and completion percentage for that intern (or the whole workbook if no name is given).

---

## The chat assistant's Approve / Edit / Cancel flow

Every mutating request (anything that would change a workbook) goes through this cycle:

1. You send a message → the assistant either asks for missing information, or shows a **proposal**: a summary of exactly what it's about to do, with the actual field values it extracted.
2. **Approve** — executes the command for real, creates/updates the output workbook, shows a download link. Nothing is written before this step.
3. **Edit** — opens an editable form built from the proposal's own fields (e.g. plan name, dates, objective text). Save Draft re-validates and shows the updated proposal; nothing is written yet.
4. **Cancel** — discards the draft entirely. No workbook is touched.

Read-only requests (progress summaries) skip this whole cycle and execute immediately, since there's nothing to approve.

---

## Running an evaluation

Admin/Super Admin only, at `/evaluation`:

1. **Upload** — the tracker workbook (with intern sheets) and a separate evaluation-framework workbook (with `SC - <name>` scorecard sheets).
2. **Match** — pick the tracker intern you're evaluating; the system suggests the closest-matching scorecard sheet by name similarity. Confirm or pick a different match.
3. **Questions** — choose a scoring basis (till-now-as-of-a-date, or the full internship), then answer 16 subjective questions (skills acquired, problem solving, communication, ownership, etc.) in plain text. For each, click "Suggest Score" to get an AI-suggested (or heuristic-fallback) 0–5 score with a rationale — accept it, or type your own score (marked "Set by user" if you override the suggestion).
4. **Review** — see every score and rationale together, with a chance to adjust anything, plus free-text fields for key strengths, development areas, and a final manager remark.
5. **Finalize** — writes 2 auto-computed delivery-completion scores (from real tracker task/project completion data) and all 16 subjective scores + rationale into the scorecard's existing layout, and gives you a download link for `Evaluated_<name>_<timestamp>.xlsx`.

---

## Managing users

At `/users` (Admin/Super Admin):

- **Approve/reject** pending signups. Admins can only approve as User; Super Admin can approve as User or Admin.
- **Change role** (Super Admin only, for promoting/demoting Admins).
- **Deactivate/reactivate** — Admin can deactivate/reactivate Users; only Super Admin can act on Admins. A deactivated user is blocked on their very next request.
- **Reset password** — issues a one-time temporary password to share with the user out of band.
- **Password reset requests** — a separate list of user-initiated forgot-password requests, reviewed the same way (issue temp password, or reject).

---

## Reviewing the activity log

At `/logs` (Admin/Super Admin): every logged-in action — logins/logouts, workbook uploads, command approvals, chat approvals, user-management actions, task creation — with filters by free-text search, email, action, status, and interface. Export the current filtered view as CSV.

---

## The internal task tracker

At `/tasks` (Admin/Super Admin) — this is unrelated to intern tracking; it's a small internal to-do list for the team managing this tool (e.g. "follow up on X evaluation," "check Y's account request"). Create a task with a title, category, priority, assigned-to, and due date; update its status as work progresses.

---

## Deploying / updating via Docker Compose

**First-time setup on a server/VM:**
```bash
git clone https://github.com/bilal-ahmed-khan7412/codeing.git
cd codeing
cat > .env <<'EOF'
AI_PROVIDER=groq
GROQ_API_KEY=your_key_here
GROQ_MODEL=llama-3.1-8b-instant
LLM_VERIFY_SSL=false
JWT_SECRET=
JWT_SESSION_TTL_SECONDS=28800
EOF
sudo docker compose up -d --build
```
(`.env` is gitignored on purpose — never committed — so you create it yourself on each machine you deploy to.)

**Applying a code update** (already have it running, pulled new commits):
```bash
git pull
sudo docker compose up -d --build
```
`--build` rebuilds the image with the new code; Compose recreates the container from it automatically. Your data (users, logs, uploaded/generated workbooks) survives, because it lives in named volumes, not inside the container itself.

**Stopping it:**
```bash
sudo docker compose down          # keeps your data
sudo docker compose down -v       # also deletes the volumes - only if you actually want a clean slate
```

**Checking on it:**
```bash
sudo docker compose ps
sudo docker compose logs -f
```

If you ever copy the project into a folder with a **different name** than before, the volumes are pinned to fixed names in `docker-compose.yml` (not derived from the folder), so your data is still found and reused rather than silently starting fresh.
