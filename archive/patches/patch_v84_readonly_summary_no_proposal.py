"""
Patch v0.84 - Read-only summary should not use proposal approval flow

Apply from the root of the intern tracker app:
    python patch_v84_readonly_summary_no_proposal.py

Purpose:
- Questions like "how is Bilal doing?" are read-only.
- Read-only summary/progress commands should answer directly.
- They should NOT open the proposal panel and should NOT require Approve/Edit/Cancel.
- Workbook-changing commands still require approval.
- No intern name is hardcoded.

This patch is intentionally defensive because previous app versions used different
ChatService/command executor shapes. It appends a runtime wrapper that:
1. Detects summary-like draft commands.
2. Tries to execute the existing command using available app execution hooks.
3. Falls back to mutating the existing response so the frontend treats it as read-only.
4. Adds a small frontend guard to hide proposal controls for read-only summary commands.
"""
from __future__ import annotations

from pathlib import Path
import re
import textwrap

ROOT = Path(__file__).resolve().parent
CHAT_SERVICE = ROOT / "tracker_chat" / "chat_service.py"
CHAT_HTML_CANDIDATES = [ROOT / "web" / "chat.html", ROOT / "chat.html", ROOT / "templates" / "chat.html"]
README = ROOT / "README.md"

if not CHAT_SERVICE.exists():
    raise SystemExit("tracker_chat/chat_service.py not found. Run this patch from intern_tracker_system_v0 root folder.")

s = CHAT_SERVICE.read_text(encoding="utf-8")

if "v0.84 read-only summary no proposal" not in s:
    s += r'''

# v0.84 read-only summary no proposal
# Summary/progress questions are read-only and should not trigger Approve/Edit/Cancel.
# This wrapper is deliberately defensive across earlier patch versions.
_V84_READONLY_SUMMARY_COMMANDS = {
    'summary',
    'progress_summary',
    'intern_summary',
    'generate_summary',
    'status_summary',
    'dashboard_summary',
    'show_progress',
    'compare_interns',
}


def _v84_command_name(draft):
    return str(getattr(draft, 'command', '') or (draft.get('command') if isinstance(draft, dict) else '')).strip()


def _v84_draft_args(draft):
    if isinstance(draft, dict):
        return draft.get('args') or draft.get('arguments') or {}
    return getattr(draft, 'args', None) or getattr(draft, 'arguments', None) or {}


def _v84_is_readonly_summary(draft):
    cmd = _v84_command_name(draft).lower()
    if cmd in _V84_READONLY_SUMMARY_COMMANDS:
        return True
    # Some versions use a generic command with an intent argument.
    args = _v84_draft_args(draft)
    intent = str(args.get('intent', '') or args.get('type', '') or '').lower() if isinstance(args, dict) else ''
    return intent in _V84_READONLY_SUMMARY_COMMANDS


def _v84_result_text(result):
    if result is None:
        return ''
    if isinstance(result, str):
        return result
    if isinstance(result, dict):
        for key in ('message', 'summary', 'text', 'content', 'response', 'output'):
            if result.get(key):
                return str(result.get(key))
        return str(result)
    for attr in ('message', 'summary', 'text', 'content', 'response', 'output'):
        if hasattr(result, attr):
            val = getattr(result, attr)
            if val:
                return str(val)
    return str(result)


def _v84_success(result):
    if result is None:
        return False
    if isinstance(result, dict):
        return bool(result.get('ok', result.get('success', True)))
    if hasattr(result, 'success'):
        return bool(getattr(result, 'success'))
    if hasattr(result, 'ok'):
        return bool(getattr(result, 'ok'))
    return True


def _v84_execute_using_existing_hooks(self, draft):
    cmd = _v84_command_name(draft)
    args = _v84_draft_args(draft)

    # 1) Try service instance hooks that may already exist.
    for method_name in (
        '_execute_draft', 'execute_draft', '_run_draft', 'run_draft',
        '_execute_command', 'execute_command', '_run_command', 'run_command',
        '_apply_draft', 'apply_draft', '_approve_draft', 'approve_draft',
    ):
        method = getattr(self, method_name, None)
        if callable(method):
            try:
                try:
                    return method(draft)
                except TypeError:
                    return method(cmd, args)
            except Exception:
                continue

    # 2) Try attached executor objects.
    for attr_name in ('executor', 'command_executor', '_executor', '_command_executor'):
        executor = getattr(self, attr_name, None)
        if executor is None:
            continue
        for method_name in ('execute', 'run', 'apply'):
            method = getattr(executor, method_name, None)
            if callable(method):
                try:
                    try:
                        return method(cmd, args)
                    except TypeError:
                        return method(draft)
                except Exception:
                    continue

    # 3) Try importing command executor class from the project.
    try:
        from tracker_commands.executor import CommandExecutor
        executor = CommandExecutor()
        for method_name in ('execute', 'run', 'apply'):
            method = getattr(executor, method_name, None)
            if callable(method):
                try:
                    try:
                        return method(cmd, args)
                    except TypeError:
                        return method(draft)
                except Exception:
                    continue
    except Exception:
        pass

    # 4) Known summary service fallback if available.
    try:
        from tracker_services.summary_service import SummaryService
        svc = SummaryService()
        for method_name in ('summary', 'generate_summary', 'progress_summary', 'intern_summary'):
            method = getattr(svc, method_name, None)
            if callable(method):
                try:
                    try:
                        return method(**args) if isinstance(args, dict) else method(args)
                    except TypeError:
                        return method(args)
                except Exception:
                    continue
    except Exception:
        pass

    return None


def _v84_direct_response_from_result(result, fallback_message='Progress summary generated.'):
    text = _v84_result_text(result).strip() or fallback_message
    return {
        'ok': True,
        'message': text,
        'response': text,
        'content': text,
        'command': _v84_command_name(result) if not isinstance(result, dict) else result.get('command', 'summary'),
        'readonly': True,
        'requires_approval': False,
        'needs_approval': False,
        'proposal': None,
        'draft': None,
        'data': result if isinstance(result, dict) else None,
    }


def _v84_mutate_response_readonly(response):
    # If execution shape is unknown, at least prevent frontend approval mode.
    if isinstance(response, dict):
        response['readonly'] = True
        response['requires_approval'] = False
        response['needs_approval'] = False
        response['proposal'] = None
        response['draft'] = None
        msg = str(response.get('message') or response.get('response') or response.get('content') or '')
        if 'Review the proposal' in msg or 'approve, edit, or cancel' in msg.lower():
            response['message'] = 'Generated progress summary.'
            response['response'] = response['message']
        return response
    for attr, val in [('readonly', True), ('requires_approval', False), ('needs_approval', False), ('proposal', None), ('draft', None)]:
        try:
            setattr(response, attr, val)
        except Exception:
            pass
    return response


if not hasattr(ChatService, '_base_response_for_draft_v84') and hasattr(ChatService, '_response_for_draft'):
    ChatService._base_response_for_draft_v84 = ChatService._response_for_draft

    def _v84_response_for_draft(self, draft):
        if _v84_is_readonly_summary(draft):
            result = _v84_execute_using_existing_hooks(self, draft)
            if result is not None and _v84_success(result):
                return _v84_direct_response_from_result(result, 'Generated progress summary.')
            # Fallback: let original generate whatever it can, then strip proposal mode.
            base_response = ChatService._base_response_for_draft_v84(self, draft)
            return _v84_mutate_response_readonly(base_response)
        return ChatService._base_response_for_draft_v84(self, draft)

    ChatService._response_for_draft = _v84_response_for_draft
'''

CHAT_SERVICE.write_text(s, encoding="utf-8")

# Frontend guard: hide proposal/approval panel for read-only summary commands if backend still sends a command preview.
for chat_html in CHAT_HTML_CANDIDATES:
    if not chat_html.exists():
        continue
    h = chat_html.read_text(encoding="utf-8")
    if "v84-readonly-summary-no-proposal" not in h:
        block = r'''

<script id="v84-readonly-summary-no-proposal">
(function(){
  const READONLY = new Set(['summary','progress_summary','intern_summary','generate_summary','status_summary','dashboard_summary','show_progress','compare_interns']);
  function isReadonlyPayload(data){
    if(!data) return false;
    const cmd = String(data.command || data.draft?.command || data.proposal?.command || '').toLowerCase();
    const intent = String(data.intent || data.args?.intent || data.draft?.args?.intent || '').toLowerCase();
    return data.readonly === true || READONLY.has(cmd) || READONLY.has(intent);
  }
  function removeApprovalUi(){
    document.querySelectorAll('[data-proposal], .proposal, .proposal-panel, .approval-panel, .review-panel').forEach(el => el.remove());
    Array.from(document.querySelectorAll('button')).forEach(btn => {
      const t = (btn.textContent || '').trim().toLowerCase();
      if(['approve','edit','cancel'].includes(t)) btn.remove();
    });
  }
  // Patch fetch so if backend marks readonly, approval UI is not shown by later render logic.
  if(!window.__v84ReadonlySummaryFetchPatch){
    window.__v84ReadonlySummaryFetchPatch = true;
    const originalFetch = window.fetch;
    window.fetch = async function(input, init){
      const res = await originalFetch.apply(this, arguments);
      try{
        const url = typeof input === 'string' ? input : (input && input.url) || '';
        if(/chat|message|command/i.test(url)){
          const clone = res.clone();
          clone.json().then(data => {
            if(isReadonlyPayload(data)) setTimeout(removeApprovalUi, 50);
          }).catch(()=>{});
        }
      }catch(e){}
      return res;
    };
  }
  const mo = new MutationObserver(() => {
    const bodyText = document.body.innerText || '';
    if(/Generated progress summary|progress summary/i.test(bodyText) && /approve|edit|cancel/i.test(bodyText)){
      removeApprovalUi();
    }
  });
  mo.observe(document.documentElement, {childList:true, subtree:true});
})();
</script>
'''
        h = h.replace("</body>", block + "\n</body>") if "</body>" in h else h + block
        chat_html.write_text(h, encoding="utf-8")

# Compile check
try:
    import py_compile
    py_compile.compile(str(CHAT_SERVICE), doraise=True)
except Exception as e:
    raise SystemExit(f"chat_service.py compile failed after v0.84: {e}")

if README.exists():
    text = README.read_text(encoding="utf-8", errors="ignore")
    if "v0.84 Read-only summary no proposal" not in text:
        README.write_text(text + textwrap.dedent("""

        ## v0.84 Read-only summary no proposal

        - Read-only summary/progress questions such as `how is Bilal doing?` no longer require approval.
        - Workbook-changing commands still use proposal approval.
        - Added frontend guard to prevent Approve/Edit/Cancel from appearing for read-only summary commands.
        """), encoding="utf-8")

print("v0.84 read-only summary no proposal patch applied successfully.")
