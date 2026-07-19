// Pure, DOM-free layout math for the /tree "Everyone" view (F18 follow-up:
// a real family-graph chart, replacing the family-chart-based merged
// hourglass, which necessarily duplicates anyone whose marriage bridges
// two otherwise-disjoint blood lineages). This file computes a
// generation "layer" and a within-layer order for every in-family
// person, plus the edges to draw — every person exactly once, however
// many marriages or half-siblings they have. See tests/js/tree_graph_logic_test.mjs.
(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory();
  } else {
    root.TreeGraphLogic = factory();
  }
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  // Same reasoning as tree-logic.js's MAX_LEVELS: a hard cap protects the
  // relaxation loops below from hand-edited/corrupted data, never hit by
  // a real recorded family.
  var MAX_LAYERS = 64;

  // Every in-family person's generation layer: 0 for anyone with no
  // recorded parents, otherwise one more than their deepest parent's
  // layer (the standard "longest path from a root" DAG layering — the
  // only definition that can't misplace someone just because one side of
  // a couple's ancestry happens to be recorded further back than the
  // other, the exact failure mode generation_offset in kinship.py's own
  // docstring warns about). Partners are then pulled to the same layer
  // as each other (a couple reads as one generation on paper, even if
  // one of them has no recorded parents of their own — an unresearched
  // branch, not evidence they're somehow younger). The two rules are
  // applied to a fixed point: pulling a partner down can in turn pull
  // THEIR children down a layer too, and so on. Every layer value is
  // monotonically non-decreasing across the whole loop, bounded by the
  // number of people, so this always terminates; MAX_LAYERS is just a
  // safety cap, never expected to bind on real data.
  function computeLayers(ids, parentsOf, partnersOf) {
    var layer = {};
    ids.forEach(function (id) {
      layer[id] = 0;
    });
    var changed = true;
    var iterations = 0;
    var cap = Math.min(MAX_LAYERS, ids.length * 2 + 4);
    while (changed && iterations < cap) {
      changed = false;
      iterations++;
      ids.forEach(function (id) {
        var best = layer[id];
        (parentsOf[id] || []).forEach(function (parentId) {
          if (layer[parentId] !== undefined && layer[parentId] + 1 > best) {
            best = layer[parentId] + 1;
          }
        });
        if (best > layer[id]) {
          layer[id] = best;
          changed = true;
        }
      });
      ids.forEach(function (id) {
        (partnersOf[id] || []).forEach(function (partnerId) {
          if (layer[partnerId] !== undefined && layer[partnerId] > layer[id]) {
            layer[id] = layer[partnerId];
            changed = true;
          }
        });
      });
    }
    return layer;
  }

  // Groups ids into rows by layer, each row an array of ids in their
  // ORIGINAL relative order (not yet crossing-reduced — see
  // orderRows). Rows are indexed by layer number, so rows[0] is always
  // the oldest generation present; a family with nobody at layer 3
  // still gets an (empty-free) sparse structure — callers should use
  // Object.keys(rows) rather than assuming a contiguous 0..max range,
  // since a person can be pulled to a much deeper layer than their own
  // recorded generation by a partner (see computeLayers), potentially
  // leaving a gap.
  function groupByLayer(ids, layer) {
    var rows = {};
    ids.forEach(function (id) {
      var l = layer[id];
      if (!rows[l]) rows[l] = [];
      rows[l].push(id);
    });
    return rows;
  }

  // Groups a row into ordering units along its partner links — every
  // person in a connected chain of marriages (a simple couple, or a
  // remarriage chain: an ex on one side, a current partner on the
  // other) becomes one unit, in an order where every ADJACENT pair in
  // the unit is an actual couple. That last part is why this isn't just
  // "attach every partner to the first person found": a person with two
  // partners in the same row (Papa, married first to Ex-Anne and now to
  // Maman) must end up in the MIDDLE of their unit — [Ex-Anne, Papa,
  // Maman] — not with both partners bunched on one side, or Ex-Anne and
  // Maman would render adjacent to each other despite never having been
  // a couple. Walks each row-partner-subgraph component as a path from
  // one of its ends; a person with three or more partners in the same
  // row (rare — a remarriage chain branching twice at once) can't form
  // a simple path, so that component falls back to a plain traversal
  // order instead — still one connected unit, just without the
  // every-neighbor-is-a-real-couple guarantee in that rare case.
  function coupleUnits(rowIds, partnersOf) {
    var inRow = {};
    rowIds.forEach(function (id) {
      inRow[id] = true;
    });
    function rowPartners(id) {
      return (partnersOf[id] || []).filter(function (p) {
        return inRow[p];
      });
    }

    var visited = {};
    var components = [];
    rowIds.forEach(function (id) {
      if (visited[id]) return;
      var stack = [id];
      var comp = [];
      visited[id] = true;
      while (stack.length) {
        var current = stack.pop();
        comp.push(current);
        rowPartners(current).forEach(function (partnerId) {
          if (!visited[partnerId]) {
            visited[partnerId] = true;
            stack.push(partnerId);
          }
        });
      }
      components.push(comp);
    });

    return components.map(function (comp) {
      var isSimplePath = comp.every(function (id) {
        return rowPartners(id).length <= 2;
      });
      if (!isSimplePath || comp.length === 1) return comp;
      var start = comp.filter(function (id) {
        return rowPartners(id).length <= 1;
      })[0] || comp[0];
      var ordered = [start];
      var seen = {};
      seen[start] = true;
      var current = start;
      while (ordered.length < comp.length) {
        var candidates = rowPartners(current).filter(function (p) {
          return !seen[p];
        });
        if (!candidates.length) break;
        var next = candidates[0];
        ordered.push(next);
        seen[next] = true;
        current = next;
      }
      return ordered;
    });
  }

  // The barycenter (average x) of `ids` in `position`, or null if none of
  // them have a position yet (e.g. a row being ordered top-down before
  // anyone below it has been placed).
  function barycenter(ids, position) {
    var known = ids.filter(function (id) {
      return position[id] !== undefined;
    });
    if (!known.length) return null;
    var sum = known.reduce(function (acc, id) {
      return acc + position[id];
    }, 0);
    return sum / known.length;
  }

  // Every id's connected component over the UNDIRECTED blood+partner
  // graph (parent/child and partner edges both count, direction
  // ignored) — component index 0, 1, 2, ... assigned in first-appearance
  // order within `ids`. Two people can end up on the same layer (see
  // computeLayers) for entirely unrelated reasons: real root ancestors
  // at the top of a researched lineage, and someone connected to the
  // family only through a marriage with a gap in the chain (an in-law
  // whose own partner-of-partner link back to blood family was never
  // recorded), who defaults to layer 0 for lack of any recorded parents
  // — with nothing to tell them apart, they'd render intermixed in the
  // same row as if they were part of the same family. Row ordering uses
  // this to keep every true cluster contiguous and give genuinely
  // unrelated ones a visibly wider gap (see orderRows/layoutFamily),
  // rather than just leaving the coincidence of a shared layer number to
  // read as a real relationship.
  function connectedComponents(ids, parentsOf, partnersOf) {
    var idSet = {};
    ids.forEach(function (id) {
      idSet[id] = true;
    });
    var neighbors = {};
    function link(a, b) {
      if (!idSet[a] || !idSet[b]) return;
      (neighbors[a] = neighbors[a] || []).push(b);
    }
    ids.forEach(function (id) {
      (parentsOf[id] || []).forEach(function (p) {
        link(id, p);
        link(p, id);
      });
      (partnersOf[id] || []).forEach(function (p) {
        link(id, p);
        link(p, id);
      });
    });

    var componentOf = {};
    var nextIndex = 0;
    ids.forEach(function (id) {
      if (componentOf[id] !== undefined) return;
      var index = nextIndex++;
      var stack = [id];
      componentOf[id] = index;
      while (stack.length) {
        var current = stack.pop();
        (neighbors[current] || []).forEach(function (n) {
          if (componentOf[n] === undefined) {
            componentOf[n] = index;
            stack.push(n);
          }
        });
      }
    });
    return componentOf;
  }

  // Reorders every row to reduce edge crossings, via the standard
  // (heuristic — true minimum-crossing layout is NP-hard) Sugiyama
  // barycenter method: repeatedly re-sort each row by the average
  // position of the neighbors it's being pulled toward, alternating
  // downward passes (order by parents' positions) and upward passes
  // (order by children's positions), a fixed handful of times. Couples
  // are ordered as a single unit (via coupleUnits) so partners always
  // land adjacent to each other, never split apart by the sort. Within
  // that, every row is grouped by connected component FIRST — barycenter
  // position only breaks ties within the same true family cluster, never
  // interleaving two unrelated ones — and component order is stable
  // across every row (component 0's members are never pushed to the
  // right of component 1's on one row and the left on another), so a
  // cluster reads as one coherent block spanning its generations rather
  // than drifting sideways from row to row.
  //
  // Returns {order: {[id]: x}, rows: {[layer]: [id, ...]}} — `order` is
  // every person's final integer rank within their own row (0-based,
  // NOT a global x — two people on different layers can share the same
  // order value and are not meant to visually align), `rows` is the
  // final per-layer id order those ranks came from.
  function orderRows(ids, layer, parentsOf, childrenOf, partnersOf, componentOf) {
    var rowsByLayer = groupByLayer(ids, layer);
    var layers = Object.keys(rowsByLayer)
      .map(Number)
      .sort(function (a, b) {
        return a - b;
      });

    var position = {};
    function assignPositions(rowIds) {
      rowIds.forEach(function (id, index) {
        position[id] = index;
      });
    }

    function sortRow(rowIds, neighborsOf) {
      var units = coupleUnits(rowIds, partnersOf);
      units.forEach(function (unit) {
        var neighborIds = [];
        unit.forEach(function (id) {
          neighborIds = neighborIds.concat(neighborsOf(id) || []);
        });
        unit.bc = barycenter(neighborIds, position);
        // Every member of a couple/chain unit is in the same component
        // by construction (they're linked by partner edges), so the
        // first member's component speaks for the whole unit.
        unit.component = componentOf[unit[0]];
      });
      // Stable-sort by component first (never interleave two unrelated
      // clusters), then by barycenter within a component; units with no
      // known neighbors yet (null) keep their current relative order
      // rather than collapsing to one end, so an initial/first pass over
      // a row with nothing placed above or below it is a no-op instead
      // of a shuffle.
      var indexed = units.map(function (unit, i) {
        return { unit: unit, i: i };
      });
      indexed.sort(function (a, b) {
        if (a.unit.component !== b.unit.component) return a.unit.component - b.unit.component;
        if (a.unit.bc === null && b.unit.bc === null) return a.i - b.i;
        if (a.unit.bc === null) return 1;
        if (b.unit.bc === null) return -1;
        if (a.unit.bc !== b.unit.bc) return a.unit.bc - b.unit.bc;
        return a.i - b.i;
      });
      var ordered = [];
      indexed.forEach(function (entry) {
        entry.unit.forEach(function (id) {
          ordered.push(id);
        });
      });
      return ordered;
    }

    // Initial pass: top to bottom, each row in its given (input) order
    // the very first time since nothing above it has positions yet.
    layers.forEach(function (l) {
      var rowIds = rowsByLayer[l];
      var ordered = sortRow(rowIds, function (id) {
        return parentsOf[id];
      });
      rowsByLayer[l] = ordered;
      assignPositions(ordered);
    });

    // A few refinement passes: bottom-up by children, then top-down by
    // parents again. Cheap (family trees are small) and this is exactly
    // the standard median/barycenter refinement — more passes have
    // sharply diminishing returns for graphs this size.
    for (var pass = 0; pass < 3; pass++) {
      for (var i = layers.length - 1; i >= 0; i--) {
        var l1 = layers[i];
        var ordered1 = sortRow(rowsByLayer[l1], function (id) {
          return childrenOf[id];
        });
        rowsByLayer[l1] = ordered1;
        assignPositions(ordered1);
      }
      for (var j = 0; j < layers.length; j++) {
        var l2 = layers[j];
        var ordered2 = sortRow(rowsByLayer[l2], function (id) {
          return parentsOf[id];
        });
        rowsByLayer[l2] = ordered2;
        assignPositions(ordered2);
      }
    }

    var order = {};
    layers.forEach(function (l) {
      rowsByLayer[l].forEach(function (id, index) {
        order[id] = index;
      });
    });
    return { order: order, rows: rowsByLayer };
  }

  // Parent-child edges grouped by exact parent set, so two siblings with
  // the same two parents share one drop-line from the couple instead of
  // each redrawing their own line from scratch (and a half-sibling with
  // a different second parent correctly gets its own group). Order of
  // `parents` within a group matches whichever child listed them first;
  // rendering doesn't depend on that order, only on the set.
  function groupChildrenByParents(ids, parentsOf) {
    var groups = [];
    var indexByKey = {};
    ids.forEach(function (id) {
      var parents = (parentsOf[id] || []).slice().filter(function (p) {
        return p;
      });
      if (!parents.length) return;
      var key = parents.slice().sort().join(" ");
      if (indexByKey[key] === undefined) {
        indexByKey[key] = groups.length;
        groups.push({ parents: parents, children: [] });
      }
      groups[indexByKey[key]].children.push(id);
    });
    return groups;
  }

  // Partner pairs, deduped (a person with two partners produces two
  // pairs, one per relationship — never a single 3-way group).
  function partnerPairs(ids, partnersOf) {
    var seen = {};
    var pairs = [];
    var idSet = {};
    ids.forEach(function (id) {
      idSet[id] = true;
    });
    ids.forEach(function (id) {
      (partnersOf[id] || []).forEach(function (partnerId) {
        if (!idSet[partnerId]) return;
        var key = id < partnerId ? id + " " + partnerId : partnerId + " " + id;
        if (seen[key]) return;
        seen[key] = true;
        pairs.push([id, partnerId].sort());
      });
    });
    return pairs;
  }

  // The full layout: every in-family id's {layer, x}, plus the edges to
  // draw and the connected-component every id belongs to. `x` is the
  // id's position WITHIN its own row (see orderRows) — converting that
  // to a pixel coordinate, and choosing how much horizontal room a row
  // needs (including the extra gap between two different `componentOf`
  // clusters landing on the same row), is the renderer's job, not this
  // module's; how many pixels a card takes is a presentation detail.
  // `rows` (per-layer id order) is exposed alongside `positions` so the
  // renderer can walk a row in sequence and detect exactly where a
  // component boundary falls, without having to re-derive it from
  // integer ranks.
  function layoutFamily(ids, parentsOf, partnersOf, childrenOf) {
    var layer = computeLayers(ids, parentsOf, partnersOf);
    var componentOf = connectedComponents(ids, parentsOf, partnersOf);
    var ordered = orderRows(ids, layer, parentsOf, childrenOf, partnersOf, componentOf);
    var positions = {};
    ids.forEach(function (id) {
      positions[id] = { layer: layer[id], x: ordered.order[id] };
    });
    return {
      positions: positions,
      rows: ordered.rows,
      componentOf: componentOf,
      partnerEdges: partnerPairs(ids, partnersOf),
      parentEdgeGroups: groupChildrenByParents(ids, parentsOf),
    };
  }

  return {
    computeLayers: computeLayers,
    groupByLayer: groupByLayer,
    coupleUnits: coupleUnits,
    connectedComponents: connectedComponents,
    orderRows: orderRows,
    groupChildrenByParents: groupChildrenByParents,
    partnerPairs: partnerPairs,
    layoutFamily: layoutFamily,
  };
});
