// Shared UI helpers: toast notifications (replaces native alert()),
// a styled confirm dialog (replaces native confirm()), and a loading-state
// wrapper for async button actions so a click always gives visible feedback.

function toast(message, type = 'info') {
  let container = document.getElementById('toastContainer');
  if (!container) {
    container = document.createElement('div');
    container.id = 'toastContainer';
    container.setAttribute('aria-live', 'polite');
    container.className = 'toast-container';
    document.body.appendChild(container);
  }
  const el = document.createElement('div');
  el.className = 'toast toast-' + type;
  el.textContent = message;
  container.appendChild(el);
  setTimeout(() => {
    el.style.opacity = '0';
    setTimeout(() => el.remove(), 300);
  }, 3500);
}

function confirmDialog(message) {
  return new Promise(resolve => {
    const overlay = document.createElement('div');
    overlay.className = 'confirm-overlay';
    const box = document.createElement('div');
    box.className = 'confirm-box';
    const p = document.createElement('p');
    p.textContent = message;
    const actions = document.createElement('div');
    actions.className = 'confirm-actions';
    const yes = document.createElement('button');
    yes.className = 'btn btn-danger';
    yes.textContent = 'Confirm';
    const no = document.createElement('button');
    no.className = 'btn btn-secondary';
    no.textContent = 'Cancel';
    actions.appendChild(yes);
    actions.appendChild(no);
    box.appendChild(p);
    box.appendChild(actions);
    overlay.appendChild(box);
    document.body.appendChild(overlay);
    yes.focus();
    function close(result) {
      overlay.remove();
      resolve(result);
    }
    yes.onclick = () => close(true);
    no.onclick = () => close(false);
    overlay.onclick = (e) => { if (e.target === overlay) close(false); };
  });
}

function showSecret(title, value, note) {
  return new Promise(resolve => {
    const overlay = document.createElement('div');
    overlay.className = 'confirm-overlay';
    const box = document.createElement('div');
    box.className = 'confirm-box secret-box';
    const h = document.createElement('h3');
    h.textContent = title;
    h.style.margin = '0 0 8px';
    const p = document.createElement('p');
    p.className = 'muted';
    p.textContent = note || 'Copy this now - it will not be shown again.';
    const row = document.createElement('div');
    row.className = 'secret-row';
    const code = document.createElement('code');
    code.className = 'secret-value';
    code.textContent = value;
    const copyBtn = document.createElement('button');
    copyBtn.className = 'btn btn-secondary';
    copyBtn.textContent = 'Copy';
    row.appendChild(code);
    row.appendChild(copyBtn);
    const actions = document.createElement('div');
    actions.className = 'confirm-actions';
    const close = document.createElement('button');
    close.className = 'btn btn-primary';
    close.textContent = 'Done';
    actions.appendChild(close);
    box.appendChild(h);
    box.appendChild(p);
    box.appendChild(row);
    box.appendChild(actions);
    overlay.appendChild(box);
    document.body.appendChild(overlay);
    close.focus();
    function finish() {
      overlay.remove();
      resolve();
    }
    copyBtn.onclick = async () => {
      try {
        await navigator.clipboard.writeText(value);
        copyBtn.textContent = 'Copied!';
        setTimeout(() => { copyBtn.textContent = 'Copy'; }, 1500);
      } catch (e) {
        toast('Could not copy automatically - select and copy manually.', 'error');
      }
    };
    close.onclick = finish;
    overlay.onclick = (e) => { if (e.target === overlay) finish(); };
  });
}

function showConfirmation(title, message) {
  return new Promise(resolve => {
    const overlay = document.createElement('div');
    overlay.className = 'confirm-overlay';
    const box = document.createElement('div');
    box.className = 'confirm-box';
    const h = document.createElement('h3');
    h.textContent = title;
    h.style.margin = '0 0 8px';
    const p = document.createElement('p');
    p.textContent = message;
    const actions = document.createElement('div');
    actions.className = 'confirm-actions';
    const ok = document.createElement('button');
    ok.className = 'btn btn-primary';
    ok.textContent = 'OK';
    actions.appendChild(ok);
    box.appendChild(h);
    box.appendChild(p);
    box.appendChild(actions);
    overlay.appendChild(box);
    document.body.appendChild(overlay);
    ok.focus();
    function close() {
      overlay.remove();
      resolve();
    }
    ok.onclick = close;
    overlay.onclick = (e) => { if (e.target === overlay) close(); };
  });
}

async function withLoading(btn, fn) {
  if (!btn) return fn();
  const original = btn.textContent;
  btn.disabled = true;
  btn.textContent = 'Working...';
  try {
    return await fn();
  } finally {
    btn.disabled = false;
    btn.textContent = original;
  }
}
