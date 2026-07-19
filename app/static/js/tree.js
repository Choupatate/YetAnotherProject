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
      var GRAPH_ROW_GAP = 96;
      // Four gap tiers between horizontally adjacent cards, from tightest
      // to widest, so a row reads as organized family clusters instead of
      // one undifferentiated line of boxes: a couple sits almost
      // touching; siblings/co-parents (closelyRelated) get a modest gap;
      // two people in the same connected component but with no direct
      // link between them (e.g. two grandparent couples joined only by
      // their children's marriage) get a visibly wider one; two
      // completely different connected components get the widest of all.
      var GRAPH_GAP_PARTNER = 10;
      var GRAPH_GAP_CLOSE = 28;
      var GRAPH_GAP_SAME_COMPONENT = 96;
      var GRAPH_GAP_CROSS_COMPONENT = 200;

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

        // Pixel X per id: assignPixelPositions keeps orderRows' row
        // order and the tiered minimum gaps, but aligns each couple
        // over its own children (and children under their parents) as
        // closely as those constraints allow — without it, every row
        // packs independently from the left and a couple can drift
        // sideways from its own children, making a multi-branch family
        // read as scrambled rows even when each row's order is right.
        var assigned = window.TreeGraphLogic.assignPixelPositions(
          layout.rows,
          parentsOf,
          childrenOf,
          partnersOf,
          layout.componentOf,
          {
            cardWidth: GRAPH_CARD_W,
            gapPartner: GRAPH_GAP_PARTNER,
            gapClose: GRAPH_GAP_CLOSE,
            gapSame: GRAPH_GAP_SAME_COMPONENT,
            gapCross: GRAPH_GAP_CROSS_COMPONENT,
          }
        );

        var maxLayer = 0;
        ids.forEach(function (id) {
          maxLayer = Math.max(maxLayer, layout.positions[id].layer);
        });

        function px(id) {
          return { x: assigned.xById[id], y: layout.positions[id].layer * (GRAPH_CARD_H + GRAPH_ROW_GAP) };
        }

        var contentWidth = assigned.contentWidth;
        var contentHeight = (maxLayer + 1) * (GRAPH_CARD_H + GRAPH_ROW_GAP);

        mountEl.innerHTML =
          '<svg class="tree-graph__svg"><g class="tree-graph__zoom"><g class="tree-graph__edges"></g></g></svg>' +
          '<div class="tree-graph__cards"></div>';
        var svg = mountEl.querySelector(".tree-graph__svg");
        var zoomG = mountEl.querySelector(".tree-graph__zoom");
        var edgesG = mountEl.querySelector(".tree-graph__edges");
        var cardsDiv = mountEl.querySelector(".tree-graph__cards");

        installMapBackground(mountEl, svg, zoomG);

        // Parent-child edges flow from each PARENT's card directly to
        // the child — never from an abstract union point. Every family
        // (parent pair or single parent, with their children) draws as
        // the classic T-bar descendant chart: each parent drops a line
        // from their own card bottom onto the family's horizontal bar,
        // and each child hangs from that same bar, so a two-parent
        // child visibly connects to BOTH parents' cards. Each family's
        // bar gets its own lane height in the corridor between
        // generations (assignLanes) — with one shared corridor height,
        // every family's bar merges into what reads as a single dashed
        // line spanning the whole chart, untraceable to any particular
        // family. Families whose bars don't overlap still share the
        // first lane, so a simple tree keeps clean, symmetric
        // connectors.
        var groupGeo = layout.parentEdgeGroups.map(function (group) {
          var childXs = group.children.map(function (c) {
            return px(c).x + GRAPH_CARD_W / 2;
          });
          // Parents share a layer (computeLayers equalizes partners and
          // co-parents alike), but take the max defensively — a bar
          // drawn from the wrong row is worse than a slightly long one.
          var parentLayer = group.parents.reduce(function (max, p) {
            return Math.max(max, layout.positions[p].layer);
          }, 0);
          var centers = group.parents.map(function (p) {
            return px(p).x + GRAPH_CARD_W / 2;
          });
          return {
            group: group,
            childXs: childXs,
            parentTopY: parentLayer * (GRAPH_CARD_H + GRAPH_ROW_GAP),
            parentLayer: parentLayer,
            approxMid:
              (Math.min.apply(null, centers.concat(childXs)) +
                Math.max.apply(null, centers.concat(childXs))) /
              2,
          };
        });

        // One drop per (parent, family). A remarried parent belongs to
        // several families and gets one drop per family bar — nudged a
        // touch apart around their card's center (ordered to lean
        // toward each family's side), so the verticals don't overprint
        // each other on the shared stretch below the card.
        var geosByParent = {};
        groupGeo.forEach(function (geo) {
          geo.parentDropX = {};
          geo.group.parents.forEach(function (p) {
            (geosByParent[p] = geosByParent[p] || []).push(geo);
          });
        });
        Object.keys(geosByParent).forEach(function (p) {
          var list = geosByParent[p];
          var centerX = px(p).x + GRAPH_CARD_W / 2;
          list.sort(function (a, b) {
            return a.approxMid - b.approxMid;
          });
          list.forEach(function (geo, i) {
            geo.parentDropX[p] = centerX + (i - (list.length - 1) / 2) * 12;
          });
        });

        groupGeo.forEach(function (geo) {
          var xs = geo.group.parents
            .map(function (p) {
              return geo.parentDropX[p];
            })
            .concat(geo.childXs);
          geo.left = Math.min.apply(null, xs);
          geo.right = Math.max.apply(null, xs);
        });

        var byCorridor = {};
        groupGeo.forEach(function (geo, i) {
          (byCorridor[geo.parentLayer] = byCorridor[geo.parentLayer] || []).push(i);
        });
        Object.keys(byCorridor).forEach(function (corridorKey) {
          var idxs = byCorridor[corridorKey];
          var lanes = window.TreeGraphLogic.assignLanes(
            idxs.map(function (i) {
              return { left: groupGeo[i].left, right: groupGeo[i].right };
            }),
            24
          );
          var laneCount =
            lanes.reduce(function (max, lane) {
              return Math.max(max, lane);
            }, 0) + 1;
          // Lanes spread evenly across the corridor with equal margins
          // — one lane sits at the corridor's center (the classic
          // simple-tree look), two land at 1/3 and 2/3, and so on — so
          // overlapping families' runs are separated by as much room as
          // the corridor allows, not by a token offset.
          idxs.forEach(function (i, k) {
            groupGeo[i].trunkY =
              groupGeo[i].parentTopY +
              GRAPH_CARD_H +
              (GRAPH_ROW_GAP * (lanes[k] + 1)) / (laneCount + 1);
          });
        });

        function addLink(d) {
          var path = document.createElementNS(SVG_NS, "path");
          path.setAttribute("class", "tree-graph__link");
          path.setAttribute("d", d);
          edgesG.appendChild(path);
        }

        groupGeo.forEach(function (geo) {
          var laneY = geo.trunkY;
          var parentBottomY = geo.parentTopY + GRAPH_CARD_H;
          // Terminals: each parent attaches from above (their card's
          // bottom edge), each child from below (their card's top).
          var terminals = geo.group.parents
            .map(function (p) {
              return { x: geo.parentDropX[p], y: parentBottomY, up: true };
            })
            .concat(
              geo.group.children.map(function (childId, ci) {
                return { x: geo.childXs[ci], y: px(childId).y, up: false };
              })
            )
            .sort(function (a, b) {
              return a.x - b.x;
            });

          var leftT = terminals[0];
          var rightT = terminals[terminals.length - 1];

          if (rightT.x - leftT.x < 1) {
            // Single parent directly above their only child: one
            // straight drop, no bar needed.
            addLink("M" + leftT.x + "," + parentBottomY + "V" + rightT.y);
            return;
          }

          // The bar, with rounded corners into whichever terminal sits
          // at each end (up toward a parent, down toward a child) — a
          // smooth corner is what lets the eye keep following one line
          // through a crossing instead of losing it at a sharp right
          // angle. Terminals between the ends join the bar as plain
          // T-junctions.
          function endCorner(t, inward) {
            var r = Math.min(10, (rightT.x - leftT.x) / 2, Math.abs(laneY - t.y));
            var vy = t.up ? laneY - r : laneY + r;
            return {
              start: "M" + t.x + "," + t.y + "V" + vy,
              curve: "Q" + t.x + "," + laneY + " " + (t.x + inward * r) + "," + laneY,
              barX: t.x + inward * r,
            };
          }
          var leftEnd = endCorner(leftT, 1);
          var rightEnd = endCorner(rightT, -1);
          addLink(leftEnd.start + leftEnd.curve + "H" + rightEnd.barX);
          addLink(rightEnd.start + rightEnd.curve);
          terminals.slice(1, -1).forEach(function (t) {
            addLink("M" + t.x + "," + t.y + "V" + laneY);
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
