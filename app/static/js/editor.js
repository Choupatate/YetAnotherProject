(function () {
  var form = document.getElementById("editor-form");
  var titleInput = document.getElementById("story-title");
  var dateInput = document.getElementById("story-date");
  var unlockInput = document.getElementById("story-unlock");
  var draftToggle = document.getElementById("draft-toggle");
  var archiveToggle = document.getElementById("archive-toggle");
  var root = document.getElementById("editor-root");
  var sourceTextarea = document.getElementById("markdown-source");
  var saveButton = document.getElementById("save-story");

  var storyId = form.dataset.storyId || null;
  var dirty = false;

  if (draftToggle) {
    draftToggle.addEventListener("click", function () {
      var pressed = draftToggle.getAttribute("aria-pressed") === "true";
      draftToggle.setAttribute("aria-pressed", pressed ? "false" : "true");
      markDirty();
    });
  }

  if (archiveToggle) {
    archiveToggle.addEventListener("click", function () {
      var pressed = archiveToggle.getAttribute("aria-pressed") === "true";
      archiveToggle.setAttribute("aria-pressed", pressed ? "false" : "true");
      markDirty();
    });
  }

  if (unlockInput) {
    unlockInput.addEventListener("input", markDirty);
  }

  function isDraft() {
    return !!draftToggle && draftToggle.getAttribute("aria-pressed") === "true";
  }

  function isArchived() {
    return !!archiveToggle && archiveToggle.getAttribute("aria-pressed") === "true";
  }

  function unlockValue() {
    return unlockInput ? unlockInput.value : "";
  }

  var authorsRoot = document.getElementById("editor-authors");
  var authorChipsController = window.StorybookAuthorChips.init(authorsRoot, function () {
    markDirty();
  });

  function isDarkTheme() {
    var attr = document.documentElement.getAttribute("data-theme");
    if (attr) return attr === "dark";
    return window.matchMedia("(prefers-color-scheme: dark)").matches;
  }

  function markDirty() {
    dirty = true;
    scheduleAutosave();
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
      body: JSON.stringify({
        title: title,
        date: storyDate,
        markdown: "",
        author: authorChipsController.getSelected() || "",
        draft: isDraft(),
        unlock: unlockValue(),
        archived: isArchived(),
      }),
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
      setMarkdown: function (value) {
        editor.setMarkdown(value);
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
      setMarkdown: function (value) {
        sourceTextarea.value = value;
      },
    };
  }

  var editor =
    window.toastui && window.toastui.Editor ? createToastEditor() : createFallbackEditor();

  titleInput.addEventListener("input", markDirty);
  dateInput.addEventListener("input", markDirty);

  // --- Autosave to localStorage + crash/close recovery ---------------------
  //
  // Protects against losing an in-progress edit to a browser crash, a
  // dropped connection, or an accidental tab close before the first manual
  // save — separate from server-side version history, which only records
  // content that was actually saved.

  var AUTOSAVE_KEY = "storybook-autosave-" + (storyId || "new");
  var recoveryBanner = document.getElementById("editor-recovery");
  var recoveryTimeEl = document.getElementById("editor-recovery-time");
  var recoveryRestoreBtn = document.getElementById("editor-recovery-restore");
  var recoveryDiscardBtn = document.getElementById("editor-recovery-discard");
  var autosaveTimer = null;
  var initialTitle = titleInput.value;
  var initialMarkdown = sourceTextarea.value;

  function currentDraftPayload() {
    return {
      title: titleInput.value,
      date: dateInput.value,
      markdown: editor.getMarkdown(),
      author: authorChipsController.getSelected() || "",
      draft: isDraft(),
      unlock: unlockValue(),
      archived: isArchived(),
      savedAt: Date.now(),
    };
  }

  function readAutosave() {
    var raw;
    try {
      raw = localStorage.getItem(AUTOSAVE_KEY);
    } catch (e) {
      return null;
    }
    if (!raw) return null;
    try {
      return JSON.parse(raw);
    } catch (e) {
      return null;
    }
  }

  function clearAutosave() {
    try {
      localStorage.removeItem(AUTOSAVE_KEY);
    } catch (e) {}
  }

  function scheduleAutosave() {
    if (autosaveTimer) return;
    autosaveTimer = setTimeout(function () {
      autosaveTimer = null;
      try {
        localStorage.setItem(AUTOSAVE_KEY, JSON.stringify(currentDraftPayload()));
      } catch (e) {}
    }, 2000);
  }

  function applyDraft(draftData) {
    titleInput.value = draftData.title || "";
    if (draftData.date) dateInput.value = draftData.date;
    editor.setMarkdown(draftData.markdown || "");
    if (unlockInput) unlockInput.value = draftData.unlock || "";
    if (draftToggle) draftToggle.setAttribute("aria-pressed", draftData.draft ? "true" : "false");
    if (archiveToggle) {
      archiveToggle.setAttribute("aria-pressed", draftData.archived ? "true" : "false");
    }
    authorChipsController.setSelected(draftData.author || null);
    markDirty();
  }

  var pendingDraft = readAutosave();
  if (pendingDraft) {
    var hasRecoverableChanges =
      (pendingDraft.title || "") !== initialTitle ||
      (pendingDraft.markdown || "") !== initialMarkdown;
    if (hasRecoverableChanges && recoveryBanner) {
      recoveryTimeEl.textContent = new Date(pendingDraft.savedAt).toLocaleString();
      recoveryBanner.hidden = false;
    } else {
      clearAutosave();
      pendingDraft = null;
    }
  }

  if (recoveryRestoreBtn) {
    recoveryRestoreBtn.addEventListener("click", function () {
      if (pendingDraft) applyDraft(pendingDraft);
      recoveryBanner.hidden = true;
    });
  }

  if (recoveryDiscardBtn) {
    recoveryDiscardBtn.addEventListener("click", function () {
      clearAutosave();
      recoveryBanner.hidden = true;
    });
  }

  form.addEventListener("submit", function (event) {
    event.preventDefault();
    var title = titleInput.value.trim();
    var storyDate = dateInput.value;
    if (!title) {
      titleInput.focus();
      return;
    }
    var markdown = editor.getMarkdown();
    var payload = {
      title: title,
      date: storyDate,
      markdown: markdown,
      author: authorChipsController.getSelected() || "",
      draft: isDraft(),
      unlock: unlockValue(),
      archived: isArchived(),
    };

    // A brand-new story is created with its real content in one request
    // rather than going through ensureStoryId()'s empty-body POST followed
    // by an immediate PUT — avoids a redundant write (and, now that saves
    // are versioned, a spurious near-empty entry in that story's history).
    var request = storyId
      ? fetch("/api/stories/" + storyId, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        })
      : fetch("/api/stories", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });

    request
      .then(handleJsonResponse)
      .then(function (data) {
        dirty = false;
        clearAutosave();
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
