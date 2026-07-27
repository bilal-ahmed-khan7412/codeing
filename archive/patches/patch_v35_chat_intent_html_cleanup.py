from pathlib import Path

root = Path(__file__).resolve().parent
chat_service = root / 'tracker_chat' / 'chat_service.py'
chat_html = root / 'web' / 'chat.html'
readme = root / 'README.md'

if not chat_service.exists():
    raise SystemExit('tracker_chat/chat_service.py not found. Run this patch inside intern_tracker_system_v0.')
if not chat_html.exists():
    raise SystemExit('web/chat.html not found. Run this patch inside intern_tracker_system_v0.')

# -----------------------------------------------------------------------------
# 1) ChatService: better plan intent for "add plan 8 weesk Secops" style prompts.
# -----------------------------------------------------------------------------
s = chat_service.read_text(encoding='utf-8')

# Make plan request detection include "add plan" and tolerate common typo "weesk".
old = """        return any(x in lower for x in ['create', 'make', 'draft', 'generate', 'build'])\n"""
new = """        return any(x in lower for x in ['create', 'make', 'draft', 'generate', 'build', 'add'])\n"""
if old in s:
    s = s.replace(old, new)

# Add SecOps and typo-aware plan name extraction.
if "return 'SecOps Foundation'" not in s:
    s = s.replace(
"""        if 'infosec' in lower or 'information security' in lower or 'cyber security' in lower or 'cybersecurity' in lower:\n            return 'Information Security Foundation'\n""",
"""        if 'secops' in lower or 'security operations' in lower:\n            return 'SecOps Foundation'\n        if 'infosec' in lower or 'information security' in lower or 'cyber security' in lower or 'cybersecurity' in lower:\n            return 'Information Security Foundation'\n"""
    )

# Patch generic plan extraction block if present. Add support for "add plan 8 weesk Secops".
old = """        m2 = re.search(r'(?:create|make|draft|generate|build)\\s+(?:an?|the)?\\s*([A-Za-z0-9 ._+-]+?)\\s+plan', text, re.I)\n        if m2:\n            topic = m2.group(1).strip().rstrip('.')\n            # Remove duration/level filler from topic, e.g. \"8 week Deep learning\" -> \"Deep learning\".\n            topic = re.sub(r'^(?:\\d+|one|two|three|four|five|six|seven|eight|nine|ten)\\s*-?\\s*weeks?\\s+', '', topic, flags=re.I).strip()\n            topic = re.sub(r'^(?:beginner|intermediate|advanced)\\s+', '', topic, flags=re.I).strip()\n            if topic and topic.lower() not in {'week', 'weeks', 'plan'}:\n                if topic.lower().replace(' ', '') == 'deeplearning':\n                    return 'Deep Learning Foundation'\n                return topic.title() + ' Foundation'\n        return None\n"""
new = """        # Patterns like \"create a 8 week Deep learning plan\" or \"add plan 8 weesk Secops\".\n        normalized = re.sub(r'weesk|weks|wek', 'weeks', text, flags=re.I)\n        m2 = re.search(r'(?:create|make|draft|generate|build)\\s+(?:an?|the)?\\s*([A-Za-z0-9 ._+-]+?)\\s+plan', normalized, re.I)\n        if not m2:\n            m2 = re.search(r'(?:add|create|make|draft|generate|build)\\s+plan\\s+(?:an?|the)?\\s*([A-Za-z0-9 ._+-]+)', normalized, re.I)\n        if m2:\n            topic = m2.group(1).strip().rstrip('.')\n            topic = re.sub(r'^(?:\\d+|one|two|three|four|five|six|seven|eight|nine|ten)\\s*-?\\s*weeks?\\s+', '', topic, flags=re.I).strip()\n            topic = re.sub(r'^(?:beginner|intermediate|advanced)\\s+', '', topic, flags=re.I).strip()\n            topic = re.sub(r'\\bplan\\b$', '', topic, flags=re.I).strip()\n            if topic and topic.lower() not in {'week', 'weeks', 'plan'}:\n                compact = topic.lower().replace(' ', '')\n                if compact == 'deeplearning': return 'Deep Learning Foundation'\n                if compact == 'secops': return 'SecOps Foundation'\n                return topic.title() + ' Foundation'\n        return None\n"""
if old in s:
    s = s.replace(old, new)

# Patch week count extraction to tolerate typo.
old = """        m = re.search(r'(\\d+)\\s+weeks?', text.lower())\n        return int(m.group(1)) if m else None\n"""
new = """        normalized = re.sub(r'weesk|weks|wek', 'weeks', text.lower())\n        m = re.search(r'(\\d+)\\s+weeks?', normalized)\n        return int(m.group(1)) if m else None\n"""
if old in s:
    s = s.replace(old, new)

# Add SecOps fallback weeks if not present.
needle = """        elif 'deep learning' in lower or 'deeplearning' in lower:\n            base = [\n"""
insert = """        elif 'secops' in lower or 'security operations' in lower:\n            base = [\n                ('Security Operations Foundations', 'Review SOC workflows, alert lifecycle, incident severity, escalation paths, and security operations roles.', 'Create a SOC workflow and escalation checklist.'),\n                ('Log Sources and SIEM Basics', 'Learn common log sources, SIEM alert structure, correlation rules, and investigation notes.', 'Map sample log sources to security use cases.'),\n                ('Alert Triage and Investigation', 'Practice reviewing alerts, identifying indicators, checking context, and documenting investigation steps.', 'Triage simulated alerts and write investigation notes.'),\n                ('Endpoint and Identity Signals', 'Review endpoint events, authentication failures, risky sign-ins, and identity-based detections.', 'Analyze sample endpoint and identity alerts.'),\n                ('Network and Cloud Security Monitoring', 'Review network indicators, firewall/proxy logs, cloud audit logs, and suspicious activity patterns.', 'Investigate a cloud/network alert scenario.'),\n                ('Incident Response Coordination', 'Practice containment, evidence capture, communication, and incident timeline creation.', 'Write an incident response mini-report.'),\n                ('Detection Improvement and Reporting', 'Learn false positive review, detection tuning, metrics, dashboards, and reporting hygiene.', 'Improve a noisy detection and summarize before/after impact.'),\n                ('Final SecOps Investigation Project', 'Run an end-to-end security operations investigation from alert to report.', 'Deliver a final SOC investigation report and presentation.'),\n            ]\n        elif 'deep learning' in lower or 'deeplearning' in lower:\n            base = [\n"""
if needle in s and 'Security Operations Foundations' not in s:
    s = s.replace(needle, insert)

chat_service.write_text(s, encoding='utf-8')

# -----------------------------------------------------------------------------
# 2) Chat UI: sanitize assistant/user messages so raw <br>, <strong>, data-lexical tags never show.
# -----------------------------------------------------------------------------
h = chat_html.read_text(encoding='utf-8')

# Add sanitizer helpers and replace chatAppend if exact function exists.
old = """function chatAppend(who, text, cls){ const box=document.getElementById('chatLog'); const div=document.createElement('div'); div.className='msg ' + (cls || who); div.innerHTML=escapeHtml(text); box.appendChild(div); box.scrollTop=box.scrollHeight; }\n"""
new = """function stripHtml(raw){\n  let s = String(raw ?? '');\n  s = s.replace(/<br\\s*\\/?\\s*>/gi, '\\n');\n  s = s.replace(/<\\/?(strong|b|em|i)[^>]*>/gi, '');\n  s = s.replace(/<[^>]+>/g, '');\n  return s;\n}\nfunction chatAppend(who, text, cls){\n  const box=document.getElementById('chatLog');\n  const div=document.createElement('div');\n  div.className='msg ' + (cls || who);\n  div.textContent = stripHtml(text);\n  box.appendChild(div);\n  box.scrollTop=box.scrollHeight;\n}\n"""
if old in h:
    h = h.replace(old, new)
else:
    # If function differs, add stripHtml and do a conservative replacement.
    if 'function stripHtml(raw)' not in h:
        h = h.replace('function escapeHtml', new + '\nfunction escapeHtml')

# If human summary or proposal has <br><br> embedded, use newline in chat message.
h = h.replace(" + '<br><br>Review the proposal card on the right. You can approve, edit, or cancel.'", " + '\\n\\nReview the proposal card on the right. You can approve, edit, or cancel.'")
h = h.replace('<br><br>Review the proposal card on the right. You can approve, edit, or cancel.', '\\n\\nReview the proposal card on the right. You can approve, edit, or cancel.')

chat_html.write_text(h, encoding='utf-8')

# -----------------------------------------------------------------------------
# 3) README note.
# -----------------------------------------------------------------------------
if readme.exists():
    readme.write_text(readme.read_text(encoding='utf-8') + r'''

## v0.35 Chat intent and HTML cleanup

- `add plan 8 weesk Secops` now routes to plan creation and infers `SecOps Foundation`.
- Plan detection now tolerates `add plan ...` and common typo `weesk`.
- Chat bubbles now strip raw HTML tags such as `<br>` and `<strong data-lexical-text=...>` so the user sees clean text.
''', encoding='utf-8')

print('v0.35 chat intent and HTML cleanup patch applied successfully.')
