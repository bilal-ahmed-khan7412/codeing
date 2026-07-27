from pathlib import Path

root = Path(__file__).resolve().parent
chat_service = root / 'tracker_chat' / 'chat_service.py'
chat_html = root / 'web' / 'chat.html'
readme = root / 'README.md'

if not chat_service.exists():
    raise SystemExit('tracker_chat/chat_service.py not found. Run this patch inside intern_tracker_system_v0.')

s = chat_service.read_text(encoding='utf-8')

# -----------------------------------------------------------------------------
# v0.44: Ensure missing-info flow gets the SAME full Add Intern With Plan preview
# as when the user provides all fields in one message.
# -----------------------------------------------------------------------------

# Add helper method to force enrich a ready add_intern_with_plan draft.
if 'def _force_enrich_ready_add_intern_with_plan' not in s:
    helper = r'''
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

'''
    marker = '    def _response_for_draft(self, draft: ChatDraft) -> dict:'
    if marker not in s:
        raise SystemExit('Could not find _response_for_draft insertion point in chat_service.py')
    s = s.replace(marker, helper + marker)

# Patch update_draft to call force enrichment after args update and before missing/proposal response.
old = """        for k, v in args.items():\n            if v not in [None, '']:\n                if k == 'weeks' and isinstance(v, str):\n                    try:\n                        v = json.loads(v)\n                    except Exception:\n                        pass\n                draft.args[k] = v\n        return self._response_for_draft(draft)\n"""
new = """        for k, v in args.items():\n            if v not in [None, '']:\n                if k in ['weeks', 'schedule_preview'] and isinstance(v, str):\n                    try:\n                        v = json.loads(v)\n                    except Exception:\n                        pass\n                draft.args[k] = v\n        self._force_enrich_ready_add_intern_with_plan(draft)\n        return self._response_for_draft(draft)\n"""
if old in s:
    s = s.replace(old, new)
else:
    print('Warning: update_draft exact block not found. Trying a lighter insert.')
    old2 = """        return self._response_for_draft(draft)\n\n    def approve"""
    new2 = """        self._force_enrich_ready_add_intern_with_plan(draft)\n        return self._response_for_draft(draft)\n\n    def approve"""
    if old2 in s and 'self._force_enrich_ready_add_intern_with_plan(draft)' not in s[s.find('def update_draft'):s.find('def approve')]:
        s = s.replace(old2, new2)

# Patch fill_from_text to force enrichment after regex fallback updates too.
if 'return self._response_for_draft(draft)\n\n    def approve' in s and 'fill_from_text' in s:
    # Only patch the last return before approve if helper not already immediately before it.
    segment_start = s.find('    def fill_from_text')
    segment_end = s.find('    def approve', segment_start)
    if segment_start != -1 and segment_end != -1:
        seg = s[segment_start:segment_end]
        if 'self._force_enrich_ready_add_intern_with_plan(draft)' not in seg:
            seg2 = seg.replace('        return self._response_for_draft(draft)\n', '        self._force_enrich_ready_add_intern_with_plan(draft)\n        return self._response_for_draft(draft)\n')
            s = s[:segment_start] + seg2 + s[segment_end:]

# Patch _response_for_draft too, in case a ready draft reaches it directly.
old = """        if missing:\n            draft.status = 'needs_more_info'\n"""
new = """        if not missing:\n            self._force_enrich_ready_add_intern_with_plan(draft)\n        if missing:\n            draft.status = 'needs_more_info'\n"""
if old in s and 'if not missing:\n            self._force_enrich_ready_add_intern_with_plan(draft)' not in s:
    s = s.replace(old, new, 1)

chat_service.write_text(s, encoding='utf-8')

# -----------------------------------------------------------------------------
# UI: if an Add Intern With Plan proposal is still missing schedule_preview,
# show a visible note instead of looking like a tiny/empty approval.
# -----------------------------------------------------------------------------
if chat_html.exists():
    h = chat_html.read_text(encoding='utf-8')
    marker = "if(args.schedule_preview && Array.isArray(args.schedule_preview)){"
    if marker in h and 'Schedule preview could not be generated' not in h:
        # Add an else after the first occurrence in v41 renderProposal area by replacing the closing of that block conservatively is risky.
        # Instead inject a small check after scenario section if present.
        scen = "body += `<div class=\"section-card\"><h4>Real-World Scenario</h4>${v41Rows(args, [['Scenario','scenario'],['Skills','skills'],['Deliverable','deliverable']])}</div>`;"
        note = scen + "\n    if(!args.schedule_preview || !Array.isArray(args.schedule_preview)){ body += `<div class=\"missing\"><b>Schedule preview could not be generated yet.</b><br><span class=\"hint\">Check that the selected workbook contains the plan name, then save/update the draft again.</span></div>`; }"
        if scen in h:
            h = h.replace(scen, note, 1)
    chat_html.write_text(h, encoding='utf-8')

if readme.exists():
    readme.write_text(readme.read_text(encoding='utf-8') + r'''

## v0.44 Missing-info Add Intern full preview fix

- When a user says `add intern Basit` and fills missing fields through the form, the proposal now forces the same full Add Intern With Plan enrichment as the one-shot prompt.
- The proposal should show main project, scenario, schedule preview, and editable daily tasks after `Update Proposal`.
- If schedule preview cannot be generated, the UI now shows a clear warning instead of a tiny/basic approval.
''', encoding='utf-8')

print('v0.44 missing-info full preview patch applied successfully.')
