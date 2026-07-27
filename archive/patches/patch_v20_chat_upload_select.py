from pathlib import Path
import re

root = Path(__file__).resolve().parent
chat = root / 'web' / 'chat.html'
if not chat.exists():
    raise SystemExit('web/chat.html not found. Apply v0.19 first, then run this patch inside intern_tracker_system_v0.')

s = chat.read_text(encoding='utf-8')

# Add styles for file controls if not already there.
if '.file-row' not in s:
    s = s.replace(".download a { color:#1d4ed8; font-weight:700; }", ".download a { color:#1d4ed8; font-weight:700; }\n    .file-row { display:flex; gap:8px; align-items:center; flex-wrap:wrap; margin:8px 0; }\n    .file-row input[type=file] { max-width:210px; }\n    select { width:100%; padding:9px; border:1px solid var(--border); border-radius:9px; background:white; }\n    .mini { padding:8px 10px; font-size:13px; }")

old_block = '''    <h2>Current Workbook</h2>
    <div class="current" id="currentWorkbook">None selected</div>
    <p class="hint">The chat uses the current workbook from the forms page. If the wrong workbook shows here, go back to Forms, upload/select the correct workbook, then return here.</p>
    <button onclick="clearCurrent()">Clear Current Workbook</button>
'''
new_block = '''    <h2>Current Workbook</h2>
    <div class="current" id="currentWorkbook">None selected</div>
    <p class="hint">Select or upload the workbook the chat should use. The selected workbook is stored as the current workbook.</p>

    <label>Workbook files
      <select id="fileSelect" onchange="selectWorkbookFromDropdown()">
        <option value="">Loading files...</option>
      </select>
    </label>
    <div class="file-row">
      <button class="mini" onclick="refreshFiles()">Refresh</button>
      <button class="mini" onclick="clearCurrent()">Clear</button>
    </div>

    <label>Upload workbook
      <input id="uploadFile" type="file" accept=".xlsx" />
    </label>
    <div class="file-row">
      <button class="primary mini" onclick="uploadWorkbook()">Upload & Select</button>
    </div>
    <div id="uploadStatus" class="hint"></div>
'''
if old_block in s:
    s = s.replace(old_block, new_block)
elif 'id="fileSelect"' not in s:
    raise SystemExit('Could not find Current Workbook block in chat.html; patch may need manual merge.')

# Replace init/helpers with file functions.
old = """function currentWorkbook(){ return localStorage.getItem('currentWorkbook') || ''; }
function setCurrentWorkbook(name){ if(name){ localStorage.setItem('currentWorkbook', name); document.getElementById('currentWorkbook').textContent = name; } }
function clearCurrent(){ localStorage.removeItem('currentWorkbook'); document.getElementById('currentWorkbook').textContent='None selected'; }
function init(){ const cw=currentWorkbook(); if(cw) document.getElementById('currentWorkbook').textContent=cw; chatAppend('assistant','Hi. Tell me what you want to do. I will prepare a proposal and wait for your approval.'); }
"""
new = """function currentWorkbook(){ return localStorage.getItem('currentWorkbook') || ''; }
function setCurrentWorkbook(name){ if(name){ localStorage.setItem('currentWorkbook', name); document.getElementById('currentWorkbook').textContent = name; const sel=document.getElementById('fileSelect'); if(sel){ sel.value=name; } } }
function clearCurrent(){ localStorage.removeItem('currentWorkbook'); document.getElementById('currentWorkbook').textContent='None selected'; const sel=document.getElementById('fileSelect'); if(sel) sel.value=''; }
async function refreshFiles(){
  const sel=document.getElementById('fileSelect');
  if(!sel) return;
  sel.innerHTML='<option value="">Loading files...</option>';
  try{
    const res=await fetch('/api/files');
    const data=await res.json();
    const all=[...(data.outputs||[]).map(x=>({name:x.name, group:'outputs'})), ...(data.uploads||[]).map(x=>({name:x.name, group:'uploads'}))];
    sel.innerHTML='<option value="">Select workbook...</option>' + all.map(x=>`<option value="${escapeHtml(x.name)}">${escapeHtml(x.group + ' / ' + x.name)}</option>`).join('');
    const cw=currentWorkbook(); if(cw) sel.value=cw;
  }catch(e){ sel.innerHTML='<option value="">Could not load files</option>'; }
}
function selectWorkbookFromDropdown(){ const val=document.getElementById('fileSelect').value; if(val) setCurrentWorkbook(val); }
async function uploadWorkbook(){
  const f=document.getElementById('uploadFile').files[0];
  if(!f){ document.getElementById('uploadStatus').textContent='Choose a .xlsx file first.'; return; }
  const fd=new FormData(); fd.append('file', f);
  const res=await fetch('/api/upload',{method:'POST', body:fd});
  const data=await res.json();
  if(data.ok){ document.getElementById('uploadStatus').textContent=`Uploaded and selected: ${data.filename}`; await refreshFiles(); setCurrentWorkbook(data.filename); }
  else { document.getElementById('uploadStatus').textContent='Upload failed.'; }
}
function init(){ const cw=currentWorkbook(); if(cw) document.getElementById('currentWorkbook').textContent=cw; refreshFiles(); chatAppend('assistant','Hi. Select or upload a workbook on the right, then tell me what you want to do. I will prepare a proposal and wait for your approval.'); }
"""
if old in s:
    s = s.replace(old, new)
elif 'async function refreshFiles' not in s:
    raise SystemExit('Could not patch JS workbook helpers; patch may need manual merge.')

chat.write_text(s, encoding='utf-8')

readme = root / 'README.md'
if readme.exists():
    readme.write_text(readme.read_text(encoding='utf-8') + r'''

## v0.20 Chat workbook selector/upload

- Added workbook dropdown to `/chat` populated from `outputs/` and `uploads/`.
- Added upload control directly on `/chat`.
- Uploading a workbook from `/chat` now sets it as the current workbook.
- Refresh button updates the workbook list without leaving the chat page.
''', encoding='utf-8')

print('v0.20 chat upload/select patch applied successfully.')
