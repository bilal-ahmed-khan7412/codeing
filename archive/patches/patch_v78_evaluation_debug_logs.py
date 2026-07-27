"""
Patch v0.78 - Evaluation scoring debug logs for F12 console

Apply from the root of the evaluation app project:
    python patch_v78_evaluation_debug_logs.py

Purpose:
- Add detailed browser console diagnostics to the /evaluation review page.
- Help identify why Weekly score is still 0 while Weekly progress is 7/8 (88%).
- This patch does NOT change scoring, rubric, final scores, or workbook writing.
- It only adds logs and a small debug helper button.
- No intern name is hardcoded.

How to use after applying:
1. Open /evaluation.
2. Press F12 > Console.
3. Look for logs prefixed with [EvalDebug v78].
4. Run this manually if needed:
   window.evalDebugV78()
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

<!-- v0.78 evaluation debug logs for F12 console -->
<style id="v78-eval-debug-style">
  .v78-debug-button {
    position: fixed;
    right: 14px;
    bottom: 14px;
    z-index: 99999;
    background: #1d4ed8;
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
<script id="v78-eval-debug-script">
(function(){
  const PREFIX = '[EvalDebug v78]';

  function norm(text){
    return String(text || '').replace(/\s+/g, ' ').trim();
  }

  function normLower(text){
    return norm(text).toLowerCase();
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
    const raw = String(text || '');
    const m = raw.match(/(\d+)\s*\/\s*(\d+)\s*\(\s*(\d+)%\s*\)/);
    if (!m) return null;
    return {
      raw: m[0],
      completed: Number(m[1]),
      total: Number(m[2]),
      percent: Number(m[3])
    };
  }

  function parseScore(text){
    const raw = String(text || '');
    const m = raw.match(/\b([0-5])\b/);
    if (!m) return null;
    return Number(m[1]);
  }

  function labelMatches(labelText, wanted){
    const l = normLower(labelText);
    const w = normLower(wanted);
    return l === w || l.endsWith(w) || l.includes(w + ' ');
  }

  function findLabelElements(wanted){
    const all = Array.from(document.querySelectorAll('body *'));
    return all.filter(el => {
      const o = ownText(el);
      const t = norm(el.textContent);
      return labelMatches(o, wanted) || labelMatches(t, wanted);
    });
  }

  function siblingTexts(el, max=6){
    const out = [];
    let next = el.nextElementSibling;
    let guard = 0;
    while(next && guard < max){
      out.push({tag: next.tagName, className: next.className, text: norm(next.textContent).slice(0, 250)});
      next = next.nextElementSibling;
      guard += 1;
    }
    return out;
  }

  function closestRowInfo(el){
    const row = el.closest('tr, .row, .score-row, .basis-row, .field-row, li, p, div');
    if (!row) return null;
    return {
      tag: row.tagName,
      className: row.className,
      dataset: {...row.dataset},
      text: norm(row.textContent).slice(0, 500),
      html: row.outerHTML.slice(0, 1000)
    };
  }

  function findValueNear(label){
    const els = findLabelElements(label);
    const results = [];
    for (const el of els){
      const row = closestRowInfo(el);
      let progress = row ? parseProgress(row.text) : null;
      let score = row ? parseScore(row.text.replace(norm(el.textContent), '')) : null;

      let nextProgress = null;
      let nextScore = null;
      let next = el.nextElementSibling;
      let guard = 0;
      while(next && guard < 6){
        const t = norm(next.textContent);
        if (!nextProgress) nextProgress = parseProgress(t);
        if (nextScore === null) nextScore = parseScore(t);
        next = next.nextElementSibling;
        guard += 1;
      }

      results.push({
        label,
        element: {
          tag: el.tagName,
          className: el.className,
          dataset: {...el.dataset},
          ownText: ownText(el),
          text: norm(el.textContent).slice(0, 500)
        },
        row,
        siblingTexts: siblingTexts(el),
        progress: progress || nextProgress,
        score: score !== null ? score : nextScore
      });
    }
    return results;
  }

  function findInputLike(label){
    const labels = findLabelElements(label);
    const candidates = [];
    for (const el of labels){
      const row = el.closest('tr, .row, .score-row, .basis-row, .field-row, li, p, div') || el.parentElement;
      if (!row) continue;
      row.querySelectorAll('input, textarea, select').forEach(inp => {
        candidates.push({
          label,
          tag: inp.tagName,
          type: inp.getAttribute('type'),
          name: inp.getAttribute('name'),
          id: inp.id,
          className: inp.className,
          value: inp.value,
          dataset: {...inp.dataset}
        });
      });
    }
    return candidates;
  }

  function collectGlobals(){
    const keys = Object.keys(window).filter(k => /eval|score|weekly|daily|rubric|review/i.test(k)).sort();
    const sample = {};
    for (const k of keys.slice(0, 80)){
      try{
        const v = window[k];
        if (typeof v === 'function') sample[k] = '[function]';
        else if (typeof v === 'object') sample[k] = v === null ? null : '[object]';
        else sample[k] = v;
      }catch(e){ sample[k] = '[unreadable]'; }
    }
    return {count: keys.length, keys, sample};
  }

  function collectStorage(){
    const out = {localStorage:{}, sessionStorage:{}};
    try{
      for(let i=0;i<localStorage.length;i++){
        const k = localStorage.key(i);
        if(/eval|score|weekly|daily|rubric|review/i.test(k)) out.localStorage[k] = localStorage.getItem(k);
      }
    }catch(e){}
    try{
      for(let i=0;i<sessionStorage.length;i++){
        const k = sessionStorage.key(i);
        if(/eval|score|weekly|daily|rubric|review/i.test(k)) out.sessionStorage[k] = sessionStorage.getItem(k);
      }
    }catch(e){}
    return out;
  }

  function collectScorePayloadFromForms(){
    const fields = [];
    document.querySelectorAll('input, textarea, select').forEach(el => {
      const name = el.getAttribute('name') || '';
      const id = el.id || '';
      const cls = el.className || '';
      const ds = JSON.stringify(el.dataset || {});
      if(/score|weekly|daily|rubric|criterion|final/i.test(name + ' ' + id + ' ' + cls + ' ' + ds)){
        fields.push({tag:el.tagName,type:el.getAttribute('type'),name,id,className:cls,value:el.value,dataset:{...el.dataset}});
      }
    });
    return fields;
  }

  function debugEvaluationScoring(){
    const dailyProgress = findValueNear('Daily progress').concat(findValueNear('Overall daily'));
    const weeklyProgress = findValueNear('Weekly progress').concat(findValueNear('Overall weekly'));
    const dailyScore = findValueNear('Daily score');
    const weeklyScore = findValueNear('Weekly score');
    const selectedWeekly = findValueNear('Selected weekly');
    const tillNowWeekly = findValueNear('Till-now weekly').concat(findValueNear('Till now weekly'));
    const selectedDaily = findValueNear('Selected daily');
    const tillNowDaily = findValueNear('Till-now daily').concat(findValueNear('Till now daily'));

    const weeklyProgressValue = weeklyProgress.map(x => x.progress).find(Boolean);
    const weeklyScoreValue = weeklyScore.map(x => x.score).find(v => v !== null && v !== undefined);

    console.group(PREFIX + ' Scoring diagnostics');
    console.log('Visible Daily progress / Overall daily matches:', dailyProgress);
    console.log('Visible Weekly progress / Overall weekly matches:', weeklyProgress);
    console.log('Visible Daily score matches:', dailyScore);
    console.log('Visible Weekly score matches:', weeklyScore);
    console.log('Hidden/old Selected weekly matches:', selectedWeekly);
    console.log('Hidden/old Till-now weekly matches:', tillNowWeekly);
    console.log('Hidden/old Selected daily matches:', selectedDaily);
    console.log('Hidden/old Till-now daily matches:', tillNowDaily);
    console.log('Score-related form fields:', collectScorePayloadFromForms());
    console.log('Score-related inputs near Daily score:', findInputLike('Daily score'));
    console.log('Score-related inputs near Weekly score:', findInputLike('Weekly score'));
    console.log('Relevant window globals:', collectGlobals());
    console.log('Relevant storage:', collectStorage());

    if(weeklyProgressValue && weeklyProgressValue.total > 0 && weeklyProgressValue.percent >= 70 && Number(weeklyScoreValue) === 0){
      console.warn(PREFIX + ' BUG CONFIRMED: Weekly progress is high but Weekly score is 0. This strongly suggests Weekly score is sourced from selected/till-now weekly or stale payload, not overall weekly.', {
        weeklyProgressValue,
        weeklyScoreValue,
        selectedWeekly,
        tillNowWeekly
      });
    }
    console.groupEnd();

    return {
      dailyProgress,
      weeklyProgress,
      dailyScore,
      weeklyScore,
      selectedWeekly,
      tillNowWeekly,
      selectedDaily,
      tillNowDaily,
      fields: collectScorePayloadFromForms(),
      globals: collectGlobals(),
      storage: collectStorage()
    };
  }

  function installFetchLogger(){
    if(window.__evalDebugV78FetchInstalled) return;
    window.__evalDebugV78FetchInstalled = true;
    const originalFetch = window.fetch;
    window.fetch = async function(input, init){
      const url = typeof input === 'string' ? input : (input && input.url) || '';
      const method = (init && init.method) || 'GET';
      const body = init && init.body;
      const interested = /eval|score|final|review|workbook/i.test(url) || (body && /score|weekly|daily|rubric|criterion/i.test(String(body)));
      if(interested){
        console.group(PREFIX + ' fetch request');
        console.log('method:', method);
        console.log('url:', url);
        if(body){
          try{ console.log('body parsed:', JSON.parse(body)); }
          catch(e){ console.log('body raw:', String(body).slice(0, 3000)); }
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
          try{ console.log('json:', JSON.parse(text)); }
          catch(e){ console.log('text:', text.slice(0, 3000)); }
          console.groupEnd();
        }catch(e){
          console.warn(PREFIX + ' could not inspect fetch response', e);
        }
      }
      return response;
    };
  }

  function addDebugButton(){
    if(document.getElementById('v78EvalDebugButton')) return;
    const btn = document.createElement('button');
    btn.id = 'v78EvalDebugButton';
    btn.className = 'v78-debug-button';
    btn.type = 'button';
    btn.textContent = 'Eval Debug';
    btn.onclick = function(){ debugEvaluationScoring(); };
    document.body.appendChild(btn);
  }

  window.evalDebugV78 = debugEvaluationScoring;
  installFetchLogger();

  function boot(){
    addDebugButton();
    setTimeout(debugEvaluationScoring, 200);
    setTimeout(debugEvaluationScoring, 1000);
  }

  document.addEventListener('DOMContentLoaded', boot);
  setTimeout(boot, 500);
})();
</script>
'''

if 'v78-eval-debug-script' not in html:
    if '</body>' in html:
        html = html.replace('</body>', block + '\n</body>', 1)
    else:
        html += block
    page.write_text(html, encoding='utf-8')
    print('v0.78 patch applied: evaluation debug logs added.')
else:
    print('v0.78 patch already applied.')
print(f'Updated: {page}')
