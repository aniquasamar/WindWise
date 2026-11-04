// Sets the theme before first paint so dark mode never flashes light.
(function () {
  try {
    var saved = localStorage.getItem("windwise-theme");
    var dark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    document.documentElement.dataset.theme = saved === "light" || saved === "dark" ? saved : dark ? "dark" : "light";
  } catch (e) {}
})();