from pathlib import Path

root = Path(__file__).resolve().parent
chat_html = root / 'web' / 'chat.html'
readme = root / 'README.md'

if not chat_html.exists():
    raise SystemExit('web/chat.html not found. Run this patch inside intern_tracker_system_v0.')

h = chat_html.read_text(encoding='utf-8')

css = r'''

/* v0.42: make review/approve panel visible without scrolling */
.side {
  overflow: auto !important;
}
#proposalBox {
  order: -100 !important;
  flex: 0 0 auto !important;
  min-height: 360px !important;
  max-height: 58vh !important;
  overflow: hidden !important;
  padding: 16px !important;
  border-bottom: 1px solid var(--border);
  background: #ffffff;
}
#proposalBox:empty::before {
  content: 'No active proposal yet.';
  color: #64748b;
}
#proposalBox .proposal {
  height: 100% !important;
  min-height: 320px !important;
}
#proposalBox .proposal-body {
  max-height: calc(58vh - 150px) !important;
}
.side > h2:nth-of-type(1) {
  order: -90;
}
.side > .current,
.side > label,
.side > .file-row,
.side > #uploadStatus {
  flex-shrink: 0;
}
#approvalState {
  font-weight: 700;
  color: #1d4ed8;
}
.proposal-footer button {
  min-width: 90px;
}
@media (max-width: 980px) {
  #proposalBox { max-height: none !important; min-height: 320px !important; }
  #proposalBox .proposal-body { max-height: none !important; }
}
'''
if 'v0.42: make review/approve panel visible' not in h:
    h = h.replace('</style>', css + '\n  </style>')

# Add a small heading inside proposalBox when no proposal and ensure the proposal area is visually first.
if "function ensureProposalFirst" not in h:
    js = r'''

// v0.42: move proposal/review panel to the top of the right sidebar
function ensureProposalFirst(){
  const side = document.querySelector('.side');
  const proposal = document.getElementById('proposalBox');
  if(!side || !proposal) return;
  if(!document.getElementById('proposalPanelTitle')){
    const title = document.createElement('h2');
    title.id = 'proposalPanelTitle';
    title.textContent = 'Review & Approval';
    title.style.order = '-101';
    title.style.margin = '16px 16px 8px';
    side.insertBefore(title, side.firstChild);
  }
  proposal.style.order = '-100';
  if(!proposal.textContent.trim()) proposal.innerHTML = '<div class="hint">No active proposal yet. Send a request in chat to prepare one.</div>';
}
'''
    pos = h.rfind('init();')
    if pos != -1:
        h = h[:pos] + js + '\nensureProposalFirst();\n' + h[pos:]
    else:
        h += '<script>' + js + '\nensureProposalFirst();</script>'

# Also call ensureProposalFirst in renderProposal if the function exists.
if "ensureProposalFirst();\n  activeProposal = data;" not in h and "function renderProposal(data)" in h:
    h = h.replace("function renderProposal(data){\n  activeProposal = data;", "function renderProposal(data){\n  ensureProposalFirst();\n  activeProposal = data;")

chat_html.write_text(h, encoding='utf-8')

if readme.exists():
    readme.write_text(readme.read_text(encoding='utf-8') + r'''

## v0.42 Chat review/approval visibility fix

- The proposal/review panel is now moved to the top of the right sidebar.
- Users no longer need to scroll past workbook selector/examples to find Approve/Edit/Cancel.
- The proposal body scrolls internally while the footer buttons stay visible.
''', encoding='utf-8')

print('v0.42 chat review/approval visibility patch applied successfully.')
