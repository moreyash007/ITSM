/* ITSM Suite — main.js */

document.addEventListener('DOMContentLoaded', () => {

  // ── Auto-dismiss alerts after 5s ──────────────────────
  document.querySelectorAll('.alert').forEach(alert => {
    setTimeout(() => {
      alert.style.opacity = '0';
      alert.style.transition = 'opacity 0.4s';
      setTimeout(() => alert.remove(), 400);
    }, 5000);
  });

  // ── Sidebar overlay close on mobile ───────────────────
  document.addEventListener('click', (e) => {
    const sidebar = document.getElementById('sidebar');
    const menuBtn = document.querySelector('.topbar__menu-btn');
    if (sidebar && sidebar.classList.contains('open')) {
      if (!sidebar.contains(e.target) && e.target !== menuBtn) {
        sidebar.classList.remove('open');
      }
    }
  });

  // ── Active nav link highlight ──────────────────────────
  const currentPath = window.location.pathname;
  document.querySelectorAll('.nav-item').forEach(link => {
    if (link.getAttribute('href') && currentPath.startsWith(link.getAttribute('href'))) {
      link.classList.add('active');
    }
  });

  // ── Confirm dangerous actions ──────────────────────────
  document.querySelectorAll('[data-confirm]').forEach(el => {
    el.addEventListener('click', (e) => {
      if (!confirm(el.dataset.confirm)) {
        e.preventDefault();
      }
    });
  });

  // ── Form: disable submit button after click (prevent double submit) ──
  document.querySelectorAll('form').forEach(form => {
    form.addEventListener('submit', () => {
      const btn = form.querySelector('button[type="submit"]');
      if (btn) {
        btn.disabled = true;
        btn.textContent = 'Saving...';
      }
    });
  });

  // ── Datetime-local: pre-fill with current datetime if empty ──
  document.querySelectorAll('input[type="datetime-local"]').forEach(input => {
    if (!input.value && input.name && input.name.includes('scheduled')) {
      const now = new Date();
      now.setMinutes(now.getMinutes() - now.getTimezoneOffset());
      input.placeholder = now.toISOString().slice(0, 16);
    }
  });

});
