from pathlib import Path

root = Path(__file__).resolve().parent
chat_service = root / 'tracker_chat' / 'chat_service.py'
readme = root / 'README.md'

if not chat_service.exists():
    raise SystemExit('tracker_chat/chat_service.py not found. Run this patch inside intern_tracker_system_v0.')

s = chat_service.read_text(encoding='utf-8')

# v0.51: Fix plan-name extraction for prompts like:
#   make a plan 8 weeks Ai engineering
#   add plan 8 weeks software engineering
#   create plan 6 weeks secops
# The topic appears AFTER the duration, so older extraction may fall back to
# Custom Learning Plan.

# 1) Add/patch helper if v43 helper exists.
if 'def _explicit_plan_name_from_prompt' in s:
    start = s.find('    def _explicit_plan_name_from_prompt')
    end = s.find('\n    def _clean_plan_name_candidate', start)
    if start == -1 or end == -1:
        raise SystemExit('Could not locate _explicit_plan_name_from_prompt block boundaries.')
    new_helper = r'''    def _explicit_plan_name_from_prompt(self, text: str) -> str | None:
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

'''
    s = s[:start] + new_helper + s[end:]
else:
    # If helper does not exist, add minimal helper before _extract_plan_name.
    marker = '    def _extract_plan_name(self, text: str) -> str | None:'
    if marker not in s:
        raise SystemExit('Could not find _extract_plan_name in chat_service.py')
    helper = r'''    def _explicit_plan_name_from_prompt(self, text: str) -> str | None:
        text = text or ''
        normalized = re.sub(r'weesk|weks|wek', 'weeks', text, flags=re.I)
        patterns = [
            r'\b(?:called|named|plan called|plan named)\s+([A-Za-z0-9 ._+-]+?)(?:\.|,|$)',
            r'\b(?:create|make|draft|generate|build|add)\s+(?:an?|the)?\s*(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten)?\s*-?\s*(?:weeks?|week)?\s*([A-Za-z0-9 ._+-]+?)\s+plan\b',
            r'\b(?:add|create|make|draft|generate|build)\s+(?:an?|the)?\s*plan\s+([A-Za-z0-9 ._+-]+?)(?:\s+(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s*-?\s*weeks?|\.|,|$)',
            r'\b(?:add|create|make|draft|generate|build)\s+(?:an?|the)?\s*plan\s+(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s*-?\s*weeks?\s+([A-Za-z0-9 ._+-]+?)(?:\.|,|$)',
        ]
        for pat in patterns:
            m = re.search(pat, normalized, re.I)
            if m:
                return self._clean_plan_name_candidate(m.group(1))
        return None

    def _clean_plan_name_candidate(self, value: str) -> str | None:
        value = (value or '').strip().rstrip('.')
        value = re.sub(r'\b(?:an?|the)\b', '', value, flags=re.I).strip()
        value = re.sub(r'\b(?:week|weeks)\b', '', value, flags=re.I).strip()
        value = re.sub(r'\s+', ' ', value).strip()
        if not value or value.lower() in {'plan', 'learning', 'custom'}:
            return None
        words = []
        for part in value.split(' '):
            low = part.lower()
            if low in {'ai','ml','llm'}:
                words.append(low.upper())
            elif low == 'devops':
                words.append('DevOps')
            elif low == 'secops':
                words.append('SecOps')
            else:
                words.append(part[:1].upper() + part[1:])
        cleaned = ' '.join(words)
        if 'foundation' not in cleaned.lower() and 'plan' not in cleaned.lower():
            cleaned += ' Foundation'
        return cleaned

'''
    s = s.replace(marker, helper + marker)

# 2) Ensure AI Engineering alias/casing is handled in _clean_plan_name_candidate.
start = s.find('    def _clean_plan_name_candidate')
end = s.find('\n    def ', start + 5) if start != -1 else -1
if start != -1:
    segment = s[start:end if end != -1 else len(s)]
    if "'aiengineering': 'AI Engineering Foundation'" not in segment:
        # If aliases dict exists, add AI Engineering aliases.
        if 'aliases = {' in segment:
            segment = segment.replace("aliases = {", "aliases = {\n            'aiengineering': 'AI Engineering Foundation',\n            'aiengineer': 'AI Engineering Foundation',")
        # Ensure acronym formatting covers AI.
        if "if low == 'secops': words.append('SecOps')" in segment and "elif low == 'ai': words.append('AI')" not in segment:
            segment = segment.replace("if low == 'secops': words.append('SecOps')", "if low == 'secops': words.append('SecOps')\n            elif low == 'ai': words.append('AI')")
        s = s[:start] + segment + (s[end:] if end != -1 else '')

# 3) Ensure _extract_plan_name honors explicit helper first.
idx = s.find('    def _extract_plan_name(self, text: str) -> str | None:')
if idx != -1:
    next_idx = s.find('\n    def ', idx + 5)
    seg = s[idx:next_idx if next_idx != -1 else len(s)]
    if 'explicit_name = self._explicit_plan_name_from_prompt(text)' not in seg:
        old = '        lower = text.lower()\n'
        new = '        explicit_name = self._explicit_plan_name_from_prompt(text)\n        if explicit_name:\n            return explicit_name\n        lower = text.lower()\n'
        if old in seg:
            seg = seg.replace(old, new, 1)
            s = s[:idx] + seg + (s[next_idx:] if next_idx != -1 else '')

# 4) Ensure LLM returned generic names are overridden with explicit prompt name.
if 'explicit_prompt_name = self._explicit_plan_name_from_prompt(text)' not in s:
    old = "                plan_name = self._normalize_plan_name(plan_name, text)\n                description = data.get('description') or text\n"
    new = "                plan_name = self._normalize_plan_name(plan_name, text)\n                explicit_prompt_name = self._explicit_plan_name_from_prompt(text)\n                if explicit_prompt_name:\n                    plan_name = explicit_prompt_name\n                description = data.get('description') or text\n"
    if old in s:
        s = s.replace(old, new, 1)

chat_service.write_text(s, encoding='utf-8')

if readme.exists():
    readme.write_text(readme.read_text(encoding='utf-8') + r'''

## v0.51 Plan name after duration fix

- Fixes prompts like `make a plan 8 weeks Ai engineering` creating `Custom Learning Plan`.
- The chatbot now extracts the topic after the duration and names the plan `AI Engineering Foundation`.
- Also works for patterns like `add plan 8 weeks software engineering`.
''', encoding='utf-8')

print('v0.51 plan-name-after-duration patch applied successfully.')
