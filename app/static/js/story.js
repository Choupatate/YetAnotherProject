(function () {
  var prevLink = document.querySelector(".story__prev");
  var nextLink = document.querySelector(".story__next");

  var overlay = null;
  var lastFocused = null;

  function closeLightbox(viaPopstate) {
    if (!overlay) return;
    overlay.remove();
    overlay = null;
    document.body.style.overflow = "";
    if (lastFocused) lastFocused.focus();
    if (!viaPopstate) history.back();
  }

  function openLightbox(img) {
    lastFocused = document.activeElement;
    var figure = img.closest("figure");
    var caption = figure ? figure.querySelector("figcaption") : null;
    var captionText = caption ? caption.textContent.trim() : "";

    overlay = document.createElement("div");
    overlay.className = "lightbox";
    overlay.setAttribute("role", "dialog");
    overlay.setAttribute("aria-label", captionText || "Photo");
    overlay.tabIndex = -1;
    overlay.addEventListener("click", function () {
      closeLightbox(false);
    });

    var bigImg = document.createElement("img");
    bigImg.src = img.currentSrc || img.src;
    bigImg.alt = img.alt || "";
    bigImg.className = "lightbox__image";
    overlay.appendChild(bigImg);

    if (captionText) {
      var cap = document.createElement("p");
      cap.className = "lightbox__caption";
      cap.textContent = captionText;
      overlay.appendChild(cap);
    }

    document.body.appendChild(overlay);
    document.body.style.overflow = "hidden";
    overlay.focus();
    history.pushState({ storybookLightbox: true }, "");
  }

  document.querySelectorAll(".story__body figure img, .story__cover").forEach(function (img) {
    img.addEventListener("click", function () {
      openLightbox(img);
    });
  });

  window.addEventListener("popstate", function () {
    if (overlay) closeLightbox(true);
  });

  document.addEventListener("keydown", function (event) {
    if (overlay) {
      if (event.key === "Escape") closeLightbox(false);
      return;
    }
    if (event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) return;
    var target = event.target;
    var tag = target && target.tagName;
    if (tag === "INPUT" || tag === "TEXTAREA" || (target && target.isContentEditable)) return;

    if (event.key === "ArrowLeft" && prevLink) {
      window.location.href = prevLink.href;
    } else if (event.key === "ArrowRight" && nextLink) {
      window.location.href = nextLink.href;
    }
  });
})();
