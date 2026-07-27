"""
Patch v0.90 - Chat layout debug logs for Review & Approval height issue

Apply from intern_tracker_system_v0 root:
    python patch_v90_chat_layout_debug.py

Purpose:
- Adds F12 console diagnostics for the /chat layout issue where the empty
  Review & Approval panel remains too tall.
- Does not change backend logic, scoring, workbook actions, or approval behavior.
- Adds a floating Debug Layout button and exposes window.chatLayoutDebugV90().

How to use after applying:
1. Restart app and open /chat.
2. Press F12 > Console.
3. Click the floating "Layout Debug" button OR run:
   window.chatLayoutDebugV90()
4. Copy the console output group: [ChatLayoutDebug v90]
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

<!-- v0.90 chat layout debug logs -->
<style id="v90-chat-layout-debug-style">
  #v90ChatLayoutDebugButton {
    position: fixed;
    right: 16px;
    bottom: 16px;
    z-index: 999999;
    border: none;
    border-radius: 10px;
    background: #7c3aed;
    color: #fff;
    padding: 9px 12px;
    font-weight: 800;
    box-shadow: 0 4px 14px rgba(15,23,42,.22);
    cursor: pointer;
    font-size: 12px;
  }
</style>
<script id="v90-chat-layout-debug-script">
(function(){
  const PREFIX = '[ChatLayoutDebug v90]';

  function norm(value){ return String(value || '').replace(/\s+/g, ' ').trim(); }
  function lower(value){ return norm(value).toLowerCase(); }
  function short(value, len=700){ value = norm(value); return value.length > len ? value.slice(0, len) + '...' : value; }
  function isIgnored(el){ return !el || ['SCRIPT','STYLE','NOSCRIPT'].includes(el.tagName); }

  function ownText(el){
    return Array.from(el.childNodes || [])
      .filter(n => n.nodeType === Node.TEXT_NODE)
      .map(n => n.textContent)
      .join(' ')
      .replace(/\s+/g, ' ')
      .trim();
  }

  function rectInfo(el){
    const r = el.getBoundingClientRect();
    const s = window.getComputedStyle(el);
    return {
      top: Math.round(r.top), left: Math.round(r.left), width: Math.round(r.width), height: Math.round(r.height),
      display: s.display, visibility: s.visibility, overflow: s.overflow,
      position: s.position, minHeight: s.minHeight, maxHeight: s.maxHeight, heightStyle: s.height,
      paddingTop: s.paddingTop, paddingBottom: s.paddingBottom, marginTop: s.marginTop, marginBottom: s.marginBottom,
      classes: el.className || '', id: el.id || '', tag: el.tagName
    };
  }

  function pathInfo(el){
    const out = [];
    let n = el;
    while(n && n !== document.documentElement){
      out.push({
        tag: n.tagName,
        id: n.id || '',
        className: String(n.className || ''),
        text: short(ownText(n) || n.textContent, 120),
        rect: rectInfo(n)
      });
      n = n.parentElement;
    }
    return out;
  }

  function visibleElements(){
    return Array.from(document.querySelectorAll('body *')).filter(el => {
      if(isIgnored(el)) return false;
      const s = window.getComputedStyle(el);
      return s.display !== 'none' && s.visibility !== 'hidden';
    });
  }

  function findTextElements(needle){
    const n = lower(needle);
    const items = [];
    for(const el of visibleElements()){
      const ot = lower(ownText(el));
      const tt = lower(el.textContent);
      if(ot === n || tt === n || ot.includes(n) || tt.includes(n)){
        items.push({
          el,
          ownText: short(ownText(el), 200),
          text: short(el.textContent, 300),
          rect: rectInfo(el),
          path: pathInfo(el).slice(0, 8)
        });
      }
    }
    items.sort((a,b) => a.text.length - b.text.length || a.rect.height - b.rect.height);
    return items.slice(0, 12);
  }

  function largestElements(){
    return visibleElements()
      .map(el => ({
        elem: el,
        tag: el.tagName,
        id: el.id || '',
        className: String(el.className || ''),
        text: short(el.textContent, 220),
        ownText: short(ownText(el), 160),
        rect: rectInfo(el),
        childCount: el.children.length
      }))
      .filter(x => x.rect.height > 120 && x.rect.width > 250)
      .sort((a,b) => b.rect.height - a.rect.height)
      .slice(0, 20);
  }

  function commonAncestor(a,b){
    if(!a || !b) return null;
    const set = new Set();
    let n=a; while(n){ set.add(n); n=n.parentElement; }
    n=b; while(n){ if(set.has(n)) return n; n=n.parentElement; }
    return null;
  }

  function branchBetween(reviewEl, workbookEl){
    const lca = commonAncestor(reviewEl, workbookEl);
    if(!lca) return null;
    function directChildContaining(parent, target){
      let n = target, last = target;
      while(n && n !== parent){ last = n; n = n.parentElement; }
      return n === parent ? last : null;
    }
    let parent = lca;
    while(parent){
      const r = directChildContaining(parent, reviewEl);
      const w = directChildContaining(parent, workbookEl);
      if(r && w && r !== w) return {lca, reviewBranch:r, workbookBranch:w};
      if(r && r === w){ parent = r; continue; }
      return {lca, reviewBranch:r, workbookBranch:w};
    }
    return {lca};
  }

  function debug(){
    const reviewMatches = findTextElements('Review & Approval');
    const noProposalMatches = findTextElements('No active proposal yet.');
    const workbookMatches = findTextElements('Current Workbook');
    const reviewEl = reviewMatches[0] && reviewMatches[0].el;
    const workbookEl = workbookMatches[0] && workbookMatches[0].el;
    const branches = branchBetween(reviewEl, workbookEl);

    const data = {
      reviewMatches: reviewMatches.map(x => ({ownText:x.ownText, text:x.text, rect:x.rect, path:x.path})),
      noProposalMatches: noProposalMatches.map(x => ({ownText:x.ownText, text:x.text, rect:x.rect, path:x.path})),
      currentWorkbookMatches: workbookMatches.map(x => ({ownText:x.ownText, text:x.text, rect:x.rect, path:x.path})),
      branchAnalysis: branches ? {
        lca: branches.lca ? {rect: rectInfo(branches.lca), text: short(branches.lca.textContent, 500), html: branches.lca.outerHTML.slice(0, 1200)} : null,
        reviewBranch: branches.reviewBranch ? {rect: rectInfo(branches.reviewBranch), text: short(branches.reviewBranch.textContent, 500), html: branches.reviewBranch.outerHTML.slice(0, 1200)} : null,
        workbookBranch: branches.workbookBranch ? {rect: rectInfo(branches.workbookBranch), text: short(branches.workbookBranch.textContent, 500), html: branches.workbookBranch.outerHTML.slice(0, 1200)} : null
      } : null,
      largestVisibleElements: largestElements().map(x => ({tag:x.tag,id:x.id,className:x.className,text:x.text,ownText:x.ownText,rect:x.rect,childCount:x.childCount})),
      bodyRect: rectInfo(document.body),
      viewport: {width: window.innerWidth, height: window.innerHeight, scrollY: window.scrollY}
    };

    console.group(PREFIX);
    console.log('COPY THIS JSON:', JSON.stringify(data, null, 2));
    console.log('Raw object:', data);
    console.groupEnd();
    return data;
  }

  function addButton(){
    if(document.getElementById('v90ChatLayoutDebugButton')) return;
    const btn = document.createElement('button');
    btn.id = 'v90ChatLayoutDebugButton';
    btn.type = 'button';
    btn.textContent = 'Layout Debug';
    btn.onclick = debug;
    document.body.appendChild(btn);
  }

  window.chatLayoutDebugV90 = debug;
  document.addEventListener('DOMContentLoaded', function(){ addButton(); setTimeout(debug, 700); });
  setTimeout(addButton, 500);
})();
</script>
'''

if "v90-chat-layout-debug-script" not in html:
    html = html.replace("</body>", block + "\n</body>") if "</body>" in html else html + block
    chat_html.write_text(html, encoding="utf-8")
    print(f"v0.90 applied to {chat_html}")
else:
    print("v0.90 already applied.")

if README.exists():
    txt = README.read_text(encoding="utf-8", errors="ignore")
    if "v0.90 Chat layout debug logs" not in txt:
        README.write_text(txt + textwrap.dedent("""

        ## v0.90 Chat layout debug logs

        - Adds F12 diagnostics for the empty Review & Approval panel height issue.
        - Use `window.chatLayoutDebugV90()` or the floating Layout Debug button.
        - Does not change backend logic or approval behavior.
        """), encoding="utf-8")

print("v0.90 chat layout debug patch completed.")
