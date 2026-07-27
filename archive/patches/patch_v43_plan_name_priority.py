from pathlib import Path

root = Path(__file__).resolve().parent
chat_service = root / 'tracker_chat' / 'chat_service.py'
readme = root / 'README.md'

if not chat_service.exists():
    raise SystemExit('tracker_chat/chat_service.py not found. Run this patch inside intern_tracker_system_v0.')

s = chat_service.read_text(encoding='utf-8')

# -----------------------------------------------------------------------------
# v0.43 Plan name priority fix
# Goal: explicit plan name in the user prompt must override incidental keywords.
# Example:
#   "Create an 8 week SecOps Foundation plan. It should include Linux..."
# must become:
#   SecOps Foundation
# not:
#   Linux Foundation
# -----------------------------------------------------------------------------

# Add helper methods before _extract_plan_name.
if 'def _explicit_plan_name_from_prompt' not in s:
    helper = r'''
    def _explicit_plan_name_from_prompt(self, text: str) -> str | None:
        """Extract a user-specified plan name with highest priority.

        This prevents incidental topic words inside the description, such as
        "Linux and cloud log analysis", from overriding the actual requested
        plan name, such as "SecOps Foundation".
        """
        text = text or ''
        normalized = re.sub(r'weesk|weks|wek', 'weeks', text, flags=re.I)

        # Strongest signal: "called/named X".
        m = re.search(r'\b(?:called|named|plan called|plan named)\s+([A-Za-z0-9 ._+-]+?)(?:\.|,|$)', normalized, re.I)
        if m:
            return self._clean_plan_name_candidate(m.group(1))

        # "Create an 8 week X plan" or "Make a 6 weeks X plan".
        m = re.search(r'\b(?:create|make|draft|generate|build|add)\s+(?:an?|the)?\s*(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten)?\s*-?\s*(?:weeks?|week)?\s*([A-Za-z0-9 ._+-]+?)\s+plan\b', normalized, re.I)
        if m:
            return self._clean_plan_name_candidate(m.group(1))

        # "Add plan X 8 weeks" / "Create plan X".
        m = re.search(r'\b(?:add|create|make|draft|generate|build)\s+plan\s+([A-Za-z0-9 ._+-]+?)(?:\s+(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s*-?\s*weeks?|\.|,|$)', normalized, re.I)
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
        compact = value.lower().replace(' ', '')
        aliases = {
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
            elif low == 'devops': words.append('DevOps')
            elif low in {'ai', 'ml', 'llm'}: words.append(low.upper())
            else: words.append(part[:1].upper() + part[1:])
        cleaned = ' '.join(words)
        if 'foundation' not in cleaned.lower() and 'plan' not in cleaned.lower():
            cleaned += ' Foundation'
        return cleaned

'''
    marker = '    def _extract_plan_name(self, text: str) -> str | None:'
    if marker not in s:
        raise SystemExit('Could not find _extract_plan_name in chat_service.py')
    s = s.replace(marker, helper + marker)

# Ensure _extract_plan_name begins by honoring explicit plan name.
idx = s.find('    def _extract_plan_name(self, text: str) -> str | None:')
if idx == -1:
    raise SystemExit('Could not find _extract_plan_name in chat_service.py after helper insertion.')
next_idx = s.find('\n    def ', idx + 5)
segment = s[idx: next_idx if next_idx != -1 else len(s)]
if 'explicit_name = self._explicit_plan_name_from_prompt(text)' not in segment:
    old = "        lower = text.lower()\n"
    new = "        explicit_name = self._explicit_plan_name_from_prompt(text)\n        if explicit_name:\n            return explicit_name\n        lower = text.lower()\n"
    if old not in segment:
        raise SystemExit('Could not patch _extract_plan_name lower assignment.')
    segment = segment.replace(old, new, 1)
    s = s[:idx] + segment + (s[next_idx:] if next_idx != -1 else '')

# In _draft_plan_with_llm, force explicit prompt name after LLM returns plan_name.
if 'explicit_prompt_name = self._explicit_plan_name_from_prompt(text)' not in s:
    old = "                plan_name = self._normalize_plan_name(plan_name, text)\n                description = data.get('description') or text\n"
    new = "                plan_name = self._normalize_plan_name(plan_name, text)\n                explicit_prompt_name = self._explicit_plan_name_from_prompt(text)\n                if explicit_prompt_name:\n                    plan_name = explicit_prompt_name\n                description = data.get('description') or text\n"
    if old in s:
        s = s.replace(old, new, 1)
    else:
        print('Warning: could not patch LLM plan_name post-processing; _extract_plan_name priority still fixed.')

chat_service.write_text(s, encoding='utf-8')

if readme.exists():
    readme.write_text(readme.read_text(encoding='utf-8') + r'''

## v0.43 Plan name priority fix

- The chatbot now respects the explicit plan name in the prompt.
- Example: `Create an 8 week SecOps Foundation plan. It should include Linux and cloud log analysis...` now creates `SecOps Foundation`, not `Linux Foundation`.
- Priority order is now:
  1. `called/named X`
  2. `Create an 8 week X plan`
  3. `Create/Add plan X 8 weeks`
  4. Topic keyword fallback only if no explicit name exists.
''', encoding='utf-8')

print('v0.43 plan name priority patch applied successfully.')
