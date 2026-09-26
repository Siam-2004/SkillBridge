/* Skill picker: reveal level and years when a skill is ticked, and filter the
   long list by name. The server re-reads every checkbox on submit, so nothing
   here is load-bearing. */
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
        /* A ticked skill always stays visible, so filtering can never hide a
           selection the person is about to save. */
        const ticked = row.querySelector("input[type=checkbox]").checked;
        row.classList.toggle("is-hidden", !match && !ticked);
      });
    });
  }
})();
