(function () {
  "use strict";

  const budget = document.getElementById("id_budget");
  const panel = document.getElementById("available-balance");
  const warning = document.getElementById("budget-warning");
  const text = document.getElementById("budget-warning-text");
  if (!budget || !panel || !warning || !text) return;

  const available = parseFloat(panel.dataset.available || "0");

  function check() {
    const wanted = parseFloat(budget.value || "0");
    if (!isFinite(wanted) || wanted <= available) {
      warning.classList.add("hide");
      return;
    }
    const short = (wanted - available).toFixed(2);
    text.textContent =
      "That is " + short + " SKC more than your available balance. " +
      "Deposit the difference, or save this as a draft.";
    warning.classList.remove("hide");
  }

  budget.addEventListener("input", check);
  check();
})();
