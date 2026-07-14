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

  // --- Dedicated photo panel: upload -> pan/zoom crop -> sepia tone ----------
  // (people only). The crop is rasterized client-side and uploaded as the
  // final image — there is no separate stored focus point.
  var photoPreview = document.getElementById("editor-photo-preview");
  var photoPlaceholder = document.getElementById("editor-photo-placeholder");
  var photoImg = document.getElementById("editor-photo-img");
  var photoFileInput = document.getElementById("editor-photo-file");
  var photoUploadLabel = document.getElementById("editor-photo-upload-label");
  var photoMessageEl = document.getElementById("editor-photo-message");
  var photoSepiaGroup = document.getElementById("editor-photo-sepia-group");
  var photoSepiaRange = document.getElementById("editor-photo-sepia-range");
  var photoSepiaNumber = document.getElementById("editor-photo-sepia-number");
  var photoUrlTemplate = form.dataset.photoUrlTemplate || "";
  var mediaUrlTemplate = form.dataset.mediaUrlTemplate || "";

  var hasPhoto = !!(photoPreview && !photoPreview.hidden);

  function showPhotoMessage(text) {
    if (!photoMessageEl) return;
    photoMessageEl.textContent = text || "";
    photoMessageEl.hidden = !text;
  }

  function setPhotoSepia(value) {
    value = Math.max(0, Math.min(100, Math.round(value)));
    if (photoImg) photoImg.style.setProperty("--photo-sepia", value + "%");
    if (photoSepiaRange) photoSepiaRange.value = value;
    if (photoSepiaNumber) photoSepiaNumber.value = value;
  }

  if (photoSepiaRange) {
    photoSepiaRange.addEventListener("input", function () {
      setPhotoSepia(photoSepiaRange.value);
      markDirty();
    });
  }

  if (photoSepiaNumber) {
    photoSepiaNumber.addEventListener("input", function () {
      if (photoSepiaNumber.value === "") return;
      setPhotoSepia(photoSepiaNumber.value);
      markDirty();
    });
  }

  function revealPhoto(mediaUrl) {
    hasPhoto = true;
    if (photoPlaceholder) photoPlaceholder.hidden = true;
    if (photoPreview) photoPreview.hidden = false;
    if (photoImg) photoImg.src = mediaUrl;
    if (photoSepiaGroup) photoSepiaGroup.hidden = false;
    if (photoUploadLabel) photoUploadLabel.textContent = "Change photo";
    setPhotoSepia(30);
  }

  // --- Pan/zoom crop overlay -------------------------------------------------
  var cropperRoot = document.getElementById("editor-photo-cropper");
  var cropperStage = document.getElementById("editor-photo-cropper-stage");
  var cropperImg = document.getElementById("editor-photo-cropper-img");
  var zoomRange = document.getElementById("editor-photo-zoom-range");
  var zoomOutBtn = document.getElementById("editor-photo-zoom-out");
  var zoomInBtn = document.getElementById("editor-photo-zoom-in");
  var cropCancelBtn = document.getElementById("editor-photo-crop-cancel");
  var cropConfirmBtn = document.getElementById("editor-photo-crop-confirm");

  var MAX_ZOOM_MULT = 3; // how far past "fits the frame" the slider can zoom
  var OUTPUT_SIZE = 900; // final square crop resolution, in px

  var cropObjectUrl = null;
  var stageSize = 0;
  var naturalW = 0;
  var naturalH = 0;
  var fitScale = 1;
  var zoomPct = 0;
  var panX = 0;
  var panY = 0;
  var dragging = false;
  var dragStartX = 0;
  var dragStartY = 0;
  var panStartX = 0;
  var panStartY = 0;
  var activePointers = {};
  var pinchStartDist = null;
  var pinchStartZoom = 0;

  function currentScale() {
    return fitScale * (1 + (MAX_ZOOM_MULT - 1) * (zoomPct / 100));
  }

  function clampPan() {
    var scale = currentScale();
    var dispW = naturalW * scale;
    var dispH = naturalH * scale;
    var maxX = Math.max(0, (dispW - stageSize) / 2);
    var maxY = Math.max(0, (dispH - stageSize) / 2);
    panX = Math.max(-maxX, Math.min(maxX, panX));
    panY = Math.max(-maxY, Math.min(maxY, panY));
  }

  function updateCropTransform() {
    var scale = currentScale();
    var dispW = naturalW * scale;
    var dispH = naturalH * scale;
    cropperImg.style.width = dispW + "px";
    cropperImg.style.height = dispH + "px";
    cropperImg.style.left = (stageSize / 2 - dispW / 2 + panX) + "px";
    cropperImg.style.top = (stageSize / 2 - dispH / 2 + panY) + "px";
  }

  function setZoom(value) {
    zoomPct = Math.max(0, Math.min(100, value));
    if (zoomRange) zoomRange.value = zoomPct;
    clampPan();
    updateCropTransform();
  }

  if (zoomRange) {
    zoomRange.addEventListener("input", function () {
      setZoom(parseFloat(zoomRange.value));
    });
  }
  if (zoomOutBtn) {
    zoomOutBtn.addEventListener("click", function () {
      setZoom(zoomPct - 10);
    });
  }
  if (zoomInBtn) {
    zoomInBtn.addEventListener("click", function () {
      setZoom(zoomPct + 10);
    });
  }

  function pointerDistance(a, b) {
    var dx = a.x - b.x;
    var dy = a.y - b.y;
    return Math.sqrt(dx * dx + dy * dy);
  }

  function beginDragFrom(x, y) {
    dragging = true;
    dragStartX = x;
    dragStartY = y;
    panStartX = panX;
    panStartY = panY;
  }

  if (cropperStage) {
    cropperStage.addEventListener("pointerdown", function (event) {
      activePointers[event.pointerId] = { x: event.clientX, y: event.clientY };
      try {
        cropperStage.setPointerCapture(event.pointerId);
      } catch (e) {
        // Capture is a robustness nicety (keeps the drag tracking even if
        // the finger slides outside the stage); its absence shouldn't stop
        // the drag from working.
      }
      var ids = Object.keys(activePointers);
      if (ids.length === 1) {
        beginDragFrom(event.clientX, event.clientY);
      } else if (ids.length === 2) {
        dragging = false;
        var pts = ids.map(function (id) { return activePointers[id]; });
        pinchStartDist = pointerDistance(pts[0], pts[1]);
        pinchStartZoom = zoomPct;
      }
      event.preventDefault();
    });

    cropperStage.addEventListener("pointermove", function (event) {
      if (!(event.pointerId in activePointers)) return;
      activePointers[event.pointerId] = { x: event.clientX, y: event.clientY };
      var ids = Object.keys(activePointers);
      if (ids.length === 2 && pinchStartDist) {
        var pts = ids.map(function (id) { return activePointers[id]; });
        var dist = pointerDistance(pts[0], pts[1]);
        var ratio = dist / pinchStartDist;
        setZoom(pinchStartZoom + (ratio - 1) * 100);
      } else if (dragging) {
        panX = panStartX + (event.clientX - dragStartX);
        panY = panStartY + (event.clientY - dragStartY);
        clampPan();
        updateCropTransform();
      }
    });

    function endPointer(event) {
      delete activePointers[event.pointerId];
      var ids = Object.keys(activePointers);
      if (ids.length < 2) pinchStartDist = null;
      if (ids.length === 1) {
        var pt = activePointers[ids[0]];
        beginDragFrom(pt.x, pt.y);
      } else if (ids.length === 0) {
        dragging = false;
      }
    }
    cropperStage.addEventListener("pointerup", endPointer);
    cropperStage.addEventListener("pointercancel", endPointer);
  }

  function isHeicFile(file) {
    var type = (file.type || "").toLowerCase();
    if (type === "image/heic" || type === "image/heif") return true;
    return /\.(heic|heif)$/i.test(file.name || "");
  }

  function openCropperFromUrl(url) {
    cropperImg.onload = function () {
      stageSize = cropperStage.clientWidth;
      naturalW = cropperImg.naturalWidth;
      naturalH = cropperImg.naturalHeight;
      panX = 0;
      panY = 0;
      if (!naturalW || !naturalH || !stageSize) {
        showPhotoMessage("Could not read that photo. Try a different one.");
        closeCropper();
        return;
      }
      fitScale = Math.max(stageSize / naturalW, stageSize / naturalH);
      setZoom(0);
    };
    cropperImg.onerror = function () {
      showPhotoMessage("Could not read that photo. Try a different one.");
      closeCropper();
    };
    cropperImg.src = url;
    if (photoPreview) photoPreview.hidden = true;
    if (photoPlaceholder) photoPlaceholder.hidden = true;
    if (cropperRoot) cropperRoot.hidden = false;
  }

  function openCropper(file) {
    if (cropObjectUrl) {
      URL.revokeObjectURL(cropObjectUrl);
      cropObjectUrl = null;
    }
    if (isHeicFile(file)) {
      // Browsers (Chrome on Android included) cannot decode HEIC/HEIF in an
      // <img> or canvas at all, so a HEIC photo can't be cropped in the
      // browser directly. Route it through the server's existing
      // Pillow/pillow-heif conversion (the same one F11 body-image uploads
      // already use) first, then crop the resulting JPEG.
      showPhotoMessage("Converting photo…");
      ensureStoryId()
        .then(function (id) {
          var formData = new FormData();
          formData.append("file", file);
          return fetch(fillUrlTemplate(imageUrlTemplate, id), {
            method: "POST",
            body: formData,
          }).then(handleJsonResponse);
        })
        .then(function (data) {
          showPhotoMessage("");
          openCropperFromUrl(
            mediaUrlTemplate.replace("__ID__", storyId).replace("__FILENAME__", data.filename)
          );
        })
        .catch(function (error) {
          showPhotoMessage(error.message || "Could not read that photo.");
        });
      return;
    }
    cropObjectUrl = URL.createObjectURL(file);
    openCropperFromUrl(cropObjectUrl);
  }

  function closeCropper() {
    if (cropperRoot) cropperRoot.hidden = true;
    if (photoPreview) photoPreview.hidden = !hasPhoto;
    if (photoPlaceholder) photoPlaceholder.hidden = hasPhoto;
    if (cropObjectUrl) {
      URL.revokeObjectURL(cropObjectUrl);
      cropObjectUrl = null;
    }
  }

  if (cropCancelBtn) {
    cropCancelBtn.addEventListener("click", function () {
      if (photoFileInput) photoFileInput.value = "";
      closeCropper();
    });
  }

  function rasterizeCrop() {
    return new Promise(function (resolve, reject) {
      var canvas = document.createElement("canvas");
      canvas.width = OUTPUT_SIZE;
      canvas.height = OUTPUT_SIZE;
      var ctx = canvas.getContext("2d");
      var k = OUTPUT_SIZE / stageSize;
      var scale = currentScale();
      var dispW = naturalW * scale;
      var dispH = naturalH * scale;
      var left = stageSize / 2 - dispW / 2 + panX;
      var top = stageSize / 2 - dispH / 2 + panY;
      try {
        ctx.drawImage(cropperImg, left * k, top * k, dispW * k, dispH * k);
      } catch (e) {
        reject(new Error("Could not process that photo. Try a different one."));
        return;
      }
      canvas.toBlob(function (blob) {
        if (!blob) {
          reject(new Error("Could not process that photo. Try a different one."));
          return;
        }
        resolve(blob);
      }, "image/jpeg", 0.92);
    });
  }

  if (cropConfirmBtn) {
    cropConfirmBtn.addEventListener("click", function () {
      showPhotoMessage("");
      cropConfirmBtn.disabled = true;
      rasterizeCrop()
        .then(function (blob) {
          return ensureStoryId().then(function (id) {
            var formData = new FormData();
            formData.append("file", blob, "photo.jpg");
            return fetch(fillUrlTemplate(photoUrlTemplate, id), {
              method: "POST",
              body: formData,
            }).then(handleJsonResponse);
          });
        })
        .then(function (data) {
          var mediaUrl = mediaUrlTemplate
            .replace("__ID__", storyId)
            .replace("__FILENAME__", data.filename);
          revealPhoto(mediaUrl);
          if (photoFileInput) photoFileInput.value = "";
          closeCropper();
          markDirty();
        })
        .catch(function (error) {
          showPhotoMessage(error.message || "Could not upload that photo.");
        })
        .then(function () {
          cropConfirmBtn.disabled = false;
        });
    });
  }

  if (photoFileInput && photoUrlTemplate) {
    photoFileInput.addEventListener("change", function () {
      var file = photoFileInput.files[0];
      if (!file) return;
      showPhotoMessage("");
      openCropper(file);
    });
  }

  function addFamilyFields(payload) {
    if (familyRoot) {
      payload.parents = parentsPicker.getSelected();
      payload.partners = partnersPicker.getSelected();
      payload.friend_of = friendOfPicker.getSelected();
      payload.gender = getGender();
    }
    if (hasPhoto) {
      payload.photo_sepia = photoSepiaRange ? parseInt(photoSepiaRange.value, 10) : 30;
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
    if (hasPhoto && draftData.photo_sepia !== undefined) {
      setPhotoSepia(draftData.photo_sepia);
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
