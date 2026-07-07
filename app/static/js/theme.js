(function () {
  var STORAGE_KEY = "storybook-theme";
  var THEMES = ["dark", "light", "manuscript"];
  var toggle = document.getElementById("theme-toggle");
  if (!toggle) return;

  function currentTheme() {
    var attr = document.documentElement.getAttribute("data-theme");
    if (attr) return attr;
    return window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
  }

  toggle.addEventListener("click", function () {
    var index = THEMES.indexOf(currentTheme());
    var next = THEMES[(index + 1) % THEMES.length];
    document.documentElement.setAttribute("data-theme", next);
    localStorage.setItem(STORAGE_KEY, next);
  });
})();
