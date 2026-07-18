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

  // One id per otherwise-disjoint blood lineage in the whole family (not
  // just one focus person's) — the topmost ancestor of each. Used to
  // build the "Everyone" merged view: a synthetic hidden root whose
  // children are exactly these ids, so one family-chart instance
  // recurses down through every lineage at once instead of requiring a
  // separate panel per couple.
  //
  // A person with no recorded parents only needs to be an explicit root
  // if EVERY one of their partners also has no recorded parents (an
  // unresearched-further couple, or no partner at all). Someone whose
  // partner DOES have recorded parents will already be pulled in
  // automatically as that partner's spouse once the partner's own
  // lineage is rooted — including them separately would draw their
  // whole descendant subtree a second time for no reason (this is
  // common: any ancestor whose own parents just were never recorded,
  // despite marrying into an otherwise fully-connected line).
  function rootAncestors(ids, parentsOf, partnersOf) {
    var hasParents = function (id) {
      return !!(parentsOf[id] || []).length;
    };
    var topmost = ids.filter(function (id) {
      return !hasParents(id);
    });
    var candidates = topmost.filter(function (id) {
      return (partnersOf[id] || []).every(function (partnerId) {
        return !hasParents(partnerId);
      });
    });
    return coupleGroups(candidates, partnersOf).map(function (group) {
      return group[0];
    });
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
    rootAncestors: rootAncestors,
    levelLabel: levelLabel,
  };
});
