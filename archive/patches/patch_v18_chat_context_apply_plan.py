from pathlib import Path

root = Path(__file__).resolve().parent
chat_service = root / 'tracker_chat' / 'chat_service.py'
web_app = root / 'web_app.py'
web_index = root / 'web' / 'index.html'

if not chat_service.exists():
    raise SystemExit('tracker_chat/chat_service.py not found. Run inside intern_tracker_system_v0 after chat patches.')
if not web_app.exists():
    raise SystemExit('web_app.py not found. Run inside intern_tracker_system_v0.')
if not web_index.exists():
    raise SystemExit('web/index.html not found. Run inside intern_tracker_system_v0.')

s = chat_service.read_text(encoding='utf-8')

# 1) Add fill_from_text method after update_draft, if missing.
if 'def fill_from_text' not in s:
    marker = "    def approve(self, draft_id: str) -> dict:\n"
    method = r'''
    def fill_from_text(self, draft_id: str, text: str) -> dict:
        """Fill missing fields on the active draft from a natural-language reply.

        This prevents a follow-up such as "intern name is Musab Khan plan name is
        OpenShift Foundation" from being interpreted as a brand-new create-plan
        request.
        """
        draft = self.drafts.get(draft_id)
        if not draft:
            return {'ok': False, 'error': 'Draft not found'}
        lower = text.lower()
        args = draft.args

        # Common field extractions.
        dates = re.findall(r'20\d{2}-\d{2}-\d{2}', text)
        if draft.command == 'add_intern_basic':
            if 'name' not in args or not args.get('name'):
                m = re.search(r'(?:intern name is|name is|named)\s+([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){0,3})', text)
                if m: args['name'] = m.group(1).strip()
            if dates:
                args.setdefault('start_date', dates[0])
                if len(dates) > 1: args.setdefault('end_date', dates[1])
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
        return self._response_for_draft(draft)

'''
    if marker not in s:
        raise SystemExit('Could not find approve method insertion point in chat_service.py')
    s = s.replace(marker, method + marker)

# 2) Improve _extract_common for apply_plan_to_intern and explicit plan names.
if 'apply plan name extraction v18' not in s:
    old = """        if command == 'add_holiday':\n            hm = re.search(r'holiday(?: named| called)?\\s+([A-Za-z0-9 ._-]+)', text, re.I)\n            args['name'] = hm.group(1).strip() if hm else 'Holiday'\n"""
    new = """        # apply plan name extraction v18\n        if command == 'apply_plan_to_intern':\n            ap = re.search(r'apply\\s+plan\\s+(.+?)\\s+to\\s+intern\\s+([A-Z][A-Za-z]+(?:\\s+[A-Z][A-Za-z]+){0,3})', text, re.I)\n            if ap:\n                args['plan_name'] = ap.group(1).strip().rstrip('.')\n                args['intern'] = ap.group(2).strip()\n            else:\n                pm = re.search(r'(?:plan name is|plan is)\\s+([A-Za-z0-9 ._+-]+)', text, re.I)\n                if pm: args['plan_name'] = pm.group(1).strip().rstrip('.')\n        if command == 'add_holiday':\n            hm = re.search(r'holiday(?: named| called)?\\s+([A-Za-z0-9 ._-]+)', text, re.I)\n            args['name'] = hm.group(1).strip() if hm else 'Holiday'\n"""
    if old in s:
        s = s.replace(old, new)
    else:
        print('Warning: add_holiday extraction block not found; skipping apply-plan extraction patch.')

chat_service.write_text(s, encoding='utf-8')

# 3) Add /api/chat/fill route to web_app.py
s = web_app.read_text(encoding='utf-8')
if '@app.post("/api/chat/fill")' not in s:
    insert_after = r'''@app.post("/api/chat/update")
def chat_update(payload: dict):
    return chat_service.update_draft(payload.get('draft_id'), payload.get('args') or {})
'''
    fill_route = r'''

@app.post("/api/chat/fill")
def chat_fill(payload: dict):
    """Fill the active chat draft from a follow-up natural language message."""
    return chat_service.fill_from_text(payload.get('draft_id'), payload.get('message', ''))
'''
    if insert_after not in s:
        raise SystemExit('Could not find chat_update route to insert chat_fill route.')
    s = s.replace(insert_after, insert_after + fill_route)
web_app.write_text(s, encoding='utf-8')

# 4) Patch frontend sendChat: if active draft is waiting for missing info, send follow-up to /api/chat/fill.
s = web_index.read_text(encoding='utf-8')
if 'let activeDraftNeedsInfo' not in s:
    s = s.replace('let activeDraftId = null;', 'let activeDraftId = null;\nlet activeDraftNeedsInfo = false;')

old = """async function sendChat(){ const msg=document.getElementById('chatInput').value.trim(); if(!msg) return; const lower=msg.toLowerCase(); if(activeDraftId && ['approve','approved','yes','confirm','ok'].includes(lower)){ document.getElementById('chatInput').value=''; await approveChat(); return; } if(activeDraftId && ['cancel','stop'].includes(lower)){ document.getElementById('chatInput').value=''; await cancelChat(); return; } chatAppend('You', msg); document.getElementById('chatInput').value=''; const current=localStorage.getItem('currentWorkbook') || ''; const res=await fetch('/api/chat/message',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:msg,current_workbook:current})}); const data=await res.json(); handleChatResponse(data); }\n"""
new = """async function sendChat(){ const msg=document.getElementById('chatInput').value.trim(); if(!msg) return; const lower=msg.toLowerCase(); if(activeDraftId && ['approve','approved','yes','confirm','ok'].includes(lower)){ document.getElementById('chatInput').value=''; await approveChat(); return; } if(activeDraftId && ['cancel','stop'].includes(lower)){ document.getElementById('chatInput').value=''; await cancelChat(); return; } chatAppend('You', msg); document.getElementById('chatInput').value=''; if(activeDraftId && activeDraftNeedsInfo){ const res=await fetch('/api/chat/fill',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({draft_id:activeDraftId,message:msg})}); const data=await res.json(); handleChatResponse(data); return; } const current=localStorage.getItem('currentWorkbook') || ''; const res=await fetch('/api/chat/message',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:msg,current_workbook:current})}); const data=await res.json(); handleChatResponse(data); }\n"""
if old in s:
    s = s.replace(old, new)
else:
    print('Warning: exact sendChat function not found; frontend may need manual patch.')

old = """function handleChatResponse(data){ if(!data.ok){ chatAppend('Assistant', data.error || 'Something went wrong'); return; } activeDraftId=data.draft_id; chatAppend('Assistant', data.message || JSON.stringify(data,null,2)); document.getElementById('approveBtn').disabled = data.type !== 'proposal'; document.getElementById('cancelBtn').disabled = false; renderMissing(data); }\n"""
new = """function handleChatResponse(data){ if(!data.ok){ chatAppend('Assistant', data.error || 'Something went wrong'); return; } activeDraftId=data.draft_id; activeDraftNeedsInfo = data.type === 'needs_more_info'; chatAppend('Assistant', data.message || JSON.stringify(data,null,2)); document.getElementById('approveBtn').disabled = data.type !== 'proposal'; document.getElementById('cancelBtn').disabled = false; renderMissing(data); }\n"""
if old in s:
    s = s.replace(old, new)
else:
    print('Warning: exact handleChatResponse function not found; frontend may need manual patch.')

# Clear activeDraftNeedsInfo on approve/cancel.
s = s.replace("document.getElementById('approveBtn').disabled=true; document.getElementById('cancelBtn').disabled=true; document.getElementById('missingFields').innerHTML='';", "document.getElementById('approveBtn').disabled=true; document.getElementById('cancelBtn').disabled=true; activeDraftNeedsInfo=false; document.getElementById('missingFields').innerHTML='';")
s = s.replace("activeDraftId=null; document.getElementById('approveBtn').disabled=true; document.getElementById('cancelBtn').disabled=true; document.getElementById('missingFields').innerHTML='';", "activeDraftId=null; activeDraftNeedsInfo=false; document.getElementById('approveBtn').disabled=true; document.getElementById('cancelBtn').disabled=true; document.getElementById('missingFields').innerHTML='';")
web_index.write_text(s, encoding='utf-8')

# README note
readme = root / 'README.md'
if readme.exists():
    readme.write_text(readme.read_text(encoding='utf-8') + r'''

## v0.18 Chat context/missing-info fix

- Follow-up messages now fill the active draft instead of creating a new command.
- Example fixed flow:
  1. `Apply Plan to Intern`
  2. Assistant asks for `intern, plan_name`
  3. User replies `intern name is Musab Khan plan name is OpenShift Foundation`
  4. Existing apply-plan draft is completed and can be approved.
- Direct message `apply plan OpenShift Foundation to intern Musab Khan` now extracts both fields.
''', encoding='utf-8')

print('v0.18 chat context/missing-info patch applied successfully.')
