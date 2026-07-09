(function () {
  var prevLink = document.querySelector(".story__prev");
  var nextLink = document.querySelector(".story__next");

  document.addEventListener("keydown", function (event) {
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
