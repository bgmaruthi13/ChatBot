(function () {
  var STORAGE_KEY = 'nav-collapsed';

  document.addEventListener('DOMContentLoaded', function () {
    var shell = document.getElementById('app-shell');
    var toggle = document.getElementById('nav-toggle');
    if (!shell || !toggle) {
      return;
    }

    if (localStorage.getItem(STORAGE_KEY) === '1') {
      shell.classList.add('nav-collapsed');
    }

    toggle.addEventListener('click', function () {
      var collapsed = shell.classList.toggle('nav-collapsed');
      localStorage.setItem(STORAGE_KEY, collapsed ? '1' : '0');
    });
  });
})();
