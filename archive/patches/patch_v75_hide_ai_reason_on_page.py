"""
Patch v0.75 - Hide AI rationale/reason text from evaluation review page

Apply from the root of the evaluation app project:
    python patch_v75_hide_ai_reason_on_page.py

Purpose:
- Admin should view/edit final scores before workbook write.
- AI reasoning/rationale should NOT be shown on the page.
- Workbook is still not updated until Finalize Evaluation is clicked.

This patch is UI-only and does not hardcode any intern name.
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

<!-- v0.75 hide AI rationale/reason on page -->
<style id="v75-hide-ai-reason-style">
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
</style>
<script id="v75-hide-ai-reason-script">
(function(){
  function isReasonLabelText(text){
    const t = String(text || '').trim().toLowerCase();
    return t === 'reason shown on page only'
        || t === 'ai reason'
        || t === 'ai rationale'
        || t === 'rationale shown on page only';
  }

  function looksLikeReasonText(text){
    const t = String(text || '').trim().toLowerCase();
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
        .filter(n => n.nodeType === Node.TEXT_NODE)
        .map(n => n.textContent)
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

  // Hide now, after normal renders, and after dynamic question/review updates.
  document.addEventListener('DOMContentLoaded', hideReasonBlocks);
  setTimeout(hideReasonBlocks, 100);
  setTimeout(hideReasonBlocks, 500);
  const mo = new MutationObserver(hideReasonBlocks);
  mo.observe(document.documentElement, {childList:true, subtree:true});
})();
</script>
'''

if "v75-hide-ai-reason-script" not in html:
    if "</body>" in html:
        html = html.replace("</body>", block + "\n</body>", 1)
    else:
        html += block
    page.write_text(html, encoding="utf-8")
    print("v0.75 patch applied: AI reason/rationale hidden from evaluation page.")
else:
    print("v0.75 patch already applied.")
print(f"Updated: {page}")
