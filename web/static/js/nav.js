// Shared sidebar nav. Renders into an initially-empty <aside id="sidebar">
// only once /api/me resolves, so a role's links are never shown then
// stripped - nothing appears until the real role is known.
const NAV_LINKS = {
  "Super Admin": [["/", "Dashboard"], ["/workflow", "Workflow"], ["/evaluation", "Evaluation"], ["/users", "Users"], ["/logs", "Logs"], ["/tasks", "Create Ticket"], ["/profile", "Profile & Key Management"], ["/logout", "Logout"]],
  "Admin": [["/", "Dashboard"], ["/workflow", "Workflow"], ["/evaluation", "Evaluation"], ["/users", "Users"], ["/logs", "Logs"], ["/tasks", "Create Ticket"], ["/profile", "Profile & Key Management"], ["/logout", "Logout"]],
  "User": [["/", "Dashboard"], ["/workflow", "Workflow"], ["/tasks", "Create Ticket"], ["/profile", "Profile & Key Management"], ["/logout", "Logout"]],
};

function navEscapeHtml(s) { return String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c])); }

async function fetchNotificationCount() {
  try {
    const res = await fetch("/api/notifications");
    const data = await res.json();
    return data.count || 0;
  } catch (e) {
    return 0;
  }
}

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
    let links = NAV_LINKS[user.role] || NAV_LINKS["User"];
    if (user.is_maintainer) {
      links = links.slice();
      const profileIdx = links.findIndex(([href]) => href === "/profile");
      links.splice(profileIdx === -1 ? links.length : profileIdx, 0, ["/ticket-queue", "Ticket Queue"]);
    }
    const path = location.pathname;
    if (id === "sidebar") {
      const notifCount = await fetchNotificationCount();
      const notifActive = path === "/notifications";
      const bellHtml = `
        <div style="padding:0 16px">
          <a href="/notifications" style="color:${notifActive ? 'var(--color-bg)' : 'color-mix(in srgb, var(--color-bg) 80%, transparent)'};text-decoration:none;font-size:13px;font-weight:600;padding:6px 0;display:flex;align-items:center;gap:7px">
            <span style="font-size:15px;line-height:1">&#128276;</span>
            <span>Notifications</span>
            ${notifCount ? `<span class="tag tag-accent" style="padding:1px 6px">${notifCount}</span>` : ''}
          </a>
        </div>`;
      el.innerHTML = `
        <div class="brand">Intern Tracker</div>
        ${bellHtml}
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
