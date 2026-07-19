(function () {
  var container = document.getElementById("FamilyChart");
  if (!container || !window.f3 || !window.TreeLogic || !window.TreeGraphLogic || !window.SafeStorage) return;

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
      var peopleById = {};
      var parentsOf = {};
      var partnersOf = {};
      var childrenOf = {};
      familyPeople.forEach(function (p) {
        urlById[p.id] = p.url;
        nameById[p.id] = p.name;
        peopleById[p.id] = p;
        parentsOf[p.id] = p.rels.parents || [];
        partnersOf[p.id] = p.rels.partners || [];
        childrenOf[p.id] = p.rels.children || [];
      });
      var exists = function (id) {
        return urlById.hasOwnProperty(id);
      };

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
        // of; from level 1 up, each root is an ancestor and focus shows
        // up somewhere in it as their descendant — mark them with their
        // own thin gold ring so they stay findable among the
        // aunts/uncles/cousins. (The "Everyone" view has its own
        // separate renderer, renderFamilyGraph — this function is only
        // ever used for family-chart instances: Direct line and the
        // branch-level panels.)
        var isFocus = viewLevel !== 0 && node.data.id === focusId;
        // Pedigree collapse — e.g. a first-cousin marriage puts the same
        // shared grandparent on two different lines of one person's own
        // ancestry, so they appear twice within this single chart.
        // family-chart flags every occurrence past the first with
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
      function installMapBackground(mountEl, svg, view) {
        if (!svg || !view) {
          if (window.console && window.console.warn) {
            window.console.warn(
              "Storybook: couldn't find the chart's SVG pan/zoom group to attach the map " +
                "background to."
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
        installMapBackground(mountEl, mountEl.querySelector("svg.main_svg"), mountEl.querySelector("svg.main_svg g.view"));
        installRecenterButton();
        captureFitTransform();
      }

      var SVG_NS = "http://www.w3.org/2000/svg";
      var GRAPH_CARD_W = 176;
      var GRAPH_CARD_H = 56;
      var GRAPH_COL_GAP = 28;
      var GRAPH_ROW_GAP = 96;
      // The extra breathing room opened up between two different
      // connected-component clusters landing on the same row — several
      // times the normal within-family column gap, so it reads as a
      // deliberate separation rather than just a slightly wider gap.
      var GRAPH_CLUSTER_GAP = GRAPH_COL_GAP + 96;

      function graphCardInnerHtml(person) {
        var avatar = person.photo || fallbackAvatar;
        var avatarClass = "tree-graph__avatar" + (person.photo ? " tree-graph__avatar--photo" : "");
        var avatarStyle = person.photo ? ' style="--photo-sepia: ' + person.photo_sepia + '%;"' : "";
        var kinshipHtml = person.kinship
          ? '<div class="tree-graph__kinship" title="' + escapeHtml(person.kinship) + '">' +
            escapeHtml(person.kinship) + "</div>"
          : "";
        return (
          '<img class="' + avatarClass + '" src="' + escapeHtml(avatar) + '" alt=""' + avatarStyle + '>' +
          '<div class="tree-graph__text">' +
          '<div class="tree-graph__name">' + escapeHtml(person.name) + "</div>" +
          kinshipHtml +
          "</div>"
        );
      }

      // The "Everyone" view: a from-scratch graph layout (TreeGraphLogic),
      // not family-chart — every person gets exactly one card, however
      // many marriages connect them to the rest of the family. family-chart
      // is a single-root hourglass; there's no way to ask it for "the
      // whole family, everyone once" without duplicating whoever bridges
      // two otherwise-disjoint branches (see FEATURES.md). SVG for the
      // connector lines, plain HTML for cards (photos/text-overflow "for
      // free" via normal CSS) — same split family-chart itself uses,
      // avoiding <foreignObject>'s cross-browser quirks — both driven by
      // one d3-zoom transform so they pan/zoom in lockstep.
      function renderFamilyGraph(mountEl) {
        mountEl.className = "tree-graph tree__chart";
        var ids = familyPeople.map(function (p) {
          return p.id;
        });
        var layout = window.TreeGraphLogic.layoutFamily(ids, parentsOf, partnersOf, childrenOf);

        // Pixel X per id, walked row by row in the layout's own order —
        // not a uniform `x * width` grid, because two people can share a
        // layer for entirely unrelated reasons (real root ancestors, vs.
        // someone connected to the family only through a marriage with a
        // gap in the chain — see connectedComponents' docstring). A
        // normal generation-to-generation gap separates cards within the
        // same family cluster; a wider one opens up wherever a row
        // crosses from one connected component to a different one, so an
        // unrelated cluster reads as visually separate at a glance
        // instead of looking like it belongs to the same family purely
        // because it landed on the same row.
        var pixelXById = {};
        var maxLayer = 0;
        var contentWidth = 0;
        Object.keys(layout.rows).forEach(function (layerKey) {
          maxLayer = Math.max(maxLayer, Number(layerKey));
          var rowIds = layout.rows[layerKey];
          var x = 0;
          rowIds.forEach(function (id, i) {
            if (i > 0) {
              var sameCluster = layout.componentOf[id] === layout.componentOf[rowIds[i - 1]];
              x += GRAPH_CARD_W + (sameCluster ? GRAPH_COL_GAP : GRAPH_CLUSTER_GAP);
            }
            pixelXById[id] = x;
          });
          contentWidth = Math.max(contentWidth, x + GRAPH_CARD_W);
        });

        function px(id) {
          return { x: pixelXById[id], y: layout.positions[id].layer * (GRAPH_CARD_H + GRAPH_ROW_GAP) };
        }

        var contentHeight = (maxLayer + 1) * (GRAPH_CARD_H + GRAPH_ROW_GAP);

        mountEl.innerHTML =
          '<svg class="tree-graph__svg"><g class="tree-graph__zoom"><g class="tree-graph__edges"></g></g></svg>' +
          '<div class="tree-graph__cards"></div>';
        var svg = mountEl.querySelector(".tree-graph__svg");
        var zoomG = mountEl.querySelector(".tree-graph__zoom");
        var edgesG = mountEl.querySelector(".tree-graph__edges");
        var cardsDiv = mountEl.querySelector(".tree-graph__cards");

        installMapBackground(mountEl, svg, zoomG);

        // Parent-child edges: one shared trunk from the couple's (or
        // single parent's) midpoint, branching out to each child — so
        // three siblings share one drop-line instead of three separate
        // ones stacking on top of each other.
        layout.parentEdgeGroups.forEach(function (group) {
          var parentPositions = group.parents.map(px);
          var midX =
            parentPositions.reduce(function (sum, p) {
              return sum + p.x;
            }, 0) / parentPositions.length + GRAPH_CARD_W / 2;
          var parentY = parentPositions[0].y + GRAPH_CARD_H;
          var trunkY = parentY + GRAPH_ROW_GAP / 2;

          var trunk = document.createElementNS(SVG_NS, "path");
          trunk.setAttribute("class", "tree-graph__link");
          trunk.setAttribute("d", "M" + midX + "," + parentY + "V" + trunkY);
          edgesG.appendChild(trunk);

          group.children.forEach(function (childId) {
            var childPos = px(childId);
            var childX = childPos.x + GRAPH_CARD_W / 2;
            var branch = document.createElementNS(SVG_NS, "path");
            branch.setAttribute("class", "tree-graph__link");
            branch.setAttribute(
              "d",
              "M" + midX + "," + trunkY + "H" + childX + "V" + childPos.y
            );
            edgesG.appendChild(branch);
          });
        });

        // Partner edges: a short horizontal connector between adjacent
        // partner cards (coupleUnits in the layout already guarantees
        // every rendered neighbor in a chain is a real couple).
        layout.partnerEdges.forEach(function (pair) {
          var posA = px(pair[0]);
          var posB = px(pair[1]);
          var y = posA.y + GRAPH_CARD_H / 2;
          var left = Math.min(posA.x, posB.x) + GRAPH_CARD_W;
          var right = Math.max(posA.x, posB.x);
          if (right <= left) return; // shouldn't happen once ordered, but never draw a backwards/zero-width line
          var line = document.createElementNS(SVG_NS, "line");
          line.setAttribute("class", "tree-graph__link tree-graph__link--partner");
          line.setAttribute("x1", left);
          line.setAttribute("y1", y);
          line.setAttribute("x2", right);
          line.setAttribute("y2", y);
          edgesG.appendChild(line);
        });

        ids.forEach(function (id) {
          var person = peopleById[id];
          var pos = px(id);
          var card = document.createElement("div");
          card.className = "tree-graph__card" + (id === focusId ? " tree-graph__card--focus" : "");
          card.style.left = pos.x + "px";
          card.style.top = pos.y + "px";
          card.style.width = GRAPH_CARD_W + "px";
          card.innerHTML = graphCardInnerHtml(person);
          card.addEventListener("click", function () {
            window.location.href = urlById[id];
          });
          cardsDiv.appendChild(card);
        });

        // Zoom/pan, mirroring createChartInstance's approach: the SVG
        // group and the HTML card layer are two separate DOM subtrees,
        // so both need the same transform applied on every zoom event
        // rather than relying on one containing the other.
        var zoomBehavior = window.d3.zoom().on("zoom", function (event) {
          zoomG.setAttribute("transform", event.transform);
          cardsDiv.style.transform =
            "translate(" + event.transform.x + "px," + event.transform.y + "px) scale(" + event.transform.k + ")";
        });
        window.d3.select(svg).call(zoomBehavior);

        var rect = mountEl.getBoundingClientRect();
        var padding = 48;
        var scale = Math.min(
          (rect.width - padding) / contentWidth,
          (rect.height - padding) / contentHeight,
          1
        );
        if (!isFinite(scale) || scale <= 0) scale = 1;
        var fitTransform = window.d3.zoomIdentity
          .translate((rect.width - contentWidth * scale) / 2, (rect.height - contentHeight * scale) / 2)
          .scale(scale);
        window.d3.select(svg).call(zoomBehavior.transform, fitTransform);

        var recenterBtn = document.createElement("button");
        recenterBtn.type = "button";
        recenterBtn.className = "btn tree__recenter-btn";
        recenterBtn.textContent = "Recenter";
        recenterBtn.setAttribute("aria-label", "Recenter the family tree");
        recenterBtn.addEventListener("click", function () {
          window.d3.select(svg).call(zoomBehavior.transform, fitTransform);
        });
        mountEl.appendChild(recenterBtn);
      }

      // Rebuilds the chart area for the current viewLevel. Every level
      // change can change how many charts are needed (one big pedigree at
      // level 0, one small hourglass per ancestor couple beyond that), so
      // instances are always torn down and recreated rather than
      // reused/re-rooted in place — the same "just rebuild it" approach
      // renderToolbar already takes.
      function renderChartArea(levels) {
        container.innerHTML = "";
        var chartData = familyPeople.map(toDatum);
        if (viewLevel === 0) {
          container.className = "tree__chart f3";
          createChartInstance(container, focusId, chartData);
          return;
        }
        if (viewLevel === "all") {
          renderFamilyGraph(container);
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
        renderChartArea(levels);
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
