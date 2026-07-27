"""
Patch v0.80 - Force evaluation questions request to overall basis

Apply from the root of the evaluation app project:
    python patch_v80_evaluation_force_overall_basis.py

Purpose:
- Fix the confirmed bug where /api/evaluation/questions is still called with basis='as_of'.
- Do NOT change rubric.
- Do NOT change scoring method.
- Only change the scoring basis sent to the backend from as_of/till-now to overall.
- This makes backend metrics weekly_done/weekly_planned/weekly_score come from overall weekly data.
- Workbook is still not updated until Finalize Evaluation is clicked.

Confirmed from F12 logs:
    request body: basis: 'as_of'
    response metrics: weekly_done=0, weekly_planned=0, weekly_score=0
    response metrics: overall_weekly_done=7, overall_weekly_planned=8, overall_weekly_pct=0.875

So the root issue is not the rubric. The API request still asks for as_of scoring.
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

<!-- v0.80 force overall evaluation basis before questions API call -->
<script id="v80-force-overall-basis-script">
(function(){
  const PREFIX = '[Eval v80]';

  function setBasisControlsToOverall(){
    document.querySelectorAll('select[name="basis"], input[name="basis"], select#basis, input#basis').forEach(function(el){
      try {
        el.value = 'overall';
        el.setAttribute('data-v80-forced-overall', 'true');
      } catch(e) {}
    });
  }

  function forceOverallInBody(init){
    if(!init || !init.body) return init;
    if(init.body instanceof FormData) return init;
    try {
      const parsed = JSON.parse(init.body);
      if(parsed && typeof parsed === 'object'){
        const before = parsed.basis;
        parsed.basis = 'overall';
        init = Object.assign({}, init, {body: JSON.stringify(parsed)});
        if(before !== 'overall'){
          console.info(PREFIX, 'Changed /api/evaluation/questions basis from', before, 'to overall. Rubric/scoring method unchanged.');
        }
      }
    } catch(e) {
      // Body was not JSON. Leave it unchanged.
    }
    return init;
  }

  function patchFetch(){
    if(window.__v80ForceOverallFetchPatched) return;
    window.__v80ForceOverallFetchPatched = true;
    const originalFetch = window.fetch;
    window.fetch = async function(input, init){
      const url = typeof input === 'string' ? input : (input && input.url) || '';
      if(String(url).includes('/api/evaluation/questions')){
        init = forceOverallInBody(init || {});
      }
      const response = await originalFetch.apply(this, [input, init]);
      if(String(url).includes('/api/evaluation/questions')){
        try {
          const clone = response.clone();
          const data = await clone.json();
          if(data && data.metrics){
            console.info(PREFIX, 'questions metrics after forcing overall:', {
              basis: data.metrics.basis,
              weekly_done: data.metrics.weekly_done,
              weekly_planned: data.metrics.weekly_planned,
              weekly_pct: data.metrics.weekly_pct,
              weekly_score: data.metrics.weekly_score,
              overall_weekly_done: data.metrics.overall_weekly_done,
              overall_weekly_planned: data.metrics.overall_weekly_planned,
              overall_weekly_pct: data.metrics.overall_weekly_pct
            });
          }
        } catch(e) {}
      }
      return response;
    };
  }

  function boot(){
    setBasisControlsToOverall();
    patchFetch();
  }

  // Install immediately while page scripts are still loading.
  boot();
  document.addEventListener('DOMContentLoaded', boot);
  setTimeout(boot, 100);
  setTimeout(boot, 500);
})();
</script>
'''

if "v80-force-overall-basis-script" not in html:
    # Place as early as possible in body to patch fetch before the app sends evaluation/questions.
    if "<body" in html:
      # Insert right after opening body tag.
      body_start = html.find("<body")
      body_close = html.find(">", body_start)
      if body_close != -1:
          html = html[:body_close + 1] + block + html[body_close + 1:]
      else:
          html += block
    elif "</body>" in html:
        html = html.replace("</body>", block + "\n</body>", 1)
    else:
        html += block
    page.write_text(html, encoding="utf-8")
    print("v0.80 patch applied: /api/evaluation/questions will request overall basis.")
else:
    print("v0.80 patch already applied.")

print(f"Updated: {page}")
