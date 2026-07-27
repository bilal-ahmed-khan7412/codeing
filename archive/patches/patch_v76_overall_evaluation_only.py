"""
Patch v0.76 - Overall-only evaluation review page

Apply from the root of the evaluation app project:
    python patch_v76_overall_evaluation_only.py

Purpose:
- Drop till-now/selected evaluation from the review page.
- Show only overall daily and overall weekly progress.
- Hide confusing 0/0 selected/till-now weekly rows.
- Keep Admin editable scores before workbook write.
- Keep workbook unchanged until Finalize Evaluation is clicked.
- Continue hiding AI rationale/reason text from the page.
- UI-focused patch, does not hardcode intern names.
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

<!-- v0.76 overall-only evaluation review page -->
<style id="v76-overall-eval-style">
  /* Hide till-now / selected evaluation rows and labels */
  .till-now,
  .tillnow,
  .selected-daily,
  .selected-weekly,
  .till-now-daily,
  .till-now-weekly,
  .tillnow-daily,
  .tillnow-weekly,
  [data-scope="till-now"],
  [data-scope="selected"],
  [data-eval-scope="till-now"],
  [data-eval-scope="selected"],
  [data-score-key="selected_daily"],
  [data-score-key="selected_weekly"],
  [data-score-key="till_now_daily"],
  [data-score-key="till_now_weekly"] {
    display: none !important;
  }

  /* Keep AI/private reasoning hidden from Admin review page */
  .ai-reason,
  .ai-rationale,
  .reason,
  .reason-text,
  .rationale,
  .rationale-text,
  [data-ai-reason],
  [data-reason],
  [data-rationale] {
    display: none !important;
  }

  .v76-overall-card {
    border: 1px solid #d9e2ef;
    border-radius: 12px;
    background: #ffffff;
    padding: 14px;
    margin: 12px 0;
    box-shadow: 0 2px 10px rgba(15, 23, 42, 0.05);
  }

  .v76-overall-card h3 {
    margin: 0 0 10px;
    color: #1f3f75;
  }

  .v76-progress-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(220px, 1fr));
    gap: 12px;
  }

  .v76-progress-tile {
    border: 1px solid #e5e7eb;
    border-radius: 10px;
    padding: 12px;
    background: #f8fafc;
  }

  .v76-progress-title {
    font-weight: 700;
    color: #334155;
    margin-bottom: 6px;
  }

  .v76-progress-value {
    font-size: 18px;
    font-weight: 800;
    color: #0f172a;
  }

  .v76-progress-note {
    font-size: 12px;
    color: #64748b;
    margin-top: 6px;
  }

  @media (max-width: 760px) {
    .v76-progress-grid {
      grid-template-columns: 1fr;
    }
  }
</style>
<script id="v76-overall-eval-script">
(function(){
  function textOf(el){ return String((el && el.textContent) || '').trim(); }
  function normalized(text){ return String(text || '').replace(/\s+/g, ' ').trim().toLowerCase(); }

  function stripLexicalStrongTags(){
    // If rich-text copied markup appears as actual elements, replace strong text safely.
    document.querySelectorAll('strong[data-lexical-text="true"]').forEach(function(el){
      const span = document.createElement('span');
      span.textContent = el.textContent || '';
      span.style.fontWeight = '700';
      el.replaceWith(span);
    });
  }

  function isHiddenScoringLabel(t){
    t = normalized(t);
    return t === 'till now'
        || t.startsWith('till now / as of')
        || t === 'selected daily'
        || t === 'selected weekly'
        || t === 'till-now daily'
        || t === 'till-now weekly'
        || t === 'till now daily'
        || t === 'till now weekly';
  }

  function isOverallDailyLabel(t){
    t = normalized(t);
    return t === 'overall daily' || t === 'daily progress';
  }

  function isOverallWeeklyLabel(t){
    t = normalized(t);
    return t === 'overall weekly' || t === 'weekly progress';
  }

  function looksLikePercentValue(t){
    t = normalized(t);
    return /^\d+\s*\/\s*\d+\s*\(\s*\d+%\s*\)$/.test(t)
        || /^\d+\s*\/\s*\d+$/.test(t);
  }

  function hideElementAndNearbyValue(el){
    if (!el) return;
    el.style.display = 'none';

    // Hide closest row/card item if it appears to be a compact key-value row.
    const row = el.closest('tr, .row, .score-row, .basis-row, .field-row, li, p, div');
    if (row && row !== document.body) {
      const rowText = normalized(row.textContent);
      if (rowText.includes('selected daily') || rowText.includes('selected weekly') || rowText.includes('till-now') || rowText.includes('till now')) {
        row.style.display = 'none';
        return;
      }
    }

    // Hide next few siblings if they contain the matching count/percent value, including 0/0.
    let next = el.nextElementSibling;
    let guard = 0;
    while (next && guard < 3) {
      const nt = textOf(next);
      if (looksLikePercentValue(nt) || normalized(nt) === '0/0 (0%)' || normalized(nt) === '0/0') {
        next.style.display = 'none';
        next = next.nextElementSibling;
        guard += 1;
      } else {
        break;
      }
    }
  }

  function collectOverallValues(){
    let daily = '';
    let weekly = '';
    const all = Array.from(document.querySelectorAll('body *'));

    for (const el of all) {
      const ownText = Array.from(el.childNodes)
        .filter(function(n){ return n.nodeType === Node.TEXT_NODE; })
        .map(function(n){ return n.textContent; })
        .join(' ')
        .trim();
      const allText = textOf(el);

      if (isOverallDailyLabel(ownText) || isOverallDailyLabel(allText)) {
        const value = findSiblingValue(el);
        if (value) daily = value;
      }
      if (isOverallWeeklyLabel(ownText) || isOverallWeeklyLabel(allText)) {
        const value = findSiblingValue(el);
        if (value) weekly = value;
      }
    }
    return {daily: daily, weekly: weekly};
  }

  function findSiblingValue(el){
    // Try same row first.
    const row = el.closest('tr, .row, .score-row, .basis-row, .field-row, li, p, div');
    if (row) {
      const cells = Array.from(row.querySelectorAll('td, span, strong, b, div'));
      for (const c of cells) {
        const t = textOf(c);
        if (looksLikePercentValue(t)) return t;
      }
      const rowText = textOf(row);
      const m = rowText.match(/\d+\s*\/\s*\d+\s*\(\s*\d+%\s*\)/);
      if (m) return m[0];
    }

    // Then try next siblings.
    let next = el.nextElementSibling;
    let guard = 0;
    while (next && guard < 4) {
      const t = textOf(next);
      if (looksLikePercentValue(t)) return t;
      const m = t.match(/\d+\s*\/\s*\d+\s*\(\s*\d+%\s*\)/);
      if (m) return m[0];
      next = next.nextElementSibling;
      guard += 1;
    }
    return '';
  }

  function hideTillNowAndSelectedRows(){
    const all = Array.from(document.querySelectorAll('body *'));
    for (const el of all) {
      const ownText = Array.from(el.childNodes)
        .filter(function(n){ return n.nodeType === Node.TEXT_NODE; })
        .map(function(n){ return n.textContent; })
        .join(' ')
        .trim();
      if (isHiddenScoringLabel(ownText) || isHiddenScoringLabel(el.textContent)) {
        hideElementAndNearbyValue(el);
      }
    }
  }

  function relabelOverallRows(){
    const all = Array.from(document.querySelectorAll('body *'));
    for (const el of all) {
      const ownText = Array.from(el.childNodes)
        .filter(function(n){ return n.nodeType === Node.TEXT_NODE; })
        .map(function(n){ return n.textContent; })
        .join(' ')
        .trim();

      if (normalized(ownText) === 'overall daily') {
        el.textContent = 'Daily progress';
      }
      if (normalized(ownText) === 'overall weekly') {
        el.textContent = 'Weekly progress';
      }
    }
  }

  function removeExistingOverallCard(){
    document.querySelectorAll('.v76-overall-card').forEach(function(el){ el.remove(); });
  }

  function insertCleanOverallCard(){
    const vals = collectOverallValues();
    if (!vals.daily && !vals.weekly) return;

    removeExistingOverallCard();

    const card = document.createElement('div');
    card.className = 'v76-overall-card';
    card.innerHTML = ''
      + '<h3>Scoring basis</h3>'
      + '<div class="v76-progress-grid">'
      + '  <div class="v76-progress-tile">'
      + '    <div class="v76-progress-title">Daily progress</div>'
      + '    <div class="v76-progress-value">' + escapeHtml(vals.daily || 'Not available') + '</div>'
      + '    <div class="v76-progress-note">Overall daily task completion across the workbook.</div>'
      + '  </div>'
      + '  <div class="v76-progress-tile">'
      + '    <div class="v76-progress-title">Weekly progress</div>'
      + '    <div class="v76-progress-value">' + escapeHtml(vals.weekly || 'Not available') + '</div>'
      + '    <div class="v76-progress-note">Overall weekly/project completion across the workbook.</div>'
      + '  </div>'
      + '</div>';

    const scoringTitle = Array.from(document.querySelectorAll('body *')).find(function(el){
      return normalized(el.textContent) === 'scoring basis';
    });

    if (scoringTitle && scoringTitle.parentElement) {
      scoringTitle.parentElement.insertBefore(card, scoringTitle.nextSibling);
    } else {
      const target = document.querySelector('main') || document.body;
      target.insertBefore(card, target.firstChild);
    }
  }

  function escapeHtml(value){
    return String(value || '').replace(/[&<>\"]/g, function(c){
      return {'&':'&amp;', '<':'&lt;', '>':'&gt;', '\"':'&quot;'}[c];
    });
  }

  // Keep v0.75 reason hiding behavior active too.
  function isReasonLabelText(text){
    const t = normalized(text);
    return t === 'reason shown on page only'
        || t === 'ai reason'
        || t === 'ai rationale'
        || t === 'rationale shown on page only';
  }

  function looksLikeReasonText(text){
    const t = normalized(text);
    if (!t) return false;
    return t.startsWith('the evaluator')
        || t.startsWith('score ')
        || t.includes('because the evaluator answer')
        || t.includes('warranting a score')
        || t.includes('admin should confirm')
        || t.includes('reasonable to infer');
  }

  function hideReasonBlocks(){
    const all = Array.from(document.querySelectorAll('body *'));
    for (const el of all) {
      const ownText = Array.from(el.childNodes)
        .filter(function(n){ return n.nodeType === Node.TEXT_NODE; })
        .map(function(n){ return n.textContent; })
        .join(' ')
        .trim();

      if (isReasonLabelText(ownText) || isReasonLabelText(el.textContent)) {
        el.style.display = 'none';
        let next = el.nextElementSibling;
        let guard = 0;
        while (next && guard < 3) {
          const nt = (next.textContent || '').trim();
          if (looksLikeReasonText(nt)) {
            next.style.display = 'none';
            next = next.nextElementSibling;
            guard += 1;
          } else {
            break;
          }
        }
      }
    }
  }

  function applyOverallOnlyEvaluationView(){
    stripLexicalStrongTags();
    relabelOverallRows();
    hideTillNowAndSelectedRows();
    hideReasonBlocks();
    insertCleanOverallCard();
  }

  document.addEventListener('DOMContentLoaded', applyOverallOnlyEvaluationView);
  setTimeout(applyOverallOnlyEvaluationView, 100);
  setTimeout(applyOverallOnlyEvaluationView, 500);
  setTimeout(applyOverallOnlyEvaluationView, 1200);

  const mo = new MutationObserver(function(){
    clearTimeout(window.__v76OverallEvalTimer);
    window.__v76OverallEvalTimer = setTimeout(applyOverallOnlyEvaluationView, 80);
  });
  mo.observe(document.documentElement, {childList:true, subtree:true});
})();
</script>
'''

if "v76-overall-eval-script" not in html:
    if "</body>" in html:
        html = html.replace("</body>", block + "\n</body>", 1)
    else:
        html += block
    page.write_text(html, encoding="utf-8")
    print("v0.76 patch applied: evaluation page now shows overall-only scoring basis.")
else:
    print("v0.76 patch already applied.")
print(f"Updated: {page}")
