from pathlib import Path
import re

CHAT_FILE = Path("web/chat.html")

html = CHAT_FILE.read_text(encoding="utf-8")

# Remove broken v98 CSS block
html = re.sub(
    r'<style id="v98-clean-chat-bubble-css-only">.*?</style>',
    '',
    html,
    flags=re.DOTALL
)

# Remove v99 CSS block
html = re.sub(
    r'<style id="v99-summary-inside-chatlog-style">.*?</style>',
    '',
    html,
    flags=re.DOTALL
)

# Unify readonly summary assistant bubbles with normal assistant bubbles
html = html.replace(
    "box.className='msg assistant v92-summary-bubble';",
    "box.className='msg assistant';"
)

# Append clean final CSS before </body>
clean_css = r"""
<style id="v101-clean-chat-bubbles">
#chatLog{
    display:flex !important;
    flex-direction:column !important;
    gap:12px !important;
    overflow-y:auto !important;
    overflow-x:hidden !important;
}

#chatLog .msg{
    display:block !important;
    width:fit-content !important;
    max-width:75% !important;
    min-width:0 !important;
    padding:12px 16px !important;
    border-radius:16px !important;
    line-height:1.5 !important;
    overflow-wrap:anywhere !important;
    word-break:break-word !important;
    white-space:pre-wrap !important;
}

#chatLog .msg.user{
    align-self:flex-end !important;
    margin-left:auto !important;
    margin-right:0 !important;
    background:#dbeafe !important;
}

#chatLog .msg.assistant{
    align-self:flex-start !important;
    margin-left:0 !important;
    margin-right:auto !important;
    background:#ffffff !important;
}

#chatLog .msg.system{
    align-self:center !important;
    max-width:90% !important;
    background:#fff7ed !important;
}

#chatLog .msg h1,
#chatLog .msg h2,
#chatLog .msg h3{
    margin-top:0 !important;
}

#chatLog .msg table{
    display:block;
    overflow-x:auto;
    max-width:100%;
}
</style>
"""

html = html.replace("</body>", clean_css + "\n</body>")

CHAT_FILE.write_text(html, encoding="utf-8")

print("v101 patch applied successfully")