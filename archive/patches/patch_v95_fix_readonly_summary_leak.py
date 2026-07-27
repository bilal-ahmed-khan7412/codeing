from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent
chat_path = ROOT / "web" / "chat.html"

if not chat_path.exists():
    raise FileNotFoundError(f"Missing file: {chat_path}")

html = chat_path.read_text(encoding="utf-8")

backup = chat_path.with_suffix(".html.bak_v95")
backup.write_text(html, encoding="utf-8")

old_block = r"""  function conversationContainer(){
    const headings = Array.from(document.querySelectorAll('h1,h2,h3,h4,div')).filter(el => low(el.textContent) === 'conversation');
    if(headings[0]) return headings[0].closest('section, article, div, main') || document.querySelector('main') || document.body;
    return document.querySelector('main') || document.body;
  }
  function appendUser(text){
    const box = document.createElement('div');
    box.className = 'v92-summary-user';
    box.textContent = text;
    conversationContainer().appendChild(box);
  }
  function appendAssistant(html){
    const box = document.createElement('div');
    box.className = 'v92-summary-bubble';
    box.innerHTML = html;
    conversationContainer().appendChild(box);
    box.scrollIntoView({behavior:'smooth', block:'nearest'});
  }"""

new_block = r"""  // v95 fix: readonly summary bubbles must stay inside #chatLog.
  // Previous v92 logic appended to <main> when it could not find a Conversation heading,
  // which made "how is X doing?" bubbles appear below the composer/outside the chat box.
  function conversationContainer(){
    return document.getElementById('chatLog') || document.querySelector('main') || document.body;
  }
  function scrollConversation(){
    const box = conversationContainer();
    if(box && box.id === 'chatLog'){
      box.scrollTop = box.scrollHeight;
    }
  }
  function appendUser(text){
    const box = document.createElement('div');
    box.className = 'msg user v92-summary-user';
    box.textContent = text;
    conversationContainer().appendChild(box);
    scrollConversation();
  }
  function appendAssistant(html){
    const box = document.createElement('div');
    box.className = 'msg assistant v92-summary-bubble';
    box.innerHTML = html;
    conversationContainer().appendChild(box);
    scrollConversation();
  }"""

if old_block not in html:
    # Fallback regex in case spacing changed slightly.
    pattern = re.compile(
        r"""  function conversationContainer\(\)\{\s*
    const headings = Array\.from\(document\.querySelectorAll\('h1,h2,h3,h4,div'\)\)\.filter\(el => low\(el\.textContent\) === 'conversation'\);\s*
    if\(headings\[0\]\) return headings\[0\]\.closest\('section, article, div, main'\) \|\| document\.querySelector\('main'\) \|\| document\.body;\s*
    return document\.querySelector\('main'\) \|\| document\.body;\s*
  \}\s*
  function appendUser\(text\)\{\s*
    const box = document\.createElement\('div'\);\s*
    box\.className = 'v92-summary-user';\s*
    box\.textContent = text;\s*
    conversationContainer\(\)\.appendChild\(box\);\s*
  \}\s*
  function appendAssistant\(html\)\{\s*
    const box = document\.createElement\('div'\);\s*
    box\.className = 'v92-summary-bubble';\s*
    box\.innerHTML = html;\s*
    conversationContainer\(\)\.appendChild\(box\);\s*
    box\.scrollIntoView\(\{behavior:'smooth', block:'nearest'\}\);\s*
  \}""",
        re.MULTILINE
    )

    html2, count = pattern.subn(new_block, html, count=1)
    if count == 0:
        raise RuntimeError(
            "Could not find the v92 conversationContainer/appendUser/appendAssistant block. "
            "Upload the latest web/chat.html after this failed run."
        )
    html = html2
else:
    html = html.replace(old_block, new_block, 1)

css_marker = "/* ===== v95 readonly summary inside chatLog fix ===== */"

css = r"""
/* ===== v95 readonly summary inside chatLog fix ===== */

/* v92 readonly summary bubbles now live inside #chatLog, so remove old outside-main spacing. */
#chatLog .v92-summary-user,
#chatLog .v92-summary-bubble {
  margin-top: 10px !important;
  margin-bottom: 10px !important;
}

#chatLog .v92-summary-user {
  margin-left: auto !important;
  margin-right: 0 !important;
  max-width: min(520px, 72%) !important;
}

#chatLog .v92-summary-bubble {
  margin-left: 0 !important;
  margin-right: auto !important;
  max-width: min(920px, 86%) !important;
}

/* Make sure HTML returned by readonly summary cannot break the chat width. */
#chatLog .v92-summary-bubble *,
#chatLog .v92-summary-user * {
  max-width: 100% !important;
  box-sizing: border-box !important;
  overflow-wrap: anywhere !important;
  word-break: break-word !important;
}
"""

if css_marker not in html:
    style_close = html.rfind("</style>")
    if style_close != -1:
        html = html[:style_close] + "\n" + css + "\n" + html[style_close:]
    else:
        body_close = html.rfind("</body>")
        block = "\n<style>\n" + css + "\n</style>\n"
        if body_close != -1:
            html = html[:body_close] + block + html[body_close:]
        else:
            html += block

chat_path.write_text(html, encoding="utf-8")

print("Applied v95 readonly summary leak fix.")
print(f"Patched: {chat_path}")
print(f"Backup:  {backup}")