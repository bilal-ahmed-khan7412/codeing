from pathlib import Path
root = Path(__file__).resolve().parent

(root/'tracker_chat').mkdir(exist_ok=True)
(root/'tracker_chat'/'__init__.py').write_text('')

(root/'tracker_chat'/'chat_service.py').write_text(r'''
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
import re
import uuid
from typing import Any

from tracker_commands.executor import CommandExecutor

COMMAND_LABELS = {
    'create_workbook': 'Create Fresh Workbook',
    'render_workbook': 'Render/Clean Uploaded Workbook',
    'summary': 'Generate Progress Summary',
    'extend_intern': 'Extend Intern',
    'edit_task': 'Edit Task',
    'update_task_status': 'Update Task Status',
    'update_capstone': 'Update Capstone/Main Project',
    'update_scenario': 'Update Real-World Scenario',
    'edit_project': 'Edit Weekly/Small Project',
    'update_project_status': 'Update Project Status',
    'add_intern': 'Add Intern From JSON Spec',
    'add_intern_basic': 'Add Intern (Form)',
    'add_holiday': 'Add Holiday',
    'create_plan': 'Create Plan',
    'edit_plan': 'Edit Plan',
    'edit_plan_week': 'Edit Plan Week',
    'apply_plan_to_intern': 'Apply Plan to Intern',
}

REQUIRED = {
    'create_workbook': ['output'],
    'render_workbook': ['source', 'output'],
    'summary': ['workbook'],
    'extend_intern': ['source', 'intern', 'new_end', 'output'],
    'edit_task': ['source', 'intern', 'task_ref', 'output'],
    'update_task_status': ['source', 'intern', 'task_ref', 'status', 'output'],
    'update_capstone': ['source', 'intern', 'output'],
    'update_scenario': ['source', 'intern', 'output'],
    'edit_project': ['source', 'intern', 'project_number', 'output'],
    'update_project_status': ['source', 'intern', 'project_number', 'status', 'output'],
    'add_intern': ['source', 'spec', 'output'],
    'add_intern_basic': ['source', 'name', 'start_date', 'end_date', 'output'],
    'add_holiday': ['source', 'name', 'date', 'output'],
    'create_plan': ['source', 'plan_name', 'output'],
    'edit_plan': ['source', 'plan_name', 'output'],
    'edit_plan_week': ['source', 'plan_name', 'week', 'output'],
    'apply_plan_to_intern': ['source', 'intern', 'plan_name', 'output'],
}

@dataclass
class ChatDraft:
    draft_id: str
    command: str
    args: dict[str, Any] = field(default_factory=dict)
    status: str = 'drafting'
    summary: str = ''

class ChatService:
    def __init__(self):
        self.drafts: dict[str, ChatDraft] = {}
        self.executor = CommandExecutor()

    def message(self, text: str, current_workbook: str | None = None) -> dict:
        draft = self._build_draft(text, current_workbook)
        missing = self._missing(draft)
        if missing:
            draft.status = 'needs_more_info'
            self.drafts[draft.draft_id] = draft
            return {
                'ok': True,
                'type': 'needs_more_info',
                'draft_id': draft.draft_id,
                'message': self._question(draft.command, missing),
                'missing': missing,
                'known_args': draft.args,
                'command': draft.command,
            }
        draft.status = 'awaiting_approval'
        draft.summary = self._summary(draft)
        self.drafts[draft.draft_id] = draft
        return {
            'ok': True,
            'type': 'proposal',
            'draft_id': draft.draft_id,
            'message': draft.summary,
            'command': draft.command,
            'label': COMMAND_LABELS.get(draft.command, draft.command),
            'args': draft.args,
        }

    def update_draft(self, draft_id: str, args: dict) -> dict:
        draft = self.drafts.get(draft_id)
        if not draft:
            return {'ok': False, 'error': 'Draft not found'}
        for k, v in args.items():
            if v not in [None, '']:
                draft.args[k] = v
        missing = self._missing(draft)
        if missing:
            return {
                'ok': True,
                'type': 'needs_more_info',
                'draft_id': draft_id,
                'message': self._question(draft.command, missing),
                'missing': missing,
                'known_args': draft.args,
                'command': draft.command,
            }
        draft.status = 'awaiting_approval'
        draft.summary = self._summary(draft)
        return {
            'ok': True,
            'type': 'proposal',
            'draft_id': draft_id,
            'message': draft.summary,
            'command': draft.command,
            'label': COMMAND_LABELS.get(draft.command, draft.command),
            'args': draft.args,
        }

    def approve(self, draft_id: str) -> dict:
        draft = self.drafts.get(draft_id)
        if not draft:
            return {'ok': False, 'error': 'Draft not found'}
        missing = self._missing(draft)
        if missing:
            return {'ok': False, 'error': f'Missing fields: {", ".join(missing)}'}
        result = self.executor.execute({'command': draft.command, 'args': draft.args})
        return {
            'ok': result.ok,
            'message': result.message,
            'output_path': result.output_path,
            'data': result.data,
        }

    def cancel(self, draft_id: str) -> dict:
        self.drafts.pop(draft_id, None)
        return {'ok': True, 'message': 'Draft cancelled'}

    def _build_draft(self, text: str, current_workbook: str | None) -> ChatDraft:
        lower = text.lower()
        command = self._detect_command(lower)
        args = {}
        if current_workbook:
            if command == 'summary':
                args['workbook'] = current_workbook
            elif command != 'create_workbook':
                args['source'] = current_workbook
        self._extract_common(text, lower, command, args)
        self._defaults(command, args)
        return ChatDraft(str(uuid.uuid4()), command, args)

    def _detect_command(self, lower: str) -> str:
        if 'clean' in lower or 'render' in lower: return 'render_workbook'
        if 'summary' in lower or 'progress' in lower or 'report' in lower: return 'summary'
        if 'holiday' in lower: return 'add_holiday'
        if 'extend' in lower: return 'extend_intern'
        if 'task status' in lower or ('mark' in lower and 'task' in lower): return 'update_task_status'
        if 'edit task' in lower or ('change' in lower and 'task' in lower): return 'edit_task'
        if 'capstone' in lower or 'main project' in lower: return 'update_capstone'
        if 'scenario' in lower: return 'update_scenario'
        if 'project status' in lower: return 'update_project_status'
        if 'edit project' in lower or 'weekly project' in lower or 'small project' in lower: return 'edit_project'
        if 'json' in lower and 'intern' in lower: return 'add_intern'
        if 'add intern' in lower or 'create intern' in lower: return 'add_intern_basic'
        if 'apply plan' in lower or ('apply' in lower and 'plan' in lower): return 'apply_plan_to_intern'
        if 'edit plan week' in lower or ('week' in lower and 'plan' in lower and 'edit' in lower): return 'edit_plan_week'
        if 'edit plan' in lower or 'rename plan' in lower: return 'edit_plan'
        if 'plan' in lower: return 'create_plan'
        if 'fresh workbook' in lower or 'blank workbook' in lower or 'create workbook' in lower: return 'create_workbook'
        return 'summary'

    def _extract_common(self, text: str, lower: str, command: str, args: dict):
        dates = re.findall(r'20\d{2}-\d{2}-\d{2}', text)
        if command == 'extend_intern' and dates: args['new_end'] = dates[-1]
        if command == 'add_holiday' and dates: args['date'] = dates[-1]
        if command == 'add_intern_basic':
            if len(dates) >= 1: args['start_date'] = dates[0]
            if len(dates) >= 2: args['end_date'] = dates[1]
        if command in ['edit_task','update_task_status'] and dates: args['task_ref'] = dates[0]
        if command in ['update_scenario'] and dates: args['due_date'] = dates[-1]
        if command in ['edit_project'] and len(dates) >= 1: args['assigned_date'] = dates[0]
        if command in ['edit_project'] and len(dates) >= 2: args['due_date'] = dates[1]
        m = re.search(r'(?:intern|for|named|name)\s+([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){0,3})', text)
        if m and command in ['extend_intern','edit_task','update_task_status','update_capstone','update_scenario','edit_project','update_project_status','apply_plan_to_intern']:
            args['intern'] = m.group(1).strip()
        if command == 'add_intern_basic':
            m2 = re.search(r'(?:named|name|intern)\s+([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){0,3})', text)
            if m2: args['name'] = m2.group(1).strip()
        if command in ['create_plan','edit_plan','edit_plan_week','apply_plan_to_intern']:
            m3 = re.search(r'(?:plan(?: named| name)?|for)\s+([A-Za-z0-9 ._+-]+)', text, re.I)
            if m3:
                val = m3.group(1).strip().rstrip('.').split(' with ')[0]
                if val: args['plan_name'] = val
        if 'completed' in lower: args['status'] = 'Completed'
        elif 'in progress' in lower: args['status'] = 'In Progress'
        elif 'pending' in lower: args['status'] = 'Pending'
        wm = re.search(r'week\s+(\d+)', lower)
        if wm: args['week'] = int(wm.group(1))
        pm = re.search(r'project\s+#?\s*(\d+)', lower)
        if pm: args['project_number'] = int(pm.group(1))
        weeks = re.search(r'(\d+)\s+weeks?', lower)
        if weeks and command == 'create_plan': args['weeks'] = int(weeks.group(1))
        if command == 'add_holiday':
            hm = re.search(r'holiday(?: named| called)?\s+([A-Za-z0-9 ._-]+)', text, re.I)
            args['name'] = hm.group(1).strip() if hm else 'Holiday'
        if command == 'create_plan':
            args.setdefault('description', text)
        if command == 'edit_task':
            args.setdefault('task', text)
        if command == 'update_capstone':
            args.setdefault('objective', text)
        if command == 'update_scenario':
            args.setdefault('scenario', text)
        if command == 'edit_project':
            args.setdefault('description', text)

    def _defaults(self, command: str, args: dict):
        stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        if command == 'create_workbook': args.setdefault('output', f'Blank_Intern_Tracker_{stamp}.xlsx')
        elif command != 'summary': args.setdefault('output', f'{command}_{stamp}.xlsx')
        if command == 'create_plan': args.setdefault('weeks', 8); args.setdefault('plan_type', 'weekly')
        if command == 'add_holiday': args.setdefault('scope', 'global')

    def _missing(self, draft: ChatDraft) -> list[str]:
        return [k for k in REQUIRED.get(draft.command, []) if draft.args.get(k) in [None, '']]

    def _question(self, command: str, missing: list[str]) -> str:
        label = COMMAND_LABELS.get(command, command)
        return f'I can prepare **{label}**, but I need: {", ".join(missing)}. Please provide these values.'

    def _summary(self, draft: ChatDraft) -> str:
        lines = [f'Proposal: **{COMMAND_LABELS.get(draft.command, draft.command)}**', '', 'I will execute this command after approval:', '']
        for k, v in draft.args.items():
            lines.append(f'- {k}: {v}')
        lines.append('')
        lines.append('Approve this action?')
        return '\n'.join(lines)
''')

# Patch web_app routes
web_app = root/'web_app.py'
s = web_app.read_text()
if 'from tracker_chat.chat_service import ChatService' not in s:
    s = s.replace('from tracker_commands.validator import CommandValidationError\n', 'from tracker_commands.validator import CommandValidationError\nfrom tracker_chat.chat_service import ChatService\n')
if 'chat_service = ChatService()' not in s:
    s = s.replace('executor = CommandExecutor()\n', 'executor = CommandExecutor()\nchat_service = ChatService()\n')
if '@app.post("/api/chat/message")' not in s:
    s += r'''

@app.post("/api/chat/message")
def chat_message(payload: dict):
    text = payload.get('message', '')
    current_workbook = payload.get('current_workbook')
    if not text:
        return JSONResponse(status_code=400, content={'ok': False, 'error': 'message is required'})
    return chat_service.message(text, current_workbook)

@app.post("/api/chat/update")
def chat_update(payload: dict):
    return chat_service.update_draft(payload.get('draft_id'), payload.get('args') or {})

@app.post("/api/chat/approve")
def chat_approve(payload: dict):
    result = chat_service.approve(payload.get('draft_id'))
    if result.get('output_path'):
        result['download'] = f"/download/{Path(result['output_path']).name}"
    return result

@app.post("/api/chat/cancel")
def chat_cancel(payload: dict):
    return chat_service.cancel(payload.get('draft_id'))
'''
web_app.write_text(s)

# Patch web UI with chat panel
web = root/'web'/'index.html'
s = web.read_text()
if 'Chat Assistant' not in s:
    s = s.replace('main { display:grid; grid-template-columns: 290px 1fr; gap:20px; padding:20px; }', 'main { display:grid; grid-template-columns: 290px 1fr 360px; gap:20px; padding:20px; }')
    s = s.replace('</section>\n</main>', r'''</section>
  <aside class="card" style="padding:16px; height:max-content; position:sticky; top:20px;">
    <h2>Chat Assistant</h2>
    <p class="hint">Chat drafts actions first. Nothing executes until you approve.</p>
    <div id="chatLog" style="height:360px; overflow:auto; border:1px solid var(--border); border-radius:10px; padding:10px; background:#f8fafc;"></div>
    <textarea id="chatInput" placeholder="Example: create an 8 week OpenShift plan"></textarea>
    <div class="actions">
      <button class="primary" onclick="sendChat()">Send</button>
      <button class="secondary" onclick="approveChat()" id="approveBtn" disabled>Approve</button>
      <button class="secondary" onclick="cancelChat()" id="cancelBtn" disabled>Cancel</button>
    </div>
    <div id="missingFields"></div>
  </aside>
</main>''')
    chat_js = r'''
let activeDraftId = null;
function chatAppend(who, text){ const box=document.getElementById('chatLog'); const div=document.createElement('div'); div.style.margin='8px 0'; div.innerHTML=`<b>${who}:</b><br><span style="white-space:pre-wrap">${text}</span>`; box.appendChild(div); box.scrollTop=box.scrollHeight; }
async function sendChat(){ const msg=document.getElementById('chatInput').value.trim(); if(!msg) return; chatAppend('You', msg); document.getElementById('chatInput').value=''; const current=localStorage.getItem('currentWorkbook') || ''; const res=await fetch('/api/chat/message',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:msg,current_workbook:current})}); const data=await res.json(); handleChatResponse(data); }
function handleChatResponse(data){ if(!data.ok){ chatAppend('Assistant', data.error || 'Something went wrong'); return; } activeDraftId=data.draft_id; chatAppend('Assistant', data.message || JSON.stringify(data,null,2)); document.getElementById('approveBtn').disabled = data.type !== 'proposal'; document.getElementById('cancelBtn').disabled = false; renderMissing(data); }
function renderMissing(data){ const area=document.getElementById('missingFields'); area.innerHTML=''; if(data.type==='needs_more_info'){ let html='<h3>Missing info</h3>'; (data.missing||[]).forEach(k=>{ html += `<label>${k}<input name="${k}" /></label>`; }); html += '<button class="primary" onclick="submitMissing()">Update Draft</button>'; area.innerHTML=html; } }
async function submitMissing(){ const inputs=document.querySelectorAll('#missingFields input'); const args={}; inputs.forEach(i=>args[i.name]=i.value); const res=await fetch('/api/chat/update',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({draft_id:activeDraftId,args})}); const data=await res.json(); handleChatResponse(data); }
async function approveChat(){ if(!activeDraftId) return; chatAppend('You','Approved'); const res=await fetch('/api/chat/approve',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({draft_id:activeDraftId})}); const data=await res.json(); chatAppend('Assistant', JSON.stringify(data,null,2)); if(data.download) download.innerHTML=`<a href="${data.download}">Download chat output workbook</a>`; if(data.output_path) setCurrentWorkbook(data.output_path.split(/[\\/]/).pop(), true); document.getElementById('approveBtn').disabled=true; document.getElementById('cancelBtn').disabled=true; document.getElementById('missingFields').innerHTML=''; }
async function cancelChat(){ if(!activeDraftId) return; await fetch('/api/chat/cancel',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({draft_id:activeDraftId})}); chatAppend('Assistant','Draft cancelled.'); activeDraftId=null; document.getElementById('approveBtn').disabled=true; document.getElementById('cancelBtn').disabled=true; document.getElementById('missingFields').innerHTML=''; }
'''
    s = s.replace('init();', chat_js + '\ninit();')
web.write_text(s)

# README
readme = root/'README.md'
readme.write_text(readme.read_text()+r'''

## v0.14 Chat Assistant Add-on

Added an interactive chat panel to the web UI.

Flow:

1. User types a request.
2. Chat creates a draft/proposal or asks for missing info.
3. User approves.
4. Only then does the command execute using the existing `CommandExecutor`.

The chat assistant supports draft routing for all current command families, including plans, interns, holidays, task edits, project edits, summaries, rendering, and workbook creation.
''')
