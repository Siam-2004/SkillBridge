/* Dialogs built on <dialog>. Any element with data-modal-open="<id>" opens it;
   anything with data-modal-close inside closes it. No library. */
(function () {
  "use strict";

  document.addEventListener("click", function (event) {
    const opener = event.target.closest("[data-modal-open]");
    if (opener) {
      const dialog = document.getElementById(opener.dataset.modalOpen);
      if (dialog && typeof dialog.showModal === "function") {
        event.preventDefault();
        dialog.showModal();
      }
      return;
    }

    const closer = event.target.closest("[data-modal-close]");
    if (closer) {
      const dialog = closer.closest("dialog");
      if (dialog) {
        event.preventDefault();
        dialog.close();
      }
    }
  });

  /* Clicking the backdrop closes the dialog, which is what people expect. */
  document.addEventListener("click", function (event) {
    if (event.target.tagName === "DIALOG" && event.target.open) {
      const box = event.target.getBoundingClientRect();
      const outside =
        event.clientX < box.left || event.clientX > box.right ||
        event.clientY < box.top || event.clientY > box.bottom;
      if (outside) event.target.close();
    }
  });
})();
