
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import html
import json
import re
import uuid
from typing import Any

try:
    from dateutil import parser as _date_parser
except Exception:
    _date_parser = None

from tracker_commands.executor import CommandExecutor
from tracker_chat.intern_sheet_drafter import InternSheetDrafter, resolve_workbook_path
from tracker_chat.llm_intent_parser import LLMIntentParser
from tracker_excel.renderer.parser import parse_workbook

try:
    from tracker_config.settings import load_settings
    from tracker_llm.providers import build_provider
except Exception:
    load_settings = None
    build_provider = None

COMMAND_LABELS = {
    'create_workbook': 'Create Fresh Workbook',
    'render_workbook': 'Render/Clean Uploaded Workbook',
    'summary': 'Generate Progress Summary',
    'extend_intern': 'Extend Intern',
    'extend_intern_with_plan': 'Extend Intern With Plan',
    'edit_task': 'Edit Task',
    'update_task_status': 'Update Task Status',
    'update_capstone': 'Update Capstone/Main Project',
    'update_scenario': 'Update Real-World Scenario',
    'edit_project': 'Edit Weekly/Small Project',
    'update_project_status': 'Update Project Status',
    'add_intern': 'Add Intern From JSON Spec',
    'add_intern_basic': 'Add Intern (Form)',
    'add_intern_with_plan': 'Add Intern With Plan',
    'add_holiday': 'Add Holiday',
    'create_plan': 'Create Plan',
    'create_plan_from_draft': 'Create Plan From LLM Draft',
    'edit_plan': 'Edit Plan',
    'edit_plan_week': 'Edit Plan Week',
    'apply_plan_to_intern': 'Apply Plan to Intern',
}

REQUIRED = {
    'create_workbook': ['output'],
    'render_workbook': ['source', 'output'],
    'summary': ['workbook'],
    'extend_intern': ['source', 'intern', 'new_end', 'output'],
    'extend_intern_with_plan': ['source', 'intern', 'new_end', 'plan_name', 'output'],
    'edit_task': ['source', 'intern', 'task_ref', 'output'],
    'update_task_status': ['source', 'intern', 'task_ref', 'status', 'output'],
    'update_capstone': ['source', 'intern', 'output'],
    'update_scenario': ['source', 'intern', 'output'],
    'edit_project': ['source', 'intern', 'project_number', 'output'],
    'update_project_status': ['source', 'intern', 'project_number', 'status', 'output'],
    'add_intern': ['source', 'spec', 'output'],
    'add_intern_basic': ['source', 'name', 'start_date', 'end_date', 'output'],
    'add_intern_with_plan': ['source', 'name', 'start_date', 'end_date', 'plan_name', 'output'],
    'add_holiday': ['source', 'name', 'date', 'output'],
    'create_plan': ['source', 'plan_name', 'output'],
    'create_plan_from_draft': ['source', 'plan_name', 'weeks', 'output'],
    'edit_plan': ['source', 'plan_name', 'output'],
    'edit_plan_week': ['source', 'plan_name', 'week', 'output'],
    'apply_plan_to_intern': ['source', 'intern', 'plan_name', 'output'],
}

# Fields whose value is a semantic classification of the user's words
# (e.g. "mark it done" -> "Completed"), not a literal extraction. These
# are exempt from the groundedness check below, since a correct value
# legitimately never appears verbatim in the input text.
_ENUM_FIELDS = {'status'}

# These are always app/session-managed, never user-supplied in a chat
# message. The groundedness check alone isn't reliable enough to keep a
# small model from filling them in anyway - observed live: asked to
# parse "generate progress summary", the model returned
# workbook="progress" (a real word from the message, so groundedness
# didn't catch it, just wrongly assigned). Dropped unconditionally
# before the LLM's args are even considered, so current_workbook/
# generated-output defaults are the only source for these fields.
_PATH_FIELDS = {'source', 'workbook', 'output'}

# Commands whose task_ref should be corrected toward an actual date/task
# number found in the message when one exists, rather than trusting
# whatever free-text span the LLM chose - see _recover_task_ref.
_TASK_REF_COMMANDS = {'edit_task', 'update_task_status'}

# Date-valued fields. The groundedness check below requires a value to
# appear verbatim in the user's own text, which blocks legitimate date
# normalization: asked for "14th July 2026", the LLM correctly returning
# "2026-07-14" would get rejected since that string never appears in the
# input. These fields skip the literal-substring check in favor of an
# ISO-format validity check instead - still rejects hallucinated garbage,
# just not reformatted dates.
_DATE_FIELDS = {'start_date', 'end_date', 'new_end', 'date', 'target_end', 'due_date', 'assigned_date'}

# Commands that take an 'intern' field, and so are candidates for the
# possessive-name recovery in _recover_intern - see that method.
_INTERN_NAME_COMMANDS = {
    'extend_intern', 'extend_intern_with_plan', 'edit_task', 'update_task_status',
    'update_capstone', 'update_scenario', 'edit_project', 'update_project_status',
    'apply_plan_to_intern',
}

@dataclass
class ChatDraft:
    draft_id: str
    command: str
    args: dict[str, Any] = field(default_factory=dict)
    status: str = 'drafting'
    summary: str = ''

class ChatService:
    def __init__(self):
        self.drafts: dict[str, ChatDraft] = {}
        self.executor = CommandExecutor()
        self.intern_sheet_drafter = InternSheetDrafter()
        self.intent_parser = LLMIntentParser()
        self.provider = None
        if load_settings and build_provider:
            try:
                settings = load_settings('.env')
                if settings.ai_provider.lower() != 'mock':
                    self.provider = build_provider(settings)
            except Exception:
                self.provider = None

    def message(self, text: str, current_workbook: str | None = None) -> dict:
        # Plan-aware extension ("extend X to DATE with PLAN") and the required-four
        # workflows (edit plan / extend intern / capstone / scenario) are checked
        # with deterministic regex before the general intent parser, since they have
        # very specific phrasing that the LLM/generic rules can misroute.
        draft = self._extend_with_plan_draft(text, current_workbook)
        if not draft:
            draft = self._required_four_draft(text, current_workbook)
        if draft:
            return self._response_for_draft(draft)

        # Typed approvals are handled by the frontend. If they reach backend, do not
        # route them into a new command such as summary.
        if text.strip().lower() in {'approve', 'approved', 'yes', 'confirm', 'ok'}:
            return {'ok': False, 'error': 'Use the Approve button or keep the active draft selected.'}
        if text.strip().lower() in {'cancel', 'stop'}:
            return {'ok': False, 'error': 'Use the Cancel button or keep the active draft selected.'}
        # Explicit plan creation must be handled before the generic intent parser.
        # This fixes prompts like: add plan secops 8 weeks.
        if self._is_explicit_plan_create(text):
            draft = self._draft_plan_with_llm(text, current_workbook)
        elif self._looks_like_plan_request(text):
            draft = self._draft_plan_with_llm(text, current_workbook)
        else:
            # For all other commands, use LLM structured intent parsing first.
            # Regex/rules remain only as fallback.
            draft = self._build_llm_intent_draft(text, current_workbook) or self._build_rule_draft(text, current_workbook)
        return self._response_for_draft(draft)

    def update_draft(self, draft_id: str, args: dict) -> dict:
        draft = self.drafts.get(draft_id)
        if not draft:
            return {'ok': False, 'error': 'Draft not found'}
        for k, v in args.items():
            if v not in [None, '']:
                if k in ['weeks', 'schedule_preview'] and isinstance(v, str):
                    try:
                        v = json.loads(v)
                    except Exception:
                        pass
                draft.args[k] = v
        self._force_enrich_ready_add_intern_with_plan(draft)
        return self._response_for_draft(draft)


    def fill_from_text(self, draft_id: str, text: str) -> dict:
        """Fill missing fields on the active draft from a natural-language reply.

        This prevents a follow-up such as "intern name is Musab Khan plan name is
        OpenShift Foundation" from being interpreted as a brand-new create-plan
        request.
        """
        draft = self.drafts.get(draft_id)
        if not draft:
            return {'ok': False, 'error': 'Draft not found'}

        # "Extend X with a plan?" is asked as a plain missing-field question
        # (see _extend_intern_draft). Handle an explicit opt-out before any
        # LLM/regex parsing, since a phrase like "no plan" would otherwise
        # get fed to the LLM as if it were a plan name.
        if draft.command == 'extend_intern_with_plan' and not draft.args.get('plan_name') and self._wants_no_plan(text):
            draft.command = 'extend_intern'
            draft.args.pop('plan_name', None)
            draft.args.pop('extension_preview', None)
            return self._response_for_draft(draft)

        # Try LLM field extraction for the active draft first. This avoids brittle
        # issues such as lowercase names. Regex below remains fallback when no LLM
        # provider is configured or the LLM parse doesn't match the active command.
        parsed = self.intent_parser.parse(text, active_command=draft.command)
        if parsed and parsed.get('command') == draft.command:
            # A small LLM answering a narrow "fill these missing fields"
            # prompt can echo a placeholder/example token back as if it
            # were real data (e.g. its own few-shot example name, a
            # "__foo__" sentinel meant for internal routing only, or a
            # plausible-looking but entirely invented name/date). Only
            # accept a field the user was actually asked to supply, reject
            # any "__foo__"-shaped placeholder outright, and - since a
            # genuine answer should always be traceable back to the user's
            # own words - require the value to actually appear in what they
            # typed. That last check is skipped for fields whose value is a
            # semantic classification rather than a literal extraction.
            still_missing = {k for k in REQUIRED.get(draft.command, []) if not draft.args.get(k)}
            for k, v in (parsed.get('args') or {}).items():
                if k in _PATH_FIELDS:
                    continue
                if v in [None, '', []]:
                    continue
                if isinstance(v, str) and re.fullmatch(r'__[a-z_]+__', v):
                    continue
                if k not in still_missing:
                    continue
                if k in _DATE_FIELDS:
                    if isinstance(v, str) and not self._is_valid_iso_date(v):
                        continue
                elif isinstance(v, str) and self._looks_like_bare_date(v):
                    # Observed live: replying "26th october 2026" to a draft
                    # missing both new_end and plan_name got assigned to
                    # plan_name instead - it's grounded (appears verbatim)
                    # so the check below wouldn't catch it. A date-shaped
                    # answer is never a real value for a non-date field.
                    continue
                elif k not in _ENUM_FIELDS and isinstance(v, str) and not self._is_grounded(v, text):
                    continue
                draft.args[k] = v
            # If exactly one date field is still missing after the above,
            # the reply itself may just be a bare date ("26th october
            # 2026") that the LLM misassigned or dropped entirely -
            # recover it directly. (Only when unambiguous: if two date
            # fields are both missing, e.g. start_date and end_date, a
            # single recovered date can't safely be assigned to either.)
            missing_dates = [k for k in still_missing if k in _DATE_FIELDS and not draft.args.get(k)]
            if len(missing_dates) == 1:
                recovered = self._first_date(text)
                if recovered:
                    draft.args[missing_dates[0]] = recovered
            self._force_enrich_ready_add_intern_with_plan(draft)
            return self._response_for_draft(draft)

        lower = text.lower()
        args = draft.args

        # Common field extractions.
        dates = self._find_all_dates(text)
        if draft.command in ['add_intern_basic','add_intern_with_plan']:
            if 'name' not in args or not args.get('name'):
                m = re.search(r'(?:intern name is|name is|named|intern)\s+([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){0,3})', text)
                if m: args['name'] = m.group(1).strip()
            if dates:
                args.setdefault('start_date', dates[0])
                if len(dates) > 1: args.setdefault('end_date', dates[1])
            if draft.command == 'add_intern_with_plan':
                pm = re.search(r'(?:plan name is|plan is|with|for)\s+([A-Za-z0-9 ._+-]+)', text, re.I)
                if pm:
                    val = pm.group(1).strip().rstrip('.')
                    if 'security' in val.lower() or 'infosec' in val.lower() or 'cyber' in val.lower(): val = 'Information Security Foundation'
                    elif 'openshift' in val.lower(): val = 'OpenShift Foundation'
                    args['plan_name'] = val
        elif draft.command == 'apply_plan_to_intern':
            m = re.search(r'(?:intern name is|intern is|to intern|intern)\s+([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){0,3})', text)
            if m: args['intern'] = m.group(1).strip()
            pm = re.search(r'(?:plan name is|plan is|apply plan|plan)\s+([A-Za-z0-9 ._+-]+)', text, re.I)
            if pm:
                val = pm.group(1).strip().rstrip('.')
                # Trim if the phrase also contains "to intern".
                val = re.split(r'\s+to\s+intern\s+', val, flags=re.I)[0].strip()
                if val: args['plan_name'] = val
        elif draft.command == 'add_holiday':
            if dates: args['date'] = dates[0]
            hm = re.search(r'(?:holiday name is|holiday is|holiday called|holiday)\s+([A-Za-z0-9 ._-]+)', text, re.I)
            if hm: args['name'] = hm.group(1).strip()
        elif draft.command in ['extend_intern','extend_intern_with_plan','edit_task','update_task_status','update_capstone','update_scenario','edit_project','update_project_status']:
            m = re.search(r'(?:intern name is|intern is|intern|for)\s+([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){0,3})', text)
            if m: args['intern'] = m.group(1).strip()
            if draft.command in ['extend_intern', 'extend_intern_with_plan'] and dates: args['new_end'] = dates[-1]
            if draft.command == 'extend_intern_with_plan' and not args.get('plan_name'):
                pm = re.search(r'(?:plan name is|plan is|with|use|apply)\s+([A-Za-z0-9 ._+-]+)', text, re.I)
                if pm:
                    val = pm.group(1).strip().rstrip('.')
                    if val: args['plan_name'] = val
                elif not dates and not re.search(r'\bintern\b', lower):
                    # Nothing else recognized in this reply - treat it as
                    # the plan name itself (e.g. user just types "SecOps
                    # Foundation" when that's the only thing being asked).
                    candidate = text.strip().rstrip('.')
                    if candidate:
                        args['plan_name'] = candidate
            if draft.command in ['edit_task','update_task_status'] and dates: args['task_ref'] = dates[0]
            if 'completed' in lower: args['status'] = 'Completed'
            elif 'in progress' in lower: args['status'] = 'In Progress'
            elif 'pending' in lower: args['status'] = 'Pending'
        elif draft.command in ['create_plan','edit_plan','edit_plan_week','create_plan_from_draft']:
            pm = re.search(r'(?:plan name is|plan is|plan called|plan named|plan)\s+([A-Za-z0-9 ._+-]+)', text, re.I)
            if pm:
                val = pm.group(1).strip().rstrip('.')
                if val: args['plan_name'] = val
            wm = re.search(r'week\s+(\d+)', lower)
            if wm: args['week'] = int(wm.group(1))
        self._force_enrich_ready_add_intern_with_plan(draft)
        return self._response_for_draft(draft)

    def approve(self, draft_id: str) -> dict:
        draft = self.drafts.get(draft_id)
        if not draft:
            return {'ok': False, 'error': 'Draft not found'}
        missing = self._missing(draft)
        if missing:
            return {'ok': False, 'error': f'Missing fields: {", ".join(missing)}'}
        result = self.executor.execute({'command': draft.command, 'args': draft.args})
        return {
            'ok': result.ok,
            'message': result.message,
            'output_path': result.output_path,
            'data': result.data,
        }

    def cancel(self, draft_id: str) -> dict:
        self.drafts.pop(draft_id, None)
        return {'ok': True, 'message': 'Draft cancelled'}


    def _force_enrich_ready_add_intern_with_plan(self, draft: ChatDraft):
        """Force full intern-sheet preview after missing fields are filled.

        This makes the flow:
          User: add intern Basit
          Assistant: asks missing info
          User fills fields and clicks Update Proposal
        produce the same detailed proposal as:
          User: Add intern Basit from ... with ... plan
        """
        if not draft or draft.command != 'add_intern_with_plan':
            return
        required = ['source', 'name', 'start_date', 'end_date', 'plan_name']
        if any(not draft.args.get(k) for k in required):
            return
        try:
            self._enrich_add_intern_with_plan(draft)
        except Exception:
            # Do not block proposal; UI can still show basic fields.
            return

    def _response_for_draft(self, draft: ChatDraft) -> dict:
        missing = self._missing(draft)
        if not missing:
            self._force_enrich_ready_add_intern_with_plan(draft)
            self._enrich_extend_intern_with_plan(draft)
        if missing:
            draft.status = 'needs_more_info'
            self.drafts[draft.draft_id] = draft
            return {
                'ok': True,
                'type': 'needs_more_info',
                'draft_id': draft.draft_id,
                'message': self._question(draft.command, missing),
                'missing': missing,
                'known_args': draft.args,
                'command': draft.command,
            }
        if draft.command == 'add_intern_with_plan':
            self._enrich_add_intern_with_plan(draft)
        if draft.command == 'summary':
            return self._execute_readonly_summary(draft)
        draft.status = 'awaiting_approval'
        draft.summary = self._summary(draft)
        self.drafts[draft.draft_id] = draft
        return {
            'ok': True,
            'type': 'proposal',
            'draft_id': draft.draft_id,
            'message': draft.summary,
            'command': draft.command,
            'label': COMMAND_LABELS.get(draft.command, draft.command),
            'args': draft.args,
        }

    def _execute_readonly_summary(self, draft: ChatDraft) -> dict:
        """Summary requests are read-only: execute immediately, no approval step."""
        result = self.executor.execute({'command': draft.command, 'args': draft.args})
        self.drafts.pop(draft.draft_id, None)
        return {
            'ok': result.ok,
            'type': 'result',
            'draft_id': draft.draft_id,
            'message': result.message,
            'command': draft.command,
            'readonly': True,
            'requires_approval': False,
            'needs_approval': False,
            'proposal': None,
            'draft': None,
            'output_path': result.output_path,
            'data': result.data,
        }

    def _enrich_extend_intern_with_plan(self, draft: ChatDraft):
        """Populate the extension-period preview for Extend Intern With Plan.

        Mirrors _enrich_add_intern_with_plan: does not create the workbook, only
        fills in-memory preview fields (current/new end dates, extension focus,
        week-level schedule) so the user can review before approval.
        """
        if not draft or draft.command != 'extend_intern_with_plan':
            return
        args = draft.args
        required = ['source', 'intern', 'new_end', 'plan_name']
        if any(not args.get(k) for k in required):
            return
        if args.get('extension_schedule_preview'):
            return
        try:
            source_path = resolve_workbook_path(args.get('source'))
            data = parse_workbook(source_path)
            intern_obj = None
            for item in data.interns:
                if item.name.strip().lower() == str(args.get('intern')).strip().lower():
                    intern_obj = item
                    break
            if not intern_obj:
                return
            current_end = intern_obj.main_row[4] if len(intern_obj.main_row) > 4 else None
            if not isinstance(current_end, datetime):
                return
            new_end_dt = datetime.fromisoformat(str(args.get('new_end')))
            extension_start = current_end + timedelta(days=1)
            while extension_start.weekday() >= 5:
                extension_start += timedelta(days=1)
            if extension_start.date() > new_end_dt.date():
                return

            draft_sheet = self.intern_sheet_drafter.draft(
                source_path,
                str(args.get('intern')),
                extension_start.strftime('%Y-%m-%d'),
                new_end_dt.strftime('%Y-%m-%d'),
                str(args.get('plan_name')),
            )
            main = draft_sheet.get('main_project') or {}
            scenario = draft_sheet.get('scenario') or {}
            weeks = draft_sheet.get('weeks') or []

            args['current_end'] = current_end.strftime('%Y-%m-%d')
            args['extension_start'] = extension_start.strftime('%Y-%m-%d')
            args['extension_main_title'] = main.get('title', '')
            args['extension_objective'] = main.get('objective', '')
            args['extension_tech_stack'] = main.get('tech_stack', '')
            args['extension_scenario'] = scenario.get('scenario', '')
            args['extension_skills'] = scenario.get('skills', '')
            args['extension_deliverable'] = scenario.get('deliverable', '')
            args['extension_schedule_preview'] = weeks
        except Exception as e:
            args['extension_preview_error'] = str(e)


    def _is_explicit_plan_create(self, text: str) -> bool:
        """Detect commands that clearly mean create/add a learning plan.

        This is a deterministic safety guard before the general LLM intent parser.
        It prevents prompts like "add plan secops 8 weeks" from being interpreted
        as summary or add-intern actions.
        """
        lower = (text or '').lower()
        if 'intern' in lower or 'apply plan' in lower or 'edit plan' in lower or 'plan week' in lower:
            return False
        # Common typos for weeks.
        lower = re.sub(r'weesk|weks|wek', 'weeks', lower)
        return bool(re.search(r'\b(add|create|make|draft|generate|build)\s+(a\s+|an\s+|the\s+)?(\d+\s+weeks?\s+)?[a-z0-9 ._-]*\bplan\b', lower) or
                    re.search(r'\b(add|create|make|draft|generate|build)\s+plan\b', lower))

    def _looks_like_plan_request(self, text: str) -> bool:
        lower = text.lower()
        # Important intent priority:
        # - add/create intern with a plan should be add_intern_with_plan, not create_plan_from_draft
        # - apply plan should be apply_plan_to_intern
        # - edit plan/week should stay edit actions
        if 'plan' not in lower:
            return False
        blockers = [
            'add intern', 'create intern', 'new intern',
            'apply plan', 'apply the plan',
            'edit plan', 'plan week', 'rename plan'
        ]
        if any(x in lower for x in blockers):
            return False
        return any(x in lower for x in ['create', 'make', 'draft', 'generate', 'build'])

    def _fallback_weeks(self, plan_name: str, count: int, note: str) -> list[dict]:
        lower = plan_name.lower()
        if 'openshift' in lower:
            base = [
                ('Linux, Containers, and Platform Basics', 'Review Linux services, container images, registries, and basic troubleshooting commands.', 'Run and inspect a containerized sample app locally.'),
                ('Kubernetes Foundations', 'Learn pods, deployments, services, namespaces, labels, logs, probes, and basic kubectl workflows.', 'Deploy a simple app on Kubernetes and expose it internally.'),
                ('OpenShift Architecture and Projects', 'Understand OpenShift projects, users, routes, operators, builds, image streams, and the web console.', 'Create an OpenShift project and deploy a sample app.'),
                ('Builds, Routes, ConfigMaps, and Secrets', 'Practice source-to-image/build config concepts, routes, configuration, and secret handling.', 'Deploy a configured app with route, config map, and secret.'),
                ('Storage and Stateful Workloads', 'Learn persistent volumes, claims, storage classes, and stateful workload considerations.', 'Attach persistent storage to a sample workload.'),
                ('Monitoring and Troubleshooting', 'Use events, logs, metrics, health probes, alerts, and common debugging workflows.', 'Troubleshoot a broken OpenShift deployment and document the fix.'),
                ('Security, RBAC, and Policies', 'Practice role bindings, service accounts, security context constraints, network policies, and least privilege.', 'Create a restricted service account and validate permissions.'),
                ('Final OpenShift Deployment Project', 'Combine deployment, route, config, storage, monitoring, and troubleshooting into one final demo.', 'Deliver a final OpenShift deployment demo and short runbook.'),
            ]
        elif 'deep learning' in lower or 'deeplearning' in lower:
            base = [
                ('Python, Math, and ML Refresh', 'Review Python notebooks, NumPy, Pandas, matrices, gradients, train/test splits, and model evaluation basics.', 'Build a small supervised learning baseline and document metrics.'),
                ('Neural Network Foundations', 'Learn perceptrons, activation functions, loss functions, backpropagation intuition, and optimization basics.', 'Train a simple neural network on a tabular or image dataset.'),
                ('Deep Learning Framework Basics', 'Practice PyTorch or TensorFlow tensors, datasets, dataloaders, model classes, training loops, and checkpoints.', 'Create a reusable training loop with validation tracking.'),
                ('Computer Vision Fundamentals', 'Explore CNNs, image preprocessing, augmentation, transfer learning, and model evaluation.', 'Fine-tune an image classifier and summarize performance.'),
                ('NLP and Embeddings Basics', 'Learn tokenization, embeddings, sequence models, transformer concepts, and text classification workflows.', 'Build a small text classification or embedding similarity demo.'),
                ('Model Tuning and Experiment Tracking', 'Practice hyperparameter tuning, overfitting control, regularization, learning-rate schedules, and experiment notes.', 'Run multiple experiments and compare results in a short report.'),
                ('Deployment and Inference Basics', 'Learn model export, inference scripts, batching, latency basics, and simple API serving patterns.', 'Create a simple inference endpoint or batch prediction script.'),
                ('Final Deep Learning Project', 'Combine dataset preparation, model training, evaluation, and inference into a complete final demo.', 'Deliver a final model demo, metrics report, and brief technical write-up.'),
            ]
        elif 'security' in lower or 'infosec' in lower or 'cyber' in lower or 'soc analyst' in lower:
            base = [
                ('Security Foundations and Governance', 'Review confidentiality, integrity, availability, risk, policy basics, and common security roles.', 'Create a short security controls checklist for a sample system.'),
                ('Networking and Linux Security Basics', 'Practice basic networking, ports, protocols, Linux permissions, logs, and hardening concepts.', 'Analyze sample Linux auth logs and identify suspicious entries.'),
                ('Threats, Vulnerabilities, and Risk', 'Learn common attack types, CVEs, vulnerability severity, patching, and risk prioritization.', 'Prepare a vulnerability triage report for sample findings.'),
                ('Identity, Access, and Authentication', 'Practice IAM concepts, MFA, least privilege, password policy, and access review workflows.', 'Create an access review checklist and sample remediation notes.'),
                ('Security Monitoring and SIEM Basics', 'Review log sources, alerts, indicators of compromise, and basic SIEM investigation flow.', 'Investigate sample SIEM alerts and document conclusions.'),
                ('Incident Response Fundamentals', 'Learn incident lifecycle, triage, containment, eradication, recovery, and evidence handling basics.', 'Write a mini incident response report from a simulated alert.'),
                ('Cloud and Application Security Basics', 'Review secure configuration, secrets, web risks, dependency risks, and basic cloud controls.', 'Assess a sample app/cloud checklist and propose fixes.'),
                ('Final Security Assessment Project', 'Combine monitoring, vulnerability review, access review, and incident response into a final demo.', 'Deliver a final security assessment report and presentation.'),
            ]
        elif 'kubernetes' in lower:
            base = [
                ('Container and Kubernetes Basics', 'Review images, containers, pods, deployments, services, and namespaces.', 'Deploy a simple app on Kubernetes.'),
                ('Configuration and Networking', 'Practice ConfigMaps, Secrets, Services, Ingress, and DNS basics.', 'Expose a configured app through service and ingress.'),
                ('Storage and Scheduling', 'Learn PV/PVC, node scheduling, requests, limits, and probes.', 'Deploy a persistent workload with health probes.'),
                ('Helm and Manifests', 'Practice YAML manifests, Helm charts, values, and release management.', 'Package a sample app as a Helm chart.'),
                ('Observability', 'Use logs, events, metrics, and troubleshooting workflows.', 'Troubleshoot a simulated deployment failure.'),
                ('Security Basics', 'Practice RBAC, service accounts, and namespace isolation.', 'Implement least privilege for a sample app.'),
                ('CI/CD to Kubernetes', 'Build a simple pipeline that deploys to Kubernetes.', 'Create a basic deploy pipeline.'),
                ('Final Kubernetes Project', 'Deliver a complete Kubernetes deployment and runbook.', 'Final demo and documentation.'),
            ]
        else:
            base = [
                ('Foundation and Environment Setup', 'Set up tools, review prerequisites, and complete orientation tasks.', 'Environment setup checklist.'),
                ('Core Concepts', 'Learn the main concepts and complete guided labs.', 'Concept summary and short demo.'),
                ('Hands-on Practice', 'Practice common workflows and solve small exercises.', 'Hands-on lab output.'),
                ('Intermediate Workflows', 'Combine multiple concepts into realistic tasks.', 'Integrated mini-project.'),
                ('Troubleshooting', 'Debug common issues and document root causes.', 'Troubleshooting report.'),
                ('Automation and Repeatability', 'Automate routine steps and improve reliability.', 'Automation script or workflow.'),
                ('Project Polish', 'Improve quality, documentation, and presentation.', 'Project improvement checklist.'),
                ('Final Demo', 'Present final work and lessons learned.', 'Final demo and report.'),
            ]
        rows = []
        for i in range(1, count + 1):
            item = base[(i - 1) % len(base)]
            rows.append({'week': i, 'theme': item[0], 'task': item[1], 'weekly_project': item[2], 'notes': note})
        return rows


    def _build_llm_intent_draft(self, text: str, current_workbook: str | None) -> ChatDraft | None:
        parsed = self.intent_parser.parse(text)
        if not parsed:
            return None
        command = parsed.get('command')
        if command == '__plan_draft__':
            return self._draft_plan_with_llm(text, current_workbook)
        raw_args = parsed.get('args') or {}
        # Same grounding requirement as fill_from_text: given a message
        # with too little information, a small model can invent a
        # plausible-looking value (observed live: "add intern from
        # 2026-08-09 to 2026-09-01 ..." with no name in it at all still
        # came back with name="Shakeel", its own few-shot example name)
        # rather than just leaving the field for the user to be asked
        # about. Drop anything not actually traceable to the user's words.
        def _keep(k, v):
            if k in _PATH_FIELDS:
                return False
            if not isinstance(v, str):
                return True
            if k in _DATE_FIELDS:
                return self._is_valid_iso_date(v)
            if k in _ENUM_FIELDS:
                return True
            return self._is_grounded(v, text)
        args = {k: v for k, v in raw_args.items() if _keep(k, v)}
        # Inject current workbook defaults. The LLM must not invent source/output paths.
        if current_workbook:
            if command == 'summary':
                args.setdefault('workbook', current_workbook)
            elif command != 'create_workbook':
                args.setdefault('source', current_workbook)
        self._defaults(command, args)
        if command == 'add_holiday':
            self._normalize_holiday_args_v49(text, args)
        if command == 'add_intern_with_plan' and not args.get('plan_name'):
            self._recover_plan_name(text, args)
        if command in _TASK_REF_COMMANDS:
            self._recover_task_ref(text, args)
        if command in _INTERN_NAME_COMMANDS:
            self._recover_intern(text, args)
        return ChatDraft(str(uuid.uuid4()), command, args)

    def _recover_intern(self, text: str, args: dict):
        """Fill 'intern' via regex when the LLM dropped/ungrounded it.

        Observed live: for "mark Sara's task on 2026-08-04 as
        completed," the LLM path sometimes returns no usable intern
        value at all (grounding check strips it), leaving the user
        asked for a field their message already answered. Same
        possessive-phrasing fallback as the pure-regex parser uses.
        """
        if args.get('intern'):
            return
        m = re.search(r'(?:intern|for|named|name)\s+([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){0,3})', text)
        if not m:
            m = re.search(r"\b([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){0,3})'s\s+(?:task|project|scenario|capstone|main project)\b", text)
        if not m:
            # "extend Sara to 5th September 2026" / "extend Sara's plan
            # until ..." - name directly follows the action verb with no
            # "intern"/"for"/"named" keyword and no possessive+noun match.
            m = re.search(r'\b(?:extend|update|mark|edit)\b\s+([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){0,3})\b', text)
        if m:
            args['intern'] = m.group(1).strip()

    def _recover_task_ref(self, text: str, args: dict):
        """Prefer an actual date or task number over whatever free-text
        span the LLM chose for task_ref.

        Observed live: for "mark Sara's task on 2026-08-04 as
        completed," the model returned task_ref="Sara's task" - a real
        substring of the message (so the groundedness check doesn't
        catch it), just the wrong span. task_ref is meant to identify
        *which* task (by date, number, or matching description text);
        when the message actually contains a date or a task number,
        that is always a more reliable reference than a paraphrase, so
        it takes priority over the model's guess.
        """
        date_m = re.search(r'20\d{2}-\d{2}-\d{2}', text)
        if date_m:
            args['task_ref'] = date_m.group(0)
            return
        num_m = re.search(r'\btask\s*(?:number|#)?\s*(\d+)\b', text, re.I)
        if num_m:
            args['task_ref'] = num_m.group(1)

    def _recover_plan_name(self, text: str, args: dict):
        """Deterministic backstop for plan_name on add_intern_with_plan.

        Observed live: given "... with SecOps Foundation, main project
        should be ..." (no trailing word "plan"), the LLM filed the plan
        name under manager instead of plan_name, and the earlier regex
        fallback only matched "with X plan" (required that trailing
        word). This covers the bare "with X" phrasing directly, stopping
        at the next clause boundary instead of requiring "plan" to
        literally appear.
        """
        pm = re.search(r'\bwith\s+([A-Za-z0-9][\w .+-]*?)(?:\s*,|\s+main\b|\s+manager\b|\.|$)', text, re.I)
        if not pm:
            return
        val = pm.group(1).strip().rstrip('.')
        if not val or val.lower() == 'intern':
            return
        args['plan_name'] = val
        # The LLM likely misfiled this same value under manager - drop it
        # so it doesn't show up twice, once correctly and once wrong.
        if str(args.get('manager', '')).strip().lower() == val.lower():
            args.pop('manager', None)

    def _normalize_holiday_args_v49(self, text: str, args: dict):
        lower = (text or '').lower()
        # Global/all interns holiday should apply to all intern schedules.
        if any(x in lower for x in ['all interns', 'everyone', 'global', 'company-wide', 'company wide', 'all users']):
            args['scope'] = 'global'
            args.pop('intern_name', None)
        # If a single intern is explicitly mentioned, keep individual scope.
        m = re.search(r'(?:for intern|for)\s+([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){0,3})', text or '')
        if m and 'all interns' not in lower:
            args['scope'] = 'intern'
            args['intern_name'] = m.group(1).strip()
        # Default no explicit scope to global because holidays are usually calendar-wide.
        args.setdefault('scope', 'global')
        args.setdefault('name', 'Holiday')

    def _build_rule_draft(self, text: str, current_workbook: str | None) -> ChatDraft:
        lower = text.lower()
        command = self._detect_command(lower)
        args: dict[str, Any] = {}
        if current_workbook:
            if command == 'summary':
                args['workbook'] = current_workbook
            elif command != 'create_workbook':
                args['source'] = current_workbook
        self._extract_common(text, lower, command, args)
        self._defaults(command, args)
        if command == 'add_holiday':
            self._normalize_holiday_args_v49(text, args)
        if command == 'add_intern_with_plan' and not args.get('plan_name'):
            self._recover_plan_name(text, args)
        return ChatDraft(str(uuid.uuid4()), command, args)

    def _detect_command(self, lower: str) -> str:
        if 'clean' in lower or 'render' in lower: return 'render_workbook'
        # Checked early and before capstone/scenario/task/extend keywords:
        # a message adding a brand-new intern often *describes* that
        # intern's main project, scenario, or tasks in the same sentence
        # (e.g. "add intern Sara ... main project should be building a
        # SIEM dashboard"), which must not be misread as an edit to an
        # existing intern that doesn't exist yet.
        if 'json' in lower and 'intern' in lower: return 'add_intern'
        if 'add intern' in lower or 'create intern' in lower or 'new intern' in lower: return 'add_intern_with_plan'
        if 'summary' in lower or 'progress' in lower or 'report' in lower: return 'summary'
        if 'holiday' in lower or 'holidat' in lower: return 'add_holiday'
        if 'extend' in lower: return 'extend_intern'
        if 'task status' in lower or ('mark' in lower and 'task' in lower): return 'update_task_status'
        if 'edit task' in lower or ('change' in lower and 'task' in lower): return 'edit_task'
        if 'capstone' in lower or 'main project' in lower: return 'update_capstone'
        if 'scenario' in lower: return 'update_scenario'
        if 'project status' in lower: return 'update_project_status'
        if 'edit project' in lower or 'weekly project' in lower or 'small project' in lower: return 'edit_project'
        if 'apply plan' in lower or ('apply' in lower and 'plan' in lower): return 'apply_plan_to_intern'
        if 'edit plan week' in lower or ('week' in lower and 'plan' in lower and 'edit' in lower): return 'edit_plan_week'
        if 'edit plan' in lower or 'rename plan' in lower: return 'edit_plan'
        if 'fresh workbook' in lower or 'blank workbook' in lower or 'create workbook' in lower: return 'create_workbook'
        if any(v in lower for v in ['create', 'make', 'new', 'generate', 'build']) and any(w in lower for w in ['excel', 'workbook', 'xlsx']): return 'create_workbook'
        return 'summary'

    def _extract_common(self, text: str, lower: str, command: str, args: dict):
        dates = self._find_all_dates(text)
        if command == 'extend_intern' and dates: args['new_end'] = dates[-1]
        if command == 'add_holiday' and dates: args['date'] = dates[-1]
        if command in ['add_intern_basic','add_intern_with_plan']:
            if len(dates) >= 1: args['start_date'] = dates[0]
            if len(dates) >= 2: args['end_date'] = dates[1]
        if command in ['edit_task','update_task_status'] and dates: args['task_ref'] = dates[0]
        if command in _INTERN_NAME_COMMANDS:
            self._recover_intern(text, args)
        if command in ['add_intern_basic','add_intern_with_plan']:
            m2 = re.search(r'(?:named|name|intern)\s+([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){0,3})', text)
            if m2: args['name'] = m2.group(1).strip()
            if command == 'add_intern_with_plan':
                # Prefer explicit "with X plan" / "for X plan" pattern.
                pm = re.search(r'(?:with|for)\s+([A-Za-z0-9 ._+-]+?)\s+plan(?:\b|$)', text, re.I)
                if not pm:
                    pm = re.search(r'(?:plan name is|plan is)\s+([A-Za-z0-9 ._+-]+)', text, re.I)
                if pm:
                    val = pm.group(1).strip().rstrip('.')
                    if val and val.lower() not in ['intern']:
                        if 'security' in val.lower() or 'infosec' in val.lower() or 'cyber' in val.lower():
                            args['plan_name'] = 'Information Security Foundation'
                        elif 'openshift' in val.lower():
                            args['plan_name'] = 'OpenShift Foundation'
                        else:
                            args['plan_name'] = val
        if 'completed' in lower: args['status'] = 'Completed'
        elif 'in progress' in lower: args['status'] = 'In Progress'
        elif 'pending' in lower: args['status'] = 'Pending'
        wm = re.search(r'week\s+(\d+)', lower)
        if wm: args['week'] = int(wm.group(1))
        pm = re.search(r'project\s+#?\s*(\d+)', lower)
        if pm: args['project_number'] = int(pm.group(1))
        # apply plan name extraction v18
        if command == 'apply_plan_to_intern':
            ap = re.search(r'apply\s+plan\s+(.+?)\s+to\s+intern\s+([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){0,3})', text, re.I)
            if ap:
                args['plan_name'] = ap.group(1).strip().rstrip('.')
                args['intern'] = ap.group(2).strip()
            else:
                pm = re.search(r'(?:plan name is|plan is)\s+([A-Za-z0-9 ._+-]+)', text, re.I)
                if pm: args['plan_name'] = pm.group(1).strip().rstrip('.')
        if command == 'add_holiday':
            hm = re.search(r'holiday(?: named| called)?\s+([A-Za-z0-9 ._-]+)', text, re.I)
            args['name'] = hm.group(1).strip() if hm else 'Holiday'

    def _defaults(self, command: str, args: dict):
        stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        if command == 'create_workbook': args.setdefault('output', f'Blank_Intern_Tracker_{stamp}.xlsx')
        elif command == 'add_intern_with_plan': args.setdefault('output', f'Intern_With_Plan_{stamp}.xlsx')
        elif command != 'summary': args.setdefault('output', f'{command}_{stamp}.xlsx')
        if command == 'add_holiday': args.setdefault('scope', 'global')

    def _missing(self, draft: ChatDraft) -> list[str]:
        missing = [k for k in REQUIRED.get(draft.command, []) if draft.args.get(k) in [None, '', []]]
        if draft.command == 'create_plan_from_draft':
            weeks = draft.args.get('weeks')
            if not isinstance(weeks, list) or not weeks:
                if 'weeks' not in missing:
                    missing.append('weeks')
        return missing

    def _question(self, command: str, missing: list[str]) -> str:
        label = COMMAND_LABELS.get(command, command)
        return f'I can prepare {label}, but I need: {", ".join(missing)}. Please provide these values.'


    def _enrich_add_intern_with_plan(self, draft: ChatDraft):
        """Populate preview and editable project/scenario fields for Add Intern With Plan.

        This does not create the workbook. It only enriches the in-memory draft so
        the user can review/edit before approval.
        """
        args = draft.args
        plan_name = (args.get('plan_name') or '').strip()
        source = args.get('source')
        start_date = args.get('start_date')
        end_date = args.get('end_date')
        if not plan_name:
            return

        # Topic-aware defaults come from PlanService when available.
        try:
            defaults = self.executor.plan_service._topic_defaults(plan_name)
        except Exception:
            defaults = {
                'project_title': f'{plan_name} Final Practical Demo',
                'objective': f'Complete a practical project aligned with the {plan_name} plan and document the outcome.',
                'tech_stack': plan_name,
                'scenario': f'A realistic work scenario aligned with {plan_name}.',
                'skills': plan_name,
                'deliverable': 'Working demo, notes, and final summary report.',
            }
        args.setdefault('main_title', defaults.get('project_title', ''))
        args.setdefault('objective', defaults.get('objective', ''))
        args.setdefault('tech_stack', defaults.get('tech_stack', ''))
        args.setdefault('scenario', defaults.get('scenario', ''))
        args.setdefault('skills', defaults.get('skills', ''))
        args.setdefault('deliverable', defaults.get('deliverable', ''))
        args.setdefault('final_project', args.get('main_title', ''))

        # Build a week-level preview from the selected plan and intern dates.
        try:
            data = parse_workbook(source)
            plan = self.executor.plan_service._find_plan(data, plan_name)
            if not plan:
                return
            start = datetime.fromisoformat(str(start_date))
            end = datetime.fromisoformat(str(end_date))
            week_dates = {}
            current = start
            workday = 0
            while current.date() <= end.date():
                if current.weekday() < 5:
                    workday += 1
                    week = ((workday - 1) // 5) + 1
                    week_dates.setdefault(week, []).append(current)
                current += timedelta(days=1)
            plan_rows = {}
            for row in plan.rows:
                try:
                    w = int(row[0])
                except Exception:
                    continue
                plan_rows[w] = row
            preview = []
            for week, dates in sorted(week_dates.items()):
                row = plan_rows.get(week, [])
                theme = row[1] if len(row) > 1 and row[1] else 'Learning Plan'
                task = row[2] if len(row) > 2 and row[2] else 'Task to be assigned'
                project = row[3] if len(row) > 3 and row[3] else f'Week {week}: Weekly Project'
                preview.append({
                    'week': week,
                    'date_range': f"{dates[0].strftime('%Y-%m-%d')} to {dates[-1].strftime('%Y-%m-%d')}",
                    'theme': theme,
                    'daily_task': task,
                    'weekly_project': project,
                })
            args['schedule_preview'] = preview
        except Exception:
            # Preview is helpful but should not block the proposal.
            return


    def _plan_quality_warnings(self, weeks: list, plan_name: str = '') -> list[str]:
        warnings = []
        if not isinstance(weeks, list) or not weeks:
            return ['No detailed weekly plan content was generated.']
        generic_phrases = ['task to be assigned', 'foundation and environment setup', 'core concepts', 'hands-on practice', 'final demo', 'llm returned no detailed weeks', 'generated safe draft']
        generic_count = 0
        short_count = 0
        for w in weeks:
            text = ' '.join(str(w.get(k, '')) for k in ['theme', 'task', 'weekly_project', 'notes'] if isinstance(w, dict)).lower()
            if any(p in text for p in generic_phrases):
                generic_count += 1
            if isinstance(w, dict) and (len(str(w.get('task', '')).strip()) < 25 or len(str(w.get('weekly_project', '')).strip()) < 15):
                short_count += 1
        if generic_count:
            warnings.append(f'{generic_count} week(s) look generic or fallback-based.')
        if short_count:
            warnings.append(f'{short_count} week(s) have very short task/project details.')
        return warnings

    def _summary(self, draft: ChatDraft) -> str:
        lines = [f'Proposal: **{COMMAND_LABELS.get(draft.command, draft.command)}**', '', 'I will execute this command after approval:', '']
        for k, v in draft.args.items():
            if k == 'quality_warnings' and isinstance(v, list) and v:
                lines.append('- quality warning: ' + '; '.join(str(x) for x in v))
            elif k == 'schedule_preview' and isinstance(v, list):
                lines.append(f'- schedule preview: {len(v)} week(s) generated from selected plan and intern dates')
                for item in v[:10]:
                    if isinstance(item, dict):
                        lines.append(f"  - Week {item.get('week')} ({item.get('date_range')}): {item.get('theme')} | {item.get('weekly_project')}")
            elif k == 'weeks' and isinstance(v, list):
                lines.append(f'- weeks: {len(v)} week(s) drafted')
                for item in v[:10]:
                    if isinstance(item, dict):
                        lines.append(f"  - Week {item.get('week')}: {item.get('theme')} | {item.get('weekly_project')}")
            else:
                lines.append(f'- {k}: {v}')
        lines.append('')
        lines.append('Approve this action?')
        return '\n'.join(lines)


    def _normalize_plan_name(self, plan_name: str, user_text: str = '') -> str:
        """Return a user-friendly plan name.

        This prevents generic names such as "LLM Generated Plan" from appearing
        in proposals or confirmation messages.
        """
        raw = (plan_name or '').strip()
        generic = {'', 'llm generated plan', 'generated plan', 'ai-drafted plan', 'custom plan', 'plan'}
        if raw.lower() not in generic:
            return raw
        inferred = self._extract_plan_name(user_text or '')
        if inferred:
            return inferred
        return 'Custom Learning Plan'


    def _explicit_plan_name_from_prompt(self, text: str) -> str | None:
        """Extract user-specified plan name with highest priority.

        Supports:
        - create an 8 week SecOps Foundation plan
        - create a plan called SecOps Foundation
        - add plan SecOps Foundation 8 weeks
        - make a plan 8 weeks AI engineering
        """
        text = text or ''
        normalized = re.sub(r'weesk|weks|wek', 'weeks', text, flags=re.I)

        # Strongest signal: called/named X.
        m = re.search(r'\b(?:called|named|plan called|plan named)\s+([A-Za-z0-9 ._+-]+?)(?:\.|,|$)', normalized, re.I)
        if m:
            return self._clean_plan_name_candidate(m.group(1))

        # Create an 8 week X plan.
        m = re.search(r'\b(?:create|make|draft|generate|build|add)\s+(?:an?|the)?\s*(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten)?\s*-?\s*(?:weeks?|week)?\s*([A-Za-z0-9 ._+-]+?)\s+plan\b', normalized, re.I)
        if m:
            candidate = self._clean_plan_name_candidate(m.group(1))
            if candidate:
                return candidate

        # Add/create/make a plan X 8 weeks.
        m = re.search(r'\b(?:add|create|make|draft|generate|build)\s+(?:an?|the)?\s*plan\s+([A-Za-z0-9 ._+-]+?)(?:\s+(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s*-?\s*weeks?|\.|,|$)', normalized, re.I)
        if m:
            candidate = self._clean_plan_name_candidate(m.group(1))
            if candidate:
                return candidate

        # Add/create/make a plan 8 weeks X.  <-- this is the bug fix.
        m = re.search(r'\b(?:add|create|make|draft|generate|build)\s+(?:an?|the)?\s*plan\s+(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s*-?\s*weeks?\s+([A-Za-z0-9 ._+-]+?)(?:\.|,|$)', normalized, re.I)
        if m:
            candidate = self._clean_plan_name_candidate(m.group(1))
            if candidate:
                return candidate

        # Create 8 week plan X. (duration comes before the word "plan",
        # topic comes after it - e.g. "create 8 week plan secops". None
        # of the patterns above cover this order: they expect either
        # "topic plan" or "plan [duration] topic", not "[duration] plan
        # topic". Without this, the name falls through entirely to the
        # LLM's own free-form choice, which won't reliably match the
        # canonical name used elsewhere (e.g. "SecOps Foundation").
        m = re.search(r'\b(?:create|make|draft|generate|build|add)\s+(?:an?|the)?\s*(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s*-?\s*weeks?\s+plan\s+([A-Za-z0-9 ._+-]+?)(?:\.|,|$)', normalized, re.I)
        if m:
            candidate = self._clean_plan_name_candidate(m.group(1))
            if candidate:
                return candidate

        return None


    def _clean_plan_name_candidate(self, value: str) -> str | None:
        value = (value or '').strip().rstrip('.')
        # Remove leading duration tokens accidentally captured as part of the plan name.
        # Examples: "8 Devops", "8 weeks Devops", "eight weeks AI Engineering".
        value = re.sub(r'^(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s*-?\s*(?:week|weeks)?\s+', '', value, flags=re.I).strip()
        # Strip a leading "for"/"to" too: "plan for beginners in cloud
        # computing" / "plan to learn github" otherwise capture "for
        # beginners..."/"to learn github" whole, since nothing marks where
        # the topic itself actually starts.
        value = re.sub(r'^(?:for|to)\s+', '', value, flags=re.I).strip()
        value = re.sub(r'\b(?:an?|the)\b', '', value, flags=re.I).strip()
        value = re.sub(r'\b(?:week|weeks)\b', '', value, flags=re.I).strip()
        value = re.sub(r'\s+', ' ', value).strip()
        # Generic filler words, not real topic names. Without this, "add a
        # new plan for secops ..." matches the "TOPIC plan" pattern with
        # "new" captured as the topic (it's the word directly before
        # "plan"), producing a plan literally named "New Foundation".
        if not value or value.lower() in {'plan', 'learning', 'custom', 'new', 'simple', 'basic'}:
            return None
        # The capturing regexes above have no reliable right-hand boundary
        # for free-form sentences, so a trailing clause like "... plan for
        # secops foundation but a bit different for adults" gets swallowed
        # whole as if it were the name. A real plan name is a couple of
        # words; past this length it's very likely runaway sentence text,
        # so bail out and let the caller fall back to the LLM's own name
        # instead of presenting a garbled multi-clause "name".
        if len(value.split()) > 5:
            return None
        compact = value.lower().replace(' ', '')
        aliases = {
            'aiengineering': 'AI Engineering Foundation',
            'aiengineer': 'AI Engineering Foundation',
            'secops': 'SecOps Foundation',
            'securityoperations': 'SecOps Foundation',
            'infosec': 'Information Security Foundation',
            'informationsecurity': 'Information Security Foundation',
            'cybersecurity': 'Information Security Foundation',
            'deeplearning': 'Deep Learning Foundation',
            'machinelearning': 'Machine Learning Foundation',
            'devops': 'DevOps Foundation',
            'devopsfoundation': 'DevOps Foundation',
            'openshift': 'OpenShift Foundation',
            'kubernetes': 'Kubernetes Foundation',
            'linux': 'Linux Foundation',
        }
        if compact in aliases:
            return aliases[compact]
        # If user said "SecOps Foundation", preserve it as title/name with acronym handling.
        words = []
        for part in value.split(' '):
            low = part.lower()
            if low == 'secops': words.append('SecOps')
            elif low == 'ai': words.append('AI')
            elif low == 'devops': words.append('DevOps')
            elif low in {'ai', 'ml', 'llm'}: words.append(low.upper())
            else: words.append(part[:1].upper() + part[1:])
        cleaned = ' '.join(words)
        return cleaned

    def _extract_plan_name(self, text: str) -> str | None:
        explicit_name = self._explicit_plan_name_from_prompt(text)
        if explicit_name:
            return explicit_name
        lower = text.lower()
        normalized_text = re.sub(r'weesk|weks|wek', 'weeks', text, flags=re.I)
        # Explicit forms: add plan secops 8 weeks, add plan 8 weeks secops
        m0 = re.search(r'\b(?:add|create|make|draft|generate|build)\s+plan\s+(.+)', normalized_text, re.I)
        if m0:
            topic = m0.group(1).strip().rstrip('.')
            topic = re.sub(r'\b(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s*-?\s*weeks?\b', '', topic, flags=re.I).strip()
            topic = re.sub(r'\bplan\b', '', topic, flags=re.I).strip()
            if topic:
                compact = topic.lower().replace(' ', '')
                if compact == 'secops': return 'SecOps Foundation'
                if compact == 'deeplearning': return 'Deep Learning Foundation'
                if 'infosec' in compact or 'cyber' in compact: return 'Information Security Foundation'
                return topic.title() + ' Foundation'
        if 'openshift' in lower:
            return 'OpenShift Foundation'
        if 'kubernetes' in lower or 'k8s' in lower:
            return 'Kubernetes Foundation'
        if 'devops' in lower or 'dev ops' in lower:
            return 'DevOps Foundation'
        if 'linux' in lower:
            return 'Linux Foundation'
        # Prefer explicit naming phrases only. Avoid treating "for beginner interns" as a plan name.
        m = re.search(r'(?:called|named|plan called|plan named)\s+([A-Za-z0-9 ._+-]+)', text, re.I)
        if m:
            return m.group(1).strip().rstrip('.')
        return None

    def _extract_weeks_count(self, text: str) -> int | None:
        normalized = re.sub(r'weesk|weks|wek', 'weeks', text.lower())
        m = re.search(r'(\d+)\s+weeks?', normalized)
        return int(m.group(1)) if m else None

    def _safe_name(self, value: str) -> str:
        return re.sub(r'[^A-Za-z0-9_-]+', '_', value).strip('_')[:40] or 'Plan'



    def _enrich_add_intern_with_plan(self, draft):
        """Draft a complete intern-sheet preview using the selected plan as context.

        This does not create the workbook. It only enriches the in-memory draft so
        the user can review/edit before approval.
        """
        args = draft.args
        required = ['source', 'name', 'start_date', 'end_date', 'plan_name']
        if any(not args.get(k) for k in required):
            return
        try:
            sheet = self.intern_sheet_drafter.draft(args.get('source'), args.get('name'), args.get('start_date'), args.get('end_date'), args.get('plan_name'))
        except Exception:
            return
        main = sheet.get('main_project') or {}
        scenario = sheet.get('scenario') or {}
        weeks = sheet.get('weeks') or []
        args['main_title'] = args.get('main_title') or main.get('title', '')
        args['objective'] = args.get('objective') or main.get('objective', '')
        args['tech_stack'] = args.get('tech_stack') or main.get('tech_stack', '')
        args['final_project'] = args.get('final_project') or args.get('main_title', '')
        args['scenario'] = args.get('scenario') or scenario.get('scenario', '')
        args['skills'] = args.get('skills') or scenario.get('skills', '')
        args['deliverable'] = args.get('deliverable') or scenario.get('deliverable', '')
        if weeks:
            args['schedule_preview'] = weeks

    def _is_valid_iso_date(self, value) -> bool:
        try:
            datetime.strptime(str(value).strip(), '%Y-%m-%d')
            return True
        except (TypeError, ValueError):
            return False

    def _looks_like_bare_date(self, value: str) -> bool:
        """True if the whole string is basically just a date, nothing else.

        Deliberately doesn't use the LLM-fallback branch of _first_date -
        this only needs the cheap deterministic check, and is called on
        every candidate field value, not just ones already suspected of
        being a date.
        """
        v = (value or '').strip()
        if not v:
            return False
        if re.fullmatch(r'20\d{2}-\d{2}-\d{2}', v):
            return True
        m = self._NATURAL_DATE_RE.fullmatch(v)
        return bool(m)

    def _is_grounded(self, value, text: str) -> bool:
        """True if value plausibly came from the user's own words."""
        v = str(value).strip().lower()
        if not v:
            return False
        return v in (text or '').lower()

    def _wants_no_plan(self, text: str) -> bool:
        lower = (text or '').strip().lower()
        if lower in {'no', 'none', 'no plan', 'skip', 'no thanks'}:
            return True
        return any(p in lower for p in ['no plan', 'without a plan', 'without plan', 'skip plan', 'just placeholder', 'placeholder only'])

    def _clean_name(self, value: str) -> str:
        value = (value or '').strip().strip(' .,:;')
        value = re.sub(r'^(of|for|intern|the intern)\s+', '', value, flags=re.I).strip()
        # "extend intern jameel with this plan" (no "to DATE" boundary to
        # stop at) otherwise swallows the trailing plan-reference clause
        # whole, producing an intern named "Jameel With This Plan". "with"
        # essentially never legitimately appears inside a person's name in
        # this app's phrasing conventions, so cut there.
        value = re.sub(r'\s+with\s+.*$', '', value, flags=re.I).strip()
        if not value:
            return value
        parts = []
        for p in value.split():
            low = p.lower()
            if low == 'ai':
                parts.append('AI')
            elif low == 'ml':
                parts.append('ML')
            elif low == 'llm':
                parts.append('LLM')
            elif low == 'devops':
                parts.append('DevOps')
            elif low == 'secops':
                parts.append('SecOps')
            else:
                parts.append(p[:1].upper() + p[1:])
        return ' '.join(parts)

    # Matches "14th July 2026", "July 14, 2026", "14 July 2026", etc. -
    # deliberately requires an explicit 4-digit year and a real month name
    # right next to a day number, rather than handing arbitrary substrings
    # to dateutil, which would happily misparse unrelated text as a date.
    _NATURAL_DATE_RE = re.compile(
        r'\b(?:(\d{1,2})(?:st|nd|rd|th)?\s+(?:of\s+)?([A-Za-z]+)|([A-Za-z]+)\s+(\d{1,2})(?:st|nd|rd|th)?)\s*,?\s+(\d{4})\b'
    )

    # Cheap pre-filter before spending an LLM call in _first_date's
    # fallback: only bother asking the model if the text plausibly
    # contains a date at all (a year, an ordinal day, or a month name),
    # so a message like "extend intern Asad" (genuinely no date) doesn't
    # trigger an API call every time.
    _DATE_HINT_RE = re.compile(
        r'\b(?:19|20)\d{2}\b|\d{1,2}(?:st|nd|rd|th)\b'
        r'|\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\b',
        re.I,
    )

    def _first_date(self, text: str):
        """Return the first date found in text, normalized to yyyy-mm-dd.

        Understands literal ISO dates and common natural-language forms
        ("14th July 2026") via regex+dateutil first (instant, free) -
        deterministic pre-check builders like _extend_intern_draft run
        before the LLM ever sees the message, so without this, any
        non-ISO date in "extend"/"capstone"/"scenario" phrasing was
        silently dropped rather than parsed. Falls back to an LLM call
        only for phrasing unusual enough that the regex genuinely can't
        make sense of it, since normalizing "some date next Tuesday
        after the sprint" isn't something a fixed pattern can cover.
        """
        text = text or ''
        m = re.search(r'20\d{2}-\d{2}-\d{2}', text)
        if m:
            return m.group(0)
        if _date_parser:
            m = self._NATURAL_DATE_RE.search(text)
            if m:
                try:
                    dt = _date_parser.parse(m.group(0), fuzzy=False)
                    return dt.strftime('%Y-%m-%d')
                except (ValueError, OverflowError):
                    pass
        if self.provider and self._DATE_HINT_RE.search(text):
            return self._llm_extract_date(text)
        return None

    def _find_all_dates(self, text: str) -> list[str]:
        """Like _first_date but returns every date found, in order.

        Used where position matters (e.g. first date = start_date, second
        = end_date). Deliberately has no LLM fallback (unlike _first_date)
        - it's called on every reply while filling a draft's missing
        fields, not just ones already believed to contain a date, so an
        API call here would fire far too often.
        """
        text = text or ''
        results = [m.group(0) for m in re.finditer(r'20\d{2}-\d{2}-\d{2}', text)]
        if results or not _date_parser:
            return results
        for m in self._NATURAL_DATE_RE.finditer(text):
            try:
                dt = _date_parser.parse(m.group(0), fuzzy=False)
                results.append(dt.strftime('%Y-%m-%d'))
            except (ValueError, OverflowError):
                continue
        return results

    def _llm_extract_date(self, text: str):
        prompt = f"""Find the single calendar date mentioned in this message, in any format or phrasing, and normalize it to ISO format.

Message:
{text}

Return ONLY this JSON shape, nothing else:
{{"date": "yyyy-mm-dd"}}

If no real calendar date is mentioned, return: {{"date": null}}
"""
        try:
            data = self.provider.complete_json(prompt)
            value = (data or {}).get('date')
        except Exception:
            return None
        return value if self._is_valid_iso_date(value) else None

    def _stamped_output(self, command: str) -> str:
        return f'{command}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'

    def _edit_plan_draft(self, text: str, current_workbook: str | None):
        lower = text.lower()
        if not any(x in lower for x in ['rename plan', 'edit plan', 'update plan', 'change plan']):
            return None
        if 'week' in lower:
            return None
        args = {}
        if current_workbook:
            args['source'] = current_workbook
        m = re.search(r'(?:rename|change)\s+plan\s+(.+?)\s+to\s+(.+)$', text, re.I)
        if m:
            args['plan_name'] = self._clean_name(m.group(1))
            args['new_name'] = self._clean_name(m.group(2))
        else:
            m = re.search(r'(?:edit|update|change)\s+plan\s+(.+?)\s+description\s+(?:to|as)\s+(.+)$', text, re.I)
            if m:
                args['plan_name'] = self._clean_name(m.group(1))
                args['description'] = m.group(2).strip()
            else:
                m = re.search(r'(?:edit|update)\s+plan\s+(.+)$', text, re.I)
                if m:
                    args['plan_name'] = self._clean_name(m.group(1))
        args.setdefault('output', self._stamped_output('edit_plan'))
        return ChatDraft(str(uuid.uuid4()), 'edit_plan', args)

    def _extend_intern_draft(self, text: str, current_workbook: str | None):
        lower = text.lower()
        if not ('extend' in lower or 'end date' in lower or 'new end' in lower):
            return None
        args = {}
        if current_workbook:
            args['source'] = current_workbook
        date = self._first_date(text)
        if date:
            args['new_end'] = date
        # Name capture is deliberately decoupled from the date's literal
        # format (date itself is already resolved above via _first_date,
        # which understands natural-language dates) - anchoring this on a
        # literal ISO span here would silently drop the name whenever the
        # date was written as "5th September 2026" instead.
        m = re.search(r'extend\s+(?:intern\s+)?(.+?)\s+(?:to|until)\b', text, re.I)
        if not m:
            m = re.search(r'(?:change|update|set)\s+(?:intern\s+)?(.+?)\s+(?:end date|new end)\s+(?:to|as)\b', text, re.I)
        if not m:
            # No date in this message at all (e.g. "extend intern Asad") -
            # still capture the name so the user isn't asked to repeat it.
            m = re.search(r'extend\s+(?:intern\s+)?([A-Za-z][\w.\'-]*(?:\s+[A-Za-z][\w.\'-]*){0,3})\s*$', text, re.I)
        if m:
            candidate = self._clean_name(m.group(1))
            # "extend intern" alone (no name after it) leaves the optional
            # "intern " prefix in the fallback pattern above with nothing
            # to consume, so the capture group grabs the bare word "intern"
            # itself - guard against treating that as a real name.
            if candidate.strip().lower() not in {'intern', 'the intern', 'an intern', 'a intern'}:
                args['intern'] = candidate

        # A bare "extend" request doesn't say whether the new period should
        # follow a specific plan. Default to asking (via the ordinary
        # missing-field flow, since plan_name is required for this command)
        # unless the user has already opted out of plan content.
        if self._wants_no_plan(text):
            args.setdefault('output', self._stamped_output('extend_intern'))
            return ChatDraft(str(uuid.uuid4()), 'extend_intern', args)
        args.setdefault('output', self._stamped_output('extend_intern_with_plan'))
        return ChatDraft(str(uuid.uuid4()), 'extend_intern_with_plan', args)

    def _capstone_draft(self, text: str, current_workbook: str | None):
        lower = text.lower()
        if not any(x in lower for x in ['main project', 'capstone']):
            return None
        args = {}
        if current_workbook:
            args['source'] = current_workbook

        # update main project of Saleem to Agentic AI platform
        # (tolerates an optional leading "the" - "update the main project
        # for Saleem to ..." - which would otherwise break the literal
        # "update <keyword>" match and fall through to the wrong branch)
        m = re.search(r'(?:update|edit|change|set)\s+(?:the\s+)?(?:main project|capstone)\s+(?:of|for)\s+(.+?)\s+(?:to|as)\s+(.+)$', text, re.I)
        if m:
            args['intern'] = self._clean_name(m.group(1))
            args['title'] = m.group(2).strip()
        else:
            # update Saleem main project to Agentic AI platform
            m = re.search(r'(?:update|edit|change|set)\s+(?:intern\s+)?(.+?)\s+(?:main project|capstone)\s+(?:to|as)\s+(.+)$', text, re.I)
            if m:
                args['intern'] = self._clean_name(m.group(1))
                args['title'] = m.group(2).strip()
            else:
                m = re.search(r'(?:update|edit|change)\s+(?:intern\s+)?(.+?)\s+(?:main project|capstone)', text, re.I)
                if m:
                    args['intern'] = self._clean_name(m.group(1))

        obj = re.search(r'objective\s+(?:to|as)\s+(.+?)(?:\s+tech stack|\s+status|$)', text, re.I)
        if obj:
            args['objective'] = obj.group(1).strip()
        tech = re.search(r'tech stack\s+(?:to|as)\s+(.+?)(?:\s+status|$)', text, re.I)
        if tech:
            args['tech_stack'] = tech.group(1).strip()
        status = re.search(r'\b(pending|in progress|completed)\b', lower)
        if status:
            args['status'] = {'pending': 'Pending', 'in progress': 'In Progress', 'completed': 'Completed'}[status.group(1)]
        target_end = self._first_date(text)
        if target_end:
            args['target_end'] = target_end
        args.setdefault('output', self._stamped_output('update_capstone'))
        return ChatDraft(str(uuid.uuid4()), 'update_capstone', args)

    def _scenario_draft(self, text: str, current_workbook: str | None):
        lower = text.lower()
        if not any(x in lower for x in ['real-world scenario', 'real world scenario', 'scenario', 'scenrio']):
            return None
        args = {}
        if current_workbook:
            args['source'] = current_workbook

        # update scenario of Saleem to something new
        # (tolerates an optional leading "the" - "update the real-world
        # scenario for Saleem to ..." - which would otherwise break the
        # literal "update <keyword>" match and fall through to a branch
        # that mis-captures "the" itself as the intern's name)
        m = re.search(r'(?:update|edit|change|set)\s+(?:the\s+)?(?:real-world scenario|real world scenario|scenario|scenrio)\s+(?:of|for)\s+(.+?)\s+(?:to|as)\s+(.+)$', text, re.I)
        if m:
            args['intern'] = self._clean_name(m.group(1))
            args['scenario'] = m.group(2).strip()
        else:
            # update Saleem scenario to something new
            m = re.search(r'(?:update|edit|change|set)\s+(?:intern\s+)?(.+?)\s+(?:real-world scenario|real world scenario|scenario|scenrio)\s+(?:to|as)\s+(.+)$', text, re.I)
            if m:
                args['intern'] = self._clean_name(m.group(1))
                args['scenario'] = m.group(2).strip()
            else:
                m = re.search(r'(?:update|edit|change)\s+(?:intern\s+)?(.+?)\s+(?:real-world scenario|real world scenario|scenario|scenrio)', text, re.I)
                if m:
                    args['intern'] = self._clean_name(m.group(1))

        skills = re.search(r'skills\s+(?:to|as)\s+(.+?)(?:\s+deliverable|\s+due date|\s+status|$)', text, re.I)
        if skills:
            args['skills'] = skills.group(1).strip()
        deliverable = re.search(r'deliverable\s+(?:to|as)\s+(.+?)(?:\s+due date|\s+status|$)', text, re.I)
        if deliverable:
            args['deliverable'] = deliverable.group(1).strip()
        week = re.search(r'week\s+(\d+)', lower)
        if week:
            args['assigned_week'] = int(week.group(1))
        due = self._first_date(text)
        if due:
            args['due_date'] = due
        status = re.search(r'\b(pending|in progress|completed)\b', lower)
        if status:
            args['status'] = {'pending': 'Pending', 'in progress': 'In Progress', 'completed': 'Completed'}[status.group(1)]
        args.setdefault('output', self._stamped_output('update_scenario'))
        return ChatDraft(str(uuid.uuid4()), 'update_scenario', args)

    def _required_four_draft(self, text: str, current_workbook: str | None):
        lower = (text or '').lower()
        # "add/create/new intern ..." always means creating a new intern,
        # even if the message also mentions "main project" or "scenario"
        # to describe that new intern's details (e.g. "add intern Sara
        # ... main project should be building a SIEM dashboard"). None of
        # these four builders edit an intern that doesn't exist yet, so
        # they must not claim a message that's actually an add-intern
        # request just because it shares a keyword.
        if any(p in lower for p in ['add intern', 'create intern', 'new intern']):
            return None
        for builder in [self._edit_plan_draft, self._extend_intern_draft, self._capstone_draft, self._scenario_draft]:
            draft = builder(text, current_workbook)
            if draft:
                return draft
        return None

    def _extend_with_plan_draft(self, text: str, current_workbook: str | None):
        lower = (text or '').lower()
        # Plan-aware extension if user says: extend X to DATE with PLAN_NAME
        # The word "plan" is optional because users often say "with SecOps Foundation".
        if 'extend' not in lower or 'with' not in lower:
            return None
        new_end = self._first_date(text)
        if not new_end:
            return None
        args = {}
        if current_workbook:
            args['source'] = current_workbook
        args['new_end'] = new_end

        # Extend Habeeb to 2026-09-30 with Kubernetes Troubleshooting plan
        # Extend Habeeb to 5th September 2026 with SecOps Foundation
        # (name/plan capture doesn't anchor on the date's literal format -
        # date is already resolved above via _first_date, which handles
        # natural-language dates too.)
        m = re.search(r'extend\s+(?:intern\s+)?(.+?)\s+(?:to|until)\s+.+?\s+with\s+(.+?)(?:\s+plan)?$', text, re.I)
        if m:
            args['intern'] = self._clean_name(m.group(1))
            plan = m.group(2).strip().strip(' .,:;')
            if 'foundation' not in plan.lower() and 'plan' not in plan.lower():
                plan = plan[:1].upper() + plan[1:] + ' Foundation'
            args['plan_name'] = plan
        args['output'] = self._stamped_output('extend_intern_with_plan')

        if args.get('intern') and args.get('plan_name'):
            args['extension_preview'] = f"Extend {args['intern']} to {args['new_end']} using {args['plan_name']}. This will generate new extension-period daily tasks, weekly projects, and update the main project/scenario to the extension focus."
        return ChatDraft(str(uuid.uuid4()), 'extend_intern_with_plan', args)

    def _clean_llm_text(self, value) -> str:
        s = str(value or "")
        s = html.unescape(s)
        s = re.sub(r'<br\s*/?>', '\n', s, flags=re.I)
        s = re.sub(r'</?(strong|b|em|i|span|p|div)[^>]*>', '', s, flags=re.I)
        s = re.sub(r'data-lexical-text="true"', '', s, flags=re.I)
        s = re.sub(r'<[^>]+>', '', s)
        s = re.sub(r'\s+\n', '\n', s)
        s = re.sub(r'\n\s+', '\n', s)
        s = re.sub(r'[ \t]+', ' ', s)
        return s.strip()

    def _normalize_llm_plan_payload(self, data) -> dict:
        """Accept both top-level plan JSON and command/args JSON."""
        if not isinstance(data, dict):
            return {}
        # Preferred shape because provider SYSTEM_PROMPT asks for it.
        if isinstance(data.get("args"), dict):
            return dict(data.get("args") or {})
        return dict(data)

    def _clean_plan_weeks(self, raw_weeks, expected_count) -> list:
        if not isinstance(raw_weeks, list):
            return []
        cleaned = []
        for idx, item in enumerate(raw_weeks, start=1):
            if not isinstance(item, dict):
                continue
            week_no = item.get("week") or idx
            try:
                week_no = int(week_no)
            except Exception:
                week_no = idx
            theme = self._clean_llm_text(item.get("theme"))
            task = self._clean_llm_text(item.get("task") or item.get("daily_task"))
            weekly_project = self._clean_llm_text(item.get("weekly_project") or item.get("project"))
            notes = self._clean_llm_text(item.get("notes"))
            # Skip totally empty rows.
            if not any([theme, task, weekly_project, notes]):
                continue
            cleaned.append({
                "week": week_no,
                "theme": theme or f"Week {week_no} Focus",
                "task": task or "Complete practical learning tasks for this week.",
                "weekly_project": weekly_project or "Complete a weekly practical project.",
                "notes": notes,
            })
        # Keep expected week limit if the model returned too many.
        if expected_count and len(cleaned) > expected_count:
            cleaned = cleaned[:expected_count]
        return cleaned

    def _plan_weeks_look_usable(self, weeks) -> bool:
        if not isinstance(weeks, list) or not weeks:
            return False
        bad_markers = [
            "llm returned no detailed weeks",
            "generated safe draft",
            "foundation and environment setup",
            "core concepts",
            "hands-on practice",
            "final demo",
        ]
        usable = 0
        for w in weeks:
            if not isinstance(w, dict):
                continue
            text = " ".join(str(w.get(k, "")) for k in ("theme", "task", "weekly_project", "notes")).lower()
            if any(marker in text for marker in bad_markers):
                continue
            if len(str(w.get("task", "")).strip()) >= 30 and len(str(w.get("weekly_project", "")).strip()) >= 20:
                usable += 1
        return usable >= max(1, min(3, len(weeks)))

    def _build_plan_prompt(self, user_text, weeks_count) -> str:
        return f"""
Create a practical intern learning plan from this request:

{user_text}

Return ONLY valid JSON in this exact shape:
{{
  "command": "create_plan_from_draft",
  "args": {{
    "plan_name": "short clear plan name",
    "description": "one sentence description",
    "weeks": [
      {{
        "week": 1,
        "theme": "specific weekly theme",
        "task": "specific daily-learning task description for this week",
        "weekly_project": "specific weekly practical project",
        "notes": "short practical guidance"
      }}
    ]
  }}
}}

Rules:
- Create exactly {weeks_count} weeks unless the user clearly asked otherwise.
- Each week must be specific to the requested topic.
- Do not return generic placeholder weeks.
- Do not include HTML tags.
- Do not include markdown.
- Do not include <strong>, <br>, or data-lexical-text.
- Do not invent source, output, or workbook paths.
- plan_name should be a short, properly spelled, professional plan title
  reflecting the requested topic - correct any obvious typos in how the
  user wrote the topic (e.g. "Leanr Github" -> "Learn GitHub"), and do not
  echo filler words like "to"/"for"/"a new plan" from their phrasing.
"""

    def _draft_plan_with_llm(self, text: str, current_workbook: str | None) -> ChatDraft:
        fallback_name = self._extract_plan_name(text) or "Custom Learning Plan"
        fallback_name = self._normalize_plan_name(fallback_name, text)
        weeks_count = self._extract_weeks_count(text) or 8
        source = current_workbook or ""
        output = f"Plan_{self._safe_name(fallback_name)}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"

        plan_name = fallback_name
        description = self._clean_llm_text(text)
        weeks = []
        generation_error = ""

        if self.provider:
            for attempt in range(2):
                try:
                    prompt = self._build_plan_prompt(text, weeks_count)
                    if attempt == 1:
                        prompt += """

Your previous response was not usable. Try again.
Make sure weeks is inside args.weeks and contains detailed topic-specific week objects.
"""
                    raw = self.provider.complete_json(prompt)
                    args = self._normalize_llm_plan_payload(raw)

                    # Trust the LLM's own plan name over the regex-extracted
                    # one now that the model is reliable enough to name
                    # things sensibly (and can fix a typo like "Leanr" ->
                    # "Learn" that regex extraction never could). The regex
                    # name is only used as a fallback, when the LLM didn't
                    # return a usable one at all - see fallback_name above.
                    candidate_name = self._clean_llm_text(args.get("plan_name")) or fallback_name
                    candidate_name = self._normalize_plan_name(candidate_name, text)

                    candidate_description = self._clean_llm_text(args.get("description")) or description
                    candidate_weeks = self._clean_plan_weeks(args.get("weeks"), weeks_count)

                    if self._plan_weeks_look_usable(candidate_weeks):
                        plan_name = candidate_name
                        description = candidate_description
                        weeks = candidate_weeks
                        break

                    generation_error = "LLM returned no usable detailed weeks."

                except Exception as e:
                    generation_error = str(e)

        # If LLM still fails, do NOT silently present generic fallback as a good draft.
        # Keep deterministic fallback, but make warning clear so user should not approve blindly.
        if not weeks:
            weeks = self._fallback_weeks(
                plan_name,
                weeks_count,
                "Plan generation fallback used because LLM did not return detailed topic-specific weeks. Regenerate or edit before approval."
            )

        # Final cleanup safety.
        plan_name = self._clean_llm_text(plan_name) or fallback_name
        description = self._clean_llm_text(description)
        weeks = self._clean_plan_weeks(weeks, weeks_count)

        warnings = self._plan_quality_warnings(weeks, plan_name)
        if generation_error:
            warnings.append(f"LLM generation issue: {generation_error}")
        if any("fallback" in str(w.get("notes", "")).lower() for w in weeks if isinstance(w, dict)):
            warnings.append("This draft used fallback content. Review or regenerate before approval.")

        return ChatDraft(str(uuid.uuid4()), "create_plan_from_draft", {
            "source": source,
            "plan_name": plan_name,
            "description": description,
            "weeks": weeks,
            "quality_warnings": warnings,
            "output": output,
        })

