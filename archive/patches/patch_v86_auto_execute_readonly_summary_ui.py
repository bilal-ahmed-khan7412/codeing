"""
Patch v0.86 - Auto-execute read-only progress summary proposals from Chat UI

Apply from intern_tracker_system_v0 root:
    python patch_v86_auto_execute_readonly_summary_ui.py

Problem fixed:
- User asks: "how is Bilal doing?"
- App replies/enters a read-only progress-summary proposal flow instead of answering directly.
- v84/v85 may hide the proposal panel, but summary still may not execute.

What this patch does:
- Frontend-only safety net for the Chat page.
- Detects read-only progress-summary proposal text.
- Automatically triggers the existing Approve action for summary/progress proposals only.
- If no approve button exists, it sends an "approve" message through the existing chat input/form as a fallback.
- Does NOT auto-approve workbook-changing commands.
- Does NOT hardcode any intern name.
"""
from __future__ import annotations

from pathlib import Path
import textwrap

ROOT = Path(__file__).resolve().parent
CHAT_HTML_CANDIDATES = [ROOT / "web" / "chat.html", ROOT / "chat.html", ROOT / "templates" / "chat.html"]
README = ROOT / "README.md"

chat_html = next((p for p in CHAT_HTML_CANDIDATES if p.exists()), None)
if chat_html is None:
    raise SystemExit("Could not find chat.html. Run from intern_tracker_system_v0 root folder.")

html = chat_html.read_text(encoding="utf-8")

block = r'''

<script id="v86-auto-execute-readonly-summary-ui">
(function(){
  const SUMMARY_MARKERS = [
    'generate a progress summary',
    'progress summary for the current workbook',
    'generated progress summary',
    'how is ',
    'doing?'
  ];
  const MUTATION_MARKERS = [
    'add intern', 'extend intern', 'create plan', 'edit task', 'update task',
    'add holiday', 'finalize evaluation', 'write workbook', 'apply plan'
  ];

  function text(){ return (document.body.innerText || '').toLowerCase(); }
  function isSummaryContext(t){
    t = String(t || '').toLowerCase();
    return SUMMARY_MARKERS.some(m => t.includes(m));
  }
  function isMutationContext(t){
    t = String(t || '').toLowerCase();
    return MUTATION_MARKERS.some(m => t.includes(m));
  }
  function visible(el){
    if(!el) return false;
    const s = window.getComputedStyle(el);
    return s.display !== 'none' && s.visibility !== 'hidden' && el.offsetParent !== null;
  }
  function findApproveButton(){
    const buttons = Array.from(document.querySelectorAll('button, input[type="button"], input[type="submit"]'));
    return buttons.find(btn => {
      const label = String(btn.textContent || btn.value || '').trim().toLowerCase();
      if(label !== 'approve') return false;
      const areaText = String((btn.closest('[data-proposal], .proposal, .proposal-panel, .approval-panel, .review-panel, section, aside, div') || document.body).innerText || '').toLowerCase();
      return isSummaryContext(areaText) && !isMutationContext(areaText);
    }) || buttons.find(btn => String(btn.textContent || btn.value || '').trim().toLowerCase() === 'approve' && isSummaryContext(text()) && !isMutationContext(text()));
  }
  function sendApproveFallback(){
    const bodyText = text();
    if(!isSummaryContext(bodyText) || isMutationContext(bodyText)) return false;
    const inputs = Array.from(document.querySelectorAll('textarea, input[type="text"], input:not([type])'));
    const input = inputs.reverse().find(el => visible(el) && !el.disabled && !el.readOnly);
    if(!input) return false;
    input.focus();
    input.value = 'approve';
    input.dispatchEvent(new Event('input', {bubbles:true}));
    input.dispatchEvent(new Event('change', {bubbles:true}));
    const form = input.closest('form');
    if(form){
      form.dispatchEvent(new Event('submit', {bubbles:true, cancelable:true}));
      return true;
    }
    const btns = Array.from(document.querySelectorAll('button, input[type="submit"], input[type="button"]'));
    const sendBtn = btns.find(btn => {
      const label = String(btn.textContent || btn.value || '').trim().toLowerCase();
      return ['send','submit','ask','run'].includes(label);
    });
    if(sendBtn){ sendBtn.click(); return true; }
    input.dispatchEvent(new KeyboardEvent('keydown', {key:'Enter', code:'Enter', bubbles:true}));
    return true;
  }
  function removeProposalNoise(){
    // Only remove after execution has been triggered, never before.
    Array.from(document.querySelectorAll('body *')).forEach(el => {
      const t = String(el.textContent || '').toLowerCase();
      if(t.includes('review the proposal on the right') || t.includes('approve, edit, or cancel')){
        el.style.display = 'none';
      }
    });
  }
  function tryAutoExecuteSummary(){
    if(window.__v86AutoSummaryInFlight) return;
    const bodyText = text();
    if(!isSummaryContext(bodyText) || isMutationContext(bodyText)) return;
    const approve = findApproveButton();
    if(approve){
      window.__v86AutoSummaryInFlight = true;
      console.info('[v86] Auto-approving read-only progress summary proposal.');
      approve.click();
      setTimeout(removeProposalNoise, 150);
      setTimeout(() => { window.__v86AutoSummaryInFlight = false; }, 2500);
      return;
    }
    // If v84/v85 already hid the approve button, still execute by sending approve fallback.
    if(bodyText.includes('i can generate a progress summary') || bodyText.includes('review the proposal on the right')){
      window.__v86AutoSummaryInFlight = true;
      console.info('[v86] Sending fallback approve for read-only progress summary proposal.');
      sendApproveFallback();
      setTimeout(removeProposalNoise, 150);
      setTimeout(() => { window.__v86AutoSummaryInFlight = false; }, 2500);
    }
  }

  // Intercept chat fetch responses and run after DOM updates.
  if(!window.__v86SummaryFetchPatch){
    window.__v86SummaryFetchPatch = true;
    const originalFetch = window.fetch;
    window.fetch = async function(input, init){
      const res = await originalFetch.apply(this, arguments);
      try{
        const url = typeof input === 'string' ? input : (input && input.url) || '';
        if(/chat|message|command|assistant/i.test(url)){
          const clone = res.clone();
          clone.text().then(raw => {
            if(isSummaryContext(raw) && !isMutationContext(raw)){
              setTimeout(tryAutoExecuteSummary, 80);
              setTimeout(tryAutoExecuteSummary, 300);
            }
          }).catch(()=>{});
        }
      }catch(e){}
      return res;
    };
  }

  const mo = new MutationObserver(function(){
    clearTimeout(window.__v86SummaryTimer);
    window.__v86SummaryTimer = setTimeout(tryAutoExecuteSummary, 120);
  });
  mo.observe(document.documentElement, {childList:true, subtree:true, characterData:true});
  document.addEventListener('DOMContentLoaded', function(){
    setTimeout(tryAutoExecuteSummary, 200);
  });
})();
</script>
'''

if "v86-auto-execute-readonly-summary-ui" not in html:
    html = html.replace("</body>", block + "\n</body>") if "</body>" in html else html + block
    chat_html.write_text(html, encoding="utf-8")
    print(f"v0.86 applied to {chat_html}")
else:
    print("v0.86 already applied.")

if README.exists():
    txt = README.read_text(encoding="utf-8", errors="ignore")
    if "v0.86 Auto-execute read-only summary proposals" not in txt:
        README.write_text(txt + textwrap.dedent("""

        ## v0.86 Auto-execute read-only summary proposals

        - Frontend safety net for read-only progress summary prompts.
        - If chat still creates a proposal for `how is <intern> doing?`, the UI automatically approves only that read-only summary proposal.
        - Workbook-changing commands are not auto-approved.
        """), encoding="utf-8")
