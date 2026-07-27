
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import json
import re
import uuid
from typing import Any

from tracker_commands.executor import CommandExecutor
from tracker_chat.intern_sheet_drafter import InternSheetDrafter
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
        # Try LLM field extraction for the active draft first. This avoids brittle
        # issues such as lowercase names. Regex below remains fallback.
        parsed = self.intent_parser.parse(text, active_command=draft.command)
        if parsed and parsed.get('command') == draft.command:
            for k, v in (parsed.get('args') or {}).items():
                if v not in [None, '', []]:
                    draft.args[k] = v
            self._force_enrich_ready_add_intern_with_plan(draft)
        return self._response_for_draft(draft)
        lower = text.lower()
        args = draft.args

        # Common field extractions.
        dates = re.findall(r'20\d{2}-\d{2}-\d{2}', text)
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
        elif draft.command in ['extend_intern','edit_task','update_task_status','update_capstone','update_scenario','edit_project','update_project_status']:
            m = re.search(r'(?:intern name is|intern is|intern|for)\s+([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){0,3})', text)
            if m: args['intern'] = m.group(1).strip()
            if draft.command == 'extend_intern' and dates: args['new_end'] = dates[-1]
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

    def _draft_plan_with_llm(self, text: str, current_workbook: str | None) -> ChatDraft:
        fallback_name = self._extract_plan_name(text) or 'Custom Learning Plan'
        fallback_name = self._normalize_plan_name(fallback_name, text)
        weeks_count = self._extract_weeks_count(text) or 8
        source = current_workbook or ''
        output = f"Plan_{self._safe_name(fallback_name)}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        if self.provider:
            try:
                prompt = f"""
Create a practical intern learning plan from this request:
{text}

Return ONLY JSON with this exact shape:
{{
  "plan_name": "short plan name",
  "description": "one sentence description",
  "weeks": [
    {{"week": 1, "theme": "...", "task": "...", "weekly_project": "...", "notes": "..."}}
  ]
}}
Rules:
- Create {weeks_count} weeks unless user clearly asked otherwise.
- Intern plan should be practical, beginner-friendly if level is unclear.
- Do not include markdown.
"""
                data = self.provider.complete_json(prompt)
                plan_name = data.get('plan_name') or fallback_name
                plan_name = self._normalize_plan_name(plan_name, text)
                explicit_prompt_name = self._explicit_plan_name_from_prompt(text)
                if explicit_prompt_name:
                    plan_name = explicit_prompt_name
                description = data.get('description') or text
                weeks = data.get('weeks') or []
                if not isinstance(weeks, list) or not weeks:
                    weeks = self._fallback_weeks(plan_name, weeks_count, 'LLM returned no detailed weeks; generated safe draft.')
                lower_text = text.lower()
                if 'openshift' in lower_text and 'openshift' not in plan_name.lower():
                    plan_name = 'OpenShift Foundation'
                    weeks = self._fallback_weeks(plan_name, weeks_count, 'Adjusted to OpenShift based on user request.')
                if ('infosec' in lower_text or 'information security' in lower_text or 'cybersecurity' in lower_text or 'cyber security' in lower_text) and all(x not in plan_name.lower() for x in ['security', 'infosec', 'cyber']):
                    plan_name = 'Information Security Foundation'
                    weeks = self._fallback_weeks(plan_name, weeks_count, 'Adjusted to Information Security based on user request.')
                if ('deep learning' in lower_text or 'deeplearning' in lower_text) and 'deep learning' not in plan_name.lower():
                    plan_name = 'Deep Learning Foundation'
                    weeks = self._fallback_weeks(plan_name, weeks_count, 'Adjusted to Deep Learning based on user request.')
                return ChatDraft(str(uuid.uuid4()), 'create_plan_from_draft', {
                    'source': source,
                    'plan_name': plan_name,
                    'description': description,
                    'weeks': weeks,
                    'quality_warnings': self._plan_quality_warnings(weeks, plan_name),
                    'output': output,
                })
            except Exception as e:
                # Fall back to deterministic draft but expose the error in notes.
                weeks = self._fallback_weeks(fallback_name, weeks_count, f'LLM draft failed: {e}')
        else:
            weeks = self._fallback_weeks(fallback_name, weeks_count, '')
        fallback_name = self._normalize_plan_name(fallback_name, text)
        return ChatDraft(str(uuid.uuid4()), 'create_plan_from_draft', {
            'source': source,
            'plan_name': fallback_name,
            'description': text,
            'weeks': weeks,
            'output': output,
        })

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
        args = parsed.get('args') or {}
        # Inject current workbook defaults. The LLM must not invent source/output paths.
        if current_workbook:
            if command == 'summary':
                args.setdefault('workbook', current_workbook)
            elif command != 'create_workbook':
                args.setdefault('source', current_workbook)
        self._defaults(command, args)
        if command == 'add_holiday':
            self._normalize_holiday_args_v49(text, args)
        return ChatDraft(str(uuid.uuid4()), command, args)


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
        return ChatDraft(str(uuid.uuid4()), command, args)

    def _detect_command(self, lower: str) -> str:
        if 'clean' in lower or 'render' in lower: return 'render_workbook'
        if 'summary' in lower or 'progress' in lower or 'report' in lower: return 'summary'
        if 'holiday' in lower or 'holidat' in lower: return 'add_holiday'
        if 'extend' in lower: return 'extend_intern'
        if 'task status' in lower or ('mark' in lower and 'task' in lower): return 'update_task_status'
        if 'edit task' in lower or ('change' in lower and 'task' in lower): return 'edit_task'
        if 'capstone' in lower or 'main project' in lower: return 'update_capstone'
        if 'scenario' in lower: return 'update_scenario'
        if 'project status' in lower: return 'update_project_status'
        if 'edit project' in lower or 'weekly project' in lower or 'small project' in lower: return 'edit_project'
        if 'json' in lower and 'intern' in lower: return 'add_intern'
        # User-facing intern creation should always be plan-based.
        # If plan_name is missing, the draft asks for it instead of creating placeholders.
        if 'add intern' in lower or 'create intern' in lower or 'new intern' in lower: return 'add_intern_with_plan'
        if 'apply plan' in lower or ('apply' in lower and 'plan' in lower): return 'apply_plan_to_intern'
        if 'edit plan week' in lower or ('week' in lower and 'plan' in lower and 'edit' in lower): return 'edit_plan_week'
        if 'edit plan' in lower or 'rename plan' in lower: return 'edit_plan'
        if 'fresh workbook' in lower or 'blank workbook' in lower or 'create workbook' in lower: return 'create_workbook'
        return 'summary'

    def _extract_common(self, text: str, lower: str, command: str, args: dict):
        dates = re.findall(r'20\d{2}-\d{2}-\d{2}', text)
        if command == 'extend_intern' and dates: args['new_end'] = dates[-1]
        if command == 'add_holiday' and dates: args['date'] = dates[-1]
        if command in ['add_intern_basic','add_intern_with_plan']:
            if len(dates) >= 1: args['start_date'] = dates[0]
            if len(dates) >= 2: args['end_date'] = dates[1]
        if command in ['edit_task','update_task_status'] and dates: args['task_ref'] = dates[0]
        m = re.search(r'(?:intern|for|named|name)\s+([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){0,3})', text)
        if m and command in ['extend_intern','edit_task','update_task_status','update_capstone','update_scenario','edit_project','update_project_status','apply_plan_to_intern']:
            args['intern'] = m.group(1).strip()
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

        return None


    def _clean_plan_name_candidate(self, value: str) -> str | None:
        value = (value or '').strip().rstrip('.')
        # Remove leading duration tokens accidentally captured as part of the plan name.
        # Examples: "8 Devops", "8 weeks Devops", "eight weeks AI Engineering".
        value = re.sub(r'^(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s*-?\s*(?:week|weeks)?\s+', '', value, flags=re.I).strip()
        value = re.sub(r'\b(?:an?|the)\b', '', value, flags=re.I).strip()
        value = re.sub(r'\b(?:week|weeks)\b', '', value, flags=re.I).strip()
        value = re.sub(r'\s+', ' ', value).strip()
        if not value or value.lower() in {'plan', 'learning', 'custom'}:
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
        if 'foundation' not in cleaned.lower() and 'plan' not in cleaned.lower():
            cleaned += ' Foundation'
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


# v38 override: LLM intern sheet draft from plan context
# This intentionally overrides older enrichment logic. Add Intern With Plan now uses
# the selected plan as context to produce a complete editable intern-sheet draft.
def _v38_enrich_add_intern_with_plan(self, draft):
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

ChatService._enrich_add_intern_with_plan = _v38_enrich_add_intern_with_plan


# v0.48 repaired required-four chat workflow override
# One clean safe override. Do not re-apply v45/v46/v47 after this.
if not hasattr(ChatService, '_base_message_v48'):
    ChatService._base_message_v48 = ChatService.message


def _v48_clean_name(value: str) -> str:
    value = (value or '').strip().strip(' .,:;')
    value = re.sub(r'^(of|for|intern|the intern)\s+', '', value, flags=re.I).strip()
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


def _v48_first_date(text: str):
    m = re.search(r'20\d{2}-\d{2}-\d{2}', text or '')
    return m.group(0) if m else None


def _v48_output(command: str):
    return f'{command}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'


def _v48_edit_plan_draft(self, text: str, current_workbook: str | None):
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
        args['plan_name'] = _v48_clean_name(m.group(1))
        args['new_name'] = _v48_clean_name(m.group(2))
    else:
        m = re.search(r'(?:edit|update|change)\s+plan\s+(.+?)\s+description\s+(?:to|as)\s+(.+)$', text, re.I)
        if m:
            args['plan_name'] = _v48_clean_name(m.group(1))
            args['description'] = m.group(2).strip()
        else:
            m = re.search(r'(?:edit|update)\s+plan\s+(.+)$', text, re.I)
            if m:
                args['plan_name'] = _v48_clean_name(m.group(1))
    args.setdefault('output', _v48_output('edit_plan'))
    return ChatDraft(str(uuid.uuid4()), 'edit_plan', args)


def _v48_extend_intern_draft(self, text: str, current_workbook: str | None):
    lower = text.lower()
    if not ('extend' in lower or 'end date' in lower or 'new end' in lower):
        return None
    args = {}
    if current_workbook:
        args['source'] = current_workbook
    date = _v48_first_date(text)
    if date:
        args['new_end'] = date
    m = re.search(r'extend\s+(?:intern\s+)?(.+?)\s+(?:to|until)\s+20\d{2}-\d{2}-\d{2}', text, re.I)
    if not m:
        m = re.search(r'(?:change|update|set)\s+(?:intern\s+)?(.+?)\s+(?:end date|new end)\s+(?:to|as)\s+20\d{2}-\d{2}-\d{2}', text, re.I)
    if m:
        args['intern'] = _v48_clean_name(m.group(1))
    args.setdefault('output', _v48_output('extend_intern'))
    return ChatDraft(str(uuid.uuid4()), 'extend_intern', args)


def _v48_capstone_draft(self, text: str, current_workbook: str | None):
    lower = text.lower()
    if not any(x in lower for x in ['main project', 'capstone']):
        return None
    args = {}
    if current_workbook:
        args['source'] = current_workbook

    # update main project of Saleem to Agentic AI platform
    m = re.search(r'(?:update|edit|change|set)\s+(?:main project|capstone)\s+(?:of|for)\s+(.+?)\s+(?:to|as)\s+(.+)$', text, re.I)
    if m:
        args['intern'] = _v48_clean_name(m.group(1))
        args['title'] = m.group(2).strip()
    else:
        # update Saleem main project to Agentic AI platform
        m = re.search(r'(?:update|edit|change|set)\s+(?:intern\s+)?(.+?)\s+(?:main project|capstone)\s+(?:to|as)\s+(.+)$', text, re.I)
        if m:
            args['intern'] = _v48_clean_name(m.group(1))
            args['title'] = m.group(2).strip()
        else:
            m = re.search(r'(?:update|edit|change)\s+(?:intern\s+)?(.+?)\s+(?:main project|capstone)', text, re.I)
            if m:
                args['intern'] = _v48_clean_name(m.group(1))

    obj = re.search(r'objective\s+(?:to|as)\s+(.+?)(?:\s+tech stack|\s+status|$)', text, re.I)
    if obj:
        args['objective'] = obj.group(1).strip()
    tech = re.search(r'tech stack\s+(?:to|as)\s+(.+?)(?:\s+status|$)', text, re.I)
    if tech:
        args['tech_stack'] = tech.group(1).strip()
    status = re.search(r'\b(pending|in progress|completed)\b', lower)
    if status:
        args['status'] = {'pending': 'Pending', 'in progress': 'In Progress', 'completed': 'Completed'}[status.group(1)]
    target_end = _v48_first_date(text)
    if target_end:
        args['target_end'] = target_end
    args.setdefault('output', _v48_output('update_capstone'))
    return ChatDraft(str(uuid.uuid4()), 'update_capstone', args)


def _v48_scenario_draft(self, text: str, current_workbook: str | None):
    lower = text.lower()
    if not any(x in lower for x in ['real-world scenario', 'real world scenario', 'scenario', 'scenrio']):
        return None
    args = {}
    if current_workbook:
        args['source'] = current_workbook

    # update scenario of Saleem to something new
    m = re.search(r'(?:update|edit|change|set)\s+(?:real-world scenario|real world scenario|scenario|scenrio)\s+(?:of|for)\s+(.+?)\s+(?:to|as)\s+(.+)$', text, re.I)
    if m:
        args['intern'] = _v48_clean_name(m.group(1))
        args['scenario'] = m.group(2).strip()
    else:
        # update Saleem scenario to something new
        m = re.search(r'(?:update|edit|change|set)\s+(?:intern\s+)?(.+?)\s+(?:real-world scenario|real world scenario|scenario|scenrio)\s+(?:to|as)\s+(.+)$', text, re.I)
        if m:
            args['intern'] = _v48_clean_name(m.group(1))
            args['scenario'] = m.group(2).strip()
        else:
            m = re.search(r'(?:update|edit|change)\s+(?:intern\s+)?(.+?)\s+(?:real-world scenario|real world scenario|scenario|scenrio)', text, re.I)
            if m:
                args['intern'] = _v48_clean_name(m.group(1))

    skills = re.search(r'skills\s+(?:to|as)\s+(.+?)(?:\s+deliverable|\s+due date|\s+status|$)', text, re.I)
    if skills:
        args['skills'] = skills.group(1).strip()
    deliverable = re.search(r'deliverable\s+(?:to|as)\s+(.+?)(?:\s+due date|\s+status|$)', text, re.I)
    if deliverable:
        args['deliverable'] = deliverable.group(1).strip()
    week = re.search(r'week\s+(\d+)', lower)
    if week:
        args['assigned_week'] = int(week.group(1))
    due = _v48_first_date(text)
    if due:
        args['due_date'] = due
    status = re.search(r'\b(pending|in progress|completed)\b', lower)
    if status:
        args['status'] = {'pending': 'Pending', 'in progress': 'In Progress', 'completed': 'Completed'}[status.group(1)]
    args.setdefault('output', _v48_output('update_scenario'))
    return ChatDraft(str(uuid.uuid4()), 'update_scenario', args)


def _v48_required_four_draft(self, text: str, current_workbook: str | None):
    for builder in [_v48_edit_plan_draft, _v48_extend_intern_draft, _v48_capstone_draft, _v48_scenario_draft]:
        draft = builder(self, text, current_workbook)
        if draft:
            return draft
    return None


def _v48_message(self, text: str, current_workbook: str | None = None):
    draft = _v48_required_four_draft(self, text, current_workbook)
    if draft:
        return self._response_for_draft(draft)
    return ChatService._base_message_v48(self, text, current_workbook)

ChatService.message = _v48_message



# v0.54 extend intern with plan chat override
# v0.55 removed invalid LABELS global assignment for extend_intern_with_plan
# v0.55 removed invalid REQUIRED global assignment for extend_intern_with_plan

if not hasattr(ChatService, '_base_message_v54'):
    ChatService._base_message_v54 = ChatService.message


def _v54_chat_output(command: str):
    return f'{command}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'


def _v54_clean(value: str) -> str:
    value = (value or '').strip().strip(' .,:;')
    return ' '.join(p[:1].upper() + p[1:] for p in value.split())


def _v54_extend_with_plan_draft(self, text: str, current_workbook: str | None):
    lower = (text or '').lower()
    # Plan-aware extension if user says: extend X to DATE with PLAN_NAME
    # The word "plan" is optional because users often say "with SecOps Foundation".
    if 'extend' not in lower or 'with' not in lower:
        return None
    date_m = re.search(r'20\d{2}-\d{2}-\d{2}', text)
    if not date_m:
        return None
    args = {}
    if current_workbook:
        args['source'] = current_workbook
    args['new_end'] = date_m.group(0)

    # Extend Habeeb to 2026-09-30 with Kubernetes Troubleshooting plan
    # Extend Habeeb to 2026-09-30 with SecOps Foundation
    m = re.search(r'extend\s+(?:intern\s+)?(.+?)\s+(?:to|until)\s+20\d{2}-\d{2}-\d{2}\s+with\s+(.+?)(?:\s+plan)?$', text, re.I)
    if m:
        args['intern'] = _v54_clean(m.group(1))
        plan = m.group(2).strip().strip(' .,:;')
        if 'foundation' not in plan.lower() and 'plan' not in plan.lower():
            plan = plan[:1].upper() + plan[1:] + ' Foundation'
        args['plan_name'] = plan
    args['output'] = _v54_chat_output('extend_intern_with_plan')

    if args.get('intern') and args.get('plan_name'):
        args['extension_preview'] = f"Extend {args['intern']} to {args['new_end']} using {args['plan_name']}. This will generate new extension-period daily tasks, weekly projects, and update the main project/scenario to the extension focus."
    return ChatDraft(str(uuid.uuid4()), 'extend_intern_with_plan', args)


def _v54_message(self, text: str, current_workbook: str | None = None):
    draft = _v54_extend_with_plan_draft(self, text, current_workbook)
    if draft:
        return self._response_for_draft(draft)
    return ChatService._base_message_v54(self, text, current_workbook)

ChatService.message = _v54_message

# v0.55 note: extend_intern_with_plan label is handled by proposal/UI fallback.


# v0.60 extend intern with plan preview enrichment
# Shows the extension plan before approval. Does not change execution logic.
if not hasattr(ChatService, '_base_response_for_draft_v60'):
    ChatService._base_response_for_draft_v60 = ChatService._response_for_draft


def _v60_resolve_workbook(value: str):
    from pathlib import Path
    base = Path(__file__).resolve().parents[1]
    if not value:
        return value
    p = Path(value)
    if p.exists():
        return str(p)
    for folder in [base / 'outputs', base / 'uploads', base]:
        c = folder / Path(value).name
        if c.exists():
            return str(c)
    return value


def _v60_enrich_extend_with_plan(self, draft):
    if not draft or draft.command != 'extend_intern_with_plan':
        return
    args = draft.args
    required = ['source', 'intern', 'new_end', 'plan_name']
    if any(not args.get(k) for k in required):
        return
    if args.get('extension_schedule_preview'):
        return
    try:
        from datetime import datetime, timedelta
        from tracker_excel.renderer.parser import parse_workbook
        from tracker_chat.intern_sheet_drafter import InternSheetDrafter

        source_path = _v60_resolve_workbook(args.get('source'))
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

        drafter = InternSheetDrafter()
        draft_sheet = drafter.draft(
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


def _v60_response_for_draft(self, draft):
    _v60_enrich_extend_with_plan(self, draft)
    return ChatService._base_response_for_draft_v60(self, draft)

ChatService._response_for_draft = _v60_response_for_draft


# v0.84 read-only summary no proposal
# Summary/progress questions are read-only and should not trigger Approve/Edit/Cancel.
# This wrapper is deliberately defensive across earlier patch versions.
_V84_READONLY_SUMMARY_COMMANDS = {
    'summary',
    'progress_summary',
    'intern_summary',
    'generate_summary',
    'status_summary',
    'dashboard_summary',
    'show_progress',
    'compare_interns',
}


def _v84_command_name(draft):
    return str(getattr(draft, 'command', '') or (draft.get('command') if isinstance(draft, dict) else '')).strip()


def _v84_draft_args(draft):
    if isinstance(draft, dict):
        return draft.get('args') or draft.get('arguments') or {}
    return getattr(draft, 'args', None) or getattr(draft, 'arguments', None) or {}


def _v84_is_readonly_summary(draft):
    cmd = _v84_command_name(draft).lower()
    if cmd in _V84_READONLY_SUMMARY_COMMANDS:
        return True
    # Some versions use a generic command with an intent argument.
    args = _v84_draft_args(draft)
    intent = str(args.get('intent', '') or args.get('type', '') or '').lower() if isinstance(args, dict) else ''
    return intent in _V84_READONLY_SUMMARY_COMMANDS


def _v84_result_text(result):
    if result is None:
        return ''
    if isinstance(result, str):
        return result
    if isinstance(result, dict):
        for key in ('message', 'summary', 'text', 'content', 'response', 'output'):
            if result.get(key):
                return str(result.get(key))
        return str(result)
    for attr in ('message', 'summary', 'text', 'content', 'response', 'output'):
        if hasattr(result, attr):
            val = getattr(result, attr)
            if val:
                return str(val)
    return str(result)


def _v84_success(result):
    if result is None:
        return False
    if isinstance(result, dict):
        return bool(result.get('ok', result.get('success', True)))
    if hasattr(result, 'success'):
        return bool(getattr(result, 'success'))
    if hasattr(result, 'ok'):
        return bool(getattr(result, 'ok'))
    return True


def _v84_execute_using_existing_hooks(self, draft):
    cmd = _v84_command_name(draft)
    args = _v84_draft_args(draft)

    # 1) Try service instance hooks that may already exist.
    for method_name in (
        '_execute_draft', 'execute_draft', '_run_draft', 'run_draft',
        '_execute_command', 'execute_command', '_run_command', 'run_command',
        '_apply_draft', 'apply_draft', '_approve_draft', 'approve_draft',
    ):
        method = getattr(self, method_name, None)
        if callable(method):
            try:
                try:
                    return method(draft)
                except TypeError:
                    return method(cmd, args)
            except Exception:
                continue

    # 2) Try attached executor objects.
    for attr_name in ('executor', 'command_executor', '_executor', '_command_executor'):
        executor = getattr(self, attr_name, None)
        if executor is None:
            continue
        for method_name in ('execute', 'run', 'apply'):
            method = getattr(executor, method_name, None)
            if callable(method):
                try:
                    try:
                        return method(cmd, args)
                    except TypeError:
                        return method(draft)
                except Exception:
                    continue

    # 3) Try importing command executor class from the project.
    try:
        from tracker_commands.executor import CommandExecutor
        executor = CommandExecutor()
        for method_name in ('execute', 'run', 'apply'):
            method = getattr(executor, method_name, None)
            if callable(method):
                try:
                    try:
                        return method(cmd, args)
                    except TypeError:
                        return method(draft)
                except Exception:
                    continue
    except Exception:
        pass

    # 4) Known summary service fallback if available.
    try:
        from tracker_services.summary_service import SummaryService
        svc = SummaryService()
        for method_name in ('summary', 'generate_summary', 'progress_summary', 'intern_summary'):
            method = getattr(svc, method_name, None)
            if callable(method):
                try:
                    try:
                        return method(**args) if isinstance(args, dict) else method(args)
                    except TypeError:
                        return method(args)
                except Exception:
                    continue
    except Exception:
        pass

    return None


def _v84_direct_response_from_result(result, fallback_message='Progress summary generated.'):
    text = _v84_result_text(result).strip() or fallback_message
    return {
        'ok': True,
        'message': text,
        'response': text,
        'content': text,
        'command': _v84_command_name(result) if not isinstance(result, dict) else result.get('command', 'summary'),
        'readonly': True,
        'requires_approval': False,
        'needs_approval': False,
        'proposal': None,
        'draft': None,
        'data': result if isinstance(result, dict) else None,
    }


def _v84_mutate_response_readonly(response):
    # If execution shape is unknown, at least prevent frontend approval mode.
    if isinstance(response, dict):
        response['readonly'] = True
        response['requires_approval'] = False
        response['needs_approval'] = False
        response['proposal'] = None
        response['draft'] = None
        msg = str(response.get('message') or response.get('response') or response.get('content') or '')
        if 'Review the proposal' in msg or 'approve, edit, or cancel' in msg.lower():
            response['message'] = 'Generated progress summary.'
            response['response'] = response['message']
        return response
    for attr, val in [('readonly', True), ('requires_approval', False), ('needs_approval', False), ('proposal', None), ('draft', None)]:
        try:
            setattr(response, attr, val)
        except Exception:
            pass
    return response


if not hasattr(ChatService, '_base_response_for_draft_v84') and hasattr(ChatService, '_response_for_draft'):
    ChatService._base_response_for_draft_v84 = ChatService._response_for_draft

    def _v84_response_for_draft(self, draft):
        if _v84_is_readonly_summary(draft):
            result = _v84_execute_using_existing_hooks(self, draft)
            if result is not None and _v84_success(result):
                return _v84_direct_response_from_result(result, 'Generated progress summary.')
            # Fallback: let original generate whatever it can, then strip proposal mode.
            base_response = ChatService._base_response_for_draft_v84(self, draft)
            return _v84_mutate_response_readonly(base_response)
        return ChatService._base_response_for_draft_v84(self, draft)

    ChatService._response_for_draft = _v84_response_for_draft


# v0.85 execute read-only summaries immediately
# Read-only progress/summary commands should not enter approval flow.
# This patch is intentionally broad because older patches used different command names.
_V85_READONLY_COMMAND_KEYWORDS = {
    'summary', 'summarize', 'summarise', 'progress', 'progress_summary', 'intern_summary',
    'generate_summary', 'generate_progress_summary', 'status_summary', 'dashboard_summary',
    'show_progress', 'compare_interns', 'intern_status', 'status', 'how_is_intern_doing',
}

_V85_READONLY_TEXT_MARKERS = (
    'generate a progress summary',
    'generated progress summary',
    'progress summary for the current workbook',
    'how is ',
    ' how is ',
    'doing?',
)


def _v85_get(obj, key, default=None):
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _v85_set(obj, key, value):
    if obj is None:
        return
    if isinstance(obj, dict):
        obj[key] = value
        return
    try:
        setattr(obj, key, value)
    except Exception:
        pass


def _v85_to_text(value):
    if value is None:
        return ''
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        parts = []
        for key in ('message', 'response', 'content', 'summary', 'text', 'title', 'command'):
            if value.get(key):
                parts.append(str(value.get(key)))
        if value.get('proposal'):
            parts.append(_v85_to_text(value.get('proposal')))
        if value.get('draft'):
            parts.append(_v85_to_text(value.get('draft')))
        return ' '.join(parts)
    parts = []
    for key in ('message', 'response', 'content', 'summary', 'text', 'title', 'command'):
        val = getattr(value, key, None)
        if val:
            parts.append(str(val))
    for key in ('proposal', 'draft'):
        val = getattr(value, key, None)
        if val:
            parts.append(_v85_to_text(val))
    return ' '.join(parts) or str(value)


def _v85_command_name(obj):
    cmd = _v85_get(obj, 'command', '') or _v85_get(obj, 'intent', '') or _v85_get(obj, 'type', '')
    return str(cmd or '').strip().lower()


def _v85_args(obj):
    return _v85_get(obj, 'args', None) or _v85_get(obj, 'arguments', None) or {}


def _v85_is_readonly_summary_like(obj):
    if obj is None:
        return False
    cmd = _v85_command_name(obj)
    if cmd:
        if cmd in _V85_READONLY_COMMAND_KEYWORDS:
            return True
        if any(k in cmd for k in ('summary', 'progress', 'status')):
            return True
    args = _v85_args(obj)
    if isinstance(args, dict):
        for key in ('intent', 'type', 'command', 'mode'):
            val = str(args.get(key, '') or '').lower()
            if val in _V85_READONLY_COMMAND_KEYWORDS or any(k in val for k in ('summary', 'progress', 'status')):
                return True
    text = _v85_to_text(obj).lower()
    if any(marker in text for marker in _V85_READONLY_TEXT_MARKERS):
        # Avoid incorrectly marking mutation commands that happen to mention status/progress.
        mutation_words = ('add intern', 'extend intern', 'create plan', 'edit task', 'update task', 'add holiday', 'finalize evaluation')
        return not any(w in text for w in mutation_words)
    return False


def _v85_find_draft_or_proposal(response):
    for key in ('draft', 'proposal', 'pending', 'command_draft'):
        val = _v85_get(response, key, None)
        if val is not None:
            return val
    # Some response shapes put draft under data.
    data = _v85_get(response, 'data', None)
    if isinstance(data, dict):
        for key in ('draft', 'proposal', 'pending', 'command_draft'):
            if data.get(key) is not None:
                return data.get(key)
    return response if _v85_is_readonly_summary_like(response) else None


def _v85_success(result):
    if result is None:
        return False
    if isinstance(result, dict):
        return bool(result.get('ok', result.get('success', True)))
    for key in ('ok', 'success'):
        if hasattr(result, key):
            return bool(getattr(result, key))
    return True


def _v85_result_message(result):
    if result is None:
        return ''
    if isinstance(result, str):
        return result
    if isinstance(result, dict):
        for key in ('summary', 'message', 'response', 'content', 'text', 'output'):
            val = result.get(key)
            if val:
                return str(val)
        return str(result)
    for key in ('summary', 'message', 'response', 'content', 'text', 'output'):
        val = getattr(result, key, None)
        if val:
            return str(val)
    return str(result)


def _v85_try_execute_readonly(self, draft):
    # Prevent recursion if an approval hook eventually calls back into response generation.
    if getattr(self, '_v85_executing_readonly', False):
        return None
    self._v85_executing_readonly = True
    try:
        cmd = _v85_command_name(draft)
        args = _v85_args(draft)

        # Prefer "approve/apply" hooks because the old app already knew how to generate the summary after user typed approve.
        method_candidates = (
            'approve', 'approve_draft', '_approve_draft', 'apply_draft', '_apply_draft',
            'execute_draft', '_execute_draft', 'run_draft', '_run_draft',
            'execute_command', '_execute_command', 'run_command', '_run_command',
            'execute', 'run', 'apply',
        )
        for name in method_candidates:
            method = getattr(self, name, None)
            if callable(method):
                try:
                    try:
                        result = method(draft)
                    except TypeError:
                        result = method(cmd, args)
                    if result is not None:
                        return result
                except Exception:
                    continue

        # Try executor attributes.
        for attr in ('executor', 'command_executor', '_executor', '_command_executor'):
            executor = getattr(self, attr, None)
            if executor is None:
                continue
            for name in ('approve', 'apply', 'execute', 'run'):
                method = getattr(executor, name, None)
                if callable(method):
                    try:
                        try:
                            result = method(draft)
                        except TypeError:
                            result = method(cmd, args)
                        if result is not None:
                            return result
                    except Exception:
                        continue

        # Try project command executor.
        try:
            from tracker_commands.executor import CommandExecutor
            executor = CommandExecutor()
            for name in ('approve', 'apply', 'execute', 'run'):
                method = getattr(executor, name, None)
                if callable(method):
                    try:
                        try:
                            result = method(draft)
                        except TypeError:
                            result = method(cmd, args)
                        if result is not None:
                            return result
                    except Exception:
                        continue
        except Exception:
            pass
    finally:
        self._v85_executing_readonly = False
    return None


def _v85_clean_readonly_response(result, fallback='Generated progress summary.'):
    message = _v85_result_message(result).strip() or fallback
    if 'Review the proposal on the right' in message:
        message = message.split('Review the proposal on the right')[0].strip() or fallback
    response = {
        'ok': True,
        'success': True,
        'readonly': True,
        'requires_approval': False,
        'needs_approval': False,
        'approval_required': False,
        'message': message,
        'response': message,
        'content': message,
        'proposal': None,
        'draft': None,
        'command': 'summary',
    }
    if isinstance(result, dict):
        # Keep useful data fields, but override approval fields.
        response.update({k: v for k, v in result.items() if k not in {'proposal', 'draft', 'requires_approval', 'needs_approval', 'approval_required'}})
        response.update({'readonly': True, 'requires_approval': False, 'needs_approval': False, 'approval_required': False, 'proposal': None, 'draft': None})
        if message:
            response['message'] = message
            response['response'] = message
            response['content'] = message
    return response


def _v85_mutate_to_no_proposal(response):
    if isinstance(response, dict):
        response['readonly'] = True
        response['requires_approval'] = False
        response['needs_approval'] = False
        response['approval_required'] = False
        response['proposal'] = None
        response['draft'] = None
        msg = str(response.get('message') or response.get('response') or response.get('content') or '')
        if 'Review the proposal on the right' in msg or 'approve, edit, or cancel' in msg.lower():
            msg = msg.split('Review the proposal on the right')[0].strip() or 'Generated progress summary.'
            response['message'] = msg
            response['response'] = msg
            response['content'] = msg
        return response
    for key, value in (
        ('readonly', True), ('requires_approval', False), ('needs_approval', False),
        ('approval_required', False), ('proposal', None), ('draft', None),
    ):
        try:
            setattr(response, key, value)
        except Exception:
            pass
    return response


# Wrap _response_for_draft if available.
if hasattr(ChatService, '_response_for_draft') and not hasattr(ChatService, '_base_response_for_draft_v85'):
    ChatService._base_response_for_draft_v85 = ChatService._response_for_draft

    def _v85_response_for_draft(self, draft):
        if _v85_is_readonly_summary_like(draft):
            result = _v85_try_execute_readonly(self, draft)
            if result is not None and _v85_success(result):
                return _v85_clean_readonly_response(result)
            base = ChatService._base_response_for_draft_v85(self, draft)
            if _v85_is_readonly_summary_like(base):
                draft2 = _v85_find_draft_or_proposal(base)
                result2 = _v85_try_execute_readonly(self, draft2)
                if result2 is not None and _v85_success(result2):
                    return _v85_clean_readonly_response(result2)
                return _v85_mutate_to_no_proposal(base)
            return base
        return ChatService._base_response_for_draft_v85(self, draft)

    ChatService._response_for_draft = _v85_response_for_draft


# Also wrap common chat/message methods because some versions create proposal responses without _response_for_draft.
def _v85_wrap_method(method_name):
    if not hasattr(ChatService, method_name):
        return
    marker = f'_base_{method_name}_v85'
    if hasattr(ChatService, marker):
        return
    base = getattr(ChatService, method_name)
    if not callable(base):
        return
    setattr(ChatService, marker, base)

    def wrapped(self, *args, **kwargs):
        response = base(self, *args, **kwargs)
        if _v85_is_readonly_summary_like(response):
            draft = _v85_find_draft_or_proposal(response)
            result = _v85_try_execute_readonly(self, draft)
            if result is not None and _v85_success(result):
                return _v85_clean_readonly_response(result)
            return _v85_mutate_to_no_proposal(response)
        return response

    setattr(ChatService, method_name, wrapped)

for _v85_name in ('chat', 'ask', 'handle', 'process', 'message', 'send', 'respond', 'reply', 'run'):
    _v85_wrap_method(_v85_name)


# ===== v100 create-plan LLM shape + sanitize override =====
# Fixes:
# 1) Provider system prompt expects {"command": "...", "args": {...}},
#    while the old plan drafter expected top-level {"plan_name": ..., "weeks": ...}.
# 2) HTML/Lexical tags from LLM output leaked into proposal text.
# 3) Generic safe draft appeared because valid weeks were hidden under args or invalid.

import html as _v100_html

def _v100_clean_text(value):
    s = str(value or "")
    s = _v100_html.unescape(s)
    s = re.sub(r'<br\s*/?>', '\n', s, flags=re.I)
    s = re.sub(r'</?(strong|b|em|i|span|p|div)[^>]*>', '', s, flags=re.I)
    s = re.sub(r'data-lexical-text="true"', '', s, flags=re.I)
    s = re.sub(r'<[^>]+>', '', s)
    s = re.sub(r'\s+\n', '\n', s)
    s = re.sub(r'\n\s+', '\n', s)
    s = re.sub(r'[ \t]+', ' ', s)
    return s.strip()

def _v100_normalize_llm_plan_payload(data):
    """Accept both top-level plan JSON and command/args JSON."""
    if not isinstance(data, dict):
        return {}

    # Preferred shape because provider SYSTEM_PROMPT asks for it.
    if isinstance(data.get("args"), dict):
        args = dict(data.get("args") or {})
    else:
        args = dict(data)

    return args

def _v100_clean_weeks(raw_weeks, expected_count):
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

        theme = _v100_clean_text(item.get("theme"))
        task = _v100_clean_text(item.get("task") or item.get("daily_task"))
        weekly_project = _v100_clean_text(item.get("weekly_project") or item.get("project"))
        notes = _v100_clean_text(item.get("notes"))

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

def _v100_weeks_look_usable(weeks):
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

def _v100_plan_prompt(user_text, weeks_count):
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
"""

def _v100_draft_plan_with_llm(self, text: str, current_workbook: str | None):
    fallback_name = self._extract_plan_name(text) or "Custom Learning Plan"
    fallback_name = self._normalize_plan_name(fallback_name, text)
    weeks_count = self._extract_weeks_count(text) or 8
    source = current_workbook or ""
    output = f"Plan_{self._safe_name(fallback_name)}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"

    plan_name = fallback_name
    description = _v100_clean_text(text)
    weeks = []
    generation_error = ""

    if self.provider:
        for attempt in range(2):
            try:
                prompt = _v100_plan_prompt(text, weeks_count)
                if attempt == 1:
                    prompt += """

Your previous response was not usable. Try again.
Make sure weeks is inside args.weeks and contains detailed topic-specific week objects.
"""

                raw = self.provider.complete_json(prompt)
                args = _v100_normalize_llm_plan_payload(raw)

                candidate_name = _v100_clean_text(args.get("plan_name")) or fallback_name
                candidate_name = self._normalize_plan_name(candidate_name, text)

                explicit_prompt_name = self._explicit_plan_name_from_prompt(text)
                if explicit_prompt_name:
                    candidate_name = explicit_prompt_name

                candidate_description = _v100_clean_text(args.get("description")) or description
                candidate_weeks = _v100_clean_weeks(args.get("weeks"), weeks_count)

                if _v100_weeks_look_usable(candidate_weeks):
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
    plan_name = _v100_clean_text(plan_name) or fallback_name
    description = _v100_clean_text(description)
    weeks = _v100_clean_weeks(weeks, weeks_count)

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

ChatService._draft_plan_with_llm = _v100_draft_plan_with_llm

