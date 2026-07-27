"""
Patch v0.79 - Deeper evaluation score-source debug logs

Apply from the root of the evaluation app project:
    python patch_v79_evaluation_deeper_score_debug.py

Purpose:
- The v0.78 logs matched SCRIPT elements and did not expose the actual scoreSources/renderReview/suggestScore values clearly.
- Add cleaner diagnostics that ignore SCRIPT/STYLE tags.
- Print expanded JSON strings for scoreSources, API responses, and scoring-related globals.
- Monkey-patch suggestScore and renderReview to show the arguments/results used by the page.
- Does NOT change rubric, scores, workbook writing, or finalize behavior.

After applying:
1. Open /evaluation.
2. Press F12 > Console.
3. Run: window.evalDebugV79()
4. Copy the console output, especially:
   - scoreSources expanded
   - suggestScore calls
   - renderReview calls
   - /api/evaluation/questions response
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent
PAGE_CANDIDATES = [
    ROOT / "web" / "evaluation.html",
    ROOT / "evaluation.html",
    ROOT / "templates" / "evaluation.html",
]

page = next((p for p in PAGE_CANDIDATES if p.exists()), None)
if page is None:
    raise SystemExit("Could not find evaluation.html. Run this patch from the evaluation app root folder.")

html = page.read_text(encoding="utf-8")

block = r'''

<!-- v0.79 deeper evaluation score-source debug -->
<style id="v79-eval-debug-style">
  .v79-debug-button {
    position: fixed;
    right: 14px;
    bottom: 54px;
    z-index: 99999;
    background: #7c3aed;
    color: white;
    border: none;
    border-radius: 10px;
    padding: 9px 12px;
    font-weight: 700;
    cursor: pointer;
    box-shadow: 0 4px 14px rgba(15, 23, 42, 0.22);
    font-size: 12px;
  }
</style>
<script id="v79-eval-debug-script">
(function(){
  const PREFIX = '[EvalDebug v79]';

  function safeJson(value){
    try { return JSON.stringify(value, null, 2); }
    catch(e){ return String(value); }
  }

  function norm(text){
    return String(text || '').replace(/\s+/g, ' ').trim();
  }

  function normLower(text){
    return norm(text).toLowerCase();
  }

  function visibleElements(){
    return Array.from(document.querySelectorAll('body *')).filter(el => {
      const tag = el.tagName;
      if(tag === 'SCRIPT' || tag === 'STYLE' || tag === 'NOSCRIPT') return false;
      const style = window.getComputedStyle(el);
      return style.display !== 'none' && style.visibility !== 'hidden';
    });
  }

  function ownText(el){
    return Array.from(el.childNodes)
      .filter(n => n.nodeType === Node.TEXT_NODE)
      .map(n => n.textContent)
      .join(' ')
      .replace(/\s+/g, ' ')
      .trim();
  }

  function parseProgress(text){
    const m = String(text || '').match(/(\d+)\s*\/\s*(\d+)\s*\(\s*(\d+)%\s*\)/);
    if(!m) return null;
    return {raw:m[0], completed:Number(m[1]), total:Number(m[2]), percent:Number(m[3])};
  }

  function parseScore(text){
    const m = String(text || '').match(/\b([0-5])\b/);
    return m ? Number(m[1]) : null;
  }

  function labelEqualsOrContains(labelText, wanted){
    const text = normLower(labelText);
    const w = normLower(wanted);
    return text === w || text.startsWith(w + ' ') || text.includes(w + ' ');
  }

  function findLabelElements(wanted){
    return visibleElements().filter(el => {
      const o = ownText(el);
      const t = norm(el.textContent || '');
      return labelEqualsOrContains(o, wanted) || labelEqualsOrContains(t, wanted);
    });
  }

  function findNear(label){
    const els = findLabelElements(label);
    return els.map(el => {
      const row = el.closest('tr, .row, .score-row, .basis-row, .field-row, li, p, div');
      const rowText = row ? norm(row.textContent) : '';
      const next = [];
      let n = el.nextElementSibling;
      let guard = 0;
      while(n && guard < 5){
        if(!['SCRIPT','STYLE','NOSCRIPT'].includes(n.tagName)){
          next.push({tag:n.tagName,className:n.className,text:norm(n.textContent).slice(0,300)});
        }
        n = n.nextElementSibling;
        guard++;
      }
      return {
        label,
        element:{tag:el.tagName,className:el.className,ownText:ownText(el),text:norm(el.textContent).slice(0,300),dataset:{...el.dataset}},
        row:{tag:row && row.tagName,className:row && row.className,text:rowText.slice(0,500),progress:parseProgress(rowText),score:parseScore(rowText)},
        next
      };
    });
  }

  function collectScoreInputs(){
    return Array.from(document.querySelectorAll('input, textarea, select')).map(el => ({
      tag:el.tagName,
      type:el.getAttribute('type'),
      name:el.getAttribute('name'),
      id:el.id,
      className:el.className,
      value:el.value,
      dataset:{...el.dataset},
      nearestText: norm((el.closest('tr, .row, .score-row, .field-row, .basis-row, div, p, li') || el.parentElement || el).textContent).slice(0,500)
    })).filter(x => /score|weekly|daily|criterion|rubric|final/i.test([x.name,x.id,x.className,JSON.stringify(x.dataset),x.nearestText].join(' ')));
  }

  function collectGlobals(){
    const names = ['scoreSources','suggestScore','renderReview','finalizeEval'];
    const out = {};
    for(const name of names){
      try{
        const value = window[name];
        if(typeof value === 'function') out[name] = value.toString().slice(0,5000);
        else out[name] = value;
      }catch(e){ out[name] = '[unreadable: '+e.message+']'; }
    }
    return out;
  }

  function debug(){
    const info = {
      visibleDailyProgress: findNear('Daily progress').concat(findNear('Overall daily')),
      visibleWeeklyProgress: findNear('Weekly progress').concat(findNear('Overall weekly')),
      visibleDailyScore: findNear('Daily score'),
      visibleWeeklyScore: findNear('Weekly score'),
      oldSelectedWeekly: findNear('Selected weekly'),
      oldTillNowWeekly: findNear('Till-now weekly').concat(findNear('Till now weekly')),
      scoreInputs: collectScoreInputs(),
      globals: collectGlobals(),
      localStorage: {...localStorage},
      sessionStorage: {...sessionStorage}
    };
    console.group(PREFIX + ' expanded diagnostics');
    console.log('Expanded JSON copy below:');
    console.log(safeJson(info));
    console.log('Raw object:', info);
    console.groupEnd();
    return info;
  }

  function patchFunction(name){
    if(window['__v79Patched_' + name]) return;
    const fn = window[name];
    if(typeof fn !== 'function') return;
    window['__v79Original_' + name] = fn;
    window['__v79Patched_' + name] = true;
    window[name] = function(){
      console.group(PREFIX + ' function call: ' + name);
      console.log('arguments:', Array.from(arguments));
      try{
        const result = fn.apply(this, arguments);
        console.log('result:', result);
        console.groupEnd();
        return result;
      }catch(e){
        console.error('error:', e);
        console.groupEnd();
        throw e;
      }
    };
    console.log(PREFIX + ' patched function:', name);
  }

  function patchKnownFunctions(){
    patchFunction('suggestScore');
    patchFunction('renderReview');
    patchFunction('finalizeEval');
  }

  function patchFetch(){
    if(window.__v79FetchPatched) return;
    window.__v79FetchPatched = true;
    const originalFetch = window.fetch;
    window.fetch = async function(input, init){
      const url = typeof input === 'string' ? input : (input && input.url) || '';
      const method = (init && init.method) || 'GET';
      const body = init && init.body;
      const interested = /evaluation|eval|score|review|questions|final/i.test(url) || (body && /score|weekly|daily|rubric|criterion/i.test(String(body)));
      if(interested){
        console.group(PREFIX + ' fetch request');
        console.log('method:', method);
        console.log('url:', url);
        if(body instanceof FormData){
          const form = {};
          for(const [k,v] of body.entries()) form[k] = (v && v.name) ? '[File '+v.name+']' : String(v);
          console.log('formData:', form);
        }else if(body){
          try{ console.log('body JSON:', JSON.parse(body)); }
          catch(e){ console.log('body raw:', String(body).slice(0,5000)); }
        }
        console.groupEnd();
      }
      const response = await originalFetch.apply(this, arguments);
      if(interested){
        try{
          const clone = response.clone();
          const text = await clone.text();
          console.group(PREFIX + ' fetch response');
          console.log('url:', url);
          console.log('status:', response.status);
          try{ console.log('JSON:', JSON.parse(text)); console.log('JSON string:', JSON.stringify(JSON.parse(text), null, 2)); }
          catch(e){ console.log('text:', text.slice(0,5000)); }
          console.groupEnd();
        }catch(e){ console.warn(PREFIX + ' response inspect failed', e); }
      }
      return response;
    };
  }

  function addButton(){
    if(document.getElementById('v79EvalDebugButton')) return;
    const btn = document.createElement('button');
    btn.id = 'v79EvalDebugButton';
    btn.className = 'v79-debug-button';
    btn.type = 'button';
    btn.textContent = 'Eval Debug+JSON';
    btn.onclick = debug;
    document.body.appendChild(btn);
  }

  window.evalDebugV79 = debug;
  patchFetch();

  function boot(){
    addButton();
    patchKnownFunctions();
    setTimeout(patchKnownFunctions, 300);
    setTimeout(debug, 1000);
  }

  document.addEventListener('DOMContentLoaded', boot);
  setTimeout(boot, 500);
})();
</script>
'''

if 'v79-eval-debug-script' not in html:
    if '</body>' in html:
        html = html.replace('</body>', block + '\n</body>', 1)
    else:
        html += block
    page.write_text(html, encoding='utf-8')
    print('v0.79 patch applied: deeper evaluation score debug added.')
else:
    print('v0.79 patch already applied.')
print(f'Updated: {page}')
