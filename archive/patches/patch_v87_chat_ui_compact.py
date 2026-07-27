"""
Patch v0.87 - Chat UI compact approval panel and navbar spacing

Apply from intern_tracker_system_v0 root:
    python patch_v87_chat_ui_compact.py

Purpose:
- Fix chat page usability where Review & Approval takes almost the whole viewport.
- Keep approval workflow, but make the approval panel compact when no active proposal exists.
- Keep Current Workbook visible without excessive scrolling.
- Improve navbar spacing, especially Profile / Logout.
- Keep Evaluation link visible for Admin/Super Admin if already present.
- Do not change backend logic, workbook actions, approval rules, or role permissions.
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

<!-- v0.87 compact chat approval panel and navbar spacing -->
<style id="v87-chat-ui-compact-style">
  :root {
    --v87-primary: #305496;
    --v87-bg: #f4f6fb;
    --v87-border: #d9e2ef;
    --v87-muted: #475569;
    --v87-card: #ffffff;
  }

  body {
    background: var(--v87-bg) !important;
  }

  /* Clean navbar spacing without changing role logic. */
  header,
  .topbar,
  .navbar,
  .app-header {
    min-height: 74px;
  }

  header a,
  .topbar a,
  .navbar a,
  .app-header a {
    margin-left: 16px !important;
    display: inline-block !important;
    white-space: nowrap !important;
  }

  header a + a,
  .topbar a + a,
  .navbar a + a,
  .app-header a + a {
    margin-left: 18px !important;
  }

  /* Main chat page should not force a giant empty approval panel. */
  .v87-approval-compact,
  section:has(.v87-no-active-proposal-marker),
  div:has(.v87-no-active-proposal-marker) {
    max-height: 150px !important;
    min-height: 0 !important;
    overflow: hidden !important;
  }

  .v87-approval-empty-card {
    max-height: 150px !important;
    min-height: 0 !important;
    padding-bottom: 12px !important;
  }

  .v87-approval-empty-card h2,
  .v87-approval-empty-card h3,
  .v87-approval-empty-card h4 {
    margin-top: 0 !important;
    margin-bottom: 8px !important;
  }

  .v87-approval-empty-card p {
    margin: 0 !important;
    color: var(--v87-muted) !important;
  }

  /* If a real proposal appears, allow the panel to grow again. */
  .v87-approval-active-card {
    max-height: none !important;
    min-height: 180px !important;
    overflow: visible !important;
  }

  /* Current workbook area should be visible and compact. */
  .v87-current-workbook-card {
    margin-top: 12px !important;
  }

  .v87-current-workbook-card select,
  .v87-current-workbook-card input {
    max-width: 100% !important;
  }

  /* Prevent big empty horizontal whitespace from swallowing the UI. */
  main,
  .container,
  .page,
  .content,
  #app {
    max-width: 1280px !important;
  }
</style>
<script id="v87-chat-ui-compact-script">
(function(){
  function norm(text){ return String(text || '').replace(/\s+/g, ' ').trim(); }
  function lower(text){ return norm(text).toLowerCase(); }

  function findCardsByHeading(headingText){
    const cards = [];
    const all = Array.from(document.querySelectorAll('section, article, aside, div'));
    for(const el of all){
      const own = Array.from(el.childNodes)
        .filter(n => n.nodeType === Node.TEXT_NODE)
        .map(n => n.textContent)
        .join(' ')
        .trim();
      const t = lower(el.textContent);
      if(t.includes(lower(headingText))){
        // keep reasonably scoped containers only
        if((el.querySelector('h1,h2,h3,h4') || '').toString() || el.children.length <= 15){
          cards.push(el);
        }
      }
    }
    return cards;
  }

  function markApprovalPanel(){
    const candidates = findCardsByHeading('Review & Approval');
    if(!candidates.length) return;

    // Choose the smallest visible card containing Review & Approval.
    let best = null;
    let bestArea = Infinity;
    for(const el of candidates){
      const rect = el.getBoundingClientRect();
      const area = Math.max(rect.width, 1) * Math.max(rect.height, 1);
      if(rect.width > 100 && area < bestArea){
        best = el;
        bestArea = area;
      }
    }
    if(!best) best = candidates[0];

    const text = lower(best.textContent);
    const noProposal = text.includes('no active proposal yet');
    const hasButtons = Array.from(best.querySelectorAll('button, input[type="button"], input[type="submit"]')).some(btn => {
      const label = lower(btn.textContent || btn.value);
      return ['approve','edit','cancel'].includes(label);
    });

    if(noProposal && !hasButtons){
      best.classList.add('v87-approval-empty-card', 'v87-approval-compact');
      if(!best.querySelector('.v87-no-active-proposal-marker')){
        const marker = document.createElement('span');
        marker.className = 'v87-no-active-proposal-marker';
        marker.style.display = 'none';
        best.appendChild(marker);
      }
    } else {
      best.classList.remove('v87-approval-empty-card', 'v87-approval-compact');
      best.classList.add('v87-approval-active-card');
    }
  }

  function markCurrentWorkbookPanel(){
    const candidates = findCardsByHeading('Current Workbook');
    if(!candidates.length) return;
    for(const el of candidates){
      const t = lower(el.textContent);
      if(t.includes('workbook files') || t.includes('selected workbook')){
        el.classList.add('v87-current-workbook-card');
      }
    }
  }

  function fixProfileLogoutSpacing(){
    // Some old pages rendered ProfileLogout visually together. Ensure spacing by adding margin.
    Array.from(document.querySelectorAll('a')).forEach(a => {
      const label = lower(a.textContent);
      if(label === 'profile' || label === 'logout'){
        a.style.marginLeft = '18px';
        a.style.display = 'inline-block';
      }
    });
  }

  function applyChatUiCompact(){
    markApprovalPanel();
    markCurrentWorkbookPanel();
    fixProfileLogoutSpacing();
  }

  document.addEventListener('DOMContentLoaded', applyChatUiCompact);
  setTimeout(applyChatUiCompact, 100);
  setTimeout(applyChatUiCompact, 500);
  setTimeout(applyChatUiCompact, 1200);

  const mo = new MutationObserver(function(){
    clearTimeout(window.__v87ChatUiTimer);
    window.__v87ChatUiTimer = setTimeout(applyChatUiCompact, 100);
  });
  mo.observe(document.documentElement, {childList:true, subtree:true, characterData:true});
})();
</script>
'''

if "v87-chat-ui-compact-script" not in html:
    html = html.replace("</body>", block + "\n</body>") if "</body>" in html else html + block
    chat_html.write_text(html, encoding="utf-8")
    print(f"v0.87 applied to {chat_html}")
else:
    print("v0.87 already applied.")

if README.exists():
    txt = README.read_text(encoding="utf-8", errors="ignore")
    if "v0.87 Chat UI compact approval panel" not in txt:
        README.write_text(txt + textwrap.dedent("""

        ## v0.87 Chat UI compact approval panel

        - Review & Approval panel no longer consumes most of the page when there is no active proposal.
        - Current Workbook section stays visible without excessive scrolling.
        - Navbar spacing improved, including Profile / Logout spacing.
        - Approval workflow remains unchanged for workbook-changing actions.
        """), encoding="utf-8")

print("v0.87 chat UI compact patch completed.")
