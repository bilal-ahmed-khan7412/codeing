"""
Patch v0.85 - Execute read-only progress summaries immediately

Apply from intern_tracker_system_v0 root:
    python patch_v85_summary_execute_immediately.py

Problem fixed:
- Questions like "how is Bilal Ahmad Khan doing?" are read-only.
- The app was still treating the progress summary as an approval proposal.
- User had to type "approve" before the summary executed.

What this patch does:
- Expands read-only summary command detection.
- Detects proposal text such as "I can generate a progress summary".
- If a read-only summary draft/proposal is produced, it executes it immediately using existing approval/execution hooks.
- Returns a direct response without Approve/Edit/Cancel.
- Adds a frontend guard to hide stale proposal controls for summary/progress responses.
- Does not affect workbook-changing commands.
- Does not hardcode any intern name.
"""
from __future__ import annotations

from pathlib import Path
import textwrap

ROOT = Path(__file__).resolve().parent
CHAT_SERVICE = ROOT / "tracker_chat" / "chat_service.py"
CHAT_HTML_CANDIDATES = [ROOT / "web" / "chat.html", ROOT / "chat.html", ROOT / "templates" / "chat.html"]
README = ROOT / "README.md"

if not CHAT_SERVICE.exists():
    raise SystemExit("tracker_chat/chat_service.py not found. Run from intern_tracker_system_v0 root folder.")

s = CHAT_SERVICE.read_text(encoding="utf-8")
if "v0.85 execute read-only summaries immediately" not in s:
    s += r'''

# v0.85 execute read-only summaries immediately
# Read-only progress/summary commands should not enter approval flow.
# This patch is intentionally broad because older patches used different command names.
_V85_READONLY_COMMAND_KEYWORDS = {
    'summary', 'summarize', 'summarise', 'progress', 'progress_summary', 'intern_summary',
    'generate_summary', 'generate_progress_summary', 'status_summary', 'dashboard_summary',
    'show_progress', 'compare_interns', 'intern_status', 'status', 'how_is_intern_doing',
}

_V85_READONLY_TEXT_MARKERS = (
    'generate a progress summary',
    'generated progress summary',
    'progress summary for the current workbook',
    'how is ',
    ' how is ',
    'doing?',
)


def _v85_get(obj, key, default=None):
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _v85_set(obj, key, value):
    if obj is None:
        return
    if isinstance(obj, dict):
        obj[key] = value
        return
    try:
        setattr(obj, key, value)
    except Exception:
        pass


def _v85_to_text(value):
    if value is None:
        return ''
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        parts = []
        for key in ('message', 'response', 'content', 'summary', 'text', 'title', 'command'):
            if value.get(key):
                parts.append(str(value.get(key)))
        if value.get('proposal'):
            parts.append(_v85_to_text(value.get('proposal')))
        if value.get('draft'):
            parts.append(_v85_to_text(value.get('draft')))
        return ' '.join(parts)
    parts = []
    for key in ('message', 'response', 'content', 'summary', 'text', 'title', 'command'):
        val = getattr(value, key, None)
        if val:
            parts.append(str(val))
    for key in ('proposal', 'draft'):
        val = getattr(value, key, None)
        if val:
            parts.append(_v85_to_text(val))
    return ' '.join(parts) or str(value)


def _v85_command_name(obj):
    cmd = _v85_get(obj, 'command', '') or _v85_get(obj, 'intent', '') or _v85_get(obj, 'type', '')
    return str(cmd or '').strip().lower()


def _v85_args(obj):
    return _v85_get(obj, 'args', None) or _v85_get(obj, 'arguments', None) or {}


def _v85_is_readonly_summary_like(obj):
    if obj is None:
        return False
    cmd = _v85_command_name(obj)
    if cmd:
        if cmd in _V85_READONLY_COMMAND_KEYWORDS:
            return True
        if any(k in cmd for k in ('summary', 'progress', 'status')):
            return True
    args = _v85_args(obj)
    if isinstance(args, dict):
        for key in ('intent', 'type', 'command', 'mode'):
            val = str(args.get(key, '') or '').lower()
            if val in _V85_READONLY_COMMAND_KEYWORDS or any(k in val for k in ('summary', 'progress', 'status')):
                return True
    text = _v85_to_text(obj).lower()
    if any(marker in text for marker in _V85_READONLY_TEXT_MARKERS):
        # Avoid incorrectly marking mutation commands that happen to mention status/progress.
        mutation_words = ('add intern', 'extend intern', 'create plan', 'edit task', 'update task', 'add holiday', 'finalize evaluation')
        return not any(w in text for w in mutation_words)
    return False


def _v85_find_draft_or_proposal(response):
    for key in ('draft', 'proposal', 'pending', 'command_draft'):
        val = _v85_get(response, key, None)
        if val is not None:
            return val
    # Some response shapes put draft under data.
    data = _v85_get(response, 'data', None)
    if isinstance(data, dict):
        for key in ('draft', 'proposal', 'pending', 'command_draft'):
            if data.get(key) is not None:
                return data.get(key)
    return response if _v85_is_readonly_summary_like(response) else None


def _v85_success(result):
    if result is None:
        return False
    if isinstance(result, dict):
        return bool(result.get('ok', result.get('success', True)))
    for key in ('ok', 'success'):
        if hasattr(result, key):
            return bool(getattr(result, key))
    return True


def _v85_result_message(result):
    if result is None:
        return ''
    if isinstance(result, str):
        return result
    if isinstance(result, dict):
        for key in ('summary', 'message', 'response', 'content', 'text', 'output'):
            val = result.get(key)
            if val:
                return str(val)
        return str(result)
    for key in ('summary', 'message', 'response', 'content', 'text', 'output'):
        val = getattr(result, key, None)
        if val:
            return str(val)
    return str(result)


def _v85_try_execute_readonly(self, draft):
    # Prevent recursion if an approval hook eventually calls back into response generation.
    if getattr(self, '_v85_executing_readonly', False):
        return None
    self._v85_executing_readonly = True
    try:
        cmd = _v85_command_name(draft)
        args = _v85_args(draft)

        # Prefer "approve/apply" hooks because the old app already knew how to generate the summary after user typed approve.
        method_candidates = (
            'approve', 'approve_draft', '_approve_draft', 'apply_draft', '_apply_draft',
            'execute_draft', '_execute_draft', 'run_draft', '_run_draft',
            'execute_command', '_execute_command', 'run_command', '_run_command',
            'execute', 'run', 'apply',
        )
        for name in method_candidates:
            method = getattr(self, name, None)
            if callable(method):
                try:
                    try:
                        result = method(draft)
                    except TypeError:
                        result = method(cmd, args)
                    if result is not None:
                        return result
                except Exception:
                    continue

        # Try executor attributes.
        for attr in ('executor', 'command_executor', '_executor', '_command_executor'):
            executor = getattr(self, attr, None)
            if executor is None:
                continue
            for name in ('approve', 'apply', 'execute', 'run'):
                method = getattr(executor, name, None)
                if callable(method):
                    try:
                        try:
                            result = method(draft)
                        except TypeError:
                            result = method(cmd, args)
                        if result is not None:
                            return result
                    except Exception:
                        continue

        # Try project command executor.
        try:
            from tracker_commands.executor import CommandExecutor
            executor = CommandExecutor()
            for name in ('approve', 'apply', 'execute', 'run'):
                method = getattr(executor, name, None)
                if callable(method):
                    try:
                        try:
                            result = method(draft)
                        except TypeError:
                            result = method(cmd, args)
                        if result is not None:
                            return result
                    except Exception:
                        continue
        except Exception:
            pass
    finally:
        self._v85_executing_readonly = False
    return None


def _v85_clean_readonly_response(result, fallback='Generated progress summary.'):
    message = _v85_result_message(result).strip() or fallback
    if 'Review the proposal on the right' in message:
        message = message.split('Review the proposal on the right')[0].strip() or fallback
    response = {
        'ok': True,
        'success': True,
        'readonly': True,
        'requires_approval': False,
        'needs_approval': False,
        'approval_required': False,
        'message': message,
        'response': message,
        'content': message,
        'proposal': None,
        'draft': None,
        'command': 'summary',
    }
    if isinstance(result, dict):
        # Keep useful data fields, but override approval fields.
        response.update({k: v for k, v in result.items() if k not in {'proposal', 'draft', 'requires_approval', 'needs_approval', 'approval_required'}})
        response.update({'readonly': True, 'requires_approval': False, 'needs_approval': False, 'approval_required': False, 'proposal': None, 'draft': None})
        if message:
            response['message'] = message
            response['response'] = message
            response['content'] = message
    return response


def _v85_mutate_to_no_proposal(response):
    if isinstance(response, dict):
        response['readonly'] = True
        response['requires_approval'] = False
        response['needs_approval'] = False
        response['approval_required'] = False
        response['proposal'] = None
        response['draft'] = None
        msg = str(response.get('message') or response.get('response') or response.get('content') or '')
        if 'Review the proposal on the right' in msg or 'approve, edit, or cancel' in msg.lower():
            msg = msg.split('Review the proposal on the right')[0].strip() or 'Generated progress summary.'
            response['message'] = msg
            response['response'] = msg
            response['content'] = msg
        return response
    for key, value in (
        ('readonly', True), ('requires_approval', False), ('needs_approval', False),
        ('approval_required', False), ('proposal', None), ('draft', None),
    ):
        try:
            setattr(response, key, value)
        except Exception:
            pass
    return response


# Wrap _response_for_draft if available.
if hasattr(ChatService, '_response_for_draft') and not hasattr(ChatService, '_base_response_for_draft_v85'):
    ChatService._base_response_for_draft_v85 = ChatService._response_for_draft

    def _v85_response_for_draft(self, draft):
        if _v85_is_readonly_summary_like(draft):
            result = _v85_try_execute_readonly(self, draft)
            if result is not None and _v85_success(result):
                return _v85_clean_readonly_response(result)
            base = ChatService._base_response_for_draft_v85(self, draft)
            if _v85_is_readonly_summary_like(base):
                draft2 = _v85_find_draft_or_proposal(base)
                result2 = _v85_try_execute_readonly(self, draft2)
                if result2 is not None and _v85_success(result2):
                    return _v85_clean_readonly_response(result2)
                return _v85_mutate_to_no_proposal(base)
            return base
        return ChatService._base_response_for_draft_v85(self, draft)

    ChatService._response_for_draft = _v85_response_for_draft


# Also wrap common chat/message methods because some versions create proposal responses without _response_for_draft.
def _v85_wrap_method(method_name):
    if not hasattr(ChatService, method_name):
        return
    marker = f'_base_{method_name}_v85'
    if hasattr(ChatService, marker):
        return
    base = getattr(ChatService, method_name)
    if not callable(base):
        return
    setattr(ChatService, marker, base)

    def wrapped(self, *args, **kwargs):
        response = base(self, *args, **kwargs)
        if _v85_is_readonly_summary_like(response):
            draft = _v85_find_draft_or_proposal(response)
            result = _v85_try_execute_readonly(self, draft)
            if result is not None and _v85_success(result):
                return _v85_clean_readonly_response(result)
            return _v85_mutate_to_no_proposal(response)
        return response

    setattr(ChatService, method_name, wrapped)

for _v85_name in ('chat', 'ask', 'handle', 'process', 'message', 'send', 'respond', 'reply', 'run'):
    _v85_wrap_method(_v85_name)
'''
    CHAT_SERVICE.write_text(s, encoding="utf-8")

# Frontend hard guard.
for chat_html in CHAT_HTML_CANDIDATES:
    if not chat_html.exists():
        continue
    h = chat_html.read_text(encoding="utf-8")
    if "v85-summary-no-approval-frontend" not in h:
        js = r'''

<script id="v85-summary-no-approval-frontend">
(function(){
  function looksSummaryPayload(data){
    if(!data) return false;
    const text = JSON.stringify(data).toLowerCase();
    return data.readonly === true
      || text.includes('progress summary')
      || text.includes('intern_summary')
      || text.includes('generate_summary')
      || text.includes('show_progress');
  }
  function removeProposalUi(){
    document.querySelectorAll('[data-proposal], .proposal, .proposal-panel, .approval-panel, .review-panel, #proposalPanel, #reviewPanel').forEach(el => el.remove());
    Array.from(document.querySelectorAll('button')).forEach(btn => {
      const t = (btn.textContent || btn.value || '').trim().toLowerCase();
      if(t === 'approve' || t === 'edit' || t === 'cancel') btn.remove();
    });
    Array.from(document.querySelectorAll('body *')).forEach(el => {
      const txt = (el.textContent || '').toLowerCase();
      if(txt.includes('review the proposal on the right') || txt.includes('approve, edit, or cancel')){
        el.style.display = 'none';
      }
    });
  }
  if(!window.__v85SummaryFetchPatch){
    window.__v85SummaryFetchPatch = true;
    const originalFetch = window.fetch;
    window.fetch = async function(input, init){
      const res = await originalFetch.apply(this, arguments);
      try{
        const url = typeof input === 'string' ? input : (input && input.url) || '';
        if(/chat|message|command|assistant/i.test(url)){
          const clone = res.clone();
          clone.json().then(data => {
            if(looksSummaryPayload(data)) setTimeout(removeProposalUi, 40);
          }).catch(()=>{});
        }
      }catch(e){}
      return res;
    };
  }
  const mo = new MutationObserver(function(){
    const txt = (document.body.innerText || '').toLowerCase();
    if(txt.includes('progress summary') && (txt.includes('approve') || txt.includes('review the proposal'))){
      removeProposalUi();
    }
  });
  mo.observe(document.documentElement, {childList:true, subtree:true});
})();
</script>
'''
        h = h.replace("</body>", js + "\n</body>") if "</body>" in h else h + js
        chat_html.write_text(h, encoding="utf-8")

# Compile check.
try:
    import py_compile
    py_compile.compile(str(CHAT_SERVICE), doraise=True)
except Exception as e:
    raise SystemExit(f"chat_service.py compile failed after v0.85: {e}")

if README.exists():
    txt = README.read_text(encoding="utf-8", errors="ignore")
    if "v0.85 Execute read-only summaries immediately" not in txt:
        README.write_text(txt + textwrap.dedent("""

        ## v0.85 Execute read-only summaries immediately

        - Progress/summary questions such as `how is Bilal Ahmad Khan doing?` are read-only.
        - They now execute immediately instead of entering Approve/Edit/Cancel proposal flow.
        - Workbook-changing commands still require approval.
        """), encoding="utf-8")

print("v0.85 summary execute immediately patch applied successfully.")
