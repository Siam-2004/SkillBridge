(function () {
  "use strict";
  const panel = document.querySelector(".conversation");
  const thread = document.getElementById("thread");
  if (!panel || !thread) return;

  function toBottom() { thread.scrollTop = thread.scrollHeight; }
  toBottom();
  const box = panel.querySelector(".composer textarea");
  if (box) {
    box.addEventListener("keydown", function (event) {
      if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        box.closest("form").submit();
      }
    });
  }
  const url = panel.dataset.pollUrl;
  if (!url) return;
  function latestTimestamp() {
    const nodes = thread.querySelectorAll("[data-created]");
    return nodes.length ? nodes[nodes.length - 1].dataset.created : "";
  }
  function render(message) {
    const article = document.createElement("article");
    article.className = "msg" + (message.is_mine ? " msg--mine" : "") +
                        (message.kind === "SYSTEM" ? " msg--system" : "");
    article.dataset.created = message.created_at;

    if (message.kind === "SYSTEM") {
      const p = document.createElement("p");
      p.className = "msg__system";
      p.textContent = message.content;
      article.appendChild(p);
    } else {
      const avatar = document.createElement("span");
      avatar.className = "avatar avatar--sm";
      avatar.textContent = message.initials;

      const body = document.createElement("div");
      body.className = "msg__body";
      const meta = document.createElement("div");
      meta.className = "msg__meta";
      const who = document.createElement("strong");
      who.textContent = message.sender + (message.username ? " (@" + message.username + ")" : "");
      meta.appendChild(who);
      const text = document.createElement("div");
      text.className = "msg__text";
      text.textContent = message.content;   /* textContent, never innerHTML */
      body.appendChild(meta);
      body.appendChild(text);
      article.appendChild(avatar);
      article.appendChild(body);
    }
    thread.appendChild(article);
  }
  let failures = 0;
  function poll() {
    const after = latestTimestamp();
    fetch(url + (after ? "?after=" + encodeURIComponent(after) : ""), {
      credentials: "same-origin",
      headers: { "X-Requested-With": "XMLHttpRequest" },
    })
      .then(function (response) {
        if (!response.ok) throw new Error(response.status);
        return response.json();
      })
      .then(function (data) {
        failures = 0;
        const atBottom =
          thread.scrollHeight - thread.scrollTop - thread.clientHeight < 60;
        let added = 0;
        (data.messages || []).forEach(function (message) {
          if (!thread.querySelector('[data-created="' + message.created_at + '"]')) {
            render(message);
            added += 1;
          }
        });
        if (added && atBottom) toBottom();
      })
      .catch(function () {
        failures += 1;
      })
      .finally(function () {
        if (failures < 5) window.setTimeout(poll, 6000 + failures * 4000);
      });
  }
  window.setTimeout(poll, 6000);
})();
