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

  // Hard cap on how many generations to walk. Real recorded family trees
  // never get remotely this deep; it exists only so a cyclic `parents`
  // edge in hand-edited data (A recorded as B's parent and B recorded as
  // A's, several generations apart) can't spin the walk forever.
  var MAX_LEVELS = 24;

  // levels[0] = id's parents, levels[1] = grandparents, levels[2] =
  // great-grandparents, etc. Each level lists ALL ancestors at that
  // depth, from every branch, so the multi-panel UI can group them.
  // Dedup only happens WITHIN a level, not across levels: a remarriage
  // or cousin match can legitimately put the same person one generation
  // apart on two different lines (pedigree collapse), and they need to
  // show up at both depths rather than only the shallower one.
  function ancestorLevels(id, parentsOf, exists) {
    var levels = [];
    var current = [id];
    for (var depth = 0; depth < MAX_LEVELS; depth++) {
      var next = [];
      var seenThisLevel = {};
      current.forEach(function (childId) {
        (parentsOf[childId] || []).forEach(function (parentId) {
          if (parentId === id) return;
          if (!seenThisLevel[parentId] && exists(parentId)) {
            seenThisLevel[parentId] = true;
            next.push(parentId);
          }
        });
      });
      if (!next.length) return levels;
      levels.push(next);
      current = next;
    }
    return levels;
  }

  // Ancestors at one level, grouped into couples so the paternal and
  // maternal sides each get their own "via Rose & Jean" panel.
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
    if (level === 1) return "Parents’ branch";
    var label = "grandparents";
    for (var i = 0; i < level - 2; i++) label = "great-" + label;
    return label.charAt(0).toUpperCase() + label.slice(1) + "’ branch";
  }

  return {
    ancestorLevels: ancestorLevels,
    coupleGroups: coupleGroups,
    levelLabel: levelLabel,
  };
});
