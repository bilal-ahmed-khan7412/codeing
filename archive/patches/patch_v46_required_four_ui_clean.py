from pathlib import Path

root = Path(__file__).resolve().parent
chat_service = root / 'tracker_chat' / 'chat_service.py'
chat_html = root / 'web' / 'chat.html'
readme = root / 'README.md'

if not chat_service.exists():
    raise SystemExit('tracker_chat/chat_service.py not found. Run this patch inside intern_tracker_system_v0.')
if not chat_html.exists():
    raise SystemExit('web/chat.html not found. Run this patch inside intern_tracker_system_v0.')

s = chat_service.read_text(encoding='utf-8')

# -----------------------------------------------------------------------------
# v0.46 fixes for required four workflows:
# - "update main project of saleem to ..." should extract intern = Saleem, not "Of Saleem"
# - same for scenario "update scenario of saleem to ..."
# -----------------------------------------------------------------------------

# Add a safer name cleaner override near v45 helpers.
if 'def _v46_clean_intern_phrase' not in s:
    s += r'''

# v0.46 intern-name cleanup helper
def _v46_clean_intern_phrase(value: str) -> str:
    value = (value or '').strip().strip(' .,:;')
    value = re.sub(r'^(of|for|intern|the intern)\s+', '', value, flags=re.I).strip()
    return _v45_clean_name(value) if '_v45_clean_name' in globals() else value.title()
'''

# Patch v45 capstone regex block to specifically handle "main project of/for NAME to TITLE" first.
if 'main project of saleem v46' not in s:
    old = """    # update Bilal main project to Kubernetes Monitoring Dashboard\n    m = re.search(r'(?:update|edit|change|set)\\s+(?:intern\\s+)?(.+?)\\s+(?:main project|capstone)\\s+(?:to|as)\\s+(.+)$', text, re.I)\n    if m:\n        args['intern'] = _v45_clean_name(m.group(1))\n        args['title'] = m.group(2).strip()\n    else:\n        m = re.search(r'(?:update|edit|change|set)\\s+(?:main project|capstone)\\s+(?:for\\s+)?(.+?)\\s+(?:to|as)\\s+(.+)$', text, re.I)\n        if m:\n            args['intern'] = _v45_clean_name(m.group(1))\n            args['title'] = m.group(2).strip()\n"""
    new = """    # main project of saleem v46\n    # update main project of/for Saleem to Agentic AI platform\n    m = re.search(r'(?:update|edit|change|set)\\s+(?:main project|capstone)\\s+(?:of|for)\\s+(.+?)\\s+(?:to|as)\\s+(.+)$', text, re.I)\n    if m:\n        args['intern'] = _v46_clean_intern_phrase(m.group(1))\n        args['title'] = m.group(2).strip()\n    else:\n        # update Saleem main project to Kubernetes Monitoring Dashboard\n        m = re.search(r'(?:update|edit|change|set)\\s+(?:intern\\s+)?(.+?)\\s+(?:main project|capstone)\\s+(?:to|as)\\s+(.+)$', text, re.I)\n        if m:\n            args['intern'] = _v46_clean_intern_phrase(m.group(1))\n            args['title'] = m.group(2).strip()\n        else:\n            m = re.search(r'(?:update|edit|change|set)\\s+(?:main project|capstone)\\s+(?:for\\s+|of\\s+)?(.+?)\\s+(?:to|as)\\s+(.+)$', text, re.I)\n            if m:\n                args['intern'] = _v46_clean_intern_phrase(m.group(1))\n                args['title'] = m.group(2).strip()\n"""
    if old in s:
        s = s.replace(old, new)
    else:
        print('Warning: v45 capstone block not found; appending fallback override was not possible.')

# Patch v45 scenario block for "scenario of/for NAME to ...".
if 'scenario of saleem v46' not in s:
    old = """    # update Bilal real-world scenario to investigate failed deployment\n    m = re.search(r'(?:update|edit|change|set)\\s+(?:intern\\s+)?(.+?)\\s+(?:real-world scenario|real world scenario|scenario)\\s+(?:to|as)\\s+(.+)$', text, re.I)\n    if m:\n        args['intern'] = _v45_clean_name(m.group(1))\n        args['scenario'] = m.group(2).strip()\n    else:\n        m = re.search(r'(?:update|edit|change|set)\\s+(?:real-world scenario|real world scenario|scenario)\\s+(?:for\\s+)?(.+?)\\s+(?:to|as)\\s+(.+)$', text, re.I)\n        if m:\n            args['intern'] = _v45_clean_name(m.group(1))\n            args['scenario'] = m.group(2).strip()\n"""
    new = """    # scenario of saleem v46\n    # update scenario of/for Saleem to investigate failed deployment\n    m = re.search(r'(?:update|edit|change|set)\\s+(?:real-world scenario|real world scenario|scenario)\\s+(?:of|for)\\s+(.+?)\\s+(?:to|as)\\s+(.+)$', text, re.I)\n    if m:\n        args['intern'] = _v46_clean_intern_phrase(m.group(1))\n        args['scenario'] = m.group(2).strip()\n    else:\n        m = re.search(r'(?:update|edit|change|set)\\s+(?:intern\\s+)?(.+?)\\s+(?:real-world scenario|real world scenario|scenario)\\s+(?:to|as)\\s+(.+)$', text, re.I)\n        if m:\n            args['intern'] = _v46_clean_intern_phrase(m.group(1))\n            args['scenario'] = m.group(2).strip()\n        else:\n            m = re.search(r'(?:update|edit|change|set)\\s+(?:real-world scenario|real world scenario|scenario)\\s+(?:for\\s+|of\\s+)?(.+?)\\s+(?:to|as)\\s+(.+)$', text, re.I)\n            if m:\n                args['intern'] = _v46_clean_intern_phrase(m.group(1))\n                args['scenario'] = m.group(2).strip()\n"""
    if old in s:
        s = s.replace(old, new)
    else:
        print('Warning: v45 scenario block not found; appending fallback override was not possible.')

chat_service.write_text(s, encoding='utf-8')

# -----------------------------------------------------------------------------
# UI cleanup: generic Action Details should show clean key/value cards.
# This specifically avoids literal <strong data-lexical-text="true"> appearing.
# -----------------------------------------------------------------------------
h = chat_html.read_text(encoding='utf-8')

# Add robust sanitize helpers if not already present.
if 'function v46Plain' not in h:
    insert = r'''
function v46Plain(v){
  let s = String(v ?? '');
  s = s.replace(/<br\s*\/?\s*>/gi, '\n');
  s = s.replace(/<\/?(strong|b|em|i)[^>]*>/gi, '');
  s = s.replace(/data-lexical-text="true"/gi, '');
  s = s.replace(/<[^>]+>/g, '');
  return s;
}
function v46Safe(v){ return escapeHtml(v46Plain(v)); }
'''
    pos = h.find('function v41CleanLabel')
    if pos != -1:
        h = h[:pos] + insert + '\n' + h[pos:]
    else:
        h = h.replace('function escapeHtml', insert + '\nfunction escapeHtml')

# Override v41Rows to sanitize labels/values and avoid <b>/<strong>; use divs/spans.
if 'function v41Rows(obj, keys){' in h:
    start = h.find('function v41Rows(obj, keys){')
    end = h.find('\n}', start) + 2
    new_rows = r'''function v41Rows(obj, keys){
  return '<div class="kv">' + keys.map(([label,key]) => `<span class="kv-label">${v46Safe(label)}</span><span>${v46Safe(obj[key])}</span>`).join('') + '</div>';
}'''
    h = h[:start] + new_rows + h[end:]

# Replace generic Action Details block if it uses b tags.
h = h.replace(
"body += `<div class=\"section-card\"><h4>Action Details</h4><div class=\"kv\">${Object.keys(args).filter(k=>typeof args[k] !== 'object').map(k=>`<b>${v41Val(k)}</b><span>${v41Val(args[k])}</span>`).join('')}</div></div>`;",
"body += `<div class=\"section-card\"><h4>Action Details</h4><div class=\"kv\">${Object.keys(args).filter(k=>typeof args[k] !== 'object').map(k=>`<span class=\"kv-label\">${v46Safe(k)}</span><span>${v46Safe(args[k])}</span>`).join('')}</div></div>`;"
)

# Add simple label style.
if '.kv-label' not in h:
    h = h.replace('</style>', '\n.kv-label{font-weight:700;color:#475569;}\n</style>')

chat_html.write_text(h, encoding='utf-8')

if readme.exists():
    readme.write_text(readme.read_text(encoding='utf-8') + r'''

## v0.46 Required-four cleanup

- Fixed `update main project of Saleem to ...` extracting intern as `Of Saleem`.
- Fixed `update scenario of Saleem to ...` extraction.
- Generic proposal action details now render as clean key/value rows without raw `<strong data-lexical-text="true">` tags.
''', encoding='utf-8')

print('v0.46 required-four UI/name cleanup patch applied successfully.')
