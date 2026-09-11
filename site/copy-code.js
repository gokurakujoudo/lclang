document.querySelectorAll(".rst-content pre code").forEach((code) => {
  if (!navigator.clipboard || !window.isSecureContext) return;
  const button = document.createElement("button");
  button.type = "button";
  button.className = "copy-code";
  button.textContent = "Copy";
  button.setAttribute("aria-label", "Copy code");
  button.addEventListener("click", async () => {
    try { await navigator.clipboard.writeText(code.textContent); button.textContent = "Copied!"; }
    catch { button.textContent = "Select code to copy"; }
    setTimeout(() => { button.textContent = "Copy"; }, 2000);
  });
  code.parentElement.before(button);
});
