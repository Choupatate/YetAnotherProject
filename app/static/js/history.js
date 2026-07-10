(function () {
  var list = document.querySelector(".history__list");
  if (!list) return;
  var storyId = list.dataset.storyId;

  list.addEventListener("click", function (event) {
    var btn = event.target.closest(".history__restore");
    if (!btn) return;
    if (!window.confirm("Restore this version? Your current version will be saved to history too.")) {
      return;
    }
    var versionId = btn.dataset.versionId;
    fetch("/api/stories/" + storyId + "/versions/" + versionId + "/restore", { method: "POST" })
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
      .then(function (result) {
        if (!result.ok) {
          window.alert((result.data && result.data.error) || "Could not restore this version.");
          return;
        }
        window.location.href = "/story/" + storyId;
      })
      .catch(function () {
        window.alert("Could not restore. Please check your connection and try again.");
      });
  });
})();
