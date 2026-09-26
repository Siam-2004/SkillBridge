/* Transient messages. Django's own messages framework renders inline alerts;
   this is for feedback raised by a background request. */
(function (global) {
  "use strict";

  let stack = null;

  function ensureStack() {
    if (!stack) {
      stack = document.createElement("div");
      stack.className = "toast-stack";
      stack.setAttribute("role", "status");
      stack.setAttribute("aria-live", "polite");
      document.body.appendChild(stack);
    }
    return stack;
  }

  global.SB = global.SB || {};
  global.SB.toast = function (message, tone) {
    const el = document.createElement("div");
    el.className = "toast" + (tone ? " toast--" + tone : "");
    el.textContent = message;
    ensureStack().appendChild(el);
    setTimeout(function () { el.remove(); }, 4500);
  };
})(window);
