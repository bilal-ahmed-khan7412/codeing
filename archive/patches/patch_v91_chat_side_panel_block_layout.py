"""
Patch v0.91 - Force Chat side panel to block layout and remove empty approval gap

Apply from intern_tracker_system_v0 root:
    python patch_v91_chat_side_panel_block_layout.py

Why this patch exists:
- v90 debug shows the target is not a separate small Review panel.
- The same ASIDE contains BOTH Review & Approval and Current Workbook.
- That ASIDE is display:flex and height ~1016px:
    ASIDE class="panel side v87-approval-active-card v87-current-workbook-card"
- The blank space is caused by the side panel/flex layout, not by a simple child panel we can collapse.

What this patch does:
- Targets the exact structure using #proposalPanelTitle inside aside.panel.side.
- Forces the side panel to block/auto height when there is no active proposal.
- Removes/hides empty spacer/flex filler elements between Review & Approval and Current Workbook.
- Keeps active proposals expandable when Approve/Edit/Cancel controls exist.
- Does not change backend logic, approval behavior, workbook actions, or roles.
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

<!-- v0.91 force side panel block layout when approval is empty -->
<style id="v91-chat-side-panel-block-style">
  aside.panel.side.v91-empty-approval-side,
  .panel.side.v91-empty-approval-side {
    display: block !important;
    height: auto !important;
    min-height: 0 !important;
    max-height: none !important;
    overflow: visible !important;
    align-self: start !important;
  }

  aside.panel.side.v91-empty-approval-side #proposalPanelTitle,
  .panel.side.v91-empty-approval-side #proposalPanelTitle {
    margin-top: 0 !important;
    margin-bottom: 8px !important;
  }

  .v91-empty-proposal-gap {
    display: none !important;
    height: 0 !important;
    min-height: 0 !important;
    max-height: 0 !important;
    overflow: hidden !important;
    padding: 0 !important;
    margin: 0 !important;
  }

  .v91-no-proposal-compact {
    height: auto !important;
    min-height: 0 !important;
    max-height: 80px !important;
    overflow: hidden !important;
    padding-bottom: 10px !important;
    margin-bottom: 10px !important;
  }

  .v91-active-approval-side {
    display: block !important;
    height: auto !important;
    max-height: none !important;
    overflow: visible !important;
  }
</style>
<script id="v91-chat-side-panel-block-script">
(function(){
  function norm(v){ return String(v || '').replace(/\s+/g, ' ').trim(); }
  function low(v){ return norm(v).toLowerCase(); }

  function hasActiveProposal(side){
    if(!side) return false;
    const buttons = Array.from(side.querySelectorAll('button, input[type="button"], input[type="submit"]'));
    return buttons.some(btn => {
      const label = low(btn.textContent || btn.value);
      return label === 'approve' || label === 'edit' || label === 'cancel';
    });
  }

  function findCurrentWorkbookElement(side){
    if(!side) return null;
    const all = Array.from(side.querySelectorAll('h1,h2,h3,h4,label,div,p,section'));
    return all.find(el => low(el.textContent) === 'current workbook') ||
           all.find(el => low(el.textContent).startsWith('current workbook'));
  }

  function directChildContaining(parent, target){
    if(!parent || !target) return null;
    let n = target;
    let last = target;
    while(n && n !== parent){
      last = n;
      n = n.parentElement;
    }
    return n === parent ? last : null;
  }

  function hideEmptyChildrenBeforeWorkbook(side, title, current){
    if(!side || !current) return;
    const titleBranch = directChildContaining(side, title) || title;
    const currentBranch = directChildContaining(side, current) || current;
    const kids = Array.from(side.children);
    const start = kids.indexOf(titleBranch);
    const end = kids.indexOf(currentBranch);

    if(start !== -1 && end !== -1 && end > start){
      for(let i = start + 1; i < end; i++){
        const child = kids[i];
        const t = low(child.textContent);
        const rect = child.getBoundingClientRect();
        if(!t || t === 'no active proposal yet.' || (t.includes('no active proposal') && rect.height > 40)){
          child.classList.add('v91-empty-proposal-gap');
        }
      }
      return;
    }

    // Fallback: hide large empty descendants before current workbook, based on screen position.
    const currentTop = current.getBoundingClientRect().top;
    Array.from(side.querySelectorAll('div,section,article,aside')).forEach(el => {
      const rect = el.getBoundingClientRect();
      const t = low(el.textContent);
      if(rect.top > title.getBoundingClientRect().top && rect.bottom < currentTop && rect.height > 80){
        if(!t || t.includes('no active proposal')) el.classList.add('v91-empty-proposal-gap');
      }
    });
  }

  function compactNoProposalText(side){
    Array.from(side.querySelectorAll('p,div,span')).forEach(el => {
      if(low(el.textContent) === 'no active proposal yet.'){
        el.classList.add('v91-no-proposal-compact');
      }
    });
  }

  function applyV91(){
    const title = document.getElementById('proposalPanelTitle') || Array.from(document.querySelectorAll('h1,h2,h3,h4')).find(el => low(el.textContent) === 'review & approval');
    if(!title) return;

    const side = title.closest('aside.panel.side') || title.closest('.panel.side') || title.parentElement;
    if(!side) return;

    const current = findCurrentWorkbookElement(side);
    if(!current) return;

    if(hasActiveProposal(side)){
      side.classList.remove('v91-empty-approval-side');
      side.classList.add('v91-active-approval-side');
      return;
    }

    side.classList.remove('v87-approval-active-card', 'v88-empty-approval-area', 'v89-review-empty-branch', 'v91-active-approval-side');
    side.classList.add('v91-empty-approval-side');

    side.style.setProperty('display', 'block', 'important');
    side.style.setProperty('height', 'auto', 'important');
    side.style.setProperty('min-height', '0', 'important');
    side.style.setProperty('max-height', 'none', 'important');
    side.style.setProperty('overflow', 'visible', 'important');

    compactNoProposalText(side);
    hideEmptyChildrenBeforeWorkbook(side, title, current);
  }

  document.addEventListener('DOMContentLoaded', applyV91);
  setTimeout(applyV91, 50);
  setTimeout(applyV91, 250);
  setTimeout(applyV91, 750);
  setTimeout(applyV91, 1500);

  const mo = new MutationObserver(function(){
    clearTimeout(window.__v91ChatSidePanelTimer);
    window.__v91ChatSidePanelTimer = setTimeout(applyV91, 80);
  });
  mo.observe(document.documentElement, {childList:true, subtree:true, characterData:true});

  window.v91ApplyChatSidePanelFix = applyV91;
})();
</script>
'''

if "v91-chat-side-panel-block-script" not in html:
    html = html.replace("</body>", block + "\n</body>") if "</body>" in html else html + block
    chat_html.write_text(html, encoding="utf-8")
    print(f"v0.91 applied to {chat_html}")
else:
    print("v0.91 already applied.")

if README.exists():
    txt = README.read_text(encoding="utf-8", errors="ignore")
    if "v0.91 Force side panel block layout" not in txt:
        README.write_text(txt + textwrap.dedent("""

        ## v0.91 Force side panel block layout

        - Fixes the chat page empty Review & Approval gap based on v90 debug output.
        - The issue was the ASIDE containing both Review & Approval and Current Workbook using a tall flex layout.
        - Empty proposal state now forces that side panel to block/auto height.
        - Active proposals still expand normally.
        """), encoding="utf-8")

print("v0.91 chat side panel block-layout patch completed.")
