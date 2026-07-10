(function () {
  var reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  var entries = document.querySelectorAll(".timeline__entry");
  if (entries.length) {
    if (reduceMotion || !("IntersectionObserver" in window)) {
      entries.forEach(function (el) {
        el.classList.add("is-visible");
      });
    } else {
      var entryObserver = new IntersectionObserver(
        function (observed) {
          observed.forEach(function (entry) {
            if (entry.isIntersecting) {
              entry.target.classList.add("is-visible");
              entryObserver.unobserve(entry.target);
            }
          });
        },
        { threshold: 0.15 }
      );
      entries.forEach(function (el) {
        entryObserver.observe(el);
      });
    }
  }

  var yearMarkers = document.querySelectorAll(".timeline__year-marker");
  var minimapLinks = document.querySelectorAll(".minimap__tick");

  if (yearMarkers.length && minimapLinks.length) {
    var linksByYear = {};
    minimapLinks.forEach(function (link) {
      linksByYear[link.dataset.year] = link;
    });

    if ("IntersectionObserver" in window) {
      var yearObserver = new IntersectionObserver(
        function (observed) {
          observed.forEach(function (marker) {
            if (marker.isIntersecting) {
              minimapLinks.forEach(function (link) {
                link.classList.remove("is-active");
              });
              var link = linksByYear[marker.target.dataset.year];
              if (link) link.classList.add("is-active");
            }
          });
        },
        { rootMargin: "-45% 0px -45% 0px" }
      );
      yearMarkers.forEach(function (marker) {
        yearObserver.observe(marker);
      });
    }

    minimapLinks.forEach(function (link) {
      link.addEventListener("click", function (event) {
        var targetId = link.getAttribute("href").slice(1);
        var target = document.getElementById(targetId);
        if (!target) return;
        event.preventDefault();
        target.scrollIntoView({
          behavior: reduceMotion ? "auto" : "smooth",
          block: "start",
        });
      });
    });
  }

  // --- Client-side title/author search ------------------------------------
  //
  // Filters the already-rendered entries; nothing is fetched or re-rendered.
  // A sealed entry's real title never appears in the DOM, so it simply won't
  // match by title — expected, since the point of sealing is to hide it.

  var searchInput = document.getElementById("timeline-search");
  var searchEmpty = document.getElementById("timeline-search-empty");
  var searchEmptyQuery = document.getElementById("timeline-search-empty-query");

  if (searchInput && entries.length) {
    searchInput.addEventListener("input", function () {
      var query = searchInput.value.trim().toLowerCase();
      var visibleCount = 0;

      entries.forEach(function (entry) {
        var title = entry.querySelector(".timeline__title");
        var author = entry.querySelector(".timeline__author");
        var text = (title ? title.textContent : "") + " " + (author ? author.textContent : "");
        var match = !query || text.toLowerCase().indexOf(query) !== -1;
        entry.hidden = !match;
        if (match) visibleCount++;
      });

      yearMarkers.forEach(function (marker) {
        var el = marker.nextElementSibling;
        var anyVisible = false;
        while (el && !el.classList.contains("timeline__year-marker")) {
          if (!el.hidden) {
            anyVisible = true;
            break;
          }
          el = el.nextElementSibling;
        }
        marker.hidden = !anyVisible;
      });

      if (searchEmpty) {
        searchEmpty.hidden = !(query && visibleCount === 0);
        if (searchEmptyQuery) searchEmptyQuery.textContent = searchInput.value.trim();
      }
    });
  }

  // --- Jump to the latest entry ---------------------------------------------

  var jumpLink = document.getElementById("timeline-jump-latest");
  if (jumpLink && entries.length) {
    jumpLink.addEventListener("click", function (event) {
      event.preventDefault();
      var visible = Array.prototype.filter.call(entries, function (el) {
        return !el.hidden;
      });
      var last = visible[visible.length - 1];
      if (!last) return;
      last.scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth", block: "center" });
      var link = last.querySelector(".timeline__link");
      if (link) link.focus();
    });
  }
})();
