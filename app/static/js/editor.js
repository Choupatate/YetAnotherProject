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
  var saveSpinner = document.getElementById("editor-spinner");
  var saveMessageEl = document.getElementById("editor-save-message");
  var saveButtonDefaultLabel = saveButton.textContent;

  function showSaveMessage(text) {
    if (!saveMessageEl) return;
    saveMessageEl.textContent = text || "";
    saveMessageEl.hidden = !text;
  }

  var storyId = form.dataset.storyId || null;
  var dirty = false;

  // --- Endpoint parametrization (FEATURES.md F14) ---------------------------
  //
  // Story and person editors share this file rather than forking it. The
  // story editor template leaves these data attributes unset, so behavior
  // stays byte-for-byte identical to before; the person editor template
  // supplies the /api/people... equivalents.
  var relationInput = document.getElementById("person-relation");
  var createUrl = form.dataset.createUrl || "/api/stories";
  var updateUrlTemplate = form.dataset.updateUrlTemplate || "/api/stories/__ID__";
  var imageUrlTemplate = form.dataset.imageUrlTemplate || "/api/stories/__ID__/images";
  var redirectTemplate = form.dataset.redirectTemplate || "/story/__ID__";
  var editUrlTemplate = form.dataset.editUrlTemplate || "/edit/__ID__";

  function fillUrlTemplate(template, id) {
    return template.replace("__ID__", id);
  }

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

  // --- Family pickers (FEATURES.md F18) --------------------------------------
  var familyRoot = document.getElementById("editor-family");

  function initChipPicker(root, maxSelected) {
    var chips = root ? Array.prototype.slice.call(root.querySelectorAll(".family-chip")) : [];

    function selected() {
      return chips
        .filter(function (c) {
          return c.getAttribute("aria-pressed") === "true";
        })
        .map(function (c) {
          return c.dataset.personSlug;
        });
    }

    chips.forEach(function (chip) {
      chip.addEventListener("click", function () {
        var pressed = chip.getAttribute("aria-pressed") === "true";
        if (!pressed && maxSelected && selected().length >= maxSelected) return;
        chip.setAttribute("aria-pressed", pressed ? "false" : "true");
        markDirty();
      });
    });

    return {
      getSelected: selected,
      setSelected: function (slugs) {
        var set = {};
        (slugs || []).forEach(function (s) {
          set[s] = true;
        });
        chips.forEach(function (c) {
          c.setAttribute("aria-pressed", set[c.dataset.personSlug] ? "true" : "false");
        });
      },
    };
  }

  var parentsPicker = initChipPicker(document.getElementById("family-parents"), 2);
  var partnersPicker = initChipPicker(document.getElementById("family-partners"));
  var friendOfPicker = initChipPicker(document.getElementById("family-friend-of"));

  var genderRoot = document.getElementById("family-gender");
  var genderButtons = genderRoot
    ? Array.prototype.slice.call(genderRoot.querySelectorAll(".editor__gender-btn"))
    : [];

  function getGender() {
    var pressed = genderButtons.filter(function (b) {
      return b.getAttribute("aria-pressed") === "true";
    })[0];
    return pressed ? pressed.dataset.gender : "";
  }

  function setGender(value) {
    genderButtons.forEach(function (b) {
      b.setAttribute("aria-pressed", b.dataset.gender === (value || "") ? "true" : "false");
    });
  }

  genderButtons.forEach(function (btn) {
    btn.addEventListener("click", function () {
      setGender(btn.dataset.gender);
      markDirty();
    });
  });

  // --- Photo focus point (crop, part of the F18 family-photo styling round) --
  var photoFocusRoot = document.getElementById("editor-photo-focus");
  var photoFocusImg = photoFocusRoot ? photoFocusRoot.querySelector(".editor__photo-focus-img") : null;
  var photoFocusMarker = photoFocusRoot ? photoFocusRoot.querySelector(".editor__photo-focus-marker") : null;
  var photoFocusValue = photoFocusRoot ? photoFocusRoot.dataset.value : null;

  function setPhotoFocus(xPct, yPct) {
    xPct = Math.max(0, Math.min(100, xPct));
    yPct = Math.max(0, Math.min(100, yPct));
    photoFocusValue = Math.round(xPct) + "% " + Math.round(yPct) + "%";
    if (photoFocusImg) photoFocusImg.style.objectPosition = photoFocusValue;
    if (photoFocusMarker) {
      photoFocusMarker.style.left = xPct + "%";
      photoFocusMarker.style.top = yPct + "%";
    }
  }

  if (photoFocusRoot) {
    var initialFocus = (photoFocusValue || "50% 50%").split(" ");
    setPhotoFocus(parseFloat(initialFocus[0]) || 50, parseFloat(initialFocus[1]) || 50);

    photoFocusRoot.addEventListener("click", function (event) {
      var rect = photoFocusRoot.getBoundingClientRect();
      setPhotoFocus(
        ((event.clientX - rect.left) / rect.width) * 100,
        ((event.clientY - rect.top) / rect.height) * 100
      );
      markDirty();
    });
  }

  function addFamilyFields(payload) {
    if (familyRoot) {
      payload.parents = parentsPicker.getSelected();
      payload.partners = partnersPicker.getSelected();
      payload.friend_of = friendOfPicker.getSelected();
      payload.gender = getGender();
    }
    if (photoFocusRoot) {
      payload.photo_focus = photoFocusValue;
    }
  }

  // --- Writing prompt cycling (F16) — never inserted into the story itself.
  var promptTextEl = document.getElementById("editor-prompt-text");
  var promptCycleBtn = document.getElementById("editor-prompt-cycle");
  var promptsDataEl = document.getElementById("editor-prompts-data");
  if (promptCycleBtn && promptsDataEl) {
    var allPrompts = JSON.parse(promptsDataEl.textContent);
    var remainingPrompts = allPrompts.filter(function (p) {
      return p !== promptTextEl.textContent;
    });
    promptCycleBtn.addEventListener("click", function () {
      if (!remainingPrompts.length) remainingPrompts = allPrompts.slice();
      var index = Math.floor(Math.random() * remainingPrompts.length);
      promptTextEl.textContent = remainingPrompts[index];
      remainingPrompts.splice(index, 1);
    });
  }

  // --- Voice memos (F12) ----------------------------------------------------
  var voiceSection = document.getElementById("editor-voice");
  if (voiceSection) {
    var recordBtn = document.getElementById("voice-record-btn");
    var pauseBtn = document.getElementById("voice-pause-btn");
    var stopBtn = document.getElementById("voice-stop-btn");
    var timerEl = document.getElementById("voice-timer");
    var voiceMessageEl = document.getElementById("voice-message");
    var voiceListEl = document.getElementById("voice-list");

    var mediaRecorder = null;
    var recordedChunks = [];
    var recordStartTime = null;
    var elapsedBeforePause = 0;
    var timerInterval = null;
    var recordMimeType = null;
    var recordExt = null;

    function showVoiceMessage(text) {
      voiceMessageEl.textContent = text || "";
      voiceMessageEl.hidden = !text;
    }

    function supportsRecording() {
      return !!(
        navigator.mediaDevices &&
        navigator.mediaDevices.getUserMedia &&
        window.MediaRecorder
      );
    }

    function pickMimeType() {
      if (
        window.MediaRecorder &&
        MediaRecorder.isTypeSupported &&
        MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
      ) {
        return { mimeType: "audio/webm;codecs=opus", ext: "webm" };
      }
      return { mimeType: "audio/mp4", ext: "m4a" };
    }

    function formatElapsed(ms) {
      var totalSeconds = Math.floor(ms / 1000);
      var minutes = Math.floor(totalSeconds / 60);
      var seconds = totalSeconds % 60;
      return (minutes < 10 ? "0" : "") + minutes + ":" + (seconds < 10 ? "0" : "") + seconds;
    }

    function updateTimer() {
      var elapsed = elapsedBeforePause + (recordStartTime ? Date.now() - recordStartTime : 0);
      timerEl.textContent = formatElapsed(elapsed);
    }

    function appendMemoToList(filename) {
      var li = document.createElement("li");
      li.className = "editor__voice-item";
      li.dataset.filename = filename;

      var audio = document.createElement("audio");
      audio.controls = true;
      audio.preload = "none";
      audio.src = "/story/" + storyId + "/media/" + filename;
      li.appendChild(audio);

      var deleteBtn = document.createElement("button");
      deleteBtn.type = "button";
      deleteBtn.className = "btn editor__voice-delete";
      deleteBtn.dataset.filename = filename;
      deleteBtn.textContent = "Delete";
      li.appendChild(deleteBtn);

      voiceListEl.appendChild(li);
    }

    function uploadMemo(blob) {
      return ensureStoryId().then(function (id) {
        var formData = new FormData();
        formData.append("file", blob, "memo." + recordExt);
        return fetch("/api/stories/" + id + "/memos", {
          method: "POST",
          body: formData,
        }).then(handleJsonResponse);
      });
    }

    function resetRecordUI() {
      recordBtn.hidden = false;
      pauseBtn.hidden = true;
      pauseBtn.textContent = "Pause";
      stopBtn.hidden = true;
      timerEl.hidden = true;
      timerEl.textContent = "00:00";
    }

    if (!supportsRecording()) {
      recordBtn.hidden = true;
    } else {
      recordBtn.addEventListener("click", function () {
        showVoiceMessage("");
        navigator.mediaDevices
          .getUserMedia({ audio: true })
          .then(function (stream) {
            var picked = pickMimeType();
            recordMimeType = picked.mimeType;
            recordExt = picked.ext;
            recordedChunks = [];
            elapsedBeforePause = 0;
            try {
              mediaRecorder = new MediaRecorder(stream, { mimeType: recordMimeType });
            } catch (e) {
              mediaRecorder = new MediaRecorder(stream);
            }
            mediaRecorder.addEventListener("dataavailable", function (event) {
              if (event.data && event.data.size > 0) recordedChunks.push(event.data);
            });
            mediaRecorder.addEventListener("stop", function () {
              stream.getTracks().forEach(function (track) {
                track.stop();
              });
              clearInterval(timerInterval);
              timerInterval = null;
              var blob = new Blob(recordedChunks, { type: recordMimeType });
              recordBtn.disabled = true;
              uploadMemo(blob)
                .then(function (data) {
                  appendMemoToList(data.filename);
                  resetRecordUI();
                  recordBtn.disabled = false;
                })
                .catch(function (error) {
                  showVoiceMessage((error && error.message) || "Could not save the recording.");
                  resetRecordUI();
                  recordBtn.disabled = false;
                });
            });
            mediaRecorder.start(1000);
            recordStartTime = Date.now();
            recordBtn.hidden = true;
            pauseBtn.hidden = false;
            stopBtn.hidden = false;
            timerEl.hidden = false;
            updateTimer();
            timerInterval = setInterval(updateTimer, 1000);
          })
          .catch(function () {
            showVoiceMessage("Microphone access was denied.");
          });
      });

      pauseBtn.addEventListener("click", function () {
        if (!mediaRecorder) return;
        if (mediaRecorder.state === "recording") {
          mediaRecorder.pause();
          elapsedBeforePause += Date.now() - recordStartTime;
          recordStartTime = null;
          pauseBtn.textContent = "Resume";
        } else if (mediaRecorder.state === "paused") {
          mediaRecorder.resume();
          recordStartTime = Date.now();
          pauseBtn.textContent = "Pause";
        }
      });

      stopBtn.addEventListener("click", function () {
        if (mediaRecorder && mediaRecorder.state !== "inactive") {
          mediaRecorder.stop();
        }
      });
    }

    voiceListEl.addEventListener("click", function (event) {
      var btn = event.target.closest(".editor__voice-delete");
      if (!btn) return;
      if (!window.confirm("Delete this recording?")) return;
      var filename = btn.dataset.filename;
      fetch("/api/stories/" + storyId + "/memos/" + encodeURIComponent(filename), {
        method: "DELETE",
      }).then(function (response) {
        if (response.ok) {
          btn.closest(".editor__voice-item").remove();
        } else {
          showVoiceMessage("Could not delete the recording.");
        }
      });
    });
  }

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
    var storyDate = dateInput ? dateInput.value : "";
    var payload = {
      title: title,
      date: storyDate,
      markdown: "",
      author: authorChipsController.getSelected() || "",
      draft: isDraft(),
      unlock: unlockValue(),
      archived: isArchived(),
    };
    if (relationInput) payload.relation = relationInput.value.trim();
    addFamilyFields(payload);
    return fetch(createUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    })
      .then(handleJsonResponse)
      .then(function (data) {
        storyId = data.id;
        form.dataset.storyId = storyId;
        history.replaceState(null, "", fillUrlTemplate(editUrlTemplate, storyId));
        return storyId;
      });
  }

  function uploadImage(file) {
    return ensureStoryId().then(function (id) {
      var formData = new FormData();
      formData.append("file", file);
      return fetch(fillUrlTemplate(imageUrlTemplate, id), {
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
              showSaveMessage(error.message);
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
          showSaveMessage(error.message);
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
  if (dateInput) dateInput.addEventListener("input", markDirty);
  if (relationInput) relationInput.addEventListener("input", markDirty);

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
    var payload = {
      title: titleInput.value,
      date: dateInput ? dateInput.value : "",
      markdown: editor.getMarkdown(),
      author: authorChipsController.getSelected() || "",
      draft: isDraft(),
      unlock: unlockValue(),
      archived: isArchived(),
      savedAt: Date.now(),
    };
    if (relationInput) payload.relation = relationInput.value;
    addFamilyFields(payload);
    return payload;
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
    if (dateInput && draftData.date) dateInput.value = draftData.date;
    editor.setMarkdown(draftData.markdown || "");
    if (unlockInput) unlockInput.value = draftData.unlock || "";
    if (draftToggle) draftToggle.setAttribute("aria-pressed", draftData.draft ? "true" : "false");
    if (archiveToggle) {
      archiveToggle.setAttribute("aria-pressed", draftData.archived ? "true" : "false");
    }
    if (relationInput) relationInput.value = draftData.relation || "";
    authorChipsController.setSelected(draftData.author || null);
    if (familyRoot) {
      parentsPicker.setSelected(draftData.parents || []);
      partnersPicker.setSelected(draftData.partners || []);
      friendOfPicker.setSelected(draftData.friend_of || []);
      setGender(draftData.gender || "");
    }
    if (photoFocusRoot && draftData.photo_focus) {
      var restoredFocus = draftData.photo_focus.split(" ");
      setPhotoFocus(parseFloat(restoredFocus[0]) || 50, parseFloat(restoredFocus[1]) || 50);
    }
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
    if (saveButton.disabled) return;
    var title = titleInput.value.trim();
    var storyDate = dateInput ? dateInput.value : "";
    if (!title) {
      titleInput.focus();
      return;
    }
    showSaveMessage("");
    saveButton.disabled = true;
    saveButton.textContent = "Saving…";
    if (saveSpinner) saveSpinner.hidden = false;
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
    if (relationInput) payload.relation = relationInput.value.trim();
    addFamilyFields(payload);

    // A brand-new story is created with its real content in one request
    // rather than going through ensureStoryId()'s empty-body POST followed
    // by an immediate PUT — avoids a redundant write (and, now that saves
    // are versioned, a spurious near-empty entry in that story's history).
    var request = storyId
      ? fetch(fillUrlTemplate(updateUrlTemplate, storyId), {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        })
      : fetch(createUrl, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });

    request
      .then(handleJsonResponse)
      .then(function (data) {
        dirty = false;
        clearAutosave();
        window.location.href = fillUrlTemplate(redirectTemplate, data.id);
      })
      .catch(function (error) {
        saveButton.disabled = false;
        saveButton.textContent = saveButtonDefaultLabel;
        if (saveSpinner) saveSpinner.hidden = true;
        showSaveMessage(
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
