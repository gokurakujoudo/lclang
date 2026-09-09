const root = document.documentElement;
root.classList.add("js");
const base = new URL(document.body.dataset.base, location.href);
const theme = document.querySelector(".theme-toggle");
const updateThemeLabel = () => { theme.textContent = root.dataset.theme === "dark" ? "Light mode" : "Dark mode"; };
theme.hidden = false;
updateThemeLabel();
theme.addEventListener("click", () => {
  root.dataset.theme = root.dataset.theme === "dark" ? "light" : "dark";
  try { localStorage.setItem("lclang-theme", root.dataset.theme); } catch { /* Preference lasts for this page. */ }
  updateThemeLabel();
});

const menu = document.querySelector(".menu-toggle");
const sidebar = document.querySelector(".sidebar");
menu.hidden = false;
const closeMenu = () => { sidebar.classList.remove("is-open"); menu.setAttribute("aria-expanded", "false"); };
menu.addEventListener("click", () => {
  menu.setAttribute("aria-expanded", String(sidebar.classList.toggle("is-open")));
});
document.addEventListener("click", (event) => {
  if (!sidebar.contains(event.target) && !menu.contains(event.target)) closeMenu();
});
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && sidebar.classList.contains("is-open")) { closeMenu(); menu.focus(); }
});

document.querySelectorAll("article pre").forEach((pre) => {
  const code = pre.querySelector("code");
  if (!code) return;
  const wrapper = document.createElement("div");
  wrapper.className = "code-block";
  const toolbar = document.createElement("div");
  toolbar.className = "code-toolbar";
  const language = document.createElement("span");
  language.textContent = code.className.replace("language-", "") || "text";
  toolbar.append(language);
  if (navigator.clipboard && window.isSecureContext) {
    const copy = document.createElement("button");
    copy.type = "button";
    copy.textContent = "Copy";
    copy.setAttribute("aria-label", `Copy ${language.textContent} code`);
    copy.addEventListener("click", async () => {
      try { await navigator.clipboard.writeText(code.textContent); copy.textContent = "Copied!"; }
      catch { copy.textContent = "Select code to copy"; }
      setTimeout(() => { copy.textContent = "Copy"; }, 2000);
    });
    toolbar.append(copy);
  }
  pre.before(wrapper);
  wrapper.append(toolbar, pre);
});

const dialog = document.querySelector(".search-dialog");
const input = document.querySelector("#search-input");
const status = document.querySelector("#search-status");
const results = document.querySelector("#search-results");
let index;
let loading;
const renderSearch = () => {
  results.replaceChildren();
  const words = input.value.toLocaleLowerCase().trim().split(/\s+/).filter(Boolean);
  if (!index) return;
  if (!words.length) { status.textContent = "Type to search all documentation."; return; }
  const matches = index.map((entry) => {
    const heading = `${entry.title} ${entry.heading}`.toLocaleLowerCase();
    const text = `${heading} ${entry.text}`.toLocaleLowerCase();
    return { entry, score: words.every((word) => text.includes(word))
      ? 1 + words.filter((word) => heading.includes(word)).length * 10 : 0 };
  }).filter((match) => match.score).sort((a, b) => b.score - a.score);
  status.textContent = matches.length ? `${matches.length} matching sections${matches.length > 30 ? "; showing the first 30" : ""}.` : "No results. Try a different term, such as Frame or logging.";
  matches.slice(0, 30).forEach(({ entry }) => {
    const item = document.createElement("li");
    const link = document.createElement("a");
    link.href = new URL(entry.url, base).href;
    const context = document.createElement("small");
    context.textContent = `${entry.group} / ${entry.title}`;
    const title = document.createElement("strong");
    title.textContent = entry.heading;
    const excerpt = document.createElement("p");
    const start = Math.max(0, entry.text.toLocaleLowerCase().indexOf(words[0]) - 60);
    excerpt.textContent = `${start ? "…" : ""}${entry.text.slice(start, start + 190)}${entry.text.length > start + 190 ? "…" : ""}`;
    link.append(context, title, excerpt);
    item.append(link);
    results.append(item);
  });
};
const openSearch = async () => {
  if (!dialog.open) dialog.showModal();
  input.focus();
  if (!index) {
    status.textContent = "Loading search index…";
    try {
      loading ??= fetch(new URL("search-index.json", base)).then((response) => {
        if (!response.ok) throw new Error("Search unavailable");
        return response.json();
      });
      index = await loading;
    } catch {
      loading = undefined;
      status.textContent = "Search could not load. Close and reopen to retry, or use the documentation sidebar.";
      return;
    }
  }
  renderSearch();
};
document.querySelectorAll(".search-open").forEach((button) => {
  button.hidden = false;
  button.addEventListener("click", openSearch);
});
document.querySelector(".search-close").addEventListener("click", () => dialog.close());
results.addEventListener("click", (event) => {
  if (event.target.closest("a")) dialog.close();
});
input.addEventListener("input", renderSearch);
input.addEventListener("keydown", (event) => {
  if (event.key === "ArrowDown") { event.preventDefault(); results.querySelector("a")?.focus(); }
  if (event.key === "Enter") results.querySelector("a")?.click();
});
document.addEventListener("keydown", (event) => {
  const editing = event.target.matches("input, textarea, select, [contenteditable]");
  if ((event.key === "/" && !editing) || ((event.ctrlKey || event.metaKey) && event.key === "k")) {
    event.preventDefault();
    openSearch();
  }
});
const tocLinks = [...document.querySelectorAll(".contents nav a")];
if ("IntersectionObserver" in window) {
  const observer = new IntersectionObserver((entries) => {
    const active = entries.find((entry) => entry.isIntersecting);
    if (!active) return;
    tocLinks.forEach((link) => {
      if (decodeURIComponent(link.hash.slice(1)) === active.target.id) link.setAttribute("aria-current", "location");
      else link.removeAttribute("aria-current");
    });
  }, { rootMargin: "-90px 0px -65% 0px" });
  tocLinks.map((link) => document.getElementById(decodeURIComponent(link.hash.slice(1))))
    .filter(Boolean).forEach((heading) => observer.observe(heading));
}
