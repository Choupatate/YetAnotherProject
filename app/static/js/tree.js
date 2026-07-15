(function () {
  var container = document.getElementById("FamilyChart");
  if (!container || !window.f3) return;

  var viewsNav = document.getElementById("tree-views");
  var treeUrl = container.dataset.treeUrl;
  var fallbackAvatar = container.dataset.fallbackAvatar;

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

      // The person the tree is ABOUT. Views re-root the chart layout at
      // one of their ancestors (the hourglass layout can only show
      // aunts/uncles/cousins as an ancestor's descendants), but the focus
      // stays put; the mini-tree control moves it.
      var focusId =
        payload.anchor && urlById.hasOwnProperty(payload.anchor)
          ? payload.anchor
          : familyPeople[0].id;
      var viewLevel = 0; // 0 = direct line; n = rooted n generations above focus
      var viewRootId = focusId;

      // levels[0] = focus's parents, levels[1] = grandparents, ...
      function ancestorLevels(id) {
        var levels = [];
        var seen = {};
        seen[id] = true;
        var current = [id];
        for (;;) {
          var next = [];
          current.forEach(function (childId) {
            (parentsOf[childId] || []).forEach(function (parentId) {
              if (!seen[parentId] && urlById.hasOwnProperty(parentId)) {
                seen[parentId] = true;
                next.push(parentId);
              }
            });
          });
          if (!next.length) return levels;
          levels.push(next);
          current = next;
        }
      }

      // Ancestors at one level, grouped into couples so the paternal and
      // maternal sides each get a single "via Rose & Jean" chip.
      function coupleGroups(ids) {
        var groups = [];
        var used = {};
        ids.forEach(function (id) {
          if (used[id]) return;
          used[id] = true;
          var group = [id];
          (partnersOf[id] || []).forEach(function (partnerId) {
            if (!used[partnerId] && ids.indexOf(partnerId) !== -1) {
              used[partnerId] = true;
              group.push(partnerId);
            }
          });
          groups.push(group);
        });
        return groups;
      }

      function levelLabel(level, deepest) {
        if (level === 0) return "Direct line";
        if (level >= deepest) return "Whole family";
        var label = "grandparents";
        for (var i = 0; i < level - 2; i++) label = "great-" + label;
        return label.charAt(0).toUpperCase() + label.slice(1) + "’ branch";
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
        var levels = ancestorLevels(focusId);
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
            setView(0, focusId);
          })
        );
        var deepest = levels.length;
        for (var lv = deepest === 1 ? 1 : 2; lv <= deepest; lv++) {
          (function (lv) {
            row.appendChild(
              makeButton(levelLabel(lv, deepest), viewLevel === lv, function () {
                setView(lv, levels[lv - 1][0]);
              })
            );
          })(lv);
        }
        viewsNav.appendChild(row);

        if (viewLevel > 0) {
          var groups = coupleGroups(levels[viewLevel - 1] || []);
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
                  setView(viewLevel, group[0]);
                })
              );
            });
            viewsNav.appendChild(branches);
          }
        }
      }

      function setView(level, rootId) {
        viewLevel = level;
        viewRootId = rootId;
        chart.updateMainId(rootId);
        chart.updateTree({});
        renderToolbar();
      }

      function cardInnerHtml(node) {
        var d = node.data.data;
        // In rooted views the gold brand follows the new root card; keep
        // the focus person findable with their own thin gold ring.
        var isFocus = viewLevel > 0 && node.data.id === focusId;
        var innerClass = "card-inner" + (isFocus ? " card-inner--focus" : "");
        var avatarClass = "f3-card-avatar" + (d.avatarIsPhoto ? " f3-card-avatar--photo" : "");
        var avatarStyle = d.avatarIsPhoto ? ' style="--photo-sepia: ' + d.avatarSepia + '%;"' : "";
        return (
          '<div class="' + innerClass + '">' +
          '<img class="' + avatarClass + '" src="' + escapeHtml(d.avatar) + '" alt=""' + avatarStyle + '>' +
          '<div class="f3-card-name">' + escapeHtml(d.label) + "</div>" +
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
          setView(0, focusId);
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

      chart.updateMainId(focusId);
      chart.updateTree({ initial: true });
      renderToolbar();
      installMapBackground();
    })
    .catch(function () {
      container.textContent = "Could not load the family tree.";
    });
})();
