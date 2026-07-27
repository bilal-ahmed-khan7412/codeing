from pathlib import Path

root = Path(__file__).resolve().parent
chat_html = root / 'web' / 'chat.html'
readme = root / 'README.md'

if not chat_html.exists():
    raise SystemExit('web/chat.html not found. Run this patch inside intern_tracker_system_v0 after v0.26+.')

s = chat_html.read_text(encoding='utf-8')

# Add/override CSS to stop edit form overflow in the right proposal panel.
fix_css = r'''
    /* v0.29: keep editable proposal fields inside the proposal card */
    .proposal, .edit-area, .week-edit { max-width: 100%; overflow: hidden; }
    .edit-area label, .proposal label { min-width: 0; max-width: 100%; }
    .edit-area input, .edit-area textarea, .edit-area select,
    .proposal input, .proposal textarea, .proposal select {
      width: 100%;
      max-width: 100%;
      min-width: 0;
      box-sizing: border-box;
      font-weight: 400;
    }
    .side .two-col { grid-template-columns: 1fr; }
    .edit-area textarea { overflow-wrap: anywhere; word-break: break-word; }
'''

if 'v0.29: keep editable proposal fields' not in s:
    s = s.replace('</style>', fix_css + '\n  </style>')

# Optional: make sidebar a little wider on large screens, but still responsive.
old = 'main { max-width:1100px; margin:0 auto; padding:18px; display:grid; grid-template-columns: 1fr 320px; gap:18px; }'
new = 'main { max-width:1180px; margin:0 auto; padding:18px; display:grid; grid-template-columns: minmax(0, 1fr) 360px; gap:18px; }'
if old in s:
    s = s.replace(old, new)

chat_html.write_text(s, encoding='utf-8')

if readme.exists():
    readme.write_text(readme.read_text(encoding='utf-8') + r'''

## v0.29 Chat edit form overflow fix

- Fixed editable proposal fields overflowing outside the right-side proposal card.
- Inputs/textareas now stay inside the card.
- The Add Intern With Plan edit section uses a single-column layout in the sidebar.
- Form field text is normalized to regular weight for readability.
''', encoding='utf-8')

print('v0.29 chat edit overflow fix applied successfully.')
