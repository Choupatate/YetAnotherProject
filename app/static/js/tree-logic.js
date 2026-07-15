// Pure, DOM-free helpers for the /tree view scopes (F18 follow-up). Kept
// separate from tree.js so they can be unit-tested with plain Node — see
// tests/js/tree_logic_test.mjs — without dragging in jsdom or a browser.
(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory();
  } else {
    root.TreeLogic = factory();
  }
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  // levels[0] = id's parents, levels[1] = grandparents, levels[2] =
  // great-grandparents, etc. Each level lists ALL ancestors at that
  // depth, from every branch, so branch-switching UI can group them.
  function ancestorLevels(id, parentsOf, exists) {
    var levels = [];
    var seen = {};
    seen[id] = true;
    var current = [id];
    for (;;) {
      var next = [];
      current.forEach(function (childId) {
        (parentsOf[childId] || []).forEach(function (parentId) {
          if (!seen[parentId] && exists(parentId)) {
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
  function coupleGroups(ids, partnersOf) {
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

  // Extends (or truncates) an ancestor chain toward `targetLevel`
  // generations above focusId. Existing chain entries are kept as-is —
  // going deeper continues from whichever branch was already selected —
  // new levels are filled in by walking the first parent at each step.
  // Returns the chain actually achieved, which is shorter than
  // targetLevel when that lineage doesn't go back that far.
  function chainToLevel(chain, targetLevel, focusId, parentsOf, exists) {
    if (targetLevel <= 0) return [];
    var result = chain.slice(0, targetLevel);
    while (result.length < targetLevel) {
      var base = result.length === 0 ? focusId : result[result.length - 1];
      var candidates = ancestorLevels(base, parentsOf, exists)[0] || [];
      if (!candidates.length) break;
      result.push(candidates[0]);
    }
    return result;
  }

  return {
    ancestorLevels: ancestorLevels,
    coupleGroups: coupleGroups,
    levelLabel: levelLabel,
    chainToLevel: chainToLevel,
  };
});
