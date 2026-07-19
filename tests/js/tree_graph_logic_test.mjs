// Plain-Node tests for app/static/js/tree-graph-logic.js — no framework,
// no npm dependency, run via `node tests/js/tree_graph_logic_test.mjs`.
// Wired into the pytest suite by test_tree_graph_logic_js.py, which skips
// gracefully if node isn't on PATH.
import assert from "node:assert/strict";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const TreeGraphLogic = require("../../app/static/js/tree-graph-logic.js");

let passed = 0;
function check(name, fn) {
  fn();
  passed++;
  console.log("ok -", name);
}

// Helper: build parentsOf/partnersOf/childrenOf maps from a small
// person-list DSL, mirroring how tree.js derives them from /api/tree's
// payload — {id, parents: [...], partners: [...]}.
function graphFrom(people) {
  const parentsOf = {};
  const partnersOf = {};
  const childrenOf = {};
  const ids = people.map((p) => p.id);
  people.forEach((p) => {
    parentsOf[p.id] = p.parents || [];
    partnersOf[p.id] = p.partners || [];
  });
  ids.forEach((id) => {
    (parentsOf[id] || []).forEach((parentId) => {
      childrenOf[parentId] = childrenOf[parentId] || [];
      childrenOf[parentId].push(id);
    });
  });
  return { ids, parentsOf, partnersOf, childrenOf };
}

function layerOf(positions, id) {
  return positions[id].layer;
}

// --- computeLayers -----------------------------------------------------------

check("computeLayers: a person with no recorded parents is layer 0", () => {
  const { ids, parentsOf, partnersOf } = graphFrom([{ id: "a" }]);
  const layer = TreeGraphLogic.computeLayers(ids, parentsOf, partnersOf);
  assert.equal(layer.a, 0);
});

check("computeLayers: a child is one layer below their deepest parent", () => {
  const { ids, parentsOf, partnersOf } = graphFrom([
    { id: "grandparent" },
    { id: "parent", parents: ["grandparent"] },
    { id: "child", parents: ["parent"] },
  ]);
  const layer = TreeGraphLogic.computeLayers(ids, parentsOf, partnersOf);
  assert.equal(layer.grandparent, 0);
  assert.equal(layer.parent, 1);
  assert.equal(layer.child, 2);
});

check("computeLayers: partners are pulled to the same layer even with asymmetric research depth", () => {
  // "odette" style case: one side of a couple has a recorded parent
  // (a great-grandmother), the other side has none recorded at all —
  // they must still land on the same layer, since a couple is one
  // generation on paper regardless of how far back either side's own
  // research happens to go.
  const { ids, parentsOf, partnersOf } = graphFrom([
    { id: "great-grandmother" },
    { id: "papi-jean", parents: ["great-grandmother"], partners: ["mamie-rose"] },
    { id: "mamie-rose", partners: ["papi-jean"] },
  ]);
  const layer = TreeGraphLogic.computeLayers(ids, parentsOf, partnersOf);
  assert.equal(layer["papi-jean"], 1);
  assert.equal(layer["mamie-rose"], 1);
});

check("computeLayers: pulling a partner down also pulls their own children down (fixed point)", () => {
  // mamie-rose (no recorded parents) has a child from a PRIOR marriage,
  // oncle-remi, before marrying papi-jean. Once mamie-rose is pulled to
  // papi-jean's layer, oncle-remi must drop a layer too, or he'd end up
  // sharing a layer with his own mother.
  const { ids, parentsOf, partnersOf } = graphFrom([
    { id: "great-grandmother" },
    { id: "papi-jean", parents: ["great-grandmother"], partners: ["mamie-rose"] },
    { id: "mamie-rose", partners: ["papi-jean"] },
    { id: "oncle-remi", parents: ["mamie-rose"] },
  ]);
  const layer = TreeGraphLogic.computeLayers(ids, parentsOf, partnersOf);
  assert.equal(layer["mamie-rose"], 1);
  assert.equal(layer["oncle-remi"], 2);
});

// --- coupleUnits ---------------------------------------------------------------

check("coupleUnits: a simple couple is one two-person unit", () => {
  const units = TreeGraphLogic.coupleUnits(["a", "b"], { a: ["b"], b: ["a"] });
  assert.equal(units.length, 1);
  assert.deepEqual(units[0].slice().sort(), ["a", "b"]);
});

check("coupleUnits: an unpartnered person gets their own single-person unit", () => {
  const units = TreeGraphLogic.coupleUnits(["a"], {});
  assert.deepEqual(units, [["a"]]);
});

check("coupleUnits: a remarriage chain orders with the shared person in the middle", () => {
  // Papa married Ex-Anne first, then Maman. In the row, Ex-Anne and
  // Maman must NOT end up adjacent to each other (they were never a
  // couple) -- Papa has to sit between them.
  const partnersOf = {
    "ex-anne": ["papa"],
    papa: ["ex-anne", "maman"],
    maman: ["papa"],
  };
  const units = TreeGraphLogic.coupleUnits(["ex-anne", "papa", "maman"], partnersOf);
  assert.equal(units.length, 1);
  const chain = units[0];
  assert.equal(chain.length, 3);
  assert.equal(chain[1], "papa");
  assert.deepEqual(chain.filter((id) => id !== "papa").sort(), ["ex-anne", "maman"]);
});

check("coupleUnits: a four-person remarriage chain keeps every neighbor a real couple", () => {
  // Ex-Marc -- Maman -- Papa -- Ex-Anne
  const partnersOf = {
    "ex-marc": ["maman"],
    maman: ["ex-marc", "papa"],
    papa: ["maman", "ex-anne"],
    "ex-anne": ["papa"],
  };
  const ids = ["ex-marc", "maman", "papa", "ex-anne"];
  const units = TreeGraphLogic.coupleUnits(ids, partnersOf);
  assert.equal(units.length, 1);
  const chain = units[0];
  assert.equal(chain.length, 4);
  for (let i = 0; i < chain.length - 1; i++) {
    const a = chain[i];
    const b = chain[i + 1];
    assert.ok(
      (partnersOf[a] || []).includes(b),
      `${a} and ${b} should be adjacent-and-partnered, chain was [${chain.join(", ")}]`
    );
  }
});

// --- connectedComponents ---------------------------------------------------------

check("connectedComponents: a single blood-linked family is all one component", () => {
  const { ids, parentsOf, partnersOf } = graphFrom([
    { id: "papi-georges", partners: ["mamie-lise"] },
    { id: "mamie-lise", partners: ["papi-georges"] },
    { id: "papa", parents: ["papi-georges", "mamie-lise"] },
    { id: "milo", parents: ["papa"] },
  ]);
  const componentOf = TreeGraphLogic.connectedComponents(ids, parentsOf, partnersOf);
  const values = new Set(Object.values(componentOf));
  assert.equal(values.size, 1);
});

check("connectedComponents: an isolated in-law couple gets a component of their own", () => {
  // Belle-Soeur Nadia and Beau-Frere Karim are partnered with each other
  // only -- no recorded parents, no link back to the blood family --
  // exactly the "husband of my stepsister" bug report: they still land
  // on layer 0 (see computeLayers), same as the true grandparents, with
  // nothing else to tell them apart.
  const { ids, parentsOf, partnersOf } = graphFrom([
    { id: "papi-georges", partners: ["mamie-lise"] },
    { id: "mamie-lise", partners: ["papi-georges"] },
    { id: "papa", parents: ["papi-georges", "mamie-lise"] },
    { id: "milo", parents: ["papa"] },
    { id: "belle-soeur-nadia", partners: ["beau-frere-karim"] },
    { id: "beau-frere-karim", partners: ["belle-soeur-nadia"] },
  ]);
  const componentOf = TreeGraphLogic.connectedComponents(ids, parentsOf, partnersOf);
  assert.equal(componentOf["papi-georges"], componentOf["milo"]);
  assert.equal(componentOf["belle-soeur-nadia"], componentOf["beau-frere-karim"]);
  assert.notEqual(componentOf["papi-georges"], componentOf["belle-soeur-nadia"]);
});

// --- orderRows / layoutFamily: component clustering -------------------------------

check("layoutFamily: an isolated in-law couple shares a layer with the grandparents but a different component", () => {
  const people = [
    { id: "papi-georges", partners: ["mamie-lise"] },
    { id: "mamie-lise", partners: ["papi-georges"] },
    { id: "papa", parents: ["papi-georges", "mamie-lise"] },
    { id: "milo", parents: ["papa"] },
    { id: "belle-soeur-nadia", partners: ["beau-frere-karim"] },
    { id: "beau-frere-karim", partners: ["belle-soeur-nadia"] },
  ];
  const { ids, parentsOf, partnersOf, childrenOf } = graphFrom(people);
  const result = TreeGraphLogic.layoutFamily(ids, parentsOf, partnersOf, childrenOf);

  // Same layer as the true grandparents (nothing in the data says
  // otherwise), but a distinct component.
  assert.equal(layerOf(result.positions, "belle-soeur-nadia"), 0);
  assert.equal(layerOf(result.positions, "papi-georges"), 0);
  assert.notEqual(result.componentOf["belle-soeur-nadia"], result.componentOf["papi-georges"]);

  // The in-law couple is grouped contiguously at the end of the row,
  // after every member of the main family's component -- never
  // interleaved between them.
  const row0 = result.rows[0];
  const mainFamilyIds = ["papi-georges", "mamie-lise"];
  const inLawIds = ["belle-soeur-nadia", "beau-frere-karim"];
  const lastMainIndex = Math.max(...mainFamilyIds.map((id) => row0.indexOf(id)));
  const firstInLawIndex = Math.min(...inLawIds.map((id) => row0.indexOf(id)));
  assert.ok(
    firstInLawIndex > lastMainIndex,
    `expected the in-law component after the main family in row0=[${row0.join(", ")}]`
  );
});

// --- closelyRelated ----------------------------------------------------------

check("closelyRelated: partners are closely related", () => {
  const { parentsOf, childrenOf, partnersOf } = graphFrom([
    { id: "a", partners: ["b"] },
    { id: "b", partners: ["a"] },
  ]);
  assert.equal(TreeGraphLogic.closelyRelated("a", "b", parentsOf, childrenOf, partnersOf), true);
});

check("closelyRelated: siblings sharing a parent are closely related", () => {
  // Marc and Papa are brothers -- both children of the same parent.
  const { parentsOf, childrenOf, partnersOf } = graphFrom([
    { id: "grandparent" },
    { id: "marc", parents: ["grandparent"] },
    { id: "papa", parents: ["grandparent"] },
  ]);
  assert.equal(
    TreeGraphLogic.closelyRelated("marc", "papa", parentsOf, childrenOf, partnersOf),
    true
  );
});

check("closelyRelated: co-parents sharing a child are closely related", () => {
  const { parentsOf, childrenOf, partnersOf } = graphFrom([
    { id: "ex-marc" },
    { id: "ex-anne" },
    { id: "leo", parents: ["ex-marc", "ex-anne"] },
  ]);
  assert.equal(
    TreeGraphLogic.closelyRelated("ex-marc", "ex-anne", parentsOf, childrenOf, partnersOf),
    true
  );
});

check("closelyRelated: cousins (no shared parent or child) are not closely related", () => {
  const { parentsOf, childrenOf, partnersOf } = graphFrom([
    { id: "marc" },
    { id: "julie" },
    { id: "papa" },
    { id: "maman" },
    { id: "ines", parents: ["marc", "julie"] },
    { id: "milo", parents: ["papa", "maman"] },
  ]);
  assert.equal(
    TreeGraphLogic.closelyRelated("ines", "milo", parentsOf, childrenOf, partnersOf),
    false
  );
});

check("closelyRelated: two unconnected grandparent couples are not closely related", () => {
  const { parentsOf, childrenOf, partnersOf } = graphFrom([
    { id: "papi-georges", partners: ["mamie-lise"] },
    { id: "mamie-lise", partners: ["papi-georges"] },
    { id: "papi-jean", partners: ["mamie-sylvie"] },
    { id: "mamie-sylvie", partners: ["papi-jean"] },
  ]);
  assert.equal(
    TreeGraphLogic.closelyRelated("mamie-lise", "papi-jean", parentsOf, childrenOf, partnersOf),
    false
  );
});

// --- groupChildrenByParents / partnerPairs --------------------------------------

check("groupChildrenByParents: siblings sharing both parents share one group", () => {
  const { ids, parentsOf } = graphFrom([
    { id: "papa" },
    { id: "maman" },
    { id: "milo", parents: ["papa", "maman"] },
    { id: "emma", parents: ["papa", "maman"] },
  ]);
  const groups = TreeGraphLogic.groupChildrenByParents(ids, parentsOf);
  assert.equal(groups.length, 1);
  assert.deepEqual(groups[0].children.slice().sort(), ["emma", "milo"]);
});

check("groupChildrenByParents: half-siblings with a different second parent get separate groups", () => {
  const { ids, parentsOf } = graphFrom([
    { id: "papa" },
    { id: "maman" },
    { id: "ex-anne" },
    { id: "milo", parents: ["papa", "maman"] },
    { id: "emma", parents: ["papa", "ex-anne"] },
  ]);
  const groups = TreeGraphLogic.groupChildrenByParents(ids, parentsOf);
  assert.equal(groups.length, 2);
  const forMilo = groups.find((g) => g.children.includes("milo"));
  const forEmma = groups.find((g) => g.children.includes("emma"));
  assert.notEqual(forMilo, forEmma);
  assert.deepEqual(forMilo.parents.slice().sort(), ["maman", "papa"]);
  assert.deepEqual(forEmma.parents.slice().sort(), ["ex-anne", "papa"]);
});

check("partnerPairs: a person with two partners produces two separate pairs", () => {
  const { ids, partnersOf } = graphFrom([
    { id: "papa", partners: ["ex-anne", "maman"] },
    { id: "ex-anne", partners: ["papa"] },
    { id: "maman", partners: ["papa"] },
  ]);
  const pairs = TreeGraphLogic.partnerPairs(ids, partnersOf);
  assert.equal(pairs.length, 2);
  const asSets = pairs.map((p) => p.slice().sort());
  assert.deepEqual(
    asSets.sort(),
    [["ex-anne", "papa"], ["maman", "papa"]].map((p) => p.sort())
  );
});

// --- layoutFamily: the full pipeline, no duplication guarantee ------------------

check("layoutFamily: every person gets exactly one position, however many marriages", () => {
  // The motivating case: a blended family with two remarriages (one per
  // side of Milo's parents) plus a re-married uncle -- the family-chart
  // based "Everyone" view duplicated Papa, Maman, AND Milo here. This
  // layout must position every person exactly once.
  const people = [
    { id: "papi-georges", partners: ["mamie-lise"] },
    { id: "mamie-lise", partners: ["papi-georges"] },
    { id: "papi-jean", partners: ["mamie-sylvie"] },
    { id: "mamie-sylvie", partners: ["papi-jean"] },
    { id: "papa", parents: ["papi-georges", "mamie-lise"], partners: ["ex-anne", "maman"] },
    { id: "ex-anne", partners: ["papa"] },
    { id: "maman", parents: ["papi-jean", "mamie-sylvie"], partners: ["ex-marc", "papa"] },
    { id: "ex-marc", partners: ["maman"] },
    { id: "emma", parents: ["papa", "ex-anne"] },
    { id: "leo", parents: ["maman", "ex-marc"] },
    { id: "milo", parents: ["papa", "maman"] },
  ];
  const { ids, parentsOf, partnersOf, childrenOf } = graphFrom(people);
  const result = TreeGraphLogic.layoutFamily(ids, parentsOf, partnersOf, childrenOf);

  assert.equal(Object.keys(result.positions).length, ids.length);
  ids.forEach((id) => {
    assert.ok(result.positions[id], `${id} should have a position`);
    assert.equal(typeof result.positions[id].layer, "number");
    assert.equal(typeof result.positions[id].x, "number");
  });

  // No two people on the same layer share the same x.
  const byLayer = {};
  ids.forEach((id) => {
    const { layer, x } = result.positions[id];
    byLayer[layer] = byLayer[layer] || new Set();
    assert.ok(!byLayer[layer].has(x), `layer ${layer} has two people at x=${x}`);
    byLayer[layer].add(x);
  });

  // Generations land where expected.
  assert.equal(layerOf(result.positions, "papi-georges"), 0);
  assert.equal(layerOf(result.positions, "papa"), 1);
  assert.equal(layerOf(result.positions, "maman"), 1);
  assert.equal(layerOf(result.positions, "ex-anne"), 1);
  assert.equal(layerOf(result.positions, "ex-marc"), 1);
  assert.equal(layerOf(result.positions, "milo"), 2);
  assert.equal(layerOf(result.positions, "emma"), 2);
  assert.equal(layerOf(result.positions, "leo"), 2);

  // Milo's parent-edge group is exactly [papa, maman] -> [milo], distinct
  // from emma's and leo's groups.
  const miloGroup = result.parentEdgeGroups.find((g) => g.children.includes("milo"));
  assert.deepEqual(miloGroup.parents.slice().sort(), ["maman", "papa"]);
  // One group per distinct parent-set: georges+lise -> papa,
  // jean+sylvie -> maman, papa+ex-anne -> emma, maman+ex-marc -> leo,
  // papa+maman -> milo.
  assert.equal(result.parentEdgeGroups.length, 5);
});

check("layoutFamily: a two-branch family with no remarriages (regression baseline)", () => {
  const people = [
    { id: "papi-georges", partners: ["mamie-lise"] },
    { id: "mamie-lise", partners: ["papi-georges"] },
    { id: "papi-jean", partners: ["mamie-anne"] },
    { id: "mamie-anne", partners: ["papi-jean"] },
    { id: "papa", parents: ["papi-georges", "mamie-lise"], partners: ["maman"] },
    { id: "maman", parents: ["papi-jean", "mamie-anne"], partners: ["papa"] },
    { id: "milo", parents: ["papa", "maman"] },
  ];
  const { ids, parentsOf, partnersOf, childrenOf } = graphFrom(people);
  const result = TreeGraphLogic.layoutFamily(ids, parentsOf, partnersOf, childrenOf);
  assert.equal(Object.keys(result.positions).length, 7);
  assert.equal(result.partnerEdges.length, 3);
  assert.equal(result.parentEdgeGroups.length, 3);
});

// --- poolAdjacentViolators / assignPixelPositions -------------------------------

check("poolAdjacentViolators: already-monotone input is unchanged", () => {
  assert.deepEqual(
    TreeGraphLogic.poolAdjacentViolators([1, 2, 3], [1, 1, 1]),
    [1, 2, 3]
  );
});

check("poolAdjacentViolators: a violating pair pools to its weighted mean", () => {
  // targets [4, 0] with weights [1, 3] -> pooled value (4*1 + 0*3)/4 = 1.
  assert.deepEqual(TreeGraphLogic.poolAdjacentViolators([4, 0], [1, 3]), [1, 1]);
});

check("poolAdjacentViolators: output is always non-decreasing", () => {
  const out = TreeGraphLogic.poolAdjacentViolators([5, 1, 4, 0, 3], [1, 2, 1, 1, 2]);
  for (let i = 1; i < out.length; i++) {
    assert.ok(out[i] >= out[i - 1], `${out.join(",")} decreases at ${i}`);
  }
});

const GAPS = { cardWidth: 176, gapPartner: 10, gapClose: 28, gapSame: 96, gapCross: 200 };

function assignFor(people) {
  const { ids, parentsOf, partnersOf, childrenOf } = graphFrom(people);
  const layout = TreeGraphLogic.layoutFamily(ids, parentsOf, partnersOf, childrenOf);
  const assigned = TreeGraphLogic.assignPixelPositions(
    layout.rows, parentsOf, childrenOf, partnersOf, layout.componentOf, GAPS
  );
  return { ids, parentsOf, partnersOf, childrenOf, layout, assigned };
}

function centerIn(assigned, id) {
  return assigned.xById[id] + GAPS.cardWidth / 2;
}

check("assignPixelPositions: parents sit exactly centered over their children when nothing conflicts", () => {
  const { assigned } = assignFor([
    { id: "papi", partners: ["mamie"] },
    { id: "mamie", partners: ["papi"] },
    { id: "papa", parents: ["papi", "mamie"], partners: ["maman"] },
    { id: "maman", partners: ["papa"] },
    { id: "milo", parents: ["papa", "maman"] },
    { id: "emma", parents: ["papa", "maman"] },
  ]);
  const coupleCenter = (centerIn(assigned, "papa") + centerIn(assigned, "maman")) / 2;
  const kidsCenter = (centerIn(assigned, "milo") + centerIn(assigned, "emma")) / 2;
  assert.ok(
    Math.abs(coupleCenter - kidsCenter) < 0.5,
    `couple at ${coupleCenter}, children centroid at ${kidsCenter}`
  );
  // The grandparents center over their CHILDREN's centroid — here just
  // papa (maman married in, she's not their child) — so the trunk from
  // their midpoint drops vertically onto the blood child's card, the
  // classic pedigree presentation. NOT over the papa+maman couple
  // midpoint, which would put the trunk halfway between papa and his
  // wife.
  const gpCenter = (centerIn(assigned, "papi") + centerIn(assigned, "mamie")) / 2;
  assert.ok(
    Math.abs(gpCenter - centerIn(assigned, "papa")) < 0.5,
    `grandparent midpoint at ${gpCenter}, blood child at ${centerIn(assigned, "papa")}`
  );
});

check("assignPixelPositions: partners are exactly gapPartner apart, and min gaps never violated", () => {
  const { assigned, layout, partnersOf } = assignFor([
    { id: "papi-a", partners: ["mamie-a"] },
    { id: "mamie-a", partners: ["papi-a"] },
    { id: "papi-b", partners: ["mamie-b"] },
    { id: "mamie-b", partners: ["papi-b"] },
    { id: "papa", parents: ["papi-a", "mamie-a"], partners: ["maman"] },
    { id: "maman", parents: ["papi-b", "mamie-b"], partners: ["papa"] },
    { id: "milo", parents: ["papa", "maman"] },
    { id: "emma", parents: ["papa", "maman"] },
  ]);
  // partner spacing exact
  assert.equal(
    Math.abs(assigned.xById["mamie-a"] - assigned.xById["papi-a"]),
    GAPS.cardWidth + GAPS.gapPartner
  );
  // no same-row pair closer than the smallest tier
  Object.keys(layout.rows).forEach((l) => {
    const row = layout.rows[l].slice().sort((a, b) => assigned.xById[a] - assigned.xById[b]);
    for (let i = 1; i < row.length; i++) {
      const gap = assigned.xById[row[i]] - (assigned.xById[row[i - 1]] + GAPS.cardWidth);
      assert.ok(gap >= GAPS.gapPartner - 0.001, `gap ${gap} between ${row[i - 1]} and ${row[i]}`);
    }
  });
});

check("assignPixelPositions: an isolated couple keeps the cross-component gap from the main family", () => {
  const { assigned, layout } = assignFor([
    { id: "papi", partners: ["mamie"] },
    { id: "mamie", partners: ["papi"] },
    { id: "papa", parents: ["papi", "mamie"] },
    { id: "milo", parents: ["papa"] },
    { id: "nadia", partners: ["karim"] },
    { id: "karim", partners: ["nadia"] },
  ]);
  const row0 = layout.rows[0].slice().sort((a, b) => assigned.xById[a] - assigned.xById[b]);
  // main family first, isolated couple after with the widest gap
  const lastMain = Math.max(assigned.xById["papi"], assigned.xById["mamie"]) + GAPS.cardWidth;
  const firstIsolated = Math.min(assigned.xById["nadia"], assigned.xById["karim"]);
  assert.ok(
    firstIsolated - lastMain >= GAPS.gapCross - 0.001,
    `cross-component gap ${firstIsolated - lastMain} < ${GAPS.gapCross} in row [${row0.join(", ")}]`
  );
});

check("assignPixelPositions: deterministic — identical output across runs", () => {
  const people = [
    { id: "papi", partners: ["mamie"] },
    { id: "mamie", partners: ["papi"] },
    { id: "papa", parents: ["papi", "mamie"], partners: ["maman"] },
    { id: "maman", partners: ["papa"] },
    { id: "milo", parents: ["papa", "maman"] },
  ];
  const a = assignFor(people).assigned;
  const b = assignFor(people).assigned;
  assert.deepEqual(a, b);
});

// --- assignLanes -----------------------------------------------------------------

check("assignLanes: non-overlapping extents all share lane 0", () => {
  const lanes = TreeGraphLogic.assignLanes(
    [{ left: 0, right: 100 }, { left: 200, right: 300 }, { left: 400, right: 500 }],
    24
  );
  assert.deepEqual(lanes, [0, 0, 0]);
});

check("assignLanes: overlapping extents get distinct lanes", () => {
  const extents = [
    { left: 0, right: 300 },
    { left: 100, right: 400 },
    { left: 200, right: 500 },
  ];
  const lanes = TreeGraphLogic.assignLanes(extents, 24);
  assert.equal(new Set(lanes).size, 3, `expected 3 distinct lanes, got [${lanes.join(", ")}]`);
});

check("assignLanes: a lane is reused once its previous extent is clear of the gap", () => {
  const lanes = TreeGraphLogic.assignLanes(
    [
      { left: 0, right: 100 },
      { left: 50, right: 200 }, // overlaps first -> lane 1
      { left: 150, right: 300 }, // clear of first (100+24 <= 150) -> back on lane 0
    ],
    24
  );
  assert.deepEqual(lanes, [0, 1, 0]);
});

check("assignLanes: same-lane extents never come within minGap of each other", () => {
  const extents = [
    { left: 0, right: 250 },
    { left: 40, right: 120 },
    { left: 130, right: 320 },
    { left: 260, right: 380 },
    { left: 300, right: 520 },
  ];
  const minGap = 24;
  const lanes = TreeGraphLogic.assignLanes(extents, minGap);
  for (let i = 0; i < extents.length; i++) {
    for (let j = i + 1; j < extents.length; j++) {
      if (lanes[i] !== lanes[j]) continue;
      const gap = Math.max(
        extents[j].left - extents[i].right,
        extents[i].left - extents[j].right
      );
      assert.ok(gap >= minGap, `extents ${i} and ${j} share lane ${lanes[i]} but gap is ${gap}`);
    }
  }
});

console.log(`\n${passed} passed`);
