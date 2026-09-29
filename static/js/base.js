(function () {
  "use strict";

  const THEME_KEY = "sb-theme";

  function applyTheme(theme) {
    document.documentElement.dataset.theme = theme;
    try { localStorage.setItem(THEME_KEY, theme); } catch (e) {  }
  }

  document.addEventListener("click", function (event) {
    if (event.target.closest("[data-theme-toggle]")) {
      event.preventDefault();
      applyTheme(document.documentElement.dataset.theme === "dark" ? "light" : "dark");
    }
  });

  document.addEventListener("click", function (event) {
    const toggle = event.target.closest("[data-nav-toggle]");
    if (toggle) {
      const nav = document.getElementById(toggle.getAttribute("aria-controls"));
      if (nav) {
        const open = nav.hasAttribute("hidden");
        nav.toggleAttribute("hidden", !open);
        toggle.setAttribute("aria-expanded", String(open));
      }
      return;
    }
    if (event.target.closest("[data-side-toggle]")) {
      document.querySelector(".app").classList.toggle("is-open");
    }
  });

  document.addEventListener("submit", function (event) {
    const form = event.target;
    const message = form.dataset.confirm;
    if (message && !window.confirm(message)) {
      event.preventDefault();
      return;
    }

    const button = form.querySelector('button[type="submit"], input[type="submit"]');
    if (button && !form.dataset.noBusy) {
      window.setTimeout(function () {
        button.classList.add("is-busy");
        button.disabled = true;
      }, 0);
    }
  });

  document.addEventListener("click", function (event) {
    const link = event.target.closest("a[data-confirm]");
    if (link && !window.confirm(link.dataset.confirm)) event.preventDefault();
  });

  document.querySelectorAll("[data-autosubmit]").forEach(function (form) {
    form.querySelectorAll("select, input[type=checkbox]").forEach(function (input) {
      input.addEventListener("change", function () { form.submit(); });
    });
  });

  function renderCountdown(el) {
    const deadline = Date.parse(el.dataset.countdown);
    if (isNaN(deadline)) return;

    const left = deadline - Date.now();
    if (left <= 0) {
      el.textContent = el.dataset.elapsedLabel || "Window closed";
      el.classList.add("countdown--urgent");
      return;
    }
    const hours = Math.floor(left / 3600000);
    const minutes = Math.floor((left % 3600000) / 60000);
    const seconds = Math.floor((left % 60000) / 1000);

    if (hours >= 24) {
      const days = Math.floor(hours / 24);
      el.textContent = days + "d " + (hours % 24) + "h";
    } else if (hours > 0) {
      el.textContent = hours + "h " + minutes + "m";
    } else {
      el.textContent = minutes + "m " + String(seconds).padStart(2, "0") + "s";
    }
    el.classList.toggle("countdown--urgent", left < 3600000);
    el.classList.toggle("countdown--soon", left >= 3600000 && left < 21600000);
  }

  const countdowns = document.querySelectorAll("[data-countdown]");
  if (countdowns.length) {
    const tick = function () { countdowns.forEach(renderCountdown); };
    tick();
    window.setInterval(tick, 1000);
  }

  document.querySelectorAll("[data-counter-for]").forEach(function (out) {
    const input = document.getElementById(out.dataset.counterFor);
    if (!input) return;
    const max = input.getAttribute("maxlength");
    const update = function () {
      out.textContent = max ? input.value.length + " / " + max : String(input.value.length);
    };
    input.addEventListener("input", update);
    update();
  });
})();
