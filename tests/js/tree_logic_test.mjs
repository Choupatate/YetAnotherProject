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

check("chainToLevel: walks the first parent at each new level", () => {
  const chain = TreeLogic.chainToLevel([], 2, "milo", parentsOf, exists);
  assert.deepEqual(chain, ["papa", "papi-jean"]);
});

check("chainToLevel: keeps an already-chosen branch when going deeper", () => {
  // Simulate the user having switched to the maternal branch at level 1,
  // then asking to go one generation deeper on that same branch.
  const chain = TreeLogic.chainToLevel(["papa", "papi-paul"], 2, "milo", parentsOf, exists);
  assert.deepEqual(chain, ["papa", "papi-paul"]);
});

check("chainToLevel: stops short when a branch runs out of paper trail", () => {
  // papi-paul has no recorded parents, so "Whole family" from his branch
  // can't go past level 2 — this used to silently jump to an unrelated
  // ancestor on the other branch instead of stopping honestly.
  const chain = TreeLogic.chainToLevel(["papa", "papi-paul"], 3, "milo", parentsOf, exists);
  assert.deepEqual(chain, ["papa", "papi-paul"]);
});

check("chainToLevel: truncates when asked for a shallower level", () => {
  const chain = TreeLogic.chainToLevel(["papa", "papi-jean", "odette"], 1, "milo", parentsOf, exists);
  assert.deepEqual(chain, ["papa"]);
});

check("chainToLevel: level 0 is always the empty chain", () => {
  assert.deepEqual(TreeLogic.chainToLevel(["papa"], 0, "milo", parentsOf, exists), []);
});

check("levelLabel: level 1 has its own label, distinct from level 2", () => {
  assert.equal(TreeLogic.levelLabel(1, 3), "Parents’ branch");
  assert.notEqual(TreeLogic.levelLabel(1, 3), TreeLogic.levelLabel(2, 3));
});

check("ancestorPath: focusId maps to itself as the empty chain", () => {
  assert.deepEqual(TreeLogic.ancestorPath("milo", "milo", parentsOf, exists), []);
});

check("ancestorPath: finds the real chain to an ancestor on the paternal side", () => {
  assert.deepEqual(TreeLogic.ancestorPath("milo", "papi-jean", parentsOf, exists), ["papa", "papi-jean"]);
});

check("ancestorPath: finds the real chain to an ancestor on the maternal side", () => {
  // This is the branch-chip bug: switching to a maternal ancestor from a
  // paternal one must rebuild the WHOLE chain, not just swap the last
  // entry onto the still-paternal "papa".
  assert.deepEqual(TreeLogic.ancestorPath("milo", "papi-paul", parentsOf, exists), ["maman", "papi-paul"]);
});

check("ancestorPath: walks through multiple generations", () => {
  assert.deepEqual(TreeLogic.ancestorPath("milo", "odette", parentsOf, exists), ["papa", "papi-jean", "odette"]);
});

check("ancestorPath: null when the target isn't actually an ancestor", () => {
  assert.equal(TreeLogic.ancestorPath("milo", "cousin-theo", parentsOf, exists), null);
});

check("isValidChain: a real ancestor chain is valid", () => {
  assert.equal(TreeLogic.isValidChain(["papa", "papi-jean"], "milo", parentsOf, exists), true);
});

check("isValidChain: the empty chain is trivially valid", () => {
  assert.equal(TreeLogic.isValidChain([], "milo", parentsOf, exists), true);
});

check("isValidChain: false when a link isn't actually parent/child", () => {
  // papi-paul is maman's parent, not papa's — this is exactly the shape
  // a stale localStorage chain could have after a parent link is edited.
  assert.equal(TreeLogic.isValidChain(["papa", "papi-paul"], "milo", parentsOf, exists), false);
});

check("isValidChain: false when an entry no longer exists", () => {
  assert.equal(TreeLogic.isValidChain(["papa", "ghost"], "milo", parentsOf, exists), false);
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

console.log(`\n${passed} passed`);
