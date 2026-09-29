(function () {
  "use strict";

  const picker = document.querySelector(".skill-picker");
  if (!picker) return;

  picker.addEventListener("change", function (event) {
    if (event.target.type !== "checkbox") return;
    const row = event.target.closest(".skill-pick");
    if (row) row.classList.toggle("is-on", event.target.checked);
  });

  const filter = document.getElementById("skill-filter");
  if (filter) {
    filter.addEventListener("input", function () {
      const needle = filter.value.trim().toLowerCase();
      picker.querySelectorAll(".skill-pick").forEach(function (row) {
        const match = !needle || (row.dataset.name || "").indexOf(needle) !== -1;

        const ticked = row.querySelector("input[type=checkbox]").checked;
        row.classList.toggle("is-hidden", !match && !ticked);
      });
    });
  }
})();
