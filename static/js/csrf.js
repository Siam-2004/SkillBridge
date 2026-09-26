/* Read Django's CSRF token so fetch() POSTs are accepted.
   Every mutating request in this project is a normal form post; this exists
   for the few places that post in the background (mark-as-read, filters). */
(function (global) {
  "use strict";

  function getCookie(name) {
    const match = document.cookie.match(new RegExp("(^|;\\s*)" + name + "=([^;]*)"));
    return match ? decodeURIComponent(match[2]) : null;
  }

  const meta = document.querySelector('meta[name="csrf-token"]');

  global.SB = global.SB || {};
  global.SB.csrfToken = function () {
    return (meta && meta.content) || getCookie("csrftoken") || "";
  };

  global.SB.post = function (url, data) {
    return fetch(url, {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "X-CSRFToken": global.SB.csrfToken(),
        "X-Requested-With": "XMLHttpRequest",
        "Content-Type": "application/json",
      },
      body: JSON.stringify(data || {}),
    });
  };
})(window);
