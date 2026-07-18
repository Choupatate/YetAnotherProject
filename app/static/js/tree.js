(function () {
  var container = document.getElementById("FamilyChart");
  if (!container || !window.f3 || !window.TreeLogic || !window.SafeStorage) return;

  var viewsNav = document.getElementById("tree-views");
  var treeUrl = container.dataset.treeUrl;
  var fallbackAvatar = container.dataset.fallbackAvatar;
  var STORAGE_KEY = "storybook-tree-view";
  var FIT_SETTLE_MS = 720;

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

      // Synthetic id for the "Everyone" merged view's hidden root card
      // (see renderChartArea). Can't collide with a real person's id:
      // storage.slugify() (server-side) strips every non a-z0-9
      // character, including underscores, from every slug it produces.
      var EVERYONE_ROOT_ID = "__everyone__";

      // The person the tree is ABOUT. Level 0 ("Direct line") roots the
      // chart directly at focus, which already shows their whole pedigree
      // (every ancestor, both sides, recursing naturally — a person has
      // at most two parents). Deeper levels exist to reveal lateral
      // relatives — aunts/uncles/cousins — which only appear as an
      // ancestor's OWN descendants, a subtree disjoint from any sibling
      // couple's. The mini-tree control moves focus; the level buttons
      // never do.
      var focusId =
        payload.anchor && urlById.hasOwnProperty(payload.anchor)
          ? payload.anchor
          : familyPeople[0].id;

      var viewLevel = 0;

      function isValidViewLevel(value) {
        return typeof value === "number" || value === "all";
      }

      function restoreSavedView() {
        var saved = window.SafeStorage.getJSON(STORAGE_KEY);
        if (!saved || saved.focusId !== focusId || !isValidViewLevel(saved.viewLevel)) return;
        viewLevel = saved.viewLevel;
      }

      function saveView() {
        window.SafeStorage.setJSON(STORAGE_KEY, { focusId: focusId, viewLevel: viewLevel });
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

      function renderToolbar(levels, roots) {
        if (!viewsNav) return;
        // Rebuilding replaces every button node below, which would drop
        // keyboard focus out of the toolbar entirely on every click —
        // remember whether focus was inside it so it can be restored to
        // whichever button ends up pressed.
        var hadFocusInside = viewsNav.contains(document.activeElement);
        viewsNav.innerHTML = "";
        // "Everyone" is worth showing even when focus has no recorded
        // ancestors of their own (levels.length === 0) as long as there's
        // more than one root branch elsewhere in the family to merge.
        if (!levels.length && roots.length <= 1) {
          viewsNav.hidden = true;
          return;
        }
        viewsNav.hidden = false;
        var deepest = levels.length;

        var row = document.createElement("div");
        row.className = "tree__views-row";
        row.appendChild(
          makeButton("Direct line", viewLevel === 0, function () {
            goToLevel(0);
          })
        );
        for (var lv = 1; lv <= deepest; lv++) {
          (function (lv) {
            row.appendChild(
              makeButton(window.TreeLogic.levelLabel(lv, deepest), viewLevel === lv, function () {
                goToLevel(lv);
              })
            );
          })(lv);
        }
        row.appendChild(
          makeButton("Everyone", viewLevel === "all", function () {
            goToLevel("all");
          })
        );
        viewsNav.appendChild(row);

        if (hadFocusInside) {
          var toFocus = viewsNav.querySelector('[aria-pressed="true"]');
          if (toFocus) toFocus.focus();
        }
      }

      function goToLevel(lv) {
        viewLevel = lv;
        renderView();
      }

      function cardInnerHtml(node) {
        var d = node.data.data;
        // At level 0 there's exactly one chart and no "branch" to speak
        // of; from level 1 up (including "Everyone"), each root is an
        // ancestor and focus shows up somewhere in it as their
        // descendant — mark them with their own thin gold ring so they
        // stay findable among the aunts/uncles/cousins.
        var isFocus = viewLevel !== 0 && node.data.id === focusId;
        // In the "Everyone" view, a person whose marriage bridges two
        // otherwise-disjoint lineages is drawn once per side; the
        // vendored library flags every occurrence past the first with
        // `node.duplicate` (node.data.id itself is never suffixed).
        var isDuplicate = !!node.duplicate;
        var innerClass = "card-inner" + (isFocus ? " card-inner--focus" : "");
        var avatarClass = "f3-card-avatar" + (d.avatarIsPhoto ? " f3-card-avatar--photo" : "");
        var avatarStyle = d.avatarIsPhoto ? ' style="--photo-sepia: ' + d.avatarSepia + '%;"' : "";
        var kinshipHtml = d.kinship
          ? '<div class="f3-card-kinship" title="' + escapeHtml(d.kinship) + '">' + escapeHtml(d.kinship) + "</div>"
          : "";
        var duplicateHtml = isDuplicate
          ? '<div class="f3-card-duplicate" title="Also shown under the other side of the family">' +
            "also shown elsewhere</div>"
          : "";
        return (
          '<div class="' + innerClass + '">' +
          '<img class="' + avatarClass + '" src="' + escapeHtml(d.avatar) + '" alt=""' + avatarStyle + '>' +
          '<div class="f3-card-text">' +
          '<div class="f3-card-name">' + escapeHtml(d.label) + "</div>" +
          kinshipHtml +
          duplicateHtml +
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
          viewLevel = 0;
          renderView();
          return;
        }
        window.location.href = urlById[node.data.id];
      }

      function mapTileTheme() {
        // The map only distinguishes light vs. dark tiles — "manuscript"
        // (and any OS-fallback "light") folds into "light".
        var theme = window.StorybookTheme ? window.StorybookTheme.current() : "light";
        return theme === "dark" ? "dark" : "light";
      }

      function mapTileHref(theme) {
        return theme === "light" ? container.dataset.mapTile : container.dataset.mapTileDark;
      }

      // One shared listener refreshes every currently-mounted map tile
      // (there can be several, one per panel) on a theme change, instead
      // of each chart instance registering its own MutationObserver —
      // charts are torn down and rebuilt on every level/focus change, so
      // a per-instance observer would leak a new one on every click.
      function refreshMapTiles() {
        var href = mapTileHref(mapTileTheme());
        document.querySelectorAll(".tree-map-img").forEach(function (img) {
          img.setAttribute("href", href);
        });
      }

      // The survey map lives INSIDE the chart's pan/zoom group so it
      // translates and scales in lockstep with the tree (a CSS background
      // on the container stays put while the chart moves), at 1024 chart
      // units per tile (1:1 pixels at zoom 1). Keying the pattern id off
      // `mountEl.id` keeps each panel's <pattern>/<image> ids distinct —
      // SVG `url(#id)` resolves against the whole document, not just the
      // local subtree, so reusing one id across several simultaneous
      // panels would make them all paint whichever panel's pattern
      // happened to register first.
      function installMapBackground(mountEl) {
        var svg = mountEl.querySelector("svg.main_svg");
        var view = svg && svg.querySelector("g.view");
        if (!svg || !view) {
          if (window.console && window.console.warn) {
            window.console.warn(
              "Storybook: couldn't find the family-chart SVG structure to attach the map " +
                "background to (svg.main_svg / g.view) — the vendored bundle may have changed."
            );
          }
          return;
        }
        var gridId = "tree-map-grid-" + mountEl.id;
        svg.insertAdjacentHTML(
          "afterbegin",
          '<defs><pattern id="' + gridId + '" patternUnits="userSpaceOnUse" width="1024" height="1024">' +
            '<image class="tree-map-img" aria-hidden="true" href="' +
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
        rect.setAttribute("fill", "url(#" + gridId + ")");
        view.insertBefore(rect, view.firstChild);
      }

      // Creates one independent family-chart instance rooted at `rootId`,
      // mounted on `mountEl` (which must already have a unique `id`).
      // Recenter captures its own fit transform per instance via
      // closures, so each panel remembers its own pan/zoom independently
      // of its siblings.
      function createChartInstance(mountEl, rootId, chartData) {
        var lastFitTransform = null;
        var fitCaptureTimer = null;

        // family-chart auto-fits the tree to the viewport on every
        // updateTree() call, via a d3-zoom transform applied to
        // #f3Canvas. Snapshot that transform once it settles and offer it
        // back so a reader who has panned/zoomed off into the leather can
        // get back without reloading. The vendored bundle's own fit
        // transition adds a 100ms pre-delay before the setTransitionTime
        // (600ms) duration even starts, so it actually settles ~700ms
        // after updateTree() — capture a little past that so Recenter
        // never restores a still-interpolating transform.
        function captureFitTransform() {
          var canvas = mountEl.querySelector("#f3Canvas");
          if (!canvas || !window.d3) return;
          if (fitCaptureTimer) window.clearTimeout(fitCaptureTimer);
          fitCaptureTimer = window.setTimeout(function () {
            lastFitTransform = window.d3.zoomTransform(canvas);
          }, FIT_SETTLE_MS);
        }

        function recenter() {
          var canvas = mountEl.querySelector("#f3Canvas");
          if (!canvas || !canvas.__zoomObj || !lastFitTransform || !window.d3) return;
          window.d3.select(canvas).call(canvas.__zoomObj.transform, lastFitTransform);
        }

        function installRecenterButton() {
          var btn = document.createElement("button");
          btn.type = "button";
          btn.className = "btn tree__recenter-btn";
          btn.textContent = "Recenter";
          btn.setAttribute("aria-label", "Recenter the family tree");
          btn.addEventListener("click", recenter);
          mountEl.appendChild(btn);
        }

        var chart = window.f3
          .createChart("#" + mountEl.id, chartData)
          .setTransitionTime(600)
          .setOrientationVertical()
          .setSingleParentEmptyCard(false);

        chart
          .setCardHtml()
          .setMiniTree(true)
          .setCardInnerHtmlCreator(cardInnerHtml)
          .setOnCardClick(onCardClick);

        chart.updateMainId(rootId);
        chart.updateTree({ initial: true });
        installMapBackground(mountEl);
        installRecenterButton();
        captureFitTransform();
      }

      // Rebuilds the chart area for the current viewLevel. Every level
      // change can change how many charts are needed (one big pedigree at
      // level 0, one small hourglass per ancestor couple beyond that), so
      // instances are always torn down and recreated rather than
      // reused/re-rooted in place — the same "just rebuild it" approach
      // renderToolbar already takes.
      function renderChartArea(levels, roots) {
        container.innerHTML = "";
        var chartData = familyPeople.map(toDatum);
        if (viewLevel === 0) {
          container.className = "tree__chart f3";
          createChartInstance(container, focusId, chartData);
          return;
        }
        if (viewLevel === "all") {
          container.className = "tree__chart f3";
          // A single hidden root whose children are one representative
          // per otherwise-disjoint lineage — walking "down" from it in
          // one family-chart instance reaches every branch of the whole
          // family at once, instead of one instance per couple. Its own
          // card is hidden entirely via CSS ([data-id] selector in
          // main.css); the connector lines above each real root branch
          // still draw, reading as one shared family rather than a fake
          // ancestor.
          var everyoneData = chartData.concat([
            {
              id: EVERYONE_ROOT_ID,
              data: { label: "", avatar: fallbackAvatar, avatarIsPhoto: false, gender: undefined, kinship: null },
              rels: { parents: [], spouses: [], children: roots },
            },
          ]);
          createChartInstance(container, EVERYONE_ROOT_ID, everyoneData);
          return;
        }
        container.className = "tree__panels";
        var groups = window.TreeLogic.coupleGroups(levels[viewLevel - 1] || [], partnersOf);
        groups.forEach(function (group, idx) {
          var wrap = document.createElement("div");
          wrap.className = "tree__panel-wrap";
          var label = document.createElement("p");
          label.className = "tree__panel-label";
          label.textContent =
            "via " +
            group
              .map(function (id) {
                return nameById[id];
              })
              .join(" & ");
          var mount = document.createElement("div");
          mount.id = "tree-panel-" + idx;
          mount.className = "tree__panel tree__chart f3";
          wrap.appendChild(label);
          wrap.appendChild(mount);
          container.appendChild(wrap);
          createChartInstance(mount, group[0], chartData);
        });
      }

      function renderView() {
        var levels = window.TreeLogic.ancestorLevels(focusId, parentsOf, exists);
        var deepest = levels.length;
        if (typeof viewLevel === "number") {
          if (viewLevel > deepest) viewLevel = deepest;
          if (viewLevel < 0) viewLevel = 0;
        }
        var roots = window.TreeLogic.rootAncestors(Object.keys(parentsOf), parentsOf, partnersOf);
        renderToolbar(levels, roots);
        renderChartArea(levels, roots);
        saveView();
      }

      restoreSavedView();

      new window.MutationObserver(refreshMapTiles).observe(document.documentElement, {
        attributes: true,
        attributeFilter: ["data-theme"],
      });
      var mq = window.matchMedia && window.matchMedia("(prefers-color-scheme: light)");
      if (mq && mq.addEventListener) mq.addEventListener("change", refreshMapTiles);

      renderView();
    })
    .catch(function () {
      container.textContent = "Could not load the family tree.";
    });
})();
