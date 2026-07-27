from pathlib import Path

root = Path(__file__).resolve().parent
web_app = root / 'web_app.py'
if not web_app.exists():
    raise SystemExit('web_app.py not found. Run this patch inside intern_tracker_system_v0.')

s = web_app.read_text(encoding='utf-8')
old = r'''@app.post("/api/chat/approve")
def chat_approve(payload: dict):
    result = chat_service.approve(payload.get('draft_id'))
    if result.get('output_path'):
        result['download'] = f"/download/{Path(result['output_path']).name}"
    return result
'''
new = r'''@app.post("/api/chat/approve")
def chat_approve(payload: dict):
    """Approve and execute a chat draft.

    Important: chat drafts are created in the browser using the Current Workbook label.
    That label may be just a filename such as Rendered_Extended.xlsx. Before executing,
    normalize source/workbook/output paths exactly like /api/execute does, otherwise
    openpyxl may look in the project root and fail when the file is actually in outputs/.
    """
    draft_id = payload.get('draft_id')
    draft = getattr(chat_service, 'drafts', {}).get(draft_id)
    if not draft:
        return JSONResponse(status_code=404, content={'ok': False, 'error': 'Draft not found'})
    try:
        args = draft.args
        if 'source' in args:
            args['source'] = resolve_workbook(args['source'])
        if 'workbook' in args:
            args['workbook'] = resolve_workbook(args['workbook'])
        if 'output' in args:
            args['output'] = output_path(args.get('output'), draft.command or 'chat')
        elif draft.command not in {'summary'}:
            args['output'] = output_path(None, draft.command or 'chat')
        result = chat_service.approve(draft_id)
        if result.get('output_path'):
            result['download'] = f"/download/{Path(result['output_path']).name}"
        return result
    except Exception as e:
        return JSONResponse(status_code=500, content={'ok': False, 'error': str(e)})
'''
if old not in s:
    raise SystemExit('Could not find existing chat_approve block. Patch may already be applied or file differs.')
web_app.write_text(s.replace(old, new), encoding='utf-8')
print('v0.17 chat approve path resolver applied successfully.')
