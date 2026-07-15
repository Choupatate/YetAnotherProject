(function () {
  var STORAGE_KEY = "storybook-author";

  function initAuthorChips(root, onChange) {
    var chips = root
      ? Array.prototype.slice.call(root.querySelectorAll(".editor__author-chip"))
      : [];
    var selected = null;

    function findChipByName(name) {
      for (var i = 0; i < chips.length; i++) {
        if (chips[i].dataset.authorName === name) return chips[i];
      }
      return null;
    }

    if (chips.length) {
      var preselected = null;
      for (var i = 0; i < chips.length; i++) {
        if (chips[i].getAttribute("aria-pressed") === "true") {
          preselected = chips[i];
          break;
        }
      }
      if (preselected) {
        selected = preselected.dataset.authorName;
      } else {
        var stored = window.SafeStorage ? window.SafeStorage.getString(STORAGE_KEY) : null;
        var storedChip = stored ? findChipByName(stored) : null;
        if (storedChip) {
          storedChip.setAttribute("aria-pressed", "true");
          selected = stored;
        }
      }

      chips.forEach(function (chip) {
        chip.addEventListener("click", function () {
          var wasSelected = chip.getAttribute("aria-pressed") === "true";
          chips.forEach(function (c) {
            c.setAttribute("aria-pressed", "false");
          });
          if (wasSelected) {
            selected = null;
          } else {
            chip.setAttribute("aria-pressed", "true");
            selected = chip.dataset.authorName;
            if (window.SafeStorage) window.SafeStorage.setString(STORAGE_KEY, selected);
          }
          if (onChange) onChange(selected);
        });
      });
    }

    return {
      chips: chips,
      getSelected: function () {
        return selected;
      },
      setSelected: function (name) {
        chips.forEach(function (c) {
          c.setAttribute("aria-pressed", "false");
        });
        selected = null;
        if (name) {
          var chip = findChipByName(name);
          if (chip) {
            chip.setAttribute("aria-pressed", "true");
            selected = name;
          }
        }
      },
    };
  }

  window.StorybookAuthorChips = { init: initAuthorChips };
})();
