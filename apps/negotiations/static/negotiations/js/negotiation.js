(function () {
  "use strict";
  const dialog = document.getElementById("counter-modal");
  if (!dialog) return;
  const current = document.querySelector(".offer.is-current .coin");
  const amount = dialog.querySelector("#id_amount");
  if (!current || !amount) return;
  const base = parseFloat((current.textContent || "").replace(/[^0-9.]/g, ""));
  if (!isFinite(base) || base <= 0) return;
  const note = document.createElement("p");
  note.className = "field__hint";
  amount.insertAdjacentElement("afterend", note);
  function compare() {
    const value = parseFloat(amount.value || "0");
    if (!isFinite(value) || value <= 0) { note.textContent = ""; return; }
    const diff = value - base;
    if (Math.abs(diff) < 0.005) {
      note.textContent = "Same as the current offer.";
      return;
    }
    const pct = Math.abs(diff / base * 100).toFixed(1);
    note.textContent =
      (diff > 0 ? "Higher by " : "Lower by ") + Math.abs(diff).toFixed(2) +
      " SKC (" + pct + "%).";
  }
  amount.addEventListener("input", compare);
  dialog.addEventListener("close", function () { note.textContent = ""; });
  compare();
})();
