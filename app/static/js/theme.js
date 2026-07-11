(function () {
  var STORAGE_KEY = "storybook-theme";
  var THEMES = ["dark", "light", "manuscript"];
  var toggle = document.getElementById("theme-toggle");

  function currentTheme() {
    var attr = document.documentElement.getAttribute("data-theme");
    if (attr) return attr;
    return window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
  }

  // R4.8: the two theme-color metas key off prefers-color-scheme, so once a
  // theme is actively chosen (rather than left to follow the OS), the
  // address-bar chrome can clash with it. Once a theme is applied, overwrite
  // both metas' content with that theme's own background so whichever one
  // the browser matches shows the same color. With no stored theme neither
  // meta is touched, so the OS-scheme defaults keep applying.
  function syncThemeColorMeta() {
    var bg = getComputedStyle(document.documentElement).getPropertyValue("--color-bg").trim();
    if (!bg) return;
    document.querySelectorAll('meta[name="theme-color"]').forEach(function (meta) {
      meta.setAttribute("content", bg);
    });
  }

  if (document.documentElement.hasAttribute("data-theme")) {
    syncThemeColorMeta();
  }

  if (!toggle) return;

  toggle.addEventListener("click", function () {
    var index = THEMES.indexOf(currentTheme());
    var next = THEMES[(index + 1) % THEMES.length];
    document.documentElement.setAttribute("data-theme", next);
    localStorage.setItem(STORAGE_KEY, next);
    syncThemeColorMeta();
  });
})();
