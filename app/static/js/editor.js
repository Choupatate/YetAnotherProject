(function () {
  var form = document.getElementById("editor-form");
  var titleInput = document.getElementById("story-title");
  var dateInput = document.getElementById("story-date");
  var root = document.getElementById("editor-root");
  var sourceTextarea = document.getElementById("markdown-source");
  var saveButton = document.getElementById("save-story");

  var storyId = form.dataset.storyId || null;
  var dirty = false;

  function isDarkTheme() {
    var attr = document.documentElement.getAttribute("data-theme");
    if (attr) return attr === "dark";
    return window.matchMedia("(prefers-color-scheme: dark)").matches;
  }

  function markDirty() {
    dirty = true;
  }

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

  function ensureStoryId() {
    if (storyId) return Promise.resolve(storyId);
    var title = titleInput.value.trim() || "Untitled";
    var storyDate = dateInput.value;
    return fetch("/api/stories", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title: title, date: storyDate, markdown: "" }),
    })
      .then(handleJsonResponse)
      .then(function (data) {
        storyId = data.id;
        form.dataset.storyId = storyId;
        history.replaceState(null, "", "/edit/" + storyId);
        return storyId;
      });
  }

  function uploadImage(file) {
    return ensureStoryId().then(function (id) {
      var formData = new FormData();
      formData.append("file", file);
      return fetch("/api/stories/" + id + "/images", {
        method: "POST",
        body: formData,
      })
        .then(handleJsonResponse)
        .then(function (data) {
          return data.filename;
        });
    });
  }

  function createToastEditor() {
    var editor = new window.toastui.Editor({
      el: root,
      height: "60vh",
      initialEditType: "wysiwyg",
      previewStyle: "vertical",
      initialValue: sourceTextarea.value,
      theme: isDarkTheme() ? "dark" : undefined,
      usageStatistics: false,
      toolbarItems: [
        ["heading", "bold", "italic", "strike"],
        ["quote"],
        ["ul", "ol"],
        ["image", "link"],
      ],
      hooks: {
        addImageBlobHook: function (blob, callback) {
          uploadImage(blob)
            .then(function (filename) {
              callback(filename, "");
            })
            .catch(function (error) {
              window.alert(error.message);
            });
        },
      },
    });

    editor.insertToolbarItem(
      { groupIndex: 3, itemIndex: 2 },
      {
        name: "highlight",
        tooltip: "Highlight",
        text: "==",
        className: "toastui-editor-toolbar-icons editor__highlight-btn",
        style: { backgroundImage: "none" },
        onClick: function () {
          var selected = editor.getSelectedText();
          if (selected) {
            editor.replaceSelection("==" + selected + "==");
          } else {
            editor.insertText("====");
          }
        },
      }
    );

    editor.on("change", markDirty);

    return {
      getMarkdown: function () {
        return editor.getMarkdown();
      },
    };
  }

  function createFallbackEditor() {
    sourceTextarea.classList.add("editor__source--visible");

    var toolbar = document.createElement("div");
    toolbar.className = "editor__fallback-toolbar";
    root.insertBefore(toolbar, sourceTextarea);

    function wrapSelection(before, after) {
      after = after === undefined ? before : after;
      var start = sourceTextarea.selectionStart;
      var end = sourceTextarea.selectionEnd;
      var value = sourceTextarea.value;
      var selected = value.slice(start, end);
      sourceTextarea.value = value.slice(0, start) + before + selected + after + value.slice(end);
      sourceTextarea.focus();
      sourceTextarea.selectionStart = start + before.length;
      sourceTextarea.selectionEnd = start + before.length + selected.length;
      markDirty();
    }

    function insertLinePrefix(prefix) {
      var start = sourceTextarea.selectionStart;
      var value = sourceTextarea.value;
      var lineStart = value.lastIndexOf("\n", start - 1) + 1;
      sourceTextarea.value = value.slice(0, lineStart) + prefix + value.slice(lineStart);
      sourceTextarea.focus();
      var pos = start + prefix.length;
      sourceTextarea.selectionStart = pos;
      sourceTextarea.selectionEnd = pos;
      markDirty();
    }

    var buttons = [
      { label: "H", title: "Heading", action: function () { insertLinePrefix("## "); } },
      { label: "B", title: "Bold", action: function () { wrapSelection("**"); } },
      { label: "I", title: "Italic", action: function () { wrapSelection("*"); } },
      { label: "S", title: "Strikethrough", action: function () { wrapSelection("~~"); } },
      { label: "“", title: "Quote", action: function () { insertLinePrefix("> "); } },
      { label: "• List", title: "Bulleted list", action: function () { insertLinePrefix("- "); } },
      { label: "1. List", title: "Numbered list", action: function () { insertLinePrefix("1. "); } },
      { label: "Link", title: "Link", action: function () { wrapSelection("[", "](url)"); } },
      { label: "==", title: "Highlight", action: function () { wrapSelection("=="); } },
    ];

    buttons.forEach(function (btn) {
      var el = document.createElement("button");
      el.type = "button";
      el.textContent = btn.label;
      el.title = btn.title;
      el.className = "editor__fallback-btn";
      el.addEventListener("click", btn.action);
      toolbar.appendChild(el);
    });

    var imageInput = document.createElement("input");
    imageInput.type = "file";
    imageInput.accept = "image/*";
    imageInput.className = "editor__fallback-file-input";

    var imageBtn = document.createElement("button");
    imageBtn.type = "button";
    imageBtn.textContent = "Image";
    imageBtn.title = "Insert image";
    imageBtn.className = "editor__fallback-btn";
    imageBtn.addEventListener("click", function () {
      imageInput.click();
    });
    toolbar.appendChild(imageBtn);
    toolbar.appendChild(imageInput);

    imageInput.addEventListener("change", function () {
      var file = imageInput.files[0];
      if (!file) return;
      uploadImage(file)
        .then(function (filename) {
          var start = sourceTextarea.selectionStart;
          var value = sourceTextarea.value;
          var insertion = "![](" + filename + ")\n";
          sourceTextarea.value = value.slice(0, start) + insertion + value.slice(start);
          sourceTextarea.focus();
          imageInput.value = "";
          markDirty();
        })
        .catch(function (error) {
          window.alert(error.message);
          imageInput.value = "";
        });
    });

    sourceTextarea.addEventListener("input", markDirty);

    return {
      getMarkdown: function () {
        return sourceTextarea.value;
      },
    };
  }

  var editor =
    window.toastui && window.toastui.Editor ? createToastEditor() : createFallbackEditor();

  titleInput.addEventListener("input", markDirty);
  dateInput.addEventListener("input", markDirty);

  form.addEventListener("submit", function (event) {
    event.preventDefault();
    var title = titleInput.value.trim();
    var storyDate = dateInput.value;
    if (!title) {
      titleInput.focus();
      return;
    }
    var markdown = editor.getMarkdown();

    ensureStoryId()
      .then(function (id) {
        return fetch("/api/stories/" + id, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ title: title, date: storyDate, markdown: markdown }),
        });
      })
      .then(handleJsonResponse)
      .then(function (data) {
        dirty = false;
        window.location.href = "/story/" + data.id;
      })
      .catch(function (error) {
        window.alert(
          (error && error.message) ||
            "Could not save your story. Please check your connection and try again."
        );
      });
  });

  window.addEventListener("beforeunload", function (event) {
    if (!dirty) return;
    event.preventDefault();
    event.returnValue = "";
  });
})();
