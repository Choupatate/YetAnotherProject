(function () {
  var btn = document.getElementById("book-print-btn");
  if (btn) {
    btn.addEventListener("click", function () {
      window.print();
    });
  }
})();
