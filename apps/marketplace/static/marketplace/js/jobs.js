/* Job list: keep the filter rail usable without a page reload for the
   cheap controls, and remember whether it is open on small screens. */
(function () {
  "use strict";

  const form = document.getElementById("job-filters");
  if (!form) return;

  /* Submitting on change for selects only. Text and number inputs stay manual
     so a half-typed budget does not trigger a search. */
  form.querySelectorAll("select:not([multiple])").forEach(function (select) {
    select.addEventListener("change", function () { form.submit(); });
  });

  const sort = form.querySelector("[name=sort]");
  if (sort) sort.addEventListener("change", function () { form.submit(); });
})();