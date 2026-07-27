from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent
chat_path = ROOT / "web" / "chat.html"

if not chat_path.exists():
    raise FileNotFoundError(f"Missing file: {chat_path}")

html = chat_path.read_text(encoding="utf-8")

backup = chat_path.with_suffix(".html.bak_v96")
backup.write_text(html, encoding="utf-8")

marker = "/* ===== v96 chat bubble card UI fix ===== */"

css = r"""
/* ===== v96 chat bubble card UI fix ===== */

/*
  Fixes bubble/card visual issue after v95:
  - normal assistant bubbles must wrap all text lines
  - user bubbles should stay compact
  - readonly progress summary should render as one full card
  - HTML content inside summary must stay inside the card
*/

/* Keep chat history as a normal vertical message stream */
#chatLog {
  display: bl*ck !important;
  overflow-y: auto *important;
  overflow-x: hidden !important;
  padding: 18px 30px 24px 30px !important;
}

/* Base message bubble reset */
#chatLog .msg {
  display: block !important;
  clear: both !important;

  height: auto !important;
  min-height: unset !important;
  max-height: none !important;

  box-sizing: border-box !important;
  overflow: visible !important;

  line-height: 1.45 !important;
  white-space: pre-wrap !important;
  overflow-wrap: anywhere !important;
  word-break: break-word !important;

  border: 1px solid var(--border) !important;
  box-shadow: none !important;
}

/* Assistant normal text bubbles */
#chatLog .msg.assistant:not(.v92-summary-bubble) {
  float: left !important;
  width: fit-content !important;
  max-width: min(86%, 920px) !important;

  margin: 12px 0 18px 0 !important;
  padding: 16px 20px !important;

  background: #ffffff !important;
  color: #061a33 !important;
  border-radius: 16px !important;
  border-bottom-left-radius: 6px !important;
}

/* User bubbles */
#chatLog .msg.user:not(.v92-summary-user) {
  float: right !important;
  width: fit-content !important;
  max-width: min(72%, 520px) !important;

  margin: 12px 0 18px auto !important;
  padding: 14px 18px !important;

  background: #d9eaff !important;
  color: #061a33 !important;
  border-radius: 16px !important;
  border-bottom-right-radius: 6px !important;
}

/* System messages */
#chatLog .msg.system {
  float: none !important;
  width: fit-content !important;
  max-width: min(92%, 980px) !important;

  margin: 12px auto 18px auto !important;
  padding: 14px 18px !important;

  background: #fff7ed !important;
  color: #9a3412 !important;
  border-radius: 14px !important;
}

/* Readonly user prompt inside chat log */
#chatLog .msg.v92-summary-user {
  float: right !important;
  width: fit-content !important;
  max-width: min(72%, 520px) !important;

  margin: 12px 0 18px auto !important;
  padding: 14px 18px !important;

  background: #d9eaff !important;
  color: #061a33 !important;
  border: 1px solid var(--border) !important;
  border-radius: 16px !important;
  border-bottom-right-radius: 6px !important;
}

/* Readonly progress summary should be a full card, not a tiny text bubble */
#chatLog .msg.v92-summary-bubble {
  float: left !important;
  display: block !important;

  width: min(86%, 960px) !important;
  max-width: min(86%, 960px) !important;
  min-width: 420px !important;

  height: auto !important;
  min-height: 0 !important;
  max-height: none !important;

  margin: 18px 0 24px 0 !important;
  padding: 18px 26px !important;

  background: #ffffff !important;
  color: #1f2937 !important;
  border: 1px solid var(--border) !important;
  border-radius: 16px !important;
  box-shadow: 0 4px 14px rgba(15, 23, 42, 0.06) !important;

  white-space: normal !important;
  overflow: visible !important;
}

/* Force summary HTML to live inside the card visually */
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

/* Better summary spacing */
#chatLog .v92-summary-bubble h3 {
  margin: 0 0 16px 0 !important;
  padding: 0 0 10px 0 !important;
  color: #1f3f75 !important;
  border-bottom: 1px solid var(--border) !important;
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

/* Clear floats before composer area */
#chatLog::after {
  content: "";
  display: block;
  clear: both;
}

/* Mobile safety */
@media (max-width: 700px) {
  #chatLog .msg,
  #chatLog .msg.user,
  #chatLog .msg.assistant,
  #chatLog .msg.v92-summary-user,
  #chatLog .msg.v92-summary-bubble {
    float: none !important;
    width: auto !important;
    max-width: 100% !important;
    min-width: 0 !important;
    margin-left: 0 !important;
    margin-right: 0 !important;
  }
}
"""

if marker in html:
    print("v96 CSS already exists. Skipping.")
else:
    # Insert late, before closing body, so it overrides v92/v93/v94 styles.
    body_close = re.search(r"</body\s*>", html, flags=re.IGNORECASE)
    style_block = "\n<style id=\"v96-chat-bubble-card-ui-fix\">\n" + css + "\n</style>\n"

    if body_close:
        html = html[:body_close.start()] + style_block + html[body_close.start():]
    else:
        html += style_block

chat_path.write_text(html, encoding="utf-8")

print("Applied v96 chat bubble/card UI fix.")
print(f"Patched: {chat_path}")
print(f"Backup:  {backup}")