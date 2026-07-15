(function () {
  var container = document.getElementById("FamilyChart");
  if (!container || !window.f3 || !window.TreeLogic || !window.SafeStorage) return;

  var viewsNav = document.getElementById("tree-views");
  var treeUrl = container.dataset.treeUrl;
  var fallbackAvatar = container.dataset.fallbackAvatar;
  var STORAGE_KEY = "storybook-tree-view";

  function escapeHtml(value) {
    var div = document.createElement("div");
    div.textContent = value || "";
    // The textContent->innerHTML round-trip escapes &, <, > but never a
    // literal quote, which isn't safe inside the double-quoted title=/
    // href= attributes this is used for below.
    return div.innerHTML.replace(/"/g, "&quot;").replace(/'/g, "&#39;");
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
        var saved = window.SafeStorage.getJSON(STORAGE_KEY);
        if (!saved || saved.focusId !== focusId || !Array.isArray(saved.chain)) return;
        if (!saved.chain.length) return;
        // Every entry must still be a real link in the CURRENT parent
        // graph, not just a person who still exists — a parent link
        // edited between visits falls back to Direct line entirely
        // rather than restoring a truncated, possibly-disconnected chain.
        if (!window.TreeLogic.isValidChain(saved.chain, focusId, parentsOf, exists)) return;
        chain = saved.chain.slice();
        viewLevel = chain.length;
        viewRootId = chain[chain.length - 1];
      }

      function saveView() {
        window.SafeStorage.setJSON(STORAGE_KEY, { focusId: focusId, chain: chain });
      }

      function makeButton(label, pressed, onClick) {
        var btn = document.createElement("button");
        btn.type = "button";
        btn.className = "btn tree__view-btn";
        btn.textContent = label;
        btn.setAttribute("aria-pressed", pressed ? "true" : "false");
        btn.addEventListener("click", onClick);
        return btn;
      }

      function renderToolbar() {
        if (!viewsNav) return;
        // Rebuilding replaces every button node below, which would drop
        // keyboard focus out of the toolbar entirely on every click —
        // remember whether focus was inside it so it can be restored to
        // whichever button ends up pressed.
        var hadFocusInside = viewsNav.contains(document.activeElement);
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
        for (var lv = 1; lv <= deepest; lv++) {
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
                  // The chosen couple can be on an entirely different
                  // lineage than the one already in view (paternal vs.
                  // maternal), so the whole chain has to be rebuilt from
                  // focusId — patching just the deepest entry can leave
                  // earlier entries pointing at an unrelated branch.
                  var path = window.TreeLogic.ancestorPath(focusId, group[0], parentsOf, exists);
                  if (path) setView(path);
                })
              );
            });
            viewsNav.appendChild(branches);
          }
        }

        if (hadFocusInside) {
          var toFocus = viewsNav.querySelector('[aria-pressed="true"]');
          if (toFocus) toFocus.focus();
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
      // on the container stays put while the chart moves), at 1024 chart
      // units per tile (1:1 pixels at zoom 1). Only the active theme's
      // tile is ever inserted — a hidden `display:none` <image> still
      // gets fetched and decoded by the browser, so keeping both in the
      // DOM and toggling CSS would silently double the image payload on
      // every /tree view.
      function mapTileTheme() {
        var attr = document.documentElement.getAttribute("data-theme");
        if (attr === "light" || attr === "manuscript") return "light";
        if (attr === "dark") return "dark";
        return window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
      }

      function mapTileHref(theme) {
        return theme === "light" ? container.dataset.mapTile : container.dataset.mapTileDark;
      }

      function installMapBackground() {
        var svg = container.querySelector("svg.main_svg");
        var view = svg && svg.querySelector("g.view");
        if (svg && view && svg.querySelector("#tree-map-grid")) return;
        if (!svg || !view) {
          if (window.console && window.console.warn) {
            window.console.warn(
              "Storybook: couldn't find the family-chart SVG structure to attach the map " +
                "background to (svg.main_svg / g.view) — the vendored bundle may have changed."
            );
          }
          return;
        }
        svg.insertAdjacentHTML(
          "afterbegin",
          '<defs><pattern id="tree-map-grid" patternUnits="userSpaceOnUse" width="1024" height="1024">' +
            '<image id="tree-map-img" aria-hidden="true" href="' +
            escapeHtml(mapTileHref(mapTileTheme())) +
            '" width="1024" height="1024"/>' +
            "</pattern></defs>"
        );
        var rect = document.createElementNS("http://www.w3.org/2000/svg", "rect");
        rect.setAttribute("class", "tree-map-bg");
        rect.setAttribute("aria-hidden", "true");
        rect.setAttribute("x", "-50000");
        rect.setAttribute("y", "-50000");
        rect.setAttribute("width", "100000");
        rect.setAttribute("height", "100000");
        rect.setAttribute("fill", "url(#tree-map-grid)");
        view.insertBefore(rect, view.firstChild);

        function refreshMapTile() {
          var img = svg.querySelector("#tree-map-img");
          if (img) img.setAttribute("href", mapTileHref(mapTileTheme()));
        }
        new window.MutationObserver(refreshMapTile).observe(document.documentElement, {
          attributes: true,
          attributeFilter: ["data-theme"],
        });
        var mq = window.matchMedia && window.matchMedia("(prefers-color-scheme: light)");
        if (mq && mq.addEventListener) mq.addEventListener("change", refreshMapTile);
      }

      // Recenter: family-chart auto-fits the tree to the viewport on every
      // updateTree() call, via a d3-zoom transform applied to #f3Canvas.
      // We snapshot that transform each time it settles and offer it back
      // so a reader who has panned/zoomed off into the leather can get
      // back without a page reload. The vendored bundle's own fit
      // transition adds a 100ms pre-delay before the setTransitionTime
      // (600ms) duration even starts, so it actually settles ~700ms after
      // updateTree() — capture a little past that so Recenter never
      // restores a still-interpolating transform.
      var lastFitTransform = null;
      var fitCaptureTimer = null;
      var FIT_SETTLE_MS = 720;

      function captureFitTransform() {
        var canvas = container.querySelector("#f3Canvas");
        if (!canvas || !window.d3) return;
        if (fitCaptureTimer) window.clearTimeout(fitCaptureTimer);
        fitCaptureTimer = window.setTimeout(function () {
          lastFitTransform = window.d3.zoomTransform(canvas);
        }, FIT_SETTLE_MS);
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
        btn.className = "btn tree__recenter-btn";
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
