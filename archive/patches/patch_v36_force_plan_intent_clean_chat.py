from pathlib import Path
import re

root = Path(__file__).resolve().parent
chat_service = root / 'tracker_chat' / 'chat_service.py'
chat_html = root / 'web' / 'chat.html'
readme = root / 'README.md'

if not chat_service.exists():
    raise SystemExit('tracker_chat/chat_service.py not found. Run this inside intern_tracker_system_v0.')
if not chat_html.exists():
    raise SystemExit('web/chat.html not found. Run this inside intern_tracker_system_v0.')

# -----------------------------------------------------------------------------
# 1) Backend: force explicit plan creation before generic LLM intent parser.
# -----------------------------------------------------------------------------
s = chat_service.read_text(encoding='utf-8')

if 'def _is_explicit_plan_create' not in s:
    method = r'''
    def _is_explicit_plan_create(self, text: str) -> bool:
        """Detect commands that clearly mean create/add a learning plan.

        This guard is intentionally small: it only catches explicit plan creation
        phrases before the generic LLM intent parser can misroute them.
        """
        lower = (text or '').lower()
        if 'intern' in lower or 'apply plan' in lower or 'edit plan' in lower or 'plan week' in lower:
            return False
        lower = re.sub(r'weesk|weks|wek', 'weeks', lower)
        return bool(
            re.search(r'\b(add|create|make|draft|generate|build)\s+(a\s+|an\s+|the\s+)?(\d+\s+weeks?\s+)?[a-z0-9 ._-]*\bplan\b', lower)
            or re.search(r'\b(add|create|make|draft|generate|build)\s+plan\b', lower)
        )

'''
    marker = '    def _looks_like_plan_request(self, text: str) -> bool:'
    if marker not in s:
        raise SystemExit('Could not find _looks_like_plan_request insertion point.')
    s = s.replace(marker, method + marker)

old = """        # Groq/full LLM powered draft for free-form plan creation.\n        # Keep this specialized path because it generates complete week content.\n        if self._looks_like_plan_request(text):\n            draft = self._draft_plan_with_llm(text, current_workbook)\n        else:\n"""
new = """        # Explicit plan creation must be handled before the generic intent parser.\n        # This fixes prompts like: add plan secops 8 weeks.\n        if self._is_explicit_plan_create(text):\n            draft = self._draft_plan_with_llm(text, current_workbook)\n        elif self._looks_like_plan_request(text):\n            draft = self._draft_plan_with_llm(text, current_workbook)\n        else:\n"""
if old in s:
    s = s.replace(old, new)
elif 'if self._is_explicit_plan_create(text):' not in s:
    print('Warning: exact message flow block not found. You may need manual merge.')

# Improve _extract_plan_name for add plan secops 8 weeks / add plan 8 weeks secops.
idx = s.find('    def _extract_plan_name')
if idx != -1:
    next_idx = s.find('\n    def ', idx + 5)
    segment = s[idx:next_idx if next_idx != -1 else len(s)]
    if 'Explicit forms: add plan secops 8 weeks' not in segment:
        old_lower = "        lower = text.lower()\n"
        new_lower = """        lower = text.lower()\n        normalized_text = re.sub(r'weesk|weks|wek', 'weeks', text, flags=re.I)\n        # Explicit forms: add plan secops 8 weeks, add plan 8 weeks secops\n        m0 = re.search(r'\\b(?:add|create|make|draft|generate|build)\\s+plan\\s+(.+)', normalized_text, re.I)\n        if m0:\n            topic = m0.group(1).strip().rstrip('.')\n            topic = re.sub(r'\\b(?:\\d+|one|two|three|four|five|six|seven|eight|nine|ten)\\s*-?\\s*weeks?\\b', '', topic, flags=re.I).strip()\n            topic = re.sub(r'\\bplan\\b', '', topic, flags=re.I).strip()\n            if topic:\n                compact = topic.lower().replace(' ', '')\n                if compact == 'secops': return 'SecOps Foundation'\n                if compact == 'deeplearning': return 'Deep Learning Foundation'\n                if 'infosec' in compact or 'cyber' in compact: return 'Information Security Foundation'\n                return topic.title() + ' Foundation'\n"""
        if old_lower in segment:
            segment = segment.replace(old_lower, new_lower, 1)
            s = s[:idx] + segment + (s[next_idx:] if next_idx != -1 else '')

if "return 'SecOps Foundation'" not in s:
    s = s.replace(
        "        if 'openshift' in lower:\n            return 'OpenShift Foundation'\n",
        "        if 'openshift' in lower:\n            return 'OpenShift Foundation'\n        if 'secops' in lower or 'security operations' in lower:\n            return 'SecOps Foundation'\n"
    )

old = """        m = re.search(r'(\\d+)\\s+weeks?', text.lower())\n        return int(m.group(1)) if m else None\n"""
new = """        normalized = re.sub(r'weesk|weks|wek', 'weeks', text.lower())\n        m = re.search(r'(\\d+)\\s+weeks?', normalized)\n        return int(m.group(1)) if m else None\n"""
if old in s:
    s = s.replace(old, new)

chat_service.write_text(s, encoding='utf-8')

# -----------------------------------------------------------------------------
# 2) Frontend: clean chat text. IMPORTANT: use lambda replacement in re.sub so
#    backslashes inside JavaScript regex are not interpreted by Python re.
# -----------------------------------------------------------------------------
h = chat_html.read_text(encoding='utf-8')

clean_funcs = r'''
function stripHtml(raw){
  let s = String(raw ?? '');
  s = s.replace(/<br\s*\/?\s*>/gi, '\n');
  s = s.replace(/<\/?(strong|b|em|i)[^>]*>/gi, '');
  s = s.replace(/data-lexical-text="true"/gi, '');
  s = s.replace(/<[^>]+>/g, '');
  s = s.replace(/&lt;br\s*\/?&gt;/gi, '\n');
  s = s.replace(/&lt;\/?(strong|b|em|i)[^&]*&gt;/gi, '');
  return s;
}
function chatAppend(who, text, cls){
  const box=document.getElementById('chatLog');
  const div=document.createElement('div');
  div.className='msg ' + (cls || who);
  div.textContent = stripHtml(text);
  box.appendChild(div);
  box.scrollTop=box.scrollHeight;
}
'''

# Replace existing stripHtml+chatAppend or chatAppend only. Use lambda to avoid bad escape.
h2 = re.sub(
    r'function\s+stripHtml\s*\([^)]*\)\s*\{.*?\}\s*function\s+chatAppend\s*\([^)]*\)\s*\{.*?\}\s*',
    lambda m: clean_funcs,
    h,
    flags=re.S
)
if h2 == h:
    h2 = re.sub(
        r'function\s+chatAppend\s*\([^)]*\)\s*\{.*?\}\s*',
        lambda m: clean_funcs,
        h,
        flags=re.S
    )
h = h2

h = h.replace('<br><br>Review the proposal card on the right. You can approve, edit, or cancel.', '\n\nReview the proposal card on the right. You can approve, edit, or cancel.')
h = h.replace('&lt;br&gt;&lt;br&gt;Review the proposal card on the right. You can approve, edit, or cancel.', '\n\nReview the proposal card on the right. You can approve, edit, or cancel.')

chat_html.write_text(h, encoding='utf-8')

if readme.exists():
    readme.write_text(readme.read_text(encoding='utf-8') + r'''

## v0.36.1 Force plan intent + clean chat output

- Fixed v0.36 patch error caused by Python `re.sub` interpreting JavaScript backslashes.
- Prompts like `add plan secops 8 weeks` and `add plan 8 weeks secops` now force the AI-drafted plan workflow before the generic LLM intent parser.
- Common typo `weesk` is normalized to `weeks`.
- Chat messages strip raw HTML/lexical tags such as `<br>` and `<strong data-lexical-text="true">`.
''', encoding='utf-8')

print('v0.36.1 force plan intent + clean chat output patch applied successfully.')
