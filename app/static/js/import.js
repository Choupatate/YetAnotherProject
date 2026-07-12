(function () {
  var form = document.getElementById("import-form");
  var fileInput = document.getElementById("import-file");
  var fileLabel = document.getElementById("import-file-label");
  var fileLabelDefault = fileLabel ? fileLabel.textContent : "";
  var result = document.getElementById("import-result");
  var spinner = document.getElementById("import-spinner");
  if (!form) return;

  fileInput.addEventListener("change", function () {
    var file = fileInput.files[0];
    if (fileLabel) fileLabel.textContent = file ? file.name : fileLabelDefault;
  });

  form.addEventListener("submit", function (event) {
    event.preventDefault();
    var file = fileInput.files[0];
    if (!file) return;

    var formData = new FormData();
    formData.append("file", file);

    result.hidden = true;
    result.classList.remove("import__result--error");
    if (spinner) spinner.hidden = false;

    fetch("/api/import", { method: "POST", body: formData })
      .then(function (response) {
        return response
          .json()
          .catch(function () {
            return {};
          })
          .then(function (data) {
            return { ok: response.ok, data: data };
          });
      })
      .then(function (res) {
        result.hidden = false;
        if (!res.ok) {
          if (spinner) spinner.hidden = true;
          result.classList.add("import__result--error");
          result.textContent = (res.data && res.data.error) || "Import failed.";
          return;
        }
        var count = res.data.imported;
        result.textContent =
          "Imported " + count + (count === 1 ? " story" : " stories") + ". Reloading…";
        setTimeout(function () {
          window.location.href = "/";
        }, 1200);
      })
      .catch(function () {
        result.hidden = false;
        if (spinner) spinner.hidden = true;
        result.classList.add("import__result--error");
        result.textContent = "Could not import. Please check your connection and try again.";
      });
  });
})();
