from pathlib import Path

LOGIN = Path("web/login.html")
SIGNUP = Path("web/signup.html")
PENDING = Path("web/pending.html")

# -------------------------
# LOGIN PAGE
# -------------------------

if LOGIN.exists():
    html = LOGIN.read_text(encoding="utf-8")

    html = html.replace(
        '<p class="muted">Default admin: admin@example.com / admin123</p>',
        ''
    )

    html = html.replace(
        '<input id="email" value="admin@example.com">',
        '<input id="email" autocomplete="username" placeholder="Enter your email">'
    )

    html = html.replace(
        '<input id="password" type="password" value="admin123">',
        '<input id="password" type="password" autocomplete="current-password" placeholder="Enter your password">'
    )

    LOGIN.write_text(html, encoding="utf-8")
    print("[OK] login.html cleaned")

# -------------------------
# SIGNUP PAGE
# -------------------------

if SIGNUP.exists():
    html = SIGNUP.read_text(encoding="utf-8")

    html = html.replace(
        "setTimeout(()=>location.href='/pending', 900);",
        "setTimeout(()=>location.href='/pending', 1500);"
    )

    SIGNUP.write_text(html, encoding="utf-8")
    print("[OK] signup.html updated")

# -------------------------
# PENDING PAGE
# -------------------------

if PENDING.exists():
    html = PENDING.read_text(encoding="utf-8")

    old = """
<div class="card" style="max-width:560px;margin:40px auto;"><h2>Your request is pending</h2><p>Your access request has been submitted. Please wait for an Admin or Super Admin to approve your account.</p></div>
"""

    new = """
<div class="card" style="max-width:560px;margin:40px auto;">
<h2>Your request is pending</h2>

<p>
Your access request has been submitted.
Please wait for an Admin or Super Admin to approve your account.
</p>

<div style="margin-top:20px;">
/login
      Back to Login
</a>
</div>
</div>
"""

    html = html.replace(old, new)

    # fallback in case formatting is different
    if "Back to Login" not in html:
        html = html.replace(
            "</main>",
            """
<div style="text-align:center;margin-top:20px;">
/login:inline-block;background:#305496;color:white;
   text-decoration:none;padding:10px 16px;border-radius:10px;
   font-weight:700;">
   Back to Login
</a>
</div>
</main>
"""
        )

    PENDING.write_text(html, encoding="utf-8")
    print("[OK] pending.html updated")

print("\nPatch v104 applied successfully.")