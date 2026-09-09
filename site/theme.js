// Apply the saved preference before painting; storage may be disabled.
try {
  const saved = localStorage.getItem("lclang-theme");
  document.documentElement.dataset.theme = saved === "light" || saved === "dark"
    ? saved : (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
} catch {
  document.documentElement.dataset.theme = matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}
