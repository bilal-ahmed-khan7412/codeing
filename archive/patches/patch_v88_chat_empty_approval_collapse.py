"""
Patch v0.88 - Hard collapse empty Review & Approval area on /chat

Apply from intern_tracker_system_v0 root:
    python patch_v88_chat_empty_approval_collapse.py

Purpose:
- v0.87 did not fully collapse the empty Review & Approval area on some chat page layouts.
- This patch uses stronger DOM detection:
  - find "Review & Approval"
  - find "No active proposal yet."
  - find "Current Workbook"
  - collapse only the empty approval area between Review & Approval and Current Workbook
- Keep real active proposals expandable.
- Do not change backend logic, approval rules, or workbook execution.
"""
from __future__ import annotations

from pathlib import Path
import textwrap

ROOT = Path(__file__).resolve().parent
CHAT_HTML_CANDIDATES = [ROOT / "web" / "chat.html", ROOT / "chat.html", ROOT / "templates" / "chat.html"]
README = ROOT / "README.md"

chat_html = next((p for p in CHAT_HTML_CANDIDATES if p.exists()), None)
if chat_html is None:
    raise SystemExit("Could not find chat.html. Run this patch from intern_tracker_system_v0 root folder.")

html = chat_html.read_text(encoding="utf-8")

block = r'''

<!-- v0.88 hard collapse empty Review & Approval area -->
<style id="v88-chat-empty-approval-collapse-style">
  .v88-empty-approval-area {
    height: auto !important;
    min-height: 0 !important;
    max-height: 115px !important;
    overflow: hidden !important;
    padding-bottom: 10px !important;
    margin-bottom: 8px !important;
  }

  .v88-empty-approval-area h1,
  .v88-empty-approval-area h2,
  .v88-empty-approval-area h3,
  .v88-empty-approval-area h4 {
    margin-top: 0 !important;
    margin-bottom: 8px !important;
  }

  .v88-empty-approval-area p {
    margin-top: 0 !important;
    margin-bottom: 0 !important;
  }

  .v88-hidden-empty-gap {
    display: none !important;
  }

  .v88-has-active-proposal {
    max-height: none !important;
    min-height: 180px !important;
    overflow: visible !important;
  }
</style>
<script id="v88-chat-empty-approval-collapse-script">
(function(){
  function norm(text){ return String(text || '').replace(/\s+/g, ' ').trim(); }
  function lower(text){ return norm(text).toLowerCase(); }

  function visible(el){
    if(!el) return false;
    const s = window.getComputedStyle(el);
    return s.display !== 'none' && s.visibility !== 'hidden';
  }

  function findTextElement(exactText){
    const target = lower(exactText);
    const all = Array.from(document.querySelectorAll('body *')).filter(el => !['SCRIPT','STYLE','NOSCRIPT'].includes(el.tagName));
    return all.find(el => lower(el.textContent) === target) ||
           all.find(el => lower(el.textContent).includes(target));
  }

  function hasActiveProposalText(container){
    const t = lower(container && container.textContent);
    if(!t) return false;
    const hasApprovalButtons = Array.from((container || document).querySelectorAll('button, input[type="button"], input[type="submit"]')).some(btn => {
      const label = lower(btn.textContent || btn.value);
      return label === 'approve' || label === 'edit' || label === 'cancel';
    });
    return hasApprovalButtons || t.includes('approve') || t.includes('edit') || t.includes('cancel') || t.includes('proposal details');
  }

  function commonAncestor(a, b){
    if(!a || !b) return null;
    const parents = new Set();
    let n = a;
    while(n){ parents.add(n); n = n.parentElement; }
    n = b;
    while(n){ if(parents.has(n)) return n; n = n.parentElement; }
    return null;
  }

  function chooseApprovalContainer(reviewHeading, noProposal, currentWorkbook){
    const common = commonAncestor(noProposal, currentWorkbook) || document.body;

    // Prefer an ancestor of noProposal that does NOT include Current Workbook.
    let n = noProposal;
    let best = null;
    while(n && n !== common && n !== document.body){
      const t = lower(n.textContent);
      const rect = n.getBoundingClientRect();
      if(t.includes('review & approval') && t.includes('no active proposal') && !t.includes('current workbook') && rect.width > 200){
        best = n;
      }
      n = n.parentElement;
    }
    if(best) return best;

    // If DOM has no clean container, use the smallest ancestor containing heading + noProposal but not Current Workbook.
    n = reviewHeading || noProposal;
    while(n && n !== common && n !== document.body){
      const t = lower(n.textContent);
      if(t.includes('review & approval') && t.includes('no active proposal') && !t.includes('current workbook')) return n;
      n = n.parentElement;
    }

    // Last fallback: noProposal parent.
    return noProposal.parentElement || noProposal;
  }

  function hideEmptyNodesBetween(reviewHeading, currentWorkbook){
    // If the whitespace is caused by empty sibling blocks between approval text and Current Workbook,
    // hide empty/blank siblings, but never hide Current Workbook or anything after it.
    if(!reviewHeading || !currentWorkbook) return;
    const common = commonAncestor(reviewHeading, currentWorkbook);
    if(!common) return;

    const children = Array.from(common.children);
    const reviewIndex = children.findIndex(ch => ch === reviewHeading || ch.contains(reviewHeading));
    const currentIndex = children.findIndex(ch => ch === currentWorkbook || ch.contains(currentWorkbook));
    if(reviewIndex === -1 || currentIndex === -1 || currentIndex <= reviewIndex) return;

    for(let i = reviewIndex + 1; i < currentIndex; i++){
      const ch = children[i];
      const t = lower(ch.textContent);
      const rect = ch.getBoundingClientRect();
      if(!t || t === 'no active proposal yet.' || (rect.height > 160 && t.includes('no active proposal'))){
        // Do not hide if there are real approval buttons.
        if(!hasActiveProposalText(ch)) ch.classList.add('v88-hidden-empty-gap');
      }
    }
  }

  function hardCollapseEmptyApproval(){
    const reviewHeading = findTextElement('Review & Approval');
    const noProposal = findTextElement('No active proposal yet.');
    const currentWorkbook = findTextElement('Current Workbook');

    if(!reviewHeading || !noProposal) return;

    const container = chooseApprovalContainer(reviewHeading, noProposal, currentWorkbook);
    if(!container) return;

    if(hasActiveProposalText(container) && !lower(container.textContent).includes('no active proposal yet')){
      container.classList.remove('v88-empty-approval-area');
      container.classList.add('v88-has-active-proposal');
      return;
    }

    container.classList.remove('v88-has-active-proposal');
    container.classList.add('v88-empty-approval-area');

    // Direct style override in case old CSS has high-specificity height/min-height.
    container.style.height = 'auto';
    container.style.minHeight = '0';
    container.style.maxHeight = '115px';
    container.style.overflow = 'hidden';

    hideEmptyNodesBetween(reviewHeading, currentWorkbook);
  }

  function fixHeaderSpacing(){
    Array.from(document.querySelectorAll('header a, .topbar a, .navbar a, .app-header a')).forEach(a => {
      a.style.marginLeft = '18px';
      a.style.display = 'inline-block';
      a.style.whiteSpace = 'nowrap';
    });
  }

  function apply(){
    hardCollapseEmptyApproval();
    fixHeaderSpacing();
  }

  document.addEventListener('DOMContentLoaded', apply);
  setTimeout(apply, 100);
  setTimeout(apply, 500);
  setTimeout(apply, 1200);
  const mo = new MutationObserver(function(){
    clearTimeout(window.__v88ChatApprovalCollapseTimer);
    window.__v88ChatApprovalCollapseTimer = setTimeout(apply, 100);
  });
  mo.observe(document.documentElement, {childList:true, subtree:true, characterData:true});
})();
</script>
'''

if "v88-chat-empty-approval-collapse-script" not in html:
    html = html.replace("</body>", block + "\n</body>") if "</body>" in html else html + block
    chat_html.write_text(html, encoding="utf-8")
    print(f"v0.88 applied to {chat_html}")
else:
    print("v0.88 already applied.")

if README.exists():
    txt = README.read_text(encoding="utf-8", errors="ignore")
    if "v0.88 Hard collapse empty approval area" not in txt:
        README.write_text(txt + textwrap.dedent("""

        ## v0.88 Hard collapse empty approval area

        - Stronger DOM-based fix for the empty `Review & Approval` panel on `/chat`.
        - Collapses the empty area when it only says `No active proposal yet.`
        - Allows active proposals to expand normally.
        - Improves navbar spacing.
        """), encoding="utf-8")

print("v0.88 chat empty approval hard-collapse patch completed.")
