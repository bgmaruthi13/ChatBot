(function () {
  const POLL_INTERVAL_MS = 2000;
  const TERMINAL_STATUSES = ["ready", "failed"];

  function poll() {
    const badges = document.querySelectorAll('[data-status-badge]');
    let pending = false;

    badges.forEach(function (badge) {
      const status = badge.getAttribute('data-status');
      if (TERMINAL_STATUSES.indexOf(status) !== -1) {
        return;
      }
      pending = true;

      const documentId = badge.getAttribute('data-status-badge');
      fetch('/documents/' + documentId + '/status/')
        .then(function (response) {
          return response.json();
        })
        .then(function (data) {
          if (data.status === status) {
            return;
          }
          badge.textContent = data.status_display;
          badge.setAttribute('data-status', data.status);
          badge.className = 'status-badge status-badge--' + data.status;

          const pagesEl = document.querySelector('[data-pages="' + documentId + '"]');
          if (pagesEl) {
            pagesEl.textContent = data.page_count != null ? data.page_count : '—';
          }
        })
        .catch(function () {
          // Transient network error - next poll tick will retry.
        });
    });

    if (pending) {
      setTimeout(poll, POLL_INTERVAL_MS);
    }
  }

  document.addEventListener('DOMContentLoaded', function () {
    poll();
  });
})();
