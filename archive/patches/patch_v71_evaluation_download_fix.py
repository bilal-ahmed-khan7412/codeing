from pathlib import Path

root = Path(__file__).resolve().parent
web_app = root / 'web_app.py'
readme = root / 'README.md'

if not web_app.exists():
    raise SystemExit('web_app.py not found. Run this patch inside intern_tracker_system_v0.')

s = web_app.read_text(encoding='utf-8')

# v0.71: Evaluation download fix.
# Problem: /api/evaluation/finalize returned /download?path=<absolute Windows path>.
# On Windows this produced a URL like:
#   /download?path=D:\OneDrive ...\outputs\Evaluated_....xlsx
# Some existing download route rejects or cannot resolve this, causing 404.
# Fix: add a dedicated /evaluation/download endpoint that downloads by filename
# from the trusted outputs folder, and return that URL from finalize.

# Ensure FileResponse import exists.
if 'FileResponse' not in s:
    if 'from fastapi.responses import ' in s:
        s = s.replace('from fastapi.responses import ', 'from fastapi.responses import FileResponse, ', 1)
    else:
        s = 'from fastapi.responses import FileResponse\n' + s

# Add dedicated evaluation download endpoint.
if "@app.get('/evaluation/download')" not in s:
    endpoint = r'''

@app.get('/evaluation/download')
def evaluation_download(request: Request, file: str):
    user = require_login(request)
    if user.get('role') not in {'Super Admin', 'Admin'}:
        return JSONResponse(status_code=403, content={'ok': False, 'error': 'Admin or Super Admin only'})
    # Only allow downloading files from outputs by filename, not arbitrary paths.
    safe_name = Path(file).name
    target = BASE_DIR / 'outputs' / safe_name
    if not target.exists() or not target.is_file():
        return JSONResponse(status_code=404, content={'ok': False, 'error': f'Evaluation output not found: {safe_name}'})
    return FileResponse(str(target), filename=safe_name, media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
'''
    s += endpoint

# Patch finalize route to return filename-based evaluation download URL.
old = "return {'ok': True, 'output_path': str(out), 'download': '/download?path=' + str(out)}"
new = "return {'ok': True, 'output_path': str(out), 'download': '/evaluation/download?file=' + Path(out).name}"
if old in s:
    s = s.replace(old, new, 1)
else:
    # Handle already partially modified versions.
    import re
    s2 = re.sub(r"return \{'ok': True, 'output_path': str\(out\), 'download': .*?\}", new, s, count=1)
    if s2 == s:
        print('Warning: Could not find finalize download return. Dedicated download route was still added.')
    s = s2

web_app.write_text(s, encoding='utf-8')

# Compile check.
try:
    import py_compile
    py_compile.compile(str(web_app), doraise=True)
except Exception as e:
    raise SystemExit(f'web_app.py compile failed after v0.71 patch: {e}')

if readme.exists():
    readme.write_text(readme.read_text(encoding='utf-8') + r'''

## v0.71 Evaluation download fix

- Fixed evaluated workbook download 404 caused by returning an absolute Windows path in `/download?path=...`.
- Added a dedicated endpoint:
  `/evaluation/download?file=<filename>`
- Finalization now returns a filename-based download URL that safely serves files from `outputs/`.
''', encoding='utf-8')

print('v0.71 evaluation download fix applied successfully.')
