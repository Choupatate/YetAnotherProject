// Plain-Node tests for app/static/js/tree-logic.js — no framework, no
// npm dependency, run via `node tests/js/tree_logic_test.mjs`. Wired into
// the pytest suite by test_tree_logic_js.py, which skips gracefully if
// node isn't on PATH.
import assert from "node:assert/strict";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const TreeLogic = require("../../app/static/js/tree-logic.js");

// Fixture: three generations plus one great-grandmother on the paternal
// side only, matching the family used to verify the /tree UI by hand.
//
//                          odette
//                            |
//   papi-jean == mamie-rose     papi-paul == mamie-marta
//         |                              |
//    +----+----+                   +-----+-----+
//    papa    oncle-remi          maman      tante-lea
//     \_________________ +milo__/
//                          |
//                    (oncle-remi's child)
//                      cousin-theo

const parentsOf = {
  "papi-jean": ["odette"],
  papa: ["papi-jean", "mamie-rose"],
  "oncle-remi": ["papi-jean", "mamie-rose"],
  maman: ["papi-paul", "mamie-marta"],
  "tante-lea": ["papi-paul", "mamie-marta"],
  milo: ["papa", "maman"],
  "cousin-theo": ["oncle-remi"],
};

const partnersOf = {
  "papi-jean": ["mamie-rose"],
  "mamie-rose": ["papi-jean"],
  "papi-paul": ["mamie-marta"],
  "mamie-marta": ["papi-paul"],
  papa: ["maman"],
  maman: ["papa"],
};

const allIds = new Set([
  "odette", "papi-jean", "mamie-rose", "papi-paul", "mamie-marta",
  "papa", "oncle-remi", "maman", "tante-lea", "milo", "cousin-theo",
]);
const exists = (id) => allIds.has(id);

let passed = 0;
function check(name, fn) {
  fn();
  passed++;
  console.log("ok -", name);
}

check("ancestorLevels: level 0 is the direct parents", () => {
  const levels = TreeLogic.ancestorLevels("milo", parentsOf, exists);
  assert.deepEqual(levels[0].slice().sort(), ["maman", "papa"]);
});

check("ancestorLevels: level 1 mixes both branches' grandparents", () => {
  const levels = TreeLogic.ancestorLevels("milo", parentsOf, exists);
  assert.deepEqual(
    levels[1].slice().sort(),
    ["mamie-marta", "mamie-rose", "papi-jean", "papi-paul"]
  );
});

check("ancestorLevels: stops where the paper trail stops", () => {
  const levels = TreeLogic.ancestorLevels("milo", parentsOf, exists);
  assert.equal(levels.length, 3); // parents, grandparents, one great-grandmother
  assert.deepEqual(levels[2], ["odette"]);
});

check("ancestorLevels: a person with no recorded parents has no levels", () => {
  assert.deepEqual(TreeLogic.ancestorLevels("odette", parentsOf, exists), []);
});

check("coupleGroups: pairs partners into one chip per couple", () => {
  const level1 = TreeLogic.ancestorLevels("milo", parentsOf, exists)[1];
  const groups = TreeLogic.coupleGroups(level1, partnersOf);
  assert.equal(groups.length, 2);
  const asSets = groups.map((g) => g.slice().sort());
  assert.deepEqual(
    asSets.sort(),
    [["mamie-marta", "papi-paul"], ["mamie-rose", "papi-jean"]].map((g) => g.sort())
  );
});

check("coupleGroups: an unpartnered ancestor gets its own single-person group", () => {
  const groups = TreeLogic.coupleGroups(["odette"], partnersOf);
  assert.deepEqual(groups, [["odette"]]);
});

check("levelLabel: 0 is Direct line, deepest is Whole family", () => {
  assert.equal(TreeLogic.levelLabel(0, 3), "Direct line");
  assert.equal(TreeLogic.levelLabel(3, 3), "Whole family");
});

check("levelLabel: intermediate levels step through the great- prefix", () => {
  assert.equal(TreeLogic.levelLabel(2, 4), "Grandparents’ branch");
  assert.equal(TreeLogic.levelLabel(3, 4), "Great-grandparents’ branch");
  assert.equal(TreeLogic.levelLabel(4, 5), "Great-great-grandparents’ branch");
});

check("levelLabel: level 1 has its own label, distinct from level 2", () => {
  assert.equal(TreeLogic.levelLabel(1, 3), "Parents’ branch");
  assert.notEqual(TreeLogic.levelLabel(1, 3), TreeLogic.levelLabel(2, 3));
});

check("coupleGroups: paternal and maternal branches land in separate groups (multi-panel view)", () => {
  // The two grandparent couples must come back as two distinct groups so
  // tree.js can render one mini-chart panel per branch, side by side,
  // instead of the old single-branch switcher.
  const level1 = TreeLogic.ancestorLevels("milo", parentsOf, exists)[1];
  const groups = TreeLogic.coupleGroups(level1, partnersOf);
  const paternal = groups.find((g) => g.indexOf("papi-jean") !== -1);
  const maternal = groups.find((g) => g.indexOf("papi-paul") !== -1);
  assert.notEqual(paternal, maternal);
  assert.deepEqual(paternal.slice().sort(), ["mamie-rose", "papi-jean"]);
  assert.deepEqual(maternal.slice().sort(), ["mamie-marta", "papi-paul"]);
});

check("ancestorLevels: the same ancestor can appear at two depths (pedigree collapse)", () => {
  // child's two parents are p1 and p2; p1's parent is g, and p2's
  // parent is y, who is ALSO g's child — so g is both child's
  // grandparent (via p1) and great-grandparent (via p2 -> y). A global
  // "seen" set would drop the second occurrence; both must show up.
  const collapseParentsOf = { child: ["p1", "p2"], p1: ["g"], p2: ["y"], y: ["g"] };
  const collapseExists = (id) => ["child", "p1", "p2", "g", "y"].includes(id);
  const levels = TreeLogic.ancestorLevels("child", collapseParentsOf, collapseExists);
  assert.ok(levels[1].indexOf("g") !== -1, "g should appear as a grandparent");
  assert.ok(levels[2].indexOf("g") !== -1, "g should ALSO appear as a great-grandparent");
});

check("rootAncestors: one representative per blood lineage, not per parentless person", () => {
  // odette and mamie-marta/papi-paul are genuine independent roots. Also
  // parentless: mamie-rose — but her partner papi-jean has a recorded
  // parent (odette), so she'll already be pulled in as his auto-added
  // spouse once odette's lineage is rooted; she must NOT come back as a
  // second, separate root (that would draw papa/oncle-remi/milo's whole
  // subtree a second time for no reason).
  const roots = TreeLogic.rootAncestors(Array.from(allIds), parentsOf, partnersOf);
  assert.deepEqual(roots.slice().sort(), ["odette", "papi-paul"]);
});

check("rootAncestors: a couple where neither partner has recorded parents dedupes to one root", () => {
  const ids = ["georges", "lise", "papa"];
  const pOf = { papa: ["georges", "lise"] };
  const sOf = { georges: ["lise"], lise: ["georges"] };
  const roots = TreeLogic.rootAncestors(ids, pOf, sOf);
  assert.deepEqual(roots, ["georges"]);
});

check("rootAncestors: an unpartnered ancestor with no recorded parents is always a root", () => {
  const roots = TreeLogic.rootAncestors(["odette", "papi-jean"], parentsOf, partnersOf);
  assert.deepEqual(roots, ["odette"]);
});

console.log(`\n${passed} passed`);
