from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent
chat_path = ROOT / "web" / "chat.html"

if not chat_path.exists():
    raise FileNotFoundError(f"Missing file: {chat_path}")

html = chat_path.read_text(encoding="utf-8")

backup = chat_path.with_suffix(".html.bak_v99")
backup.write_text(html, encoding="utf-8")

old_pattern = re.compile(
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

new_block = r"""  // v99 fix: readonly summary messages must append to #chatLog, not <main>.
  function conversationContainer(){
    return document.getElementById('chatLog') || document.querySelector('main') || document.body;
  }

  function scrollConversation(){
    const c = conversationContainer();
    if(c && c.id === 'chatLog'){
      c.scrollTop = c.scrollHeight;
    } else if(c && c.scrollIntoView){
      c.scrollIntoView({behavior:'smooth', block:'nearest'});
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

html2, count = old_pattern.subn(new_block, html, count=1)

if count == 0:
    raise RuntimeError(
        "Could not find the old v92 append block. Upload latest web/chat.html if this fails."
    )

html = html2

css_marker = "/* ===== v99 summary inside chatlog minimal style ===== */"

css = r"""
/* ===== v99 summary inside chatlog minimal style ===== */
#chatLog .v92-summary-user {
  margin-left: auto !important;
  margin-right: 0 !important;
  max-width: 78% !important;
  background: var(--user) !important;
}

#chatLog .v92-summary-bubble {
  margin-left: 0 !important;
  margin-right: auto !important;
  max-width: 86% !important;
  background: #ffffff !important;
  white-space: normal !important;
}

#chatLog .v92-summary-bubble * {
  max-width: 100% !important;
  box-sizing: border-box !important;
  overflow-wrap: anywhere !important;
  word-break: break-word !important;
}

#chatLog .v92-summary-bubble h3 {
  margin-top: 0 !important;
}
"""

if css_marker not in html:
    body_close = re.search(r"</body\s*>", html, flags=re.IGNORECASE)
    style_block = '\n<style id="v99-summary-inside-chatlog-style">\n' + css + "\n</style>\n"
    if body_close:
        html = html[:body_close.start()] + style_block + html[body_close.start():]
    else:
        html += style_block

chat_path.write_text(html, encoding="utf-8")

print("Applied v99 summary append-only leak fix.")
print(f"Patched: {chat_path}")
print(f"Backup:  {backup}")