(function () {
  var btn = document.getElementById("book-print-btn");
  if (btn) {
    btn.addEventListener("click", function () {
      window.print();
    });
  }

  // The timeline's "Download as PDF" link points here with ?print=1 so the
  // browser's print-to-PDF dialog opens immediately, without the reader
  // needing to know the floating Print button exists.
  if (new URLSearchParams(window.location.search).get("print") === "1") {
    window.print();
  }
})();
