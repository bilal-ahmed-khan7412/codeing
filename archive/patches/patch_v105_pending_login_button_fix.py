from pathlib import Path

p = Path("web/pending.html")

html = p.read_text(encoding="utf-8")

# Remove the broken text that was injected
html = html.replace(
    '/login:inline-block;background:#305496;color:white;text-decoration:none;padding:10px 16px;border-radius:10px;font-weight:700;">Back to Login</a>',
    ''
)

html = html.replace(
    '/login:inline-block;background:#305496;color:white; text-decoration:none;padding:10px 16px;border-radius:10px; font-weight:700;"> Back to Login',
    ''
)

# Add a proper button if it does not already exist
if 'id="backToLoginBtn"' not in html:
    html = html.replace(
        "</main>",
        """
<div style="text-align:center;margin-top:20px;">
    login"
       style="
            display:inline-block;
            background:#305496;
            color:white;
            text-decoration:none;
            padding:10px 18px;
            border-radius:10px;
            font-weight:700;
       ">
       Back to Login
    </a>
</div>
</main>
"""
    )

p.write_text(html, encoding="utf-8")

print("v105 pending page fixed successfully")