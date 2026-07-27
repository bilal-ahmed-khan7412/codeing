from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent
chat_path = ROOT / "web" / "chat.html"

if not chat_path.exists():
    raise FileNotFoundError(f"Missing file: {chat_path}")

html = chat_path.read_text(encoding="utf-8")

backup = chat_path.with_suffix(".html.bak_v97")
backup.write_text(html, encoding="utf-8")

marker = "/* ===== v97 stable chat bubble layout final override ===== */"

css = r"""
/* ===== v97 stable chat bubble layout final override ===== */

/*
  Final stable chat bubble fix.

  Fixes:
  - assistant bubble border/background only covering first line
  - "Done..." message getting visually weird after approval
  - readonly "how is Bilal doing?" summary card splitting visually
  - old v92/v93/v94/v96 float/flex conflicts
*/

/* Chat history must be one vertical message stream */
#chatLog {
  flex: 1 1 auto !important;
  min-height: 0 !important;

  display: flex !important;
  flex-direction: column !important;
  align-items: stretch !important;
  justify-content: flex-start !important;
  gap: 14px !important;

  overflow-y: auto !important;
  overflow-x: hidden !important;

  padding: 28px 30px 28px 30px !important;
  background: linear-gradient(#f8fafc, #f4f6fb) !important;
  box-sizing: border-box !important;
}

/* Kill old float-based layout completely */
#chatLog .msg,
#chatLog .msg.user,
#chatLog .msg.assistant,
#chatLog .msg.system,
#chatLog .v92-summary-user,
#chatLog .v92-summary-bubble {
  float: none !important;
  clear: none !important;

  position: static !important;
  display: block !important;

  height: auto !important;
  min-height: 0 !important;
  max-height: none !important;

  width: auto !important;
  min-width: 0 !important;

  box-sizing: border-box !important;
  overflow: visible !important;

  line-height: 1.45 !important;
  border: 1px solid var(--border) !important;
  box-shadow: none !important;

  overflow-wrap: anywhere !important;
  word-break: break-word !important;
}

/* Normal assistant messages */
#chatLog .msg.assistant:not(.v92-summary-bubble) {
  align-self: flex-start !important;

  max-width: min(86%, 940px) !important;
  margin: 0 !important;
  padding: 16px 20px !important;

  background: #ffffff !important;
  color: #061a33 !important;

  border-radius: 16px !important;
  border-bottom-left-radius: 6px !important;

  white-space: pre-wrap !important;
}

/* Normal user messages */
#chatLog .msg.user:not(.v92-summary-user) {
  align-self: flex-end !important;

  max-width: min(72%, 560px) !important;
  margin: 0 !important;
  padding: 14px 18px !important;

  background: #d9eaff !important;
  color: #061a33 !important;

  border-radius: 16px !important;
  border-bottom-right-radius: 6px !important;

  white-space: pre-wrap !important;
}

/* System messages */
#chatLog .msg.system {
  align-self: center !important;

  max-width: min(92%, 980px) !important;
  margin: 0 !important;
  padding: 14px 18px !important;

  background: #fff7ed !important;
  color: #9a3412 !important;

  border-radius: 14px !important;
  white-space: pre-wrap !important;
}

/* Readonly summary user prompt */
#chatLog .msg.v92-summary-user {
  align-self: flex-end !important;

  max-width: min(72%, 560px) !important;
  margin: 0 !important;
  padding: 14px 18px !important;

  background: #d9eaff !important;
  color: #061a33 !important;

  border-radius: 16px !important;
  border-bottom-right-radius: 6px !important;

  white-space: pre-wrap !important;
}

/* Readonly summary answer should be one complete card */
#chatLog .msg.v92-summary-bubble {
  align-self: flex-start !important;

  width: min(86%, 960px) !important;
  max-width: min(86%, 960px) !important;
  min-width: 0 !important;

  margin: 0 !important;
  padding: 20px 26px !important;

  background: #ffffff !important;
  color: #1f2937 !important;

  border: 1px solid var(--border) !important;
  border-radius: 16px !important;
  box-shadow: 0 4px 14px rgba(15, 23, 42, 0.06) !important;

  white-space: normal !important;
  overflow: visible !important;
}

/* Make every child stay inside summary card */
#chatLog .v92-summary-bubble *,
#chatLog .v92-summary-bubble h1,
#chatLog .v92-summary-bubble h2,
#chatLog .v92-summary-bubble h3,
#chatLog .v92-summary-bubble h4,
#chatLog .v92-summary-bubble p,
#chatLog .v92-summary-bubble ul,
#chatLog .v92-summary-bubble ol,
#chatLog .v92-summary-bubble li,
#chatLog .v92-summary-bubble div {
  max-width: 100% !important;
  box-sizing: border-box !important;
  overflow-wrap: anywhere !important;
  word-break: break-word !important;
}

/* Summary card typography */
#chatLog .v92-summary-bubble h3 {
  margin: 0 0 14px 0 !important;
  padding: 0 0 12px 0 !important;
  color: #1f3f75 !important;
  border-bottom: 1px solid var(--border) !important;
}

#chatLog .v92-summary-bubble p {
  margin: 10px 0 !important;
}

#chatLog .v92-summary-bubble ul,
#chatLog .v92-summary-bubble ol {
  margin: 12px 0 0 24px !important;
  padding: 0 !important;
}

#chatLog .v92-summary-bubble li {
  margin: 10px 0 !important;
  line-height: 1.5 !important;
}

/* Composer stays fixed below chat log */
.composer,
.v93-chat-composer {
  flex: 0 0 auto !important;
  flex-shrink: 0 !important;
  box-sizing: border-box !important;
}

/* Mobile safety */
@media (max-width: 700px) {
  #chatLog {
    padding: 18px !important;
  }

  #chatLog .msg,
  #chatLog .msg.user,
  #chatLog .msg.assistant,
  #chatLog .msg.system,
  #chatLog .msg.v92-summary-user,
  #chatLog .msg.v92-summary-bubble {
    align-self: stretch !important;
    width: auto !important;
    max-width: 100% !important;
  }
}
"""

if marker in html:
    print("v97 CSS already exists. Skipping.")
else:
    style_block = "\n<style id=\"v97-stable-chat-bubble-layout\">\n" + css + "\n</style>\n"

    body_close = re.search(r"</body\s*>", html, flags=re.IGNORECASE)
    if body_close:
        html = html[:body_close.start()] + style_block + html[body_close.start():]
    else:
        html += style_block

chat_path.write_text(html, encoding="utf-8")

print("Applied v97 stable chat bubble layout final override.")
print(f"Patched: {chat_path}")
print(f"Backup:  {backup}")