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

console.log(`\n${passed} passed`);
