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
})();
