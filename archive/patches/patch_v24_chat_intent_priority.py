from pathlib import Path

root = Path(__file__).resolve().parent
chat_service = root / 'tracker_chat' / 'chat_service.py'

if not chat_service.exists():
    raise SystemExit('tracker_chat/chat_service.py not found. Run this patch inside intern_tracker_system_v0 after v0.23.')

s = chat_service.read_text(encoding='utf-8')

# 1) Make _looks_like_plan_request exclude add intern / apply plan / edit plan cases.
old = """    def _looks_like_plan_request(self, text: str) -> bool:\n        lower = text.lower()\n        return 'plan' in lower and not any(x in lower for x in ['edit plan', 'apply plan', 'plan week', 'rename plan'])\n"""
new = """    def _looks_like_plan_request(self, text: str) -> bool:\n        lower = text.lower()\n        # Important intent priority:\n        # - add/create intern with a plan should be add_intern_with_plan, not create_plan_from_draft\n        # - apply plan should be apply_plan_to_intern\n        # - edit plan/week should stay edit actions\n        if 'plan' not in lower:\n            return False\n        blockers = [\n            'add intern', 'create intern', 'new intern',\n            'apply plan', 'apply the plan',\n            'edit plan', 'plan week', 'rename plan'\n        ]\n        if any(x in lower for x in blockers):\n            return False\n        return any(x in lower for x in ['create', 'make', 'draft', 'generate', 'build'])\n"""
if old in s:
    s = s.replace(old, new)
else:
    raise SystemExit('Could not find _looks_like_plan_request block. Patch may need manual merge.')

# 2) Ensure add intern with plan detection handles phrases without explicit "add intern" but with "add intern Hakeel" lower-cased.
# Already handled by _detect_command in v0.23; add stronger extraction for plan name in add_intern_with_plan.
old = """            if command == 'add_intern_with_plan':\n                pm = re.search(r'(?:with|for|plan)\\s+([A-Za-z0-9 ._+-]+?)(?:\\s+plan)?(?:\\s+from|\\s+starting|$)', text, re.I)\n                if pm:\n                    val = pm.group(1).strip().rstrip('.')\n                    if val and val.lower() not in ['intern']:\n                        if 'security' in val.lower() or 'infosec' in val.lower() or 'cyber' in val.lower():\n                            args['plan_name'] = 'Information Security Foundation'\n                        elif 'openshift' in val.lower():\n                            args['plan_name'] = 'OpenShift Foundation'\n                        else:\n                            args['plan_name'] = val\n"""
new = """            if command == 'add_intern_with_plan':\n                # Prefer explicit "with X plan" / "for X plan" pattern.\n                pm = re.search(r'(?:with|for)\\s+([A-Za-z0-9 ._+-]+?)\\s+plan(?:\\b|$)', text, re.I)\n                if not pm:\n                    pm = re.search(r'(?:plan name is|plan is)\\s+([A-Za-z0-9 ._+-]+)', text, re.I)\n                if pm:\n                    val = pm.group(1).strip().rstrip('.')\n                    if val and val.lower() not in ['intern']:\n                        if 'security' in val.lower() or 'infosec' in val.lower() or 'cyber' in val.lower():\n                            args['plan_name'] = 'Information Security Foundation'\n                        elif 'openshift' in val.lower():\n                            args['plan_name'] = 'OpenShift Foundation'\n                        else:\n                            args['plan_name'] = val\n"""
if old in s:
    s = s.replace(old, new)
else:
    print('Warning: plan name extraction block not found. Main routing fix was applied.')

# 3) Make direct command detection clearer, if current exact block exists.
old = """        if ('add intern' in lower or 'create intern' in lower) and ('plan' in lower or 'with ' in lower or 'for ' in lower): return 'add_intern_with_plan'\n"""
new = """        if ('add intern' in lower or 'create intern' in lower or 'new intern' in lower) and ('plan' in lower or 'with ' in lower or 'for ' in lower): return 'add_intern_with_plan'\n"""
if old in s:
    s = s.replace(old, new)

chat_service.write_text(s, encoding='utf-8')

readme = root / 'README.md'
if readme.exists():
    readme.write_text(readme.read_text(encoding='utf-8') + r'''

## v0.24 Chat intent priority fix

- Prompts like `add intern Hakeel from 2026-08-01 to 2026-09-30 with Information Security Foundation plan` now route to `Add Intern With Plan` instead of `Create Plan From LLM Draft`.
- Plan drafting is now only triggered when the user is actually asking to create/draft/build/generate a plan, not when the user is using an existing plan for an intern.
''', encoding='utf-8')

print('v0.24 chat intent priority patch applied successfully.')
