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
  // depth, from every branch, so branch-switching UI can group them.
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

  // The real ancestor chain from focusId down to targetId, found by
  // walking the parent graph level by level (same traversal shape as
  // ancestorLevels). Used when a branch chip picks an ancestor from a
  // different lineage than the one currently in view: two couples at
  // the "same" depth can be on entirely different lines, so the chain
  // has to be rebuilt from focusId rather than patched by swapping the
  // deepest entry. Returns null if targetId isn't a recorded ancestor
  // of focusId (within MAX_LEVELS generations); returns [] if
  // targetId === focusId.
  function ancestorPath(focusId, targetId, parentsOf, exists) {
    if (targetId === focusId) return [];
    var frontier = [{ id: focusId, path: [] }];
    for (var depth = 0; depth < MAX_LEVELS && frontier.length; depth++) {
      var next = [];
      var seenThisLevel = {};
      for (var i = 0; i < frontier.length; i++) {
        var node = frontier[i];
        var parents = parentsOf[node.id] || [];
        for (var j = 0; j < parents.length; j++) {
          var parentId = parents[j];
          if (parentId === focusId || !exists(parentId)) continue;
          var path = node.path.concat([parentId]);
          if (parentId === targetId) return path;
          if (!seenThisLevel[parentId]) {
            seenThisLevel[parentId] = true;
            next.push({ id: parentId, path: path });
          }
        }
      }
      frontier = next;
    }
    return null;
  }

  // True when `chain` is a real ancestor path: chain[0] is a recorded
  // parent of focusId, chain[1] a recorded parent of chain[0], and so
  // on. Used to validate a chain restored from localStorage, which can
  // go stale if parent links are edited between visits (the person
  // still exists, but is no longer actually on this line).
  function isValidChain(chain, focusId, parentsOf, exists) {
    var base = focusId;
    for (var i = 0; i < chain.length; i++) {
      var id = chain[i];
      if (!exists(id)) return false;
      if ((parentsOf[base] || []).indexOf(id) === -1) return false;
      base = id;
    }
    return true;
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
    if (level === 1) return "Parents’ branch";
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
  //
  // This walks the parent graph client-side rather than consuming a
  // server-computed depth (kinship.py already does a similar BFS to
  // word kinship labels) because that server computation is only ever
  // relative to the fixed STORYBOOK_CHILD anchor. tree.js can re-root
  // focusId to any person via the mini-tree control, so the client
  // needs its own arbitrary-focus-relative walk; shipping every
  // possible focus's depth data up front isn't worth it for the
  // handful of people in a typical tree.
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
    ancestorPath: ancestorPath,
    coupleGroups: coupleGroups,
    levelLabel: levelLabel,
    chainToLevel: chainToLevel,
    isValidChain: isValidChain,
  };
});
