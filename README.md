# Intern Tracker System v0

Command-first modular system for the Intern Learning Tracker workbook.

## Current working commands

### Render clean workbook

```bash
python tracker_cli.py render --source "Intern Learning Tracker SL v4.0 (10).xlsx" --output "Rendered.xlsx"
```

### Generate summary

```bash
python tracker_cli.py summary --workbook "Rendered.xlsx"
python tracker_cli.py summary --workbook "Rendered.xlsx" --intern "Bilal Ahmad Khan"
```

### Add intern from JSON spec

```bash
python tracker_cli.py add-intern --source "Rendered.xlsx" --spec examples/new_intern_example.json --output "Rendered_with_Ahmed.xlsx"
```

### Extend intern

```bash
python tracker_cli.py extend-intern --source "Rendered.xlsx" --intern "Bilal Ahmad Khan" --new-end "2026-09-15" --output "Rendered_extended.xlsx"
```

## Architecture

- `tracker_core/` - command-facing models
- `tracker_services/` - business services
- `tracker_excel/renderer/` - Excel parser and renderer
- `examples/` - JSON examples for command inputs

## Design rule

The system is command-first. Future web UI and future LLM interface should call these services/commands rather than editing Excel directly.


## v0.3 editing commands

### Update task status

```bash
python tracker_cli.py update-task-status --source "Rendered.xlsx" --intern "Bilal Ahmad Khan" --task-ref "2026-08-26" --status "Completed" --output "Rendered_task_done.xlsx"
```

### Edit task remarks

```bash
python tracker_cli.py edit-task-remarks --source "Rendered.xlsx" --intern "Bilal Ahmad Khan" --task-ref "2026-08-26" --remarks "Completed extension task" --output "Rendered_remarks.xlsx"
```

### Update capstone

```bash
python tracker_cli.py update-capstone --source "Rendered.xlsx" --intern "Bilal Ahmad Khan" --title "Updated AIOps Demo" --status "In Progress" --output "Rendered_capstone.xlsx"
```

### Update weekly project status

```bash
python tracker_cli.py update-project-status --source "Rendered.xlsx" --intern "Bilal Ahmad Khan" --project-number 3 --status "Completed" --output "Rendered_project_done.xlsx"
```


## v0.4 extension behavior

`extend-intern` now updates all timeline-dependent sections:

- Header end date
- Main Project / Capstone target end
- Daily task rows
- Weekly update rows
- Small Projects / Weekly Projects rows
- Dashboard formulas and ranges through re-rendering

When extension project details are not provided, the system creates placeholder weekly project rows:

```text
Week 9: Extension Project | To be assigned | Pending
```


## v0.5 edit-task command

Use `edit-task` when you want to change a task row without adding or deleting rows.

```bash
python tracker_cli.py edit-task \
  --source "tracker.xlsx" \
  --intern "Bilal Ahmad Khan" \
  --task-ref "2026-08-26" \
  --theme "AIOps Extension" \
  --task "Improve anomaly detection threshold logic" \
  --status "In Progress" \
  --remarks "Edited placeholder extension task" \
  --output "tracker_v2.xlsx"
```

`task-ref` can be a task number, date, or text contained in the task description.


## v0.6 scenario and project editing

### Update real-world scenario

```bash
python tracker_cli.py update-scenario \
  --source "tracker.xlsx" \
  --intern "Bilal Ahmad Khan" \
  --scenario "Investigate application log spikes and classify incidents" \
  --skills "Python, Elastic, Observability" \
  --deliverable "Incident report + working demo" \
  --assigned-week 9 \
  --due-date "2026-09-05" \
  --status "In Progress" \
  --output "tracker_scenario.xlsx"
```

### Edit weekly/small project details

```bash
python tracker_cli.py edit-project \
  --source "tracker.xlsx" \
  --intern "Bilal Ahmad Khan" \
  --project-number 9 \
  --title "Improve anomaly detection accuracy" \
  --description "Tune thresholds and reduce false positives" \
  --assigned-date "2026-08-26" \
  --due-date "2026-09-01" \
  --status "In Progress" \
  --output "tracker_project.xlsx"
```


## v0.7 LLM layer

The app now supports two interfaces over the same command executor:

1. Button/forms layer can build command JSON and call `CommandExecutor`.
2. LLM layer converts natural language into the same command JSON and calls `CommandExecutor`.

### .env for Groq

```env
AI_PROVIDER=groq
GROQ_API_KEY=your_groq_key_here
GROQ_MODEL=llama-3.1-8b-instant
LLM_VERIFY_SSL=false
```

### .env for local/OpenAI-compatible LLM

```env
AI_PROVIDER=local
LLM_BASE_URL=http://localhost:11434/v1
LLM_MODEL=llama3.1
LLM_API_KEY=optional
LLM_VERIFY_SSL=false
HTTP_USER_AGENT=InternTracker/0.7
```

### Plan only

```bash
python llm_cli.py "Extend Bilal Ahmad Khan to 2026-09-15" --env .env --source tracker.xlsx --output tracker_v2.xlsx
```

### Plan and execute

```bash
python llm_cli.py "Extend Bilal Ahmad Khan to 2026-09-15" --env .env --source tracker.xlsx --output tracker_v2.xlsx --execute
```

### Offline mock provider

```env
AI_PROVIDER=mock
```


## v0.8 create fresh workbook

Create a blank automation-ready workbook without any source workbook:

```bash
python tracker_cli.py create-workbook --output "Blank_Intern_Tracker.xlsx"
```

The blank workbook contains:

- Dashboard shell
- Hidden system sheets: `_Config`, `_Interns`, `_Plans`, `_PlanItems`, `_Tasks`, `_Projects`, `_WeeklyReports`, `_Holidays`, `_Versions`
- No interns yet
- No plan sheets yet

After creating a blank workbook, use commands like `add-intern`, `summary`, and later plan-management commands.


## v0.9 LLM file path safety fix

The LLM planner no longer controls app/session file paths when CLI or UI defaults are provided.

If the user runs:

```bash
python llm_cli.py "Extend Bilal Ahmad Khan to 2026-09-15" --source "Rendered.xlsx" --output "Rendered_LLM_Extended.xlsx"
```

Then `source` and `output` from the CLI override anything the LLM guesses. This prevents bad plans like:

```python
{'source': 'Bilal Ahmad Khan'}
```


## v0.10 Web button/form interface

Run the web UI locally:

```bash
pip install -r requirements.txt
uvicorn web_app:app --reload --host 127.0.0.1 --port 8000
```

Open:

```text
http://127.0.0.1:8000
```

The UI supports buttons/forms for:

- Create fresh workbook
- Upload workbook
- Render/clean workbook
- Summary
- Extend intern
- Edit task
- Update task status
- Update capstone
- Update scenario
- Edit weekly/small project
- Update project status
- Add intern from JSON spec

All buttons call the same `CommandExecutor` used by CLI and the LLM layer.


## v0.11 Proper Add Intern form and Add Holiday

### Add intern without JSON

```bash
python tracker_cli.py add-intern-basic --source "Blank_Intern_Tracker.xlsx" --name "Ahmed Ali" --start-date "2026-08-01" --end-date "2026-09-30" --plan-name "Custom Plan" --final-project "AIOps" --main-title "AIOps Log Detection Project" --objective "Build a practical log analysis project" --tech-stack "Python, Elastic" --output "Tracker_With_Intern.xlsx"
```

This creates placeholder daily tasks, weekly updates, and weekly/small projects from dates.

### Add holiday

```bash
python tracker_cli.py add-holiday --source "Tracker_With_Intern.xlsx" --name "Company Holiday" --date "2026-08-14" --scope global --output "Tracker_With_Holiday.xlsx"
```

Holiday rows have blank status and are not counted as pending tasks in the dashboard.


## v0.12 Plan management and selected workbook state

Added commands and web forms for:

- Create Plan
- Edit Plan
- Edit Plan Week
- Apply Plan to Intern

The web UI now tracks a Current Workbook. After a command creates an output workbook, that output becomes the current workbook and source/workbook fields are auto-filled.


## v0.13 Fixes

- Fixed Create Plan from a blank workbook with no interns.
- Fixed web upload behavior so the uploaded workbook becomes the Current Workbook and source fields update immediately.


## v0.14 Chat Assistant Add-on

Added an interactive chat panel to the web UI.

Flow:

1. User types a request.
2. Chat creates a draft/proposal or asks for missing info.
3. User approves.
4. Only then does the command execute using the existing `CommandExecutor`.

The chat assistant supports draft routing for all current command families, including plans, interns, holidays, task edits, project edits, summaries, rendering, and workbook creation.


## v0.15 Groq-powered plan drafting in chat

The Chat Assistant now uses the Groq/local LLM provider for free-form plan creation requests when `.env` is configured.

Example:

```text
create an 8 week OpenShift plan for beginner interns with weekly projects
```

The assistant drafts the full plan, shows week summaries, then waits for approval before creating the workbook plan.


## v0.16 Chat approval and plan draft fixes

- Typing `approve`, `approved`, `yes`, or `confirm` in chat now triggers the active draft approval instead of creating a new Summary command.
- Create Plan From LLM Draft now requires `weeks` to be a detailed list, not just a number.
- OpenShift plan detection is improved, so prompts like `create an 8 week OpenShift plan for beginner interns with weekly projects` produce an OpenShift-focused plan name and week content.
- If Groq returns an incomplete plan, the system generates a safe OpenShift/Kubernetes/topic-aware fallback instead of asking for raw `weeks`.


## v0.18 Chat context/missing-info fix

- Follow-up messages now fill the active draft instead of creating a new command.
- Example fixed flow:
  1. `Apply Plan to Intern`
  2. Assistant asks for `intern, plan_name`
  3. User replies `intern name is Musab Khan plan name is OpenShift Foundation`
  4. Existing apply-plan draft is completed and can be approved.
- Direct message `apply plan OpenShift Foundation to intern Musab Khan` now extracts both fields.


## v0.19 Separate chat page and clean chat UX

- Chat Assistant moved to `/chat`.
- Main forms page now links to the chat page instead of embedding chat beside forms.
- Chat responses are now shown as message bubbles and proposal cards.
- Raw command JSON is hidden from the user.
- Approval results are shown as human-readable messages with download links.


## v0.20 Chat workbook selector/upload

- Added workbook dropdown to `/chat` populated from `outputs/` and `uploads/`.
- Added upload control directly on `/chat`.
- Uploading a workbook from `/chat` now sets it as the current workbook.
- Refresh button updates the workbook list without leaving the chat page.


## v0.21 Chat polish and InfoSec plan naming

- `create a 8 week infosec plan` now names the plan `Information Security Foundation` instead of `LLM Generated Plan`.
- Added topic-aware fallback weeks for information security and cybersecurity plans.
- Chat success messages no longer dump full local paths or backend messages like `Created draft plan ...`.
- Success now says a clean message such as `Done. I created Plan_Information_Security_Foundation_....xlsx` with a download link.


## v0.22 Apply Plan also fills project/scenario defaults

- Applying a plan now also fills Main Project and Real-World Scenario defaults when those fields are blank or generic.
- Topic-aware defaults are included for OpenShift, Information Security/Cybersecurity, and Kubernetes.
- Intern and plan names are stripped before lookup to avoid errors like `Intern not found: Musab Khan `.
- Existing manager-authored project/scenario text is preserved unless it is blank/generic.


## v0.23 Add Intern With Plan workflow

- Added combined workflow command `add_intern_with_plan`.
- Chat prompts like `add intern Hakeel from 2026-08-01 to 2026-09-30 with Information Security Foundation plan` now create one proposal that:
  - adds the intern,
  - applies the selected plan using the intern's start/end dates,
  - fills main project/capstone defaults,
  - fills real-world scenario defaults,
  - refreshes dashboard.
- Workbook is only created after approval.


## v0.24 Chat intent priority fix

- Prompts like `add intern Hakeel from 2026-08-01 to 2026-09-30 with Information Security Foundation plan` now route to `Add Intern With Plan` instead of `Create Plan From LLM Draft`.
- Plan drafting is now only triggered when the user is actually asking to create/draft/build/generate a plan, not when the user is using an existing plan for an intern.


## v0.25 Add Intern With Plan only UX

- User-facing intern creation now uses `Add Intern With Plan`.
- The old separate `Add Intern (Form)` and `Apply Plan to Intern` controls are hidden from the forms UI.
- In chat, `add intern ...` now routes to `Add Intern With Plan` and asks for `plan_name` if missing.
- Backend commands are kept for compatibility, but the normal UI flow is now plan-based intern creation.


## v0.26 Editable proposal cards

- Proposal cards now include Approve / Edit / Cancel.
- Create AI-Drafted Plan proposals can be edited before approval:
  - Plan name
  - Description
  - Week theme/task/weekly project/notes
- Add Intern With Plan proposals can be edited before approval:
  - Intern details
  - Plan name
  - Dates
  - Main project
  - Scenario
  - Skills and deliverable
- Save Draft updates the in-memory draft. The workbook is still created only after approval.


## v0.27 Plan name quality and duplicate handling

- Prompts like `create a 8 week Deep learning plan` now infer `Deep Learning Foundation` instead of `LLM Generated Plan`.
- Added topic-aware fallback weeks for Deep Learning plans.
- If a plan name already exists, creating another plan automatically uses a safe copy name such as `Deep Learning Foundation Copy 2` instead of failing.
- Generic LLM names like `LLM Generated Plan` are replaced with the inferred topic name when possible.


## v0.28 Add Intern With Plan preview enrichment

- Add Intern With Plan proposals now show the generated information before approval:
  - Main project
  - Objective
  - Tech stack
  - Real-world scenario
  - Skills
  - Deliverable
  - Week-level schedule preview with date ranges, daily task, and weekly project
- The Edit button lets the user edit intern details and project/scenario fields before approval.
- Schedule preview is generated from the selected plan and intern dates. To change daily task/weekly project content, edit the plan before approval or select another plan.


## v0.29 Chat edit form overflow fix

- Fixed editable proposal fields overflowing outside the right-side proposal card.
- Inputs/textareas now stay inside the card.
- The Add Intern With Plan edit section uses a single-column layout in the sidebar.
- Form field text is normalized to regular weight for readability.


## v0.30 Governance + Task Tracker Add-on

Added basic governance features:

- Login/logout
- User management page: `/users`
- Activity logs page: `/logs`
- Task tracker page: `/tasks`
- SQLite database: `data/app.db`
- Tables: `users`, `activity_logs`, `task_tracker`
- Default admin: `admin@example.com` / `admin123`
- Logs user actions including login/logout, workbook uploads, form commands, chat approvals, task creation, and log exports.

Containerization remains a later deployment step.


## v0.31.1 Logs page UI fix

- Fixed patch syntax issue caused by JavaScript template literals inside Python f-strings.
- Rewrites `/logs` with safer JavaScript and visible log counts.


## v0.32 Password hashing and admin password reset

- New passwords are stored using PBKDF2-SHA256 salted hashes in `users.password`.
- Existing plain-text passwords are migrated to hashes after the user's next successful login.
- Failed login attempts are logged.
- Admin-only password reset endpoint added: `/api/users/reset-password`.
- User Management page now includes a Reset Password action.


## v0.33 Plan name and confirmation message fix

- Generic plan names like `LLM Generated Plan`, `Generated Plan`, and `Custom Plan` are no longer allowed in chatbot plan proposals.
- If the LLM returns a generic name, the chatbot now infers a better name from the user prompt or uses `Custom Learning Plan`.
- Approval confirmation for plan creation now includes the actual plan name, e.g. `Done. I created the Deep Learning Foundation plan in ...`.


## v0.34 LLM structured intent parser

- Added `tracker_chat/llm_intent_parser.py`.
- Chat now uses Groq/LLM for command intent and field extraction before regex fallback.
- Fixes brittle parsing cases such as lowercase names:
  - `add intern shakeel ...`
  - `Add Shakeel ...`
  - `show progress of musab khan`
- Missing-info, Edit, Approve, Cancel, validation, audit logs, and CommandExecutor execution remain unchanged.
- Regex/rule parsing is still kept as fallback if the LLM provider is unavailable.


## v0.34 LLM structured intent parser

- Added `tracker_chat/llm_intent_parser.py`.
- Chat now uses Groq/LLM for command intent and field extraction before regex fallback.
- Fixes brittle parsing cases such as lowercase names:
  - `add intern shakeel ...`
  - `Add Shakeel ...`
  - `show progress of musab khan`
- Missing-info, Edit, Approve, Cancel, validation, audit logs, and CommandExecutor execution remain unchanged.
- Regex/rule parsing is still kept as fallback if the LLM provider is unavailable.


## v0.36.1 Force plan intent + clean chat output

- Fixed v0.36 patch error caused by Python `re.sub` interpreting JavaScript backslashes.
- Prompts like `add plan secops 8 weeks` and `add plan 8 weeks secops` now force the AI-drafted plan workflow before the generic LLM intent parser.
- Common typo `weesk` is normalized to `weeks`.
- Chat messages strip raw HTML/lexical tags such as `<br>` and `<strong data-lexical-text="true">`.


## v0.37 Plan quality and Add Intern editable schedule preview

- Removes internal fallback/debug text from visible Excel fields, including `LLM returned no detailed weeks; generated safe draft.`
- Adds plan quality warnings to chat proposals when generated weeks look generic, short, or fallback-based.
- Add Intern With Plan now supports edited `schedule_preview` values during approval.
- The Edit button for Add Intern With Plan now lets users edit week theme, daily task, weekly project, and notes before workbook creation.
- The approved workbook uses the edited preview if present.


## v0.37 Plan quality and Add Intern editable schedule preview

- Removes internal fallback/debug text from visible Excel fields, including `LLM returned no detailed weeks; generated safe draft.`
- Adds plan quality warnings to chat proposals when generated weeks look generic, short, or fallback-based.
- Add Intern With Plan now supports edited `schedule_preview` values during approval.
- The Edit button for Add Intern With Plan now lets users edit week theme, daily task, weekly project, and notes before workbook creation.
- The approved workbook uses the edited preview if present.


## v0.38 Add Intern uses plan as context to draft full intern sheet

- Add Intern With Plan now asks the LLM to generate a complete intern-sheet draft using the selected plan as context.
- If the selected plan is weak/generic, the intern draft is improved instead of copying weak plan rows literally.
- The proposal preview includes main project, scenario, and week-level schedule preview.
- The Edit button can edit weekly theme, daily task, weekly project, and notes before approval.
- Approval creates the workbook from the edited draft using `schedule_preview`.
- The fallback is topic-aware for DevOps and InfoSec/SecOps and no longer exposes debug text in the workbook.


## v0.39 Blank daily task remarks for LLM-generated intern sheets

- Daily task `Remarks` are now left blank when creating an intern from a plan or LLM-generated schedule preview.
- LLM notes are still used for weekly/small project descriptions where useful.
- Remarks are reserved for manager/user updates after the workbook is created.


## v0.40 Progressive daily tasks inside each weekly theme

- Add Intern With Plan now creates progressive daily tasks within each week instead of repeating the same task every day.
- Schedule preview supports `daily_tasks` per week.
- Intern sheet daily rows use Day 1, Day 2, Day 3, etc. tasks while keeping the same weekly theme.
- Edit proposal now allows editing Day 1 to Day 5 tasks for each week.


## v0.41 Professional chat proposal panel

- Chat page now uses a more professional two-column layout.
- Proposal panel is sticky and scrolls internally.
- Approve/Edit/Cancel buttons stay visible in a sticky footer.
- Edit mode replaces the proposal panel instead of dumping a giant form below messages.
- Edit mode uses collapsible sections for intern details, main project, scenario, and weekly schedule.


## v0.42 Chat review/approval visibility fix

- The proposal/review panel is now moved to the top of the right sidebar.
- Users no longer need to scroll past workbook selector/examples to find Approve/Edit/Cancel.
- The proposal body scrolls internally while the footer buttons stay visible.


## v0.43 Plan name priority fix

- The chatbot now respects the explicit plan name in the prompt.
- Example: `Create an 8 week SecOps Foundation plan. It should include Linux and cloud log analysis...` now creates `SecOps Foundation`, not `Linux Foundation`.
- Priority order is now:
  1. `called/named X`
  2. `Create an 8 week X plan`
  3. `Create/Add plan X 8 weeks`
  4. Topic keyword fallback only if no explicit name exists.


## v0.44 Missing-info Add Intern full preview fix

- When a user says `add intern Basit` and fills missing fields through the form, the proposal now forces the same full Add Intern With Plan enrichment as the one-shot prompt.
- The proposal should show main project, scenario, schedule preview, and editable daily tasks after `Update Proposal`.
- If schedule preview cannot be generated, the UI now shows a clear warning instead of a tiny/basic approval.


## v0.44 Missing-info Add Intern full preview fix

- When a user says `add intern Basit` and fills missing fields through the form, the proposal now forces the same full Add Intern With Plan enrichment as the one-shot prompt.
- The proposal should show main project, scenario, schedule preview, and editable daily tasks after `Update Proposal`.
- If schedule preview cannot be generated, the UI now shows a clear warning instead of a tiny/basic approval.


## v0.45 Chat workflows for required four commands

Added reliable chat routing/proposals for:

- Edit Plan
- Extend Intern
- Update Capstone/Main Project
- Update Real-World Scenario

Examples:

- `rename plan DevOps Foundation to DevOps Advanced`
- `extend Basit to 2026-09-15`
- `update Basit main project to Kubernetes Monitoring Dashboard`
- `update Basit real-world scenario to investigate failed CI/CD deployment`


## v0.46 Required-four cleanup

- Fixed `update main project of Saleem to ...` extracting intern as `Of Saleem`.
- Fixed `update scenario of Saleem to ...` extraction.
- Generic proposal action details now render as clean key/value rows without raw `<strong data-lexical-text="true">` tags.


## v0.47 Repair required-four chat workflow syntax

- Repairs syntax error introduced by previous v46 patch.
- Replaces broken v45/v46 appended override block with a clean version.
- Supports:
  - Edit Plan
  - Extend Intern
  - Update Capstone/Main Project
  - Update Real-World Scenario
- Fixes `update main project of Saleem to ...` extracting intern as `Saleem`.


## v0.47 Repair required-four chat workflow syntax

- Repairs syntax error introduced by previous v46 patch.
- Replaces broken v45/v46 appended override block with a clean version.
- Supports:
  - Edit Plan
  - Extend Intern
  - Update Capstone/Main Project
  - Update Real-World Scenario
- Fixes `update main project of Saleem to ...` extracting intern as `Saleem`.


## v0.48 Repair chat recursion

- Fixes `RecursionError: maximum recursion depth exceeded` caused by duplicate v47 monkey-patch blocks.
- Removes previous v45/v46/v47 override blocks and installs one safe v48 override.
- Do not re-apply v45, v46, or v47 after this patch.


## v0.49 Add Holiday all-interns scope fix

- `add holiday for all interns date 2026-07-16` now normalizes to `scope=global`.
- Common typo `holidat` is recognized as holiday.
- Executor also normalizes holiday scope before execution to avoid `No interns matched the holiday scope` for all-intern holidays.


## v0.50 Hide Forms links from user-facing UI

- Removed visible navigation links to the old Forms page from Chat, Users, Logs, and Tasks pages.
- The Forms page is not deleted. Direct `/` access still works for admin/debug use.
- The normal user-facing workflow is now Chat Assistant first.


## v0.51 Plan name after duration fix

- Fixes prompts like `make a plan 8 weeks Ai engineering` creating `Custom Learning Plan`.
- The chatbot now extracts the topic after the duration and names the plan `AI Engineering Foundation`.
- Also works for patterns like `add plan 8 weeks software engineering`.


## v0.52 Strip duration from plan names

- Fixes prompts like `add plan 8 weeks Devops` creating `8 DevOps Foundation`.
- Plan names now remove leading duration tokens, so the result becomes `DevOps Foundation`.
- Also improves aliases for DevOps and AI Engineering.


## v0.53 Fix Create Plan edit/save missing weeks

- Fixed issue where editing a generated plan and clicking Save Draft caused the assistant to ask for missing `weeks`.
- The newer proposal UI used `.week-card`, while the older save logic only read `.week-edit`.
- Save Draft now collects plan weeks from both layouts and preserves existing weeks if no week fields are found.


## v0.54 Extend Intern With Plan

- Added `extend_intern_with_plan` workflow.
- Example: `Extend Habeeb to 2026-09-30 with Kubernetes Troubleshooting plan`.
- The workflow uses the selected extension plan as context and generates only extension-period daily tasks, weekly updates, and weekly/small projects.
- It updates intern end date and can update main project/scenario to the extension focus.
- Old simple `Extend Intern` remains available.


## v0.55 Fix Extend Intern With Plan NameError

- Fixed server startup crash from v0.54:
  `NameError: name 'LABELS' is not defined`.
- Removed invalid module-level `LABELS[...]` and `REQUIRED[...]` assignments.
- `extend_intern_with_plan` chat override remains available for full prompts like:
  `Extend Habeeb to 2026-09-30 with Kubernetes Troubleshooting plan`.


## v0.56 Repair Extend Intern With Plan runtime/routing

- Fixed runtime error: `No module named tracker_commands.results`.
- Extension with plan now works even if user omits the word `plan`:
  - `Extend musab to 2026-09-30 with Secops Foundation`
  - `Extend musab to 2026-09-30 with Secops Foundation plan`
- This prevents fallback to the simple `Extend Intern` placeholder workflow when a plan is provided.


## v0.57 Fix Extend Intern With Plan CommandResult import

- Fixes runtime error from `extend_intern_with_plan`:
  - `No module named tracker_commands.results`
  - `No module named tracker_commands.result`
- The monkey-patched extension workflow now uses the existing `CommandResult` from `plan_service.py`, or a minimal compatible fallback if needed.


## v0.58 Fix Extend Intern With Plan RenderService import

- Fixes runtime error from `extend_intern_with_plan`:
  `No module named tracker_excel.renderer.render_service`.
- Removes the guessed local import path and uses the module-level `RenderService` already used by the project.
- Adds safe fallback imports only if needed.


## v0.59 Dynamic RenderService lookup for Extend Intern With Plan

- Fixes runtime error:
  `cannot import name RenderService from tracker_excel.renderer`.
- The extension workflow now dynamically scans `tracker_excel.renderer` for a `RenderService` class instead of hardcoding a module path.
- Also dynamically resolves `VersionService`.


## v0.60 Extend Intern With Plan preview

- Extend Intern With Plan proposals now show the generated extension plan before approval:
  - current end date
  - extension start date
  - new end date
  - extension plan
  - updated main project focus
  - updated scenario focus
  - extension weekly schedule preview with progressive daily tasks
- This is a proposal/UI preview fix. Execution logic remains the existing `extend_intern_with_plan` flow.


## v0.61 Super Admin / Admin / User approval workflow

- Roles are now: Super Admin, Admin, User.
- A single bootstrap Super Admin is seeded if none exists:
  - email: `superadmin@example.com`
  - password: `superadmin123`
- Super Admin should change email/password from `/profile` after first login.
- New users submit requests through `/signup` and start as `Pending`.
- Admins can approve pending users as `User` only.
- Super Admin can approve as `User` or `Admin`, promote/demote admins, and manage all users/admins.
- Normal Users can use the app but cannot access Users or Logs.


## v0.62 Reset governance database for clean demo

- Cleans `users`, `activity_logs`, and `task_tracker` tables from `data/app.db`.
- Re-seeds only one Super Admin:
  - Email: `superadmin@example.com`
  - Password: `superadmin123`
- Logs and pending signup requests are removed for a clean governance demo.


## v0.63 Signup Bad Request Fix

- Fixed signup failures caused by missing `hash_password` import in some patch orders.
- Signup now returns clear errors for blank fields, invalid email, or duplicate email.
- Failed signup attempts are logged with the actual error message.
- Signup page now shows required-field validation and server error messages clearly.


## v0.64 Signup JS fix

- Fixed signup page JavaScript error:
  `Cannot read properties of undefined (reading 'trim')`.
- Signup now uses explicit `document.getElementById(...)` instead of relying on browser global variables from element IDs.
- The Submit button no longer gets stuck on `Submitting...` when validation or server errors occur.


## v0.65 Governance user/task/reactivation fixes

- Normal Users can no longer access `/tasks` or task APIs.
- Normal Users also have Tasks links hidden from user-facing navigation.
- Inactive users can be reactivated:
  - Admin can reactivate normal Users only.
  - Super Admin can reactivate Users and Admins.
- Users page now shows errors for role/action failures.
- Super Admin `Make Admin` / `Make User` actions are more visible and reload after success.


## v0.66 Hide admin navigation for normal Users

- Normal `User` role now has `/users`, `/logs`, and `/tasks` links removed from visible navigation.
- Applied across Chat, Profile, Tasks, Logs, Users, and legacy Forms pages.
- Server-side route permissions remain the real security layer; this patch cleans the UI so normal users do not see admin/governance navigation.


## v0.68 Fix Python future import order

- Fixed server startup error:
  `SyntaxError: from __future__ imports must occur at the beginning of the file`.
- Moves `from __future__ import annotations` back to the top of `web_app.py` after previous patches inserted imports above it.


## v0.69 Consistent Profile navigation

- Profile link is now consistently visible for every logged-in role across main pages.
- Logout link is also ensured in the header.
- Normal Users still do not see Users, Logs, or Tasks.
- Admin and Super Admin see Users, Logs, Tasks, Profile, and Logout.
- Route permissions remain the actual security layer; this patch standardizes the navbar UI.


## v0.70 Evaluation workflow

- Added Admin/Super Admin-only `/evaluation` page.
- Admin uploads tracker workbook and evaluation framework workbook.
- System detects tracker interns and evaluation scorecards.
- Closest matching scorecards are shown as professional cards.
- System auto-fills delivery metrics from tracker.
- LLM/evaluation assistant asks subjective criterion questions and proposes 0–5 scores with rationale.
- Admin can edit scores/rationale before finalizing.
- Existing evaluation workbook structure is used; no new fields are added.
- Finalized scorecard is written to a downloadable evaluated workbook.


## v0.71 Evaluation download fix

- Fixed evaluated workbook download 404 caused by returning an absolute Windows path in `/download?path=...`.
- Added a dedicated endpoint:
  `/evaluation/download?file=<filename>`
- Finalization now returns a filename-based download URL that safely serves files from `outputs/`.


## v0.72 Evaluation rationale and user-edit display

- Each evaluation answer now shows an AI suggested score and a specific reason for that number.
- If the admin accepts the AI suggestion, the page keeps and displays the AI reason.
- If the admin edits the score, the page marks the criterion as `Set by user`.
- AI/user rationale is page-only and is not written to the evaluation workbook.


## v0.73 Evaluation basis: till-now vs overall

- Evaluation page now supports two scoring bases:
  - `Till now / as of evaluation date` for ongoing internships.
  - `Overall full internship` for final evaluations.
- Default basis is `Till now` with today as evaluation date.
- Metrics now show selected scoring values plus comparison values:
  - till-now daily/weekly completion
  - overall daily/weekly completion
- Auto-written delivery scores use the selected basis.


## v0.84 Read-only summary no proposal

- Read-only summary/progress questions such as `how is Bilal doing?` no longer require approval.
- Workbook-changing commands still use proposal approval.
- Added frontend guard to prevent Approve/Edit/Cancel from appearing for read-only summary commands.


## v0.85 Execute read-only summaries immediately

- Progress/summary questions such as `how is Bilal Ahmad Khan doing?` are read-only.
- They now execute immediately instead of entering Approve/Edit/Cancel proposal flow.
- Workbook-changing commands still require approval.


## v0.86 Auto-execute read-only summary proposals

- Frontend safety net for read-only progress summary prompts.
- If chat still creates a proposal for `how is <intern> doing?`, the UI automatically approves only that read-only summary proposal.
- Workbook-changing commands are not auto-approved.


## v0.87 Chat UI compact approval panel

- Review & Approval panel no longer consumes most of the page when there is no active proposal.
- Current Workbook section stays visible without excessive scrolling.
- Navbar spacing improved, including Profile / Logout spacing.
- Approval workflow remains unchanged for workbook-changing actions.


## v0.88 Hard collapse empty approval area

- Stronger DOM-based fix for the empty `Review & Approval` panel on `/chat`.
- Collapses the empty area when it only says `No active proposal yet.`
- Allows active proposals to expand normally.
- Improves navbar spacing.


## v0.89 Precise collapse for empty Review & Approval

- Stronger fix for chat page layouts where Review & Approval and Current Workbook share an outer card.
- Collapses only the Review & Approval branch when there is no active proposal.
- Active proposals still expand normally.


## v0.90 Chat layout debug logs

- Adds F12 diagnostics for the empty Review & Approval panel height issue.
- Use `window.chatLayoutDebugV90()` or the floating Layout Debug button.
- Does not change backend logic or approval behavior.


## v0.91 Force side panel block layout

- Fixes the chat page empty Review & Approval gap based on v90 debug output.
- The issue was the ASIDE containing both Review & Approval and Current Workbook using a tall flex layout.
- Empty proposal state now forces that side panel to block/auto height.
- Active proposals still expand normally.


## v0.92 Chat recovery + direct read-only intern summary

- Removes experimental chat UI/debug/auto-approval patches v84-v91 from chat.html.
- Restores normal approval panel behavior for workbook-changing commands.
- Adds direct read-only intern progress summary API and chat interceptor.
- Prompts like `how is Bilal doing?` are answered directly without approval.
