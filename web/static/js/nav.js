// Shared nav component. Renders into an initially-empty <div id="nav">
// only once /api/me resolves, so a role's links are never shown then
// stripped - nothing appears until the real role is known.
const NAV_LINKS = {
  "Super Admin": [["/", "Dashboard"], ["/chat", "Chat"], ["/users", "Users"], ["/logs", "Logs"], ["/tasks", "Tasks"], ["/evaluation", "Evaluation"], ["/profile", "Profile"], ["/logout", "Logout"]],
  "Admin": [["/", "Dashboard"], ["/chat", "Chat"], ["/users", "Users"], ["/logs", "Logs"], ["/tasks", "Tasks"], ["/evaluation", "Evaluation"], ["/profile", "Profile"], ["/logout", "Logout"]],
  "User": [["/", "Dashboard"], ["/chat", "Chat"], ["/profile", "Profile"], ["/logout", "Logout"]],
};

async function renderNav(navElementId = "nav") {
  const el = document.getElementById(navElementId);
  if (!el) return null;
  try {
    const res = await fetch("/api/me");
    const data = await res.json();
    const user = data.user || null;
    if (!user) {
      el.innerHTML = "";
      return null;
    }
    const links = NAV_LINKS[user.role] || NAV_LINKS["User"];
    el.innerHTML = links.map(([href, label]) => `<a href="${href}">${label}</a>`).join("");
    return user;
  } catch (e) {
    el.innerHTML = "";
    return null;
  }
}
