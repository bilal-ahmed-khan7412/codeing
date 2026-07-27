from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent
chat_path = ROOT / "web" / "chat.html"

if not chat_path.exists():
    raise FileNotFoundError(f"Missing file: {chat_path}")

html = chat_path.read_text(encoding="utf-8")

backup = chat_path.with_suffix(".html.bak_v94")
backup.write_text(html, encoding="utf-8")

marker = "/* ===== v94 exact chat bubble height/layout fix ===== */"

css = r"""
/* ===== v94 exact chat bubble height/layout fix ===== */

/*
  Exact fix for current DOM:
  - messages are inside #chatLog
  - each message is .msg.user / .msg.assistant / .msg.system
  - input is #chatInput
  - right panel is .side
*/

/* Keep page stable */
html,
body {
  height: 100% !important;
  margin: 0 !important;
}

/* Main page should not let chat bubbles render outside visible app area */
body {
  overflow: hidden !important;
}

/* Restore sane layout even after earlier v93 helper classes */
.v93-chat-page {
  height: calc(100vh - 92px) !important;
  max-height: calc(100vh - 92px) !important;
  min-height: 0 !important;
  overflow: hidden !important;
}

/* The left card containing #chatLog must be a proper vertical flex container */
.v93-chat-card {
  display: flex !important;
  flex-direction: column !important;
  min-height: 0 !important;
  max-height: 100% !important;
  overflow: hidden !important;
}

/* The message area scrolls internally */
#chatLog {
  flex: 1 1 0 !important;
  min-height: 0 !important;
  height: auto !important;
  max-height: none !important;

  overflow-y: auto !important;
  overflow-x: hidden !important;

  display: flex !important;
  flex-direction: column !important;
  align-items: stretch !important;
  justify-content: flex-start !important;
  gap: 14px !important;

  box-sizing: border-box !important;
  padding: 18px 24px 24px 24px !important;
}

/* Critical fix: message bubbles must not stretch vertically */
#chatLog .msg,
#chatLog div.msg,
.msg.user,
.msg.assistant,
.msg.system {
  display: block !important;

  height: auto !important;
  min-height: 0 !important;
  max-height: none !important;

  width: auto !important;
  min-width: 0 !important;

  flex: 0 0 auto !important;
  flex-grow: 0 !important;
  flex-shrink: 1 !important;

  line-height: 1.45 !important;
  box-sizing: border-box !important;

  overflow-wrap: anywhere !important;
  word-break: break-word !important;
  white-space: pre-wrap !important;
}

/* User bubble: right aligned, compact, contained */
#chatLog .msg.user,
.msg.user {
  align-self: flex-end !important;
  margin-left: auto !important;
  margin-right: 0 !important;

  max-width: min(520px, 72%) !important;
  padding: 14px 18px !important;

  border-radius: 16px !important;
  background: #d9eaff !important;
  color: #061a33 !important;
}

/* Assistant/system bubbles: left aligned, compact, contained */
#chatLog .msg.assistant,
#chatLog .msg.system,
.msg.assistant,
.msg.system {
  align-self: flex-start !important;
  margin-left: 0 !important;
  margin-right: auto !important;

  max-width: min(920px, 86%) !important;
  padding: 16px 20px !important;

  border-radius: 14px !important;
}

/* Input/composer area must stay below chatLog */
.v93-chat-composer {
  flex: 0 0 auto !important;
  flex-shrink: 0 !important;
  min-height: auto !important;
  height: auto !important;
  box-sizing: border-box !important;
}

/* Textarea cannot force layout expansion */
#chatInput {
  max-width: 100% !important;
  box-sizing: border-box !important;
}

/* Right sidebar scrolls inside itself */
.side {
  min-height: 0 !important;
  max-height: calc(100vh - 132px) !important;
  overflow-y: auto !important;
  overflow-x: hidden !important;
  box-sizing: border-box !important;
}

/* Proposal content cannot widen or stretch layout */
#proposalBox,
#proposalBox *,
.side *,
#chatLog .msg * {
  max-width: 100% !important;
  box-sizing: border-box !important;
  overflow-wrap: anywhere !important;
  word-break: break-word !important;
}
"""

js_marker = "// ===== v94 exact chat layout helper ====="

js = r"""
// ===== v94 exact chat layout helper =====
(function () {
  function applyV94ChatLayoutFix() {
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

        const page = leftColumn.parentElement;
        if (page) {
          page.classList.add("v93-chat-page");
        }
      }
    }

    if (chatInput) {
      const composer = chatInput.closest("form") || chatInput.parentElement;
      if (composer) composer.classList.add("v93-chat-composer");
    }

    if (side) {
      side.style.maxHeight = "calc(100vh - 132px)";
      side.style.overflowY = "auto";
      side.style.overflowX = "hidden";
    }

    document.querySelectorAll("#chatLog .msg").forEach(function (m) {
      m.style.height = "auto";
      m.style.minHeight = "0";
      m.style.maxHeight = "none";
      m.style.flexGrow = "0";
      m.style.flexShrink = "1";
    });

    chatLog.scrollTop = chatLog.scrollHeight;
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", applyV94ChatLayoutFix);
  } else {
    applyV94ChatLayoutFix();
  }

  window.addEventListener("resize", applyV94ChatLayoutFix);

  const oldChatAppend = window.chatAppend;
  if (typeof oldChatAppend === "function" && !window.__v94ChatAppendWrapped) {
    window.chatAppend = function () {
      const result = oldChatAppend.apply(this, arguments);
      setTimeout(applyV94ChatLayoutFix, 0);
      return result;
    };
    window.__v94ChatAppendWrapped = true;
  }
})();
"""

if marker in html:
    print("v94 CSS already exists. Skipping CSS insert.")
else:
    style_closes = list(re.finditer(r"</style\s*>", html, flags=re.IGNORECASE))
    if style_closes:
        pos = style_closes[-1].start()
        html = html[:pos] + "\n" + css + "\n" + html[pos:]
    else:
        head_close = re.search(r"</head\s*>", html, flags=re.IGNORECASE)
        block = "\n<style>\n" + css + "\n</style>\n"
        if head_close:
            html = html[:head_close.start()] + block + html[head_close.start():]
        else:
            html = block + html

if js_marker in html:
    print("v94 JS already exists. Skipping JS insert.")
else:
    script_closes = list(re.finditer(r"</script\s*>", html, flags=re.IGNORECASE))
    if script_closes:
        pos = script_closes[-1].start()
        html = html[:pos] + "\n" + js + "\n" + html[pos:]
    else:
        body_close = re.search(r"</body\s*>", html, flags=re.IGNORECASE)
        block = "\n<script>\n" + js + "\n</script>\n"
        if body_close:
            html = html[:body_close.start()] + block + html[body_close.start():]
        else:
            html += block

chat_path.write_text(html, encoding="utf-8")

print("Applied v94 exact chat bubble height/layout fix.")
print(f"Patched: {chat_path}")
print(f"Backup:  {backup}")