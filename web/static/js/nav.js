// Shared sidebar nav. Renders into an initially-empty <aside id="sidebar">
// only once /api/me resolves, so a role's links are never shown then
// stripped - nothing appears until the real role is known.
const NAV_LINKS = {
  "Super Admin": [["/", "Dashboard"], ["/workflow", "Workflow"], ["/users", "Users"], ["/logs", "Logs"], ["/tasks", "Ticket Tracker"], ["/evaluation", "Evaluation"], ["/profile", "Profile"], ["/logout", "Logout"]],
  "Admin": [["/", "Dashboard"], ["/workflow", "Workflow"], ["/users", "Users"], ["/logs", "Logs"], ["/tasks", "Ticket Tracker"], ["/evaluation", "Evaluation"], ["/profile", "Profile"], ["/logout", "Logout"]],
  "User": [["/", "Dashboard"], ["/workflow", "Workflow"], ["/tasks", "Ticket Tracker"], ["/profile", "Profile"], ["/logout", "Logout"]],
};

function navEscapeHtml(s) { return String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c])); }

async function renderNav(navElementId) {
  // Sidebar-style pages pass no id (defaults to #sidebar); legacy pages
  // (e.g. chat.html, not yet revamped) still call renderNav('nav') and
  // get the old flat link row so they keep working unchanged.
  const id = navElementId || (document.getElementById("sidebar") ? "sidebar" : "nav");
  const el = document.getElementById(id);
  if (!el) return null;
  try {
    const res = await fetch("/api/me");
    const data = await res.json();
    const user = data.user || null;
    if (!user) { el.innerHTML = ""; return null; }
    const links = NAV_LINKS[user.role] || NAV_LINKS["User"];
    const path = location.pathname;
    if (id === "sidebar") {
      el.innerHTML = `
        <div class="brand">Intern Tracker</div>
        <nav>${links.map(([href, label]) => {
          const active = href !== "/logout" && href === path;
          return `<a href="${href}"${active ? ' class="active"' : ''}><span class="dot"></span>${navEscapeHtml(label)}</a>`;
        }).join("")}</nav>
        <div class="foot">
          <span class="tag role">${navEscapeHtml(user.role)}</span>
          <div class="name">${navEscapeHtml(user.name || '')}</div>
          <div class="email">${navEscapeHtml(user.email || '')}</div>
        </div>`;
    } else {
      el.innerHTML = links.map(([href, label]) => `<a href="${href}" style="color:white;font-weight:700;margin-right:14px;text-decoration:none">${navEscapeHtml(label)}</a>`).join("");
    }
    return user;
  } catch (e) {
    el.innerHTML = "";
    return null;
  }
}
