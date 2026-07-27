from pathlib import Path

CHAT_FILE = Path("web/chat.html")

html = CHAT_FILE.read_text(encoding="utf-8")

patch_css = r"""
<style id="v102-chat-overlap-fix">
/* ===== v102 Fix overlapping chat bubbles ===== */

#chatLog{
    display:flex !important;
    flex-direction:column !important;
    align-items:stretch !important;
    gap:12px !important;
}

/* Every child becomes an independent row */
#chatLog > *{
    flex:none !important;
}

/* Message bubbles */
#chatLog .msg{
    position:relative !important;
    display:block !important;

    flex:none !important;
    flex-grow:0 !important;
    flex-shrink:0 !important;

    width:fit-content !important;
    min-width:0 !important;

    height:auto !important;
    min-height:auto !important;
    max-height:none !important;

    margin:0 !important;
    padding:12px 16px !important;

    clear:both !important;

    line-height:1.5 !important;

    white-space:pre-wrap !important;
    overflow-wrap:anywhere !important;
    word-break:break-word !important;
}

/* Guaranteed spacing */
#chatLog .msg + .msg{
    margin-top:12px !important;
}

/* User messages */
#chatLog .msg.user{
    align-self:flex-end !important;
    margin-left:auto !important;
    margin-right:0 !important;
    max-width:75% !important;
}

/* Assistant messages */
#chatLog .msg.assistant{
    align-self:flex-start !important;
    margin-left:0 !important;
    margin-right:auto !important;
    max-width:85% !important;
}

/* System messages */
#chatLog .msg.system{
    align-self:center !important;
    max-width:90% !important;
}

/* Summary cards */
#chatLog .v92-summary-bubble,
#chatLog .v92-summary-user{
    position:relative !important;
    display:block !important;
    flex:none !important;
    height:auto !important;
    min-height:auto !important;
    max-height:none !important;
}
</style>
"""

if "v102-chat-overlap-fix" not in html:
    html = html.replace("</body>", patch_css + "\n</body>")

CHAT_FILE.write_text(html, encoding="utf-8")

print("v102 chat overlap fix applied")