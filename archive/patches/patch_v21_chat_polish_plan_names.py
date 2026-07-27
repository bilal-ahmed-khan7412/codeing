from pathlib import Path
import re

root = Path(__file__).resolve().parent
chat_service = root / 'tracker_chat' / 'chat_service.py'
chat_html = root / 'web' / 'chat.html'

if not chat_service.exists():
    raise SystemExit('tracker_chat/chat_service.py not found. Run inside intern_tracker_system_v0 after chat patches.')
if not chat_html.exists():
    raise SystemExit('web/chat.html not found. Run inside intern_tracker_system_v0 after v0.19/v0.20.')

# -----------------------------------------------------------------------------
# 1. Improve plan name detection for InfoSec / cybersecurity / security plans
# -----------------------------------------------------------------------------
s = chat_service.read_text(encoding='utf-8')

old_extract = """    def _extract_plan_name(self, text: str) -> str | None:\n        lower = text.lower()\n        if 'openshift' in lower:\n            return 'OpenShift Foundation'\n        if 'kubernetes' in lower or 'k8s' in lower:\n            return 'Kubernetes Foundation'\n        if 'devops' in lower or 'dev ops' in lower:\n            return 'DevOps Foundation'\n        if 'linux' in lower:\n            return 'Linux Foundation'\n        # Prefer explicit naming phrases only. Avoid treating \\\"for beginner interns\\\" as a plan name.\n        m = re.search(r'(?:called|named|plan called|plan named)\\\\s+([A-Za-z0-9 ._+-]+)', text, re.I)\n        if m:\n            return m.group(1).strip().rstrip('.')\n        return None\n"""
new_extract = """    def _extract_plan_name(self, text: str) -> str | None:\n        lower = text.lower()\n        if 'openshift' in lower:\n            return 'OpenShift Foundation'\n        if 'infosec' in lower or 'information security' in lower or 'cyber security' in lower or 'cybersecurity' in lower:\n            return 'Information Security Foundation'\n        if 'soc' in lower and 'plan' in lower:\n            return 'SOC Analyst Foundation'\n        if 'kubernetes' in lower or 'k8s' in lower:\n            return 'Kubernetes Foundation'\n        if 'devops' in lower or 'dev ops' in lower:\n            return 'DevOps Foundation'\n        if 'linux' in lower:\n            return 'Linux Foundation'\n        # Prefer explicit naming phrases only. Avoid treating \"for beginner interns\" as a plan name.\n        m = re.search(r'(?:called|named|plan called|plan named)\\s+([A-Za-z0-9 ._+-]+)', text, re.I)\n        if m:\n            return m.group(1).strip().rstrip('.')\n        # If user says "create an X plan", use X as the topic.\n        m2 = re.search(r'create\\s+(?:an?|the)?\\s*([A-Za-z0-9 ._+-]+?)\\s+plan', text, re.I)\n        if m2:\n            topic = m2.group(1).strip().rstrip('.')\n            if topic and topic.lower() not in {'week', 'weeks', '8 week', 'eight week'}:\n                return topic.title() + ' Foundation'\n        return None\n"""
if old_extract in s:
    s = s.replace(old_extract, new_extract)
else:
    print('Warning: _extract_plan_name block not matched. Skipping exact replacement.')

# Add InfoSec fallback weeks by replacing the fallback method if it still looks like v0.16.
old_fragment = """        elif 'kubernetes' in lower:\n            base = [\n                ('Container and Kubernetes Basics', 'Review images, containers, pods, deployments, services, and namespaces.', 'Deploy a simple app on Kubernetes.'),\n"""
infosec_block = """        elif 'security' in lower or 'infosec' in lower or 'cyber' in lower or 'soc analyst' in lower:\n            base = [\n                ('Security Foundations and Governance', 'Review confidentiality, integrity, availability, risk, policy basics, and common security roles.', 'Create a short security controls checklist for a sample system.'),\n                ('Networking and Linux Security Basics', 'Practice basic networking, ports, protocols, Linux permissions, logs, and hardening concepts.', 'Analyze sample Linux auth logs and identify suspicious entries.'),\n                ('Threats, Vulnerabilities, and Risk', 'Learn common attack types, CVEs, vulnerability severity, patching, and risk prioritization.', 'Prepare a vulnerability triage report for sample findings.'),\n                ('Identity, Access, and Authentication', 'Practice IAM concepts, MFA, least privilege, password policy, and access review workflows.', 'Create an access review checklist and sample remediation notes.'),\n                ('Security Monitoring and SIEM Basics', 'Review log sources, alerts, indicators of compromise, and basic SIEM investigation flow.', 'Investigate sample SIEM alerts and document conclusions.'),\n                ('Incident Response Fundamentals', 'Learn incident lifecycle, triage, containment, eradication, recovery, and evidence handling basics.', 'Write a mini incident response report from a simulated alert.'),\n                ('Cloud and Application Security Basics', 'Review secure configuration, secrets, web risks, dependency risks, and basic cloud controls.', 'Assess a sample app/cloud checklist and propose fixes.'),\n                ('Final Security Assessment Project', 'Combine monitoring, vulnerability review, access review, and incident response into a final demo.', 'Deliver a final security assessment report and presentation.'),\n            ]\n        elif 'kubernetes' in lower:\n            base = [\n                ('Container and Kubernetes Basics', 'Review images, containers, pods, deployments, services, and namespaces.', 'Deploy a simple app on Kubernetes.'),\n"""
if old_fragment in s and 'Security Foundations and Governance' not in s:
    s = s.replace(old_fragment, infosec_block)

# If Groq returns generic LLM Generated Plan for InfoSec prompts, force a better name and fallback content.
old_adjust = """                if 'openshift' in text.lower() and 'openshift' not in plan_name.lower():\n                    plan_name = 'OpenShift Foundation'\n                    weeks = self._fallback_weeks(plan_name, weeks_count, 'Adjusted to OpenShift based on user request.')\n"""
new_adjust = """                lower_text = text.lower()\n                if 'openshift' in lower_text and 'openshift' not in plan_name.lower():\n                    plan_name = 'OpenShift Foundation'\n                    weeks = self._fallback_weeks(plan_name, weeks_count, 'Adjusted to OpenShift based on user request.')\n                if ('infosec' in lower_text or 'information security' in lower_text or 'cybersecurity' in lower_text or 'cyber security' in lower_text) and all(x not in plan_name.lower() for x in ['security', 'infosec', 'cyber']):\n                    plan_name = 'Information Security Foundation'\n                    weeks = self._fallback_weeks(plan_name, weeks_count, 'Adjusted to Information Security based on user request.')\n"""
if old_adjust in s:
    s = s.replace(old_adjust, new_adjust)

chat_service.write_text(s, encoding='utf-8')

# -----------------------------------------------------------------------------
# 2. Polish chat success messages: no full local paths, no "Created draft plan ..."
# -----------------------------------------------------------------------------
s = chat_html.read_text(encoding='utf-8')

old_success = """  if(data.ok){\n    chatAppend('assistant', data.message || 'Done.');\n    if(data.output_path){ const fn=data.output_path.split(/[\\\\/]/).pop(); setCurrentWorkbook(fn); chatAppend('assistant', `Output saved as ${fn}.`); }\n    if(data.download){ document.getElementById('proposalBox').innerHTML = `<div class=\"proposal\"><h3 class=\"status-ok\">Done</h3><p>${escapeHtml(data.message || 'Completed.')}</p><div class=\"download\"><a href=\"${data.download}\">Download output workbook</a></div></div>`; }\n  } else {\n"""
new_success = """  if(data.ok){\n    const fn = data.output_path ? data.output_path.split(/[\\\\/]/).pop() : '';\n    const friendly = fn ? `Done. I created ${fn}.` : (data.message || 'Done.');\n    chatAppend('assistant', friendly);\n    if(data.output_path){ setCurrentWorkbook(fn); }\n    if(data.download){ document.getElementById('proposalBox').innerHTML = `<div class=\"proposal\"><h3 class=\"status-ok\">Done</h3><p>${escapeHtml(friendly)}</p><div class=\"download\"><a href=\"${data.download}\">Download output workbook</a></div></div>`; }\n  } else {\n"""
if old_success in s:
    s = s.replace(old_success, new_success)
else:
    print('Warning: success message block not matched. UI may still show verbose success messages.')

# Make proposal card title friendlier for create_plan_from_draft.
s = s.replace("if(cmd === 'create_plan_from_draft') return `I drafted a ${args.weeks?.length || ''}-week plan and can create it in the current workbook.`;", "if(cmd === 'create_plan_from_draft') return `I drafted a ${args.weeks?.length || ''}-week ${args.plan_name || ''} plan and can create it in the current workbook.`;")

chat_html.write_text(s, encoding='utf-8')

# README
readme = root / 'README.md'
if readme.exists():
    readme.write_text(readme.read_text(encoding='utf-8') + r'''

## v0.21 Chat polish and InfoSec plan naming

- `create a 8 week infosec plan` now names the plan `Information Security Foundation` instead of `LLM Generated Plan`.
- Added topic-aware fallback weeks for information security and cybersecurity plans.
- Chat success messages no longer dump full local paths or backend messages like `Created draft plan ...`.
- Success now says a clean message such as `Done. I created Plan_Information_Security_Foundation_....xlsx` with a download link.
''', encoding='utf-8')

print('v0.21 chat polish and InfoSec naming patch applied successfully.')
