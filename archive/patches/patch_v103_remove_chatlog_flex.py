from pathlib import Path

p = Path("web/chat.html")

html = p.read_text(encoding="utf-8")

fix = """
<style id="v103-chatlog-scroll-fix">

/* CHAT HISTORY SHOULD BE NORMAL BLOCK FLOW */

#chatLog{
    display:block !important;
    overflow-y:auto !important;
}

/* MESSAGE ROWS */

#chatLog .msg{
    display:block !important;
    position:relative !important;

    width:fit-content !important;
    max-width:75% !important;

    margin:12px 0 !important;

    clear:both !important;

    flex:none !important;
}

/* user */

#chatLog .msg.user{
    margin-left:auto !important;
    margin-right:0 !important;
}

/* assistant */

#chatLog .msg.assistant{
    margin-left:0 !important;
    margin-right:auto !important;
}

/* system */

#chatLog .msg.system{
    margin-left:auto !important;
    margin-right:auto !important;
}

</style>
"""

if "v103-chatlog-scroll-fix" not in html:
    html = html.replace("</body>", fix + "\n</body>")

p.write_text(html, encoding="utf-8")

print("v103 installed")