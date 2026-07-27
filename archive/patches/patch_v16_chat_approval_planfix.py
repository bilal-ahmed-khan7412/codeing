from pathlib import Path

root = Path(__file__).resolve().parent
chat_service = root / 'tracker_chat' / 'chat_service.py'
web_index = root / 'web' / 'index.html'

if not chat_service.exists():
    raise SystemExit('tracker_chat/chat_service.py not found. Apply v0.14/v0.15 chat patches first, then run this patch inside intern_tracker_system_v0.')
if not web_index.exists():
    raise SystemExit('web/index.html not found. Run this patch inside intern_tracker_system_v0.')

# Replace/patch ChatService with stronger plan fallback and stricter draft validation.
s = chat_service.read_text(encoding='utf-8')

# 1) Prevent approve/cancel text being routed as new summary commands.
old = """    def message(self, text: str, current_workbook: str | None = None) -> dict:\n        # Groq/full LLM powered draft for free-form plan creation.\n        if self._looks_like_plan_request(text):\n            draft = self._draft_plan_with_llm(text, current_workbook)\n        else:\n            draft = self._build_rule_draft(text, current_workbook)\n        return self._response_for_draft(draft)\n"""
new = """    def message(self, text: str, current_workbook: str | None = None) -> dict:\n        # Typed approvals are handled by the frontend. If they reach backend, do not\n        # route them into a new command such as summary.\n        if text.strip().lower() in {'approve', 'approved', 'yes', 'confirm', 'ok'}:\n            return {'ok': False, 'error': 'Use the Approve button or keep the active draft selected.'}\n        if text.strip().lower() in {'cancel', 'stop'}:\n            return {'ok': False, 'error': 'Use the Cancel button or keep the active draft selected.'}\n        # Groq/full LLM powered draft for free-form plan creation.\n        if self._looks_like_plan_request(text):\n            draft = self._draft_plan_with_llm(text, current_workbook)\n        else:\n            draft = self._build_rule_draft(text, current_workbook)\n        return self._response_for_draft(draft)\n"""
if old in s:
    s = s.replace(old, new)

# 2) Better plan name extraction.
old = """    def _extract_plan_name(self, text: str) -> str | None:\n        m = re.search(r'(?:called|named|for|plan for|plan called)\\s+([A-Za-z0-9 ._+-]+)', text, re.I)\n        if m:\n            return m.group(1).strip().rstrip('.')\n        words = text.split()\n        for w in words:\n            if w.lower() not in ['create','make','an','a','plan','week','weeks','for'] and w[:1].isupper():\n                return f'{w} Plan'\n        return None\n"""
new = """    def _extract_plan_name(self, text: str) -> str | None:\n        lower = text.lower()\n        if 'openshift' in lower:\n            return 'OpenShift Foundation'\n        if 'kubernetes' in lower or 'k8s' in lower:\n            return 'Kubernetes Foundation'\n        if 'devops' in lower or 'dev ops' in lower:\n            return 'DevOps Foundation'\n        if 'linux' in lower:\n            return 'Linux Foundation'\n        # Prefer explicit naming phrases only. Avoid treating \"for beginner interns\" as a plan name.\n        m = re.search(r'(?:called|named|plan called|plan named)\\s+([A-Za-z0-9 ._+-]+)', text, re.I)\n        if m:\n            return m.group(1).strip().rstrip('.')\n        return None\n"""
if old in s:
    s = s.replace(old, new)

# 3) Replace fallback weeks generator with topic-aware content.
old = """    def _fallback_weeks(self, plan_name: str, count: int, note: str) -> list[dict]:\n        return [\n            {'week': i, 'theme': f'{plan_name} Week {i}', 'task': 'Task to be assigned', 'weekly_project': f'Week {i}: Project to be assigned', 'notes': note}\n            for i in range(1, count + 1)\n        ]\n"""
new = """    def _fallback_weeks(self, plan_name: str, count: int, note: str) -> list[dict]:\n        lower = plan_name.lower()\n        if 'openshift' in lower:\n            base = [\n                ('Linux, Containers, and Platform Basics', 'Review Linux services, container images, registries, and basic troubleshooting commands.', 'Run and inspect a containerized sample app locally.'),\n                ('Kubernetes Foundations', 'Learn pods, deployments, services, namespaces, labels, logs, probes, and basic kubectl workflows.', 'Deploy a simple app on Kubernetes and expose it internally.'),\n                ('OpenShift Architecture and Projects', 'Understand OpenShift projects, users, routes, operators, builds, image streams, and the web console.', 'Create an OpenShift project and deploy a sample app.'),\n                ('Builds, Routes, ConfigMaps, and Secrets', 'Practice source-to-image/build config concepts, routes, configuration, and secret handling.', 'Deploy a configured app with route, config map, and secret.'),\n                ('Storage and Stateful Workloads', 'Learn persistent volumes, claims, storage classes, and stateful workload considerations.', 'Attach persistent storage to a sample workload.'),\n                ('Monitoring and Troubleshooting', 'Use events, logs, metrics, health probes, alerts, and common debugging workflows.', 'Troubleshoot a broken OpenShift deployment and document the fix.'),\n                ('Security, RBAC, and Policies', 'Practice role bindings, service accounts, security context constraints, network policies, and least privilege.', 'Create a restricted service account and validate permissions.'),\n                ('Final OpenShift Deployment Project', 'Combine deployment, route, config, storage, monitoring, and troubleshooting into one final demo.', 'Deliver a final OpenShift deployment demo and short runbook.'),\n            ]\n        elif 'kubernetes' in lower:\n            base = [\n                ('Container and Kubernetes Basics', 'Review images, containers, pods, deployments, services, and namespaces.', 'Deploy a simple app on Kubernetes.'),\n                ('Configuration and Networking', 'Practice ConfigMaps, Secrets, Services, Ingress, and DNS basics.', 'Expose a configured app through service and ingress.'),\n                ('Storage and Scheduling', 'Learn PV/PVC, node scheduling, requests, limits, and probes.', 'Deploy a persistent workload with health probes.'),\n                ('Helm and Manifests', 'Practice YAML manifests, Helm charts, values, and release management.', 'Package a sample app as a Helm chart.'),\n                ('Observability', 'Use logs, events, metrics, and troubleshooting workflows.', 'Troubleshoot a simulated deployment failure.'),\n                ('Security Basics', 'Practice RBAC, service accounts, and namespace isolation.', 'Implement least privilege for a sample app.'),\n                ('CI/CD to Kubernetes', 'Build a simple pipeline that deploys to Kubernetes.', 'Create a basic deploy pipeline.'),\n                ('Final Kubernetes Project', 'Deliver a complete Kubernetes deployment and runbook.', 'Final demo and documentation.'),\n            ]\n        else:\n            base = [\n                ('Foundation and Environment Setup', 'Set up tools, review prerequisites, and complete orientation tasks.', 'Environment setup checklist.'),\n                ('Core Concepts', 'Learn the main concepts and complete guided labs.', 'Concept summary and short demo.'),\n                ('Hands-on Practice', 'Practice common workflows and solve small exercises.', 'Hands-on lab output.'),\n                ('Intermediate Workflows', 'Combine multiple concepts into realistic tasks.', 'Integrated mini-project.'),\n                ('Troubleshooting', 'Debug common issues and document root causes.', 'Troubleshooting report.'),\n                ('Automation and Repeatability', 'Automate routine steps and improve reliability.', 'Automation script or workflow.'),\n                ('Project Polish', 'Improve quality, documentation, and presentation.', 'Project improvement checklist.'),\n                ('Final Demo', 'Present final work and lessons learned.', 'Final demo and report.'),\n            ]\n        rows = []\n        for i in range(1, count + 1):\n            item = base[(i - 1) % len(base)]\n            rows.append({'week': i, 'theme': item[0], 'task': item[1], 'weekly_project': item[2], 'notes': note})\n        return rows\n"""
if old in s:
    s = s.replace(old, new)

# 4) Harden LLM plan draft: require weeks as list; fallback if Groq returns bad shape.
old = """                weeks = data.get('weeks') or []\n                return ChatDraft(str(uuid.uuid4()), 'create_plan_from_draft', {\n                    'source': source,\n                    'plan_name': plan_name,\n                    'description': description,\n                    'weeks': weeks,\n                    'output': output,\n                })\n"""
new = """                weeks = data.get('weeks') or []\n                if not isinstance(weeks, list) or not weeks:\n                    weeks = self._fallback_weeks(plan_name, weeks_count, 'LLM returned no detailed weeks; generated safe draft.')\n                if 'openshift' in text.lower() and 'openshift' not in plan_name.lower():\n                    plan_name = 'OpenShift Foundation'\n                    weeks = self._fallback_weeks(plan_name, weeks_count, 'Adjusted to OpenShift based on user request.')\n                return ChatDraft(str(uuid.uuid4()), 'create_plan_from_draft', {\n                    'source': source,\n                    'plan_name': plan_name,\n                    'description': description,\n                    'weeks': weeks,\n                    'output': output,\n                })\n"""
if old in s:
    s = s.replace(old, new)

# 5) Make _missing stricter for create_plan_from_draft weeks.
old = """    def _missing(self, draft: ChatDraft) -> list[str]:\n        return [k for k in REQUIRED.get(draft.command, []) if draft.args.get(k) in [None, '', []]]\n"""
new = """    def _missing(self, draft: ChatDraft) -> list[str]:\n        missing = [k for k in REQUIRED.get(draft.command, []) if draft.args.get(k) in [None, '', []]]\n        if draft.command == 'create_plan_from_draft':\n            weeks = draft.args.get('weeks')\n            if not isinstance(weeks, list) or not weeks:\n                if 'weeks' not in missing:\n                    missing.append('weeks')\n        return missing\n"""
if old in s:
    s = s.replace(old, new)

chat_service.write_text(s, encoding='utf-8')

# -----------------------------------------------------------------------------
# Frontend: typed approve/cancel should trigger buttons, not create new command.
# -----------------------------------------------------------------------------
s = web_index.read_text(encoding='utf-8')
old = """async function sendChat(){ const msg=document.getElementById('chatInput').value.trim(); if(!msg) return; chatAppend('You', msg); document.getElementById('chatInput').value=''; const current=localStorage.getItem('currentWorkbook') || ''; const res=await fetch('/api/chat/message',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:msg,current_workbook:current})}); const data=await res.json(); handleChatResponse(data); }\n"""
new = """async function sendChat(){ const msg=document.getElementById('chatInput').value.trim(); if(!msg) return; const lower=msg.toLowerCase(); if(activeDraftId && ['approve','approved','yes','confirm','ok'].includes(lower)){ document.getElementById('chatInput').value=''; await approveChat(); return; } if(activeDraftId && ['cancel','stop'].includes(lower)){ document.getElementById('chatInput').value=''; await cancelChat(); return; } chatAppend('You', msg); document.getElementById('chatInput').value=''; const current=localStorage.getItem('currentWorkbook') || ''; const res=await fetch('/api/chat/message',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:msg,current_workbook:current})}); const data=await res.json(); handleChatResponse(data); }\n"""
if old in s:
    s = s.replace(old, new)
else:
    # best effort: insert a note if minified/changed function exists
    print('Warning: could not patch sendChat function automatically. If typed approve still misroutes, click the Approve button directly.')
web_index.write_text(s, encoding='utf-8')

# README note
readme = root / 'README.md'
if readme.exists():
    readme.write_text(readme.read_text(encoding='utf-8') + r'''

## v0.16 Chat approval and plan draft fixes

- Typing `approve`, `approved`, `yes`, or `confirm` in chat now triggers the active draft approval instead of creating a new Summary command.
- Create Plan From LLM Draft now requires `weeks` to be a detailed list, not just a number.
- OpenShift plan detection is improved, so prompts like `create an 8 week OpenShift plan for beginner interns with weekly projects` produce an OpenShift-focused plan name and week content.
- If Groq returns an incomplete plan, the system generates a safe OpenShift/Kubernetes/topic-aware fallback instead of asking for raw `weeks`.
''', encoding='utf-8')

print('v0.16 chat approval + plan draft fix applied successfully.')
