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
# 1) Backend: never allow LLM Generated Plan as final plan name.
# -----------------------------------------------------------------------------
s = chat_service.read_text(encoding='utf-8')

# Add helper if missing.
if 'def _normalize_plan_name' not in s:
    helper = r'''
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

'''
    marker = '    def _extract_plan_name(self, text: str) -> str | None:'
    if marker not in s:
        raise SystemExit('Could not find _extract_plan_name method in tracker_chat/chat_service.py')
    s = s.replace(marker, helper + marker)

# Normalize fallback_name right after extraction.
old = """        fallback_name = self._extract_plan_name(text) or 'LLM Generated Plan'\n        weeks_count = self._extract_weeks_count(text) or 8\n"""
new = """        fallback_name = self._extract_plan_name(text) or 'Custom Learning Plan'\n        fallback_name = self._normalize_plan_name(fallback_name, text)\n        weeks_count = self._extract_weeks_count(text) or 8\n"""
if old in s:
    s = s.replace(old, new)

# Normalize Groq returned name. Handles multiple older variants.
old = """                plan_name = data.get('plan_name') or fallback_name\n                if not plan_name or plan_name.strip().lower() in {'llm generated plan', 'generated plan', 'custom plan'}:\n                    plan_name = fallback_name\n                description = data.get('description') or text\n"""
new = """                plan_name = data.get('plan_name') or fallback_name\n                plan_name = self._normalize_plan_name(plan_name, text)\n                description = data.get('description') or text\n"""
if old in s:
    s = s.replace(old, new)
else:
    old2 = """                plan_name = data.get('plan_name') or fallback_name\n                description = data.get('description') or text\n"""
    if old2 in s:
        s = s.replace(old2, new)

# Normalize fallback branch too.
old = """        return ChatDraft(str(uuid.uuid4()), 'create_plan_from_draft', {\n            'source': source,\n            'plan_name': fallback_name,\n"""
new = """        fallback_name = self._normalize_plan_name(fallback_name, text)\n        return ChatDraft(str(uuid.uuid4()), 'create_plan_from_draft', {\n            'source': source,\n            'plan_name': fallback_name,\n"""
if old in s:
    s = s.replace(old, new)

# Add a generic LLM/deep learning name extractor improvement if not already strong enough.
if "return 'Deep Learning Foundation'" not in s:
    s = s.replace("        if 'infosec' in lower or 'information security' in lower or 'cyber security' in lower or 'cybersecurity' in lower:\n            return 'Information Security Foundation'\n", "        if 'infosec' in lower or 'information security' in lower or 'cyber security' in lower or 'cybersecurity' in lower:\n            return 'Information Security Foundation'\n        if 'deep learning' in lower or 'deeplearning' in lower:\n            return 'Deep Learning Foundation'\n        if 'machine learning' in lower:\n            return 'Machine Learning Foundation'\n")

chat_service.write_text(s, encoding='utf-8')

# -----------------------------------------------------------------------------
# 2) Frontend: confirmation message must show plan name cleanly.
# -----------------------------------------------------------------------------
h = chat_html.read_text(encoding='utf-8')

# Replace success handling with command-aware friendly message, if old block exists.
old = """  if(data.ok){\n    const fn = data.output_path ? data.output_path.split(/[\\\\/]/).pop() : '';\n    const friendly = fn ? `Done. I created ${fn}.` : (data.message || 'Done.');\n    chatAppend('assistant', friendly);\n    if(data.output_path){ setCurrentWorkbook(fn); }\n    if(data.download){ document.getElementById('proposalBox').innerHTML = `<div class=\"proposal\"><h3 class=\"status-ok\">Done</h3><p>${escapeHtml(friendly)}</p><div class=\"download\"><a href=\"${data.download}\">Download output workbook</a></div></div>`; }\n  } else {\n"""
new = """  if(data.ok){\n    const fn = data.output_path ? data.output_path.split(/[\\\\/]/).pop() : '';\n    let friendly = data.message || 'Done.';\n    if(activeProposal && activeProposal.command === 'create_plan_from_draft'){\n      const planName = (activeProposal.args || {}).plan_name || 'the plan';\n      friendly = fn ? `Done. I created the ${planName} plan in ${fn}.` : `Done. I created the ${planName} plan.`;\n    } else if(activeProposal && activeProposal.command === 'add_intern_with_plan'){\n      const internName = (activeProposal.args || {}).name || 'the intern';\n      const planName = (activeProposal.args || {}).plan_name || 'the selected plan';\n      friendly = fn ? `Done. I added ${internName} with the ${planName} plan in ${fn}.` : `Done. I added ${internName} with the ${planName} plan.`;\n    } else if(fn){\n      friendly = `Done. I created ${fn}.`;\n    }\n    chatAppend('assistant', friendly);\n    if(data.output_path){ setCurrentWorkbook(fn); }\n    if(data.download){ document.getElementById('proposalBox').innerHTML = `<div class=\"proposal\"><h3 class=\"status-ok\">Done</h3><p>${escapeHtml(friendly)}</p><div class=\"download\"><a href=\"${data.download}\">Download output workbook</a></div></div>`; }\n  } else {\n"""
if old in h:
    h = h.replace(old, new)
else:
    print('Warning: exact approve success block not found in chat.html; backend plan-name fix still applied.')

# Clean label/message typo if needed.
h = h.replace('LLM Generated Plan', 'Custom Learning Plan')
h = h.replace('AI-Drafted Plan plan', 'AI-Drafted Plan')

chat_html.write_text(h, encoding='utf-8')

if readme.exists():
    readme.write_text(readme.read_text(encoding='utf-8') + r'''

## v0.33 Plan name and confirmation message fix

- Generic plan names like `LLM Generated Plan`, `Generated Plan`, and `Custom Plan` are no longer allowed in chatbot plan proposals.
- If the LLM returns a generic name, the chatbot now infers a better name from the user prompt or uses `Custom Learning Plan`.
- Approval confirmation for plan creation now includes the actual plan name, e.g. `Done. I created the Deep Learning Foundation plan in ...`.
''', encoding='utf-8')

print('v0.33 plan-name and confirmation-message fix applied successfully.')
