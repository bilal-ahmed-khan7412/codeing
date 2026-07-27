"""
Patch v0.89 - Precise collapse for empty Review & Approval panel on /chat

Apply from intern_tracker_system_v0 root:
    python patch_v89_chat_review_panel_precise_collapse.py

Purpose:
- v87/v88 did not collapse the visible empty Review & Approval area in some page layouts.
- This patch finds the DOM branch that contains "Review & Approval" and separates it from
  the branch that contains "Current Workbook" under their lowest common ancestor.
- It then collapses ONLY the Review & Approval branch when it contains "No active proposal yet.".
- Real active proposals still expand normally.
- No backend logic changes.
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

<!-- v0.89 precise collapse for empty Review & Approval panel -->
<style id="v89-chat-review-precise-collapse-style">
  .v89-review-empty-branch {
    height: 124px !important;
    min-height: 0 !important;
    max-height: 124px !important;
    overflow: hidden !important;
    padding-top: 18px !important;
    padding-bottom: 12px !important;
    margin-bottom: 0 !important;
  }

  .v89-review-empty-branch * {
    max-height: none;
  }

  .v89-review-empty-branch h1,
  .v89-review-empty-branch h2,
  .v89-review-empty-branch h3,
  .v89-review-empty-branch h4 {
    margin-top: 0 !important;
    margin-bottom: 12px !important;
  }

  .v89-review-empty-branch p,
  .v89-review-empty-branch div {
    margin-bottom: 0 !important;
  }

  .v89-review-active-branch {
    height: auto !important;
    min-height: 180px !important;
    max-height: none !important;
    overflow: visible !important;
  }

  .v89-hidden-empty-review-spacer {
    display: none !important;
    height: 0 !important;
    min-height: 0 !important;
    max-height: 0 !important;
    overflow: hidden !important;
  }

  header a,
  .topbar a,
  .navbar a,
  .app-header a {
    margin-left: 18px !important;
    display: inline-block !important;
    white-space: nowrap !important;
  }
</style>
<script id="v89-chat-review-precise-collapse-script">
(function(){
  function normalizedText(value){
    return String(value || '').replace(/\s+/g, ' ').trim();
  }

  function lower(value){
    return normalizedText(value).toLowerCase();
  }

  function isIgnoredElement(el){
    return !el || ['SCRIPT', 'STYLE', 'NOSCRIPT'].includes(el.tagName);
  }

  function elementText(el){
    return lower(el && el.textContent);
  }

  function visibleElements(){
    return Array.from(document.querySelectorAll('body *')).filter(function(el){
      if(isIgnoredElement(el)) return false;
      const style = window.getComputedStyle(el);
      return style.display !== 'none' && style.visibility !== 'hidden';
    });
  }

  function findBestTextElement(needle){
    const n = lower(needle);
    const matches = visibleElements().filter(function(el){
      const ownText = Array.from(el.childNodes)
        .filter(function(node){ return node.nodeType === Node.TEXT_NODE; })
        .map(function(node){ return node.textContent; })
        .join(' ');
      return lower(ownText) === n || elementText(el) === n;
    });
    if(matches.length) return matches[0];

    const loose = visibleElements().filter(function(el){
      return elementText(el).includes(n);
    });
    // Prefer smaller elements, not the whole page.
    loose.sort(function(a,b){
      return elementText(a).length - elementText(b).length;
    });
    return loose[0] || null;
  }

  function ancestors(el){
    const out = [];
    let n = el;
    while(n){ out.push(n); n = n.parentElement; }
    return out;
  }

  function lowestCommonAncestor(a, b){
    if(!a || !b) return null;
    const set = new Set(ancestors(a));
    let n = b;
    while(n){
      if(set.has(n)) return n;
      n = n.parentElement;
    }
    return null;
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

  function findSeparableReviewBranch(reviewHeading, currentHeading){
    const lca = lowestCommonAncestor(reviewHeading, currentHeading);
    if(!lca) return null;

    // Walk down from LCA until the Review branch and Current Workbook branch split.
    let parent = lca;
    while(parent){
      const reviewChild = directChildContaining(parent, reviewHeading);
      const currentChild = directChildContaining(parent, currentHeading);
      if(reviewChild && currentChild && reviewChild !== currentChild){
        return reviewChild;
      }
      if(reviewChild && reviewChild === currentChild){
        parent = reviewChild;
        continue;
      }
      break;
    }
    return null;
  }

  function containsRealProposal(container){
    if(!container) return false;
    const t = elementText(container);
    const hasNoProposal = t.includes('no active proposal yet');
    const buttons = Array.from(container.querySelectorAll('button, input[type="button"], input[type="submit"]')).map(function(btn){
      return lower(btn.textContent || btn.value);
    });
    const hasApprovalButtons = buttons.some(function(label){
      return label === 'approve' || label === 'edit' || label === 'cancel';
    });
    if(hasApprovalButtons) return true;
    if(!hasNoProposal && (t.includes('approve') || t.includes('edit') || t.includes('cancel'))) return true;
    return false;
  }

  function stripTallInlineStyles(el){
    if(!el) return;
    ['height', 'minHeight', 'maxHeight', 'overflow', 'paddingTop', 'paddingBottom', 'marginBottom'].forEach(function(prop){
      try { el.style[prop] = ''; } catch(e) {}
    });
  }

  function forceCollapseBranch(branch){
    if(!branch) return;
    branch.classList.remove('v89-review-active-branch');
    branch.classList.add('v89-review-empty-branch');
    branch.style.setProperty('height', '124px', 'important');
    branch.style.setProperty('min-height', '0', 'important');
    branch.style.setProperty('max-height', '124px', 'important');
    branch.style.setProperty('overflow', 'hidden', 'important');
    branch.style.setProperty('padding-top', '18px', 'important');
    branch.style.setProperty('padding-bottom', '12px', 'important');
    branch.style.setProperty('margin-bottom', '0', 'important');

    // If a child inside branch is responsible for the blank tall area, collapse empty descendants too.
    Array.from(branch.querySelectorAll('div, section, article, aside')).forEach(function(child){
      const t = elementText(child);
      const rect = child.getBoundingClientRect();
      if(t.includes('no active proposal yet') && rect.height > 160 && !containsRealProposal(child)){
        child.style.setProperty('height', 'auto', 'important');
        child.style.setProperty('min-height', '0', 'important');
        child.style.setProperty('max-height', '110px', 'important');
        child.style.setProperty('overflow', 'hidden', 'important');
      }
      if(!t && rect.height > 80){
        child.classList.add('v89-hidden-empty-review-spacer');
      }
    });
  }

  function expandBranch(branch){
    if(!branch) return;
    branch.classList.remove('v89-review-empty-branch');
    branch.classList.add('v89-review-active-branch');
    stripTallInlineStyles(branch);
  }

  function debugState(reviewHeading, noProposal, currentHeading, branch){
    if(!window.__v89ChatCollapseDebug) return;
    console.group('[v89 chat collapse]');
    console.log('reviewHeading', reviewHeading);
    console.log('noProposal', noProposal);
    console.log('currentHeading', currentHeading);
    console.log('branch', branch, branch && branch.getBoundingClientRect(), branch && branch.outerHTML.slice(0, 1000));
    console.groupEnd();
  }

  function applyPreciseCollapse(){
    const reviewHeading = findBestTextElement('Review & Approval');
    const noProposal = findBestTextElement('No active proposal yet.');
    const currentHeading = findBestTextElement('Current Workbook');

    if(!reviewHeading || !noProposal || !currentHeading) return;

    let branch = findSeparableReviewBranch(reviewHeading, currentHeading);

    // Fallback: use the nearest ancestor of noProposal containing Review heading but not Current Workbook.
    if(!branch){
      let n = noProposal;
      while(n && n !== document.body){
        const t = elementText(n);
        if(t.includes('review & approval') && t.includes('no active proposal yet') && !t.includes('current workbook')){
          branch = n;
          break;
        }
        n = n.parentElement;
      }
    }

    if(!branch) return;
    debugState(reviewHeading, noProposal, currentHeading, branch);

    if(containsRealProposal(branch)){
      expandBranch(branch);
    }else{
      forceCollapseBranch(branch);
    }
  }

  function fixNavSpacing(){
    Array.from(document.querySelectorAll('header a, .topbar a, .navbar a, .app-header a')).forEach(function(a){
      a.style.setProperty('margin-left', '18px', 'important');
      a.style.setProperty('display', 'inline-block', 'important');
      a.style.setProperty('white-space', 'nowrap', 'important');
    });
  }

  function apply(){
    applyPreciseCollapse();
    fixNavSpacing();
  }

  document.addEventListener('DOMContentLoaded', apply);
  setTimeout(apply, 50);
  setTimeout(apply, 250);
  setTimeout(apply, 750);
  setTimeout(apply, 1500);

  const mo = new MutationObserver(function(){
    clearTimeout(window.__v89ChatReviewCollapseTimer);
    window.__v89ChatReviewCollapseTimer = setTimeout(apply, 80);
  });
  mo.observe(document.documentElement, {childList:true, subtree:true, characterData:true});

  window.v89ApplyChatReviewCollapse = apply;
})();
</script>
'''

if "v89-chat-review-precise-collapse-script" not in html:
    html = html.replace("</body>", block + "\n</body>") if "</body>" in html else html + block
    chat_html.write_text(html, encoding="utf-8")
    print(f"v0.89 applied to {chat_html}")
else:
    print("v0.89 already applied.")

if README.exists():
    txt = README.read_text(encoding="utf-8", errors="ignore")
    if "v0.89 Precise collapse for empty Review & Approval" not in txt:
        README.write_text(txt + textwrap.dedent("""

        ## v0.89 Precise collapse for empty Review & Approval

        - Stronger fix for chat page layouts where Review & Approval and Current Workbook share an outer card.
        - Collapses only the Review & Approval branch when there is no active proposal.
        - Active proposals still expand normally.
        """), encoding="utf-8")

print("v0.89 precise chat review collapse patch completed.")
