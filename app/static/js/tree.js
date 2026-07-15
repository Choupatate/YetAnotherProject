(function () {
  var container = document.getElementById("FamilyChart");
  if (!container || !window.f3 || !window.TreeLogic) return;

  var viewsNav = document.getElementById("tree-views");
  var treeUrl = container.dataset.treeUrl;
  var fallbackAvatar = container.dataset.fallbackAvatar;
  var STORAGE_KEY = "storybook-tree-view";

  function escapeHtml(value) {
    var div = document.createElement("div");
    div.textContent = value || "";
    return div.innerHTML;
  }

  function toGender(value) {
    if (value === "m") return "M";
    if (value === "f") return "F";
    return undefined; // never assume a gender when it isn't known
  }

  function toDatum(person) {
    return {
      id: person.id,
      data: {
        label: person.name,
        avatar: person.photo || fallbackAvatar,
        avatarIsPhoto: !!person.photo,
        avatarSepia: person.photo_sepia,
        gender: toGender(person.gender),
        kinship: person.kinship || null,
      },
      rels: {
        parents: (person.rels && person.rels.parents) || [],
        spouses: (person.rels && person.rels.partners) || [],
        children: (person.rels && person.rels.children) || [],
      },
    };
  }

  fetch(treeUrl)
    .then(function (response) {
      return response.json();
    })
    .then(function (payload) {
      // Only people linked into the blood/partner graph become chart
      // cards; friends and fully unlinked people live in the plain HTML
      // "Friends & others" list rendered server-side below the chart.
      var familyPeople = payload.people.filter(function (p) {
        return !!p.rels;
      });
      if (!familyPeople.length) return;

      var urlById = {};
      var nameById = {};
      var parentsOf = {};
      var partnersOf = {};
      familyPeople.forEach(function (p) {
        urlById[p.id] = p.url;
        nameById[p.id] = p.name;
        parentsOf[p.id] = p.rels.parents || [];
        partnersOf[p.id] = p.rels.partners || [];
      });
      var exists = function (id) {
        return urlById.hasOwnProperty(id);
      };

      // The person the tree is ABOUT. Views re-root the chart layout at
      // one of their ancestors (the hourglass layout can only show
      // aunts/uncles/cousins as an ancestor's descendants), but the focus
      // stays put; the mini-tree control moves it.
      var focusId =
        payload.anchor && urlById.hasOwnProperty(payload.anchor)
          ? payload.anchor
          : familyPeople[0].id;

      // `chain[i]` is the ancestor selected i+1 generations above focus.
      // Going deeper extends whichever branch is already chosen instead
      // of jumping to an arbitrary ancestor at the new depth; a branch
      // chip overwrites the chain from that level down.
      var chain = [];
      var viewLevel = 0;
      var viewRootId = focusId;

      function restoreSavedView() {
        var raw;
        try {
          raw = window.localStorage.getItem(STORAGE_KEY);
        } catch (e) {
          return;
        }
        if (!raw) return;
        var saved;
        try {
          saved = JSON.parse(raw);
        } catch (e) {
          return;
        }
        if (!saved || saved.focusId !== focusId || !Array.isArray(saved.chain)) return;
        var restored = [];
        for (var i = 0; i < saved.chain.length; i++) {
          if (!exists(saved.chain[i])) break;
          restored.push(saved.chain[i]);
        }
        if (!restored.length) return;
        chain = restored;
        viewLevel = chain.length;
        viewRootId = chain[chain.length - 1];
      }

      function saveView() {
        try {
          window.localStorage.setItem(
            STORAGE_KEY,
            JSON.stringify({ focusId: focusId, chain: chain })
          );
        } catch (e) {
          // localStorage unavailable (private mode, quota) — view choice
          // just won't be remembered next visit; nothing else depends on it.
        }
      }

      function makeButton(label, pressed, onClick) {
        var btn = document.createElement("button");
        btn.type = "button";
        btn.className = "tree__view-btn";
        btn.textContent = label;
        btn.setAttribute("aria-pressed", pressed ? "true" : "false");
        btn.addEventListener("click", onClick);
        return btn;
      }

      function renderToolbar() {
        if (!viewsNav) return;
        var levels = window.TreeLogic.ancestorLevels(focusId, parentsOf, exists);
        viewsNav.innerHTML = "";
        if (!levels.length) {
          viewsNav.hidden = true;
          return;
        }
        viewsNav.hidden = false;

        var row = document.createElement("div");
        row.className = "tree__views-row";
        row.appendChild(
          makeButton("Direct line", viewLevel === 0, function () {
            goToLevel(0);
          })
        );
        var deepest = levels.length;
        for (var lv = deepest === 1 ? 1 : 2; lv <= deepest; lv++) {
          (function (lv) {
            row.appendChild(
              makeButton(
                window.TreeLogic.levelLabel(lv, deepest),
                viewLevel === lv,
                function () {
                  goToLevel(lv);
                }
              )
            );
          })(lv);
        }
        viewsNav.appendChild(row);

        if (viewLevel > 0) {
          var groups = window.TreeLogic.coupleGroups(levels[viewLevel - 1] || [], partnersOf);
          if (groups.length > 1) {
            var branches = document.createElement("div");
            branches.className = "tree__views-branches";
            groups.forEach(function (group) {
              var label =
                "via " +
                group
                  .map(function (id) {
                    return nameById[id];
                  })
                  .join(" & ");
              var pressed = group.indexOf(viewRootId) !== -1;
              branches.appendChild(
                makeButton(label, pressed, function () {
                  setView(chain.slice(0, viewLevel - 1).concat([group[0]]));
                })
              );
            });
            viewsNav.appendChild(branches);
          }
        }
      }

      // Level-button clicks: extend/truncate the chain, preferring the
      // branch already selected rather than an arbitrary ancestor at that
      // depth. `viewLevel` ends up at whatever depth was actually reached,
      // so "Whole family" on a branch that runs out of paper trail early
      // just settles at that branch's deepest recorded ancestor instead
      // of silently jumping to an unrelated one.
      function goToLevel(lv) {
        setView(window.TreeLogic.chainToLevel(chain, lv, focusId, parentsOf, exists));
      }

      // The chain is the single source of truth for both the current root
      // and the current depth — level and rootId are always derived from
      // it, never reconstructed separately, so they can't drift apart.
      function setView(newChain) {
        chain = newChain;
        viewLevel = chain.length;
        viewRootId = chain.length ? chain[chain.length - 1] : focusId;
        chart.updateMainId(viewRootId);
        chart.updateTree({});
        renderToolbar();
        saveView();
        captureFitTransform();
      }

      function cardInnerHtml(node) {
        var d = node.data.data;
        // In rooted views the gold brand follows the new root card; keep
        // the focus person findable with their own thin gold ring.
        var isFocus = viewLevel > 0 && node.data.id === focusId;
        var innerClass = "card-inner" + (isFocus ? " card-inner--focus" : "");
        var avatarClass = "f3-card-avatar" + (d.avatarIsPhoto ? " f3-card-avatar--photo" : "");
        var avatarStyle = d.avatarIsPhoto ? ' style="--photo-sepia: ' + d.avatarSepia + '%;"' : "";
        var kinshipHtml = d.kinship
          ? '<div class="f3-card-kinship" title="' + escapeHtml(d.kinship) + '">' + escapeHtml(d.kinship) + "</div>"
          : "";
        return (
          '<div class="' + innerClass + '">' +
          '<img class="' + avatarClass + '" src="' + escapeHtml(d.avatar) + '" alt=""' + avatarStyle + '>' +
          '<div class="f3-card-text">' +
          '<div class="f3-card-name">' + escapeHtml(d.label) + "</div>" +
          kinshipHtml +
          "</div>" +
          "</div>"
        );
      }

      function onCardClick(event, node) {
        // The library's default click behavior re-roots the tree; we keep
        // that on the mini-tree corner control only — it moves the focus
        // and drops back to the direct-line view — and make the rest of
        // the card navigate to the person's page instead.
        if (event.target.closest(".mini-tree")) {
          focusId = node.data.id;
          setView([]);
          return;
        }
        window.location.href = urlById[node.data.id];
      }

      // The survey map lives INSIDE the chart's pan/zoom group so it
      // translates and scales in lockstep with the tree (a CSS background
      // on the container stays put while the chart moves). The pattern
      // holds one seamless raster tile per theme — CSS displays the right
      // one — at 1024 chart units per tile (1:1 pixels at zoom 1).
      function installMapBackground() {
        var svg = container.querySelector("svg.main_svg");
        var view = svg && svg.querySelector("g.view");
        if (!view || svg.querySelector("#tree-map-grid")) return;
        svg.insertAdjacentHTML(
          "afterbegin",
          '<defs><pattern id="tree-map-grid" patternUnits="userSpaceOnUse" width="1024" height="1024">' +
            '<image class="tree-map-img tree-map-img--dark" href="' +
            escapeHtml(container.dataset.mapTileDark) +
            '" width="1024" height="1024"/>' +
            '<image class="tree-map-img tree-map-img--light" href="' +
            escapeHtml(container.dataset.mapTile) +
            '" width="1024" height="1024"/>' +
            "</pattern></defs>"
        );
        var rect = document.createElementNS("http://www.w3.org/2000/svg", "rect");
        rect.setAttribute("class", "tree-map-bg");
        rect.setAttribute("x", "-50000");
        rect.setAttribute("y", "-50000");
        rect.setAttribute("width", "100000");
        rect.setAttribute("height", "100000");
        rect.setAttribute("fill", "url(#tree-map-grid)");
        view.insertBefore(rect, view.firstChild);
      }

      // Recenter: family-chart auto-fits the tree to the viewport on every
      // updateTree() call, via a d3-zoom transform applied to #f3Canvas.
      // We snapshot that transform each time it settles (setTransitionTime
      // is 600ms) and offer it back so a reader who has panned/zoomed off
      // into the leather can get back without a page reload.
      var lastFitTransform = null;
      var fitCaptureTimer = null;

      function captureFitTransform() {
        var canvas = container.querySelector("#f3Canvas");
        if (!canvas || !window.d3) return;
        if (fitCaptureTimer) window.clearTimeout(fitCaptureTimer);
        fitCaptureTimer = window.setTimeout(function () {
          lastFitTransform = window.d3.zoomTransform(canvas);
        }, 650);
      }

      function recenter() {
        var canvas = container.querySelector("#f3Canvas");
        if (!canvas || !canvas.__zoomObj || !lastFitTransform || !window.d3) return;
        window.d3.select(canvas).call(canvas.__zoomObj.transform, lastFitTransform);
      }

      function installRecenterButton() {
        if (container.querySelector(".tree__recenter-btn")) return;
        var btn = document.createElement("button");
        btn.type = "button";
        btn.className = "tree__recenter-btn";
        btn.textContent = "Recenter";
        btn.setAttribute("aria-label", "Recenter the family tree");
        btn.addEventListener("click", recenter);
        container.appendChild(btn);
      }

      restoreSavedView();

      var chart = window.f3
        .createChart("#FamilyChart", familyPeople.map(toDatum))
        .setTransitionTime(600)
        .setOrientationVertical()
        .setSingleParentEmptyCard(false);

      chart
        .setCardHtml()
        .setMiniTree(true)
        .setCardInnerHtmlCreator(cardInnerHtml)
        .setOnCardClick(onCardClick);

      chart.updateMainId(viewRootId);
      chart.updateTree({ initial: true });
      renderToolbar();
      installMapBackground();
      installRecenterButton();
      captureFitTransform();
    })
    .catch(function () {
      container.textContent = "Could not load the family tree.";
    });
})();
