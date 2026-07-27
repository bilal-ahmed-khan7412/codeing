from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent
chat_path = ROOT / "web" / "chat.html"

if not chat_path.exists():
    raise FileNotFoundError(f"Missing file: {chat_path}")

html = chat_path.read_text(encoding="utf-8")

backup = chat_path.with_suffix(".html.bak_v98")
backup.write_text(html, encoding="utf-8")

marker = "/* ===== v98 clean chat bubble CSS only ===== */"

css = r"""
/* ===== v98 clean chat bubble CSS only ===== */

/*
  Minimal stable bubble styling.
  Do not use float.
  Do not fight layout.
  Normal messages are .msg user/assistant/system inside #chatLog.
  Readonly summaries are .msg assistant v92-summary-bubble after v95.
*/

#chatLog {
  flex: 1 1 auto !im*ortant;
  min-height: 0 !important*
  overflow-y: auto !important;
  *verflow-x: hidden !important;
  pa*ding: 18px !important;
  backgroun*: linear-gradient(#f8fafc, #f4f6fb* !important;
}

#chatLog .msg {
  *isplay: block !important;
  height* auto !important;
  min-height: 0 *important;
  max-height: none !imp*rtant;
  box*sizing: border-box !important;
  o*erflow: visible !important;
  line*height: 1.45 !important;
  border:*1px solid var(--border) !important*
  border-radius: 16px !important;*  padding: 12px 14px !important;
 *margin* 10px 0 !important;
  white-space:*pre-wrap !important;
  overflow-wr*p: anywhere !important;
  word-bre*k: break-word !important;
}

#chat*og .msg.user {
  margin-left: auto*!important;
  margin*right: 0 !important*
  max-width: 78% !important;
  wi*th: fit-content !important;
  back*round: var(--user) !important;
  b*rder-bottom-right-radius: 6px !imp*rtant;
}

#chatLog .msg.assistant *
  margin-left: 0 !important;
  ma*gin-right: auto !important;
  max-*idth: 86% !important;
  width: fit*content !important;
  background: *ar(--assistant) !important;
  bord*r-bottom-left-radius: 6px !importa*t;
}

#chatLog .msg.system {
  mar*in-left: auto !important;
  margin*right: auto !important;
  max-widt*: 92% !important;
  width: fit-content !important;
  background: #fff7ed !important;
  color: #9a3412 !important;
}

/* Summary card from readonly flow */
#chatLog .msg.v92-summary-bubble {
  width: auto !important;
  max-width: 86% !important;
  min-width: 0 !important;
  padding: 16px 18px !important;
  white-space: normal !important;
  background: #ffffff !important;
}

#chatLog .msg.v92-summary-bubble * {
  max-width: 100% !important;
  box-sizing: border-box !important;
  overflow-wrap: anywhere !important;
  word-break: break-word !important;
}

#chatLog .msg.v92-summary-bubble h3 {
  margin: 0 0 12px 0 !important;
  padding-bottom: 10px !important;
  color: #1f3f75 !important;
  border-bottom: 1px solid var(--border) !important;
}

#chatLog .msg.v92-summary-bubble ul,
#chatLog .msg.v92-summary-bubble ol {
  margin: 10px 0 0 22px !important;
  padding: 0 !important;
}

#chatLog .msg.v92-summary-bubble li {
  margin: 8px 0 !important;
}

.composer {
  flex: 0 0 auto !important;
  flex-shrink: 0 !important;
}
"""

if marker in html:
    print("v98 CSS already exists. Skipping.")
else:
    body_close = re.search(r"</body\s*>", html, flags=re.IGNORECASE)
    style_block = '\n<style id="v98-clean-chat-bubble-css-only">\n' + css + "\n</style>\n"
    if body_close:
        html = html[:body_close.start()] + style_block + html[body_close.start():]
    else:
        html += style_block

chat_path.write_text(html, encoding="utf-8")

print("Applied v98 clean chat bubble CSS only.")
print(f"Patched: {chat_path}")
print(f"Backup:  {backup}")