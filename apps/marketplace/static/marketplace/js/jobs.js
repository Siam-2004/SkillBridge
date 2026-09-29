(function () {
  "use strict";

  const form = document.getElementById("job-filters");
  if (!form) return;

  form.querySelectorAll("select:not([multiple])").forEach(function (select) {
    select.addEventListener("change", function () { form.submit(); });
  });

  const sort = form.querySelector("[name=sort]");
  if (sort) sort.addEventListener("change", function () { form.submit(); });
})();
