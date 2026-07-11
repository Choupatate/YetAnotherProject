(function () {
  var form = document.getElementById("instant-form");
  var photoInput = document.getElementById("instant-photo");
  var photoPicker = document.getElementById("instant-photo-picker");
  var photoPreview = document.getElementById("instant-photo-preview");
  var lineInput = document.getElementById("instant-line");
  var dateInput = document.getElementById("instant-date");
  var saveButton = document.getElementById("instant-save");

  var authorsRoot = document.getElementById("editor-authors");
  var authorChipsController = window.StorybookAuthorChips.init(authorsRoot);

  var previewUrl = null;

  photoInput.addEventListener("change", function () {
    if (previewUrl) {
      URL.revokeObjectURL(previewUrl);
      previewUrl = null;
    }
    var file = photoInput.files[0];
    if (file) {
      previewUrl = URL.createObjectURL(file);
      photoPreview.src = previewUrl;
      photoPreview.hidden = false;
      photoPicker.classList.add("has-photo");
    } else {
      photoPreview.hidden = true;
      photoPreview.removeAttribute("src");
      photoPicker.classList.remove("has-photo");
    }
  });

  function handleJsonResponse(response) {
    return response
      .json()
      .catch(function () {
        return {};
      })
      .then(function (data) {
        if (!response.ok) {
          throw new Error(data.error || "Something went wrong. Please try again.");
        }
        return data;
      });
  }

  form.addEventListener("submit", function (event) {
    event.preventDefault();
    var file = photoInput.files[0];
    if (!file) {
      window.alert("Please choose a photo.");
      return;
    }

    var line = lineInput.value.trim();
    var storyDate = dateInput.value;
    var author = authorChipsController.getSelected() || "";

    saveButton.disabled = true;

    fetch("/api/stories", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        title: line,
        date: storyDate,
        markdown: line,
        kind: "instant",
        author: author,
      }),
    })
      .then(handleJsonResponse)
      .then(function (created) {
        var formData = new FormData();
        formData.append("file", file);
        return fetch("/api/stories/" + created.id + "/images", {
          method: "POST",
          body: formData,
        })
          .then(handleJsonResponse)
          .then(function (uploaded) {
            return fetch("/api/stories/" + created.id, {
              method: "PUT",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                title: created.title,
                date: storyDate,
                markdown: line,
                cover: uploaded.filename,
                author: author,
              }),
            }).then(handleJsonResponse);
          });
      })
      .then(function () {
        window.location.href = "/";
      })
      .catch(function (error) {
        saveButton.disabled = false;
        window.alert(
          (error && error.message) ||
            "Could not save your instant. Please check your connection and try again."
        );
      });
  });
})();
