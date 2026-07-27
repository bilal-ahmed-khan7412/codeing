from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent
chat_path = ROOT / "web" / "chat.html"

if not chat_path.exists():
    raise FileNotFoundError(f"Missing file: {chat_path}")

html = chat_path.read_text(encoding="utf-8")

backup = chat_path.with_suffix(".html.bak_v93")
backup.write_text(html, encoding="utf-8")

css_marker = "/* ===== v93 chat leak containment fix ===== */"
js_marker = "// ===== v93 chat leak containment fix ====="

css = r"""
/* ===== v93 chat leak containment fix ===== */

/*
  Fixes chat bubbles leaking outside the chatbox.

  Actual chat.html behavior:
  - JS appends messages into #chatLog
  - each message bubble gets class "msg user", "msg assistant", or "msg system"
*/

html,
body {
  height: 100% !important;
}

/* Keep the chat page from creating uncontrolled vertical growth */
body {
  overflow: hidden !important;
}

/* Main two-column area */
.v93-chat-page {
  height: calc(100vh - 92px) !important;
  max-height: calc(100vh - 92px) !important;
  min-height: 0 !important;
  overflow: hidden !important;
}

/* Left chat card/column */
.v93-chat-card,
.v93-left-column {
  min-height: 0 !important;
  overflow: hidden !important;
  box-sizing: border-box !important;
}

/* The direct parent of #chatLog must be a flex column */
.v93-chat-card {
  display: flex !important;
  flex-direction: column !important;
}

/* Only the message history should scroll */
#chatLog {
  flex: 1 1 auto !important;
  min-height: 0 !important;
  overflow-y: auto !important;
  overflow-x: hidden !important;
  box-sizing: border-box !important;

  display: flex !important;
  flex-direction: column !important;
  gap: 14px !important;

  padding-bottom: 20px !important;
  scroll-behavior: smooth;
}

/* Composer/input must stay at the bottom and never get pushed out */
.v93-chat-composer {
  flex: 0 0 auto !important;
  flex-shrink: 0 !important;
  box-sizing: border-box !important;
}

/* The textarea itself should not stretch layout width */
#chatInput {
  max-width: 100% !important;
  box-sizing: border-box !important;
  resize: vertical;
}

/* Message bubble containment */
#chatLog .msg {
  max-width: min(78%, 900px) !important;
  width: fit-content !important;
  box-sizing: border-box !important;

  overflow-wrap: anywhere !important;
  word-break: break-word !important;
  white-space: pre-wrap !important;

  position: relative !important;
}

/* User bubble stays inside right edge */
#chatLog .msg.user {
  align-self: flex-end !important;
  margin-left: auto !important;
  margin-right: 0 !important;
}

/* Assistant/system bubbles stay inside left edge */
#chatLog .msg.assistant,
#chatLog .msg.system {
  align-self: flex-start !important;
  margin-left: 0 !important;
  margin-right: auto !important;
}

/* Prevent wide proposal / summary content from forcing the layout wider */
#proposalBox,
#proposalBox *,
#chatLog .msg *,
.side,
.side * {
  max-width: 100%;
  box-sizing: border-box;
  overflow-wrap: anywhere;
  word-break: break-word;
}

/* Right sidebar scrolls internally */
.side {
  min-height: 0 !important;
  overflow-y: auto !important;
  overflow-x: hidden !important;
}
"""

js = r"""
// ===== v93 chat leak containment fix =====
(function () {
  function applyV93ChatLeakFix() {
    const chatLog = document.getElementById("chatLog");
    const chatInput = document.getElementById("chatInput");
    const side = document.querySelector(".side");

    if (!chatLog) return;

    const chatCard = chatLog.parentElement;
    if (chatCard) {
      chatCard.classList.add("v93-chat-card");

      const leftColumn = chatCard.parentElement;
      if (leftColumn) {
        leftColumn.classList.add("v93-left-column");

        const possiblePage = leftColumn.parentElement;
        if (possiblePage) {
          possiblePage.classList.add("v93-chat-page");
        }
      }
    }

    if (chatInput) {
      const composer = chatInput.closest("form") || chatInput.parentElement;
      if (composer) {
        composer.classList.add("v93-chat-composer");
      }
    }

    if (side) {
      side.classList.add("v93-side-scroll");
    }

    chatLog.scrollTop = chatLog.scrollHeight;
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", applyV93ChatLeakFix);
  } else {
    applyV93ChatLeakFix();
  }

  window.addEventListener("resize", applyV93ChatLeakFix);
})();
"""

if css_marker in html:
    print("CSS v93 patch already exists. Skipping CSS insert.")
else:
    style_closes = list(re.finditer(r"</style\s*>", html, flags=re.IGNORECASE))
    if style_closes:
        pos = style_closes[-1].start()
        html = html[:pos] + "\n" + css + "\n" + html[pos:]
    else:
        head_close = re.search(r"</head\s*>", html, flags=re.IGNORECASE)
        style_block = "\n<style>\n" + css + "\n</style>\n"
        if head_close:
            html = html[:head_close.start()] + style_block + html[head_close.start():]
        else:
            html = style_block + html

if js_marker in html:
    print("JS v93 patch already exists. Skipping JS insert.")
else:
    script_closes = list(re.finditer(r"</script\s*>", html, flags=re.IGNORECASE))
    if script_closes:
        pos = script_closes[-1].start()
        html = html[:pos] + "\n" + js + "\n" + html[pos:]
    else:
        body_close = re.search(r"</body\s*>", html, flags=re.IGNORECASE)
        script_block = "\n<script>\n" + js + "\n</script>\n"
        if body_close:
            html = html[:body_close.start()] + script_block + html[body_close.start():]
        else:
            html += script_block

chat_path.write_text(html, encoding="utf-8")

print("Applied v93 chat leak containment fix.")
print(f"Patched: {chat_path}")
print(f"Backup:  {backup}")