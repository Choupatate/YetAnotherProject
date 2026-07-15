// Plain-Node tests for app/static/js/safe-storage.js — no framework, no
// npm dependency, run via `node tests/js/safe_storage_test.mjs`. Wired
// into the pytest suite by test_tree_logic_js.py, which skips gracefully
// if node isn't on PATH.
import assert from "node:assert/strict";
import { createRequire } from "node:module";

// safe-storage.js reads/writes window.localStorage — fake just enough of
// both to exercise it outside a browser.
function makeFakeLocalStorage(overrides) {
  var store = {};
  return Object.assign(
    {
      getItem: (key) => (Object.prototype.hasOwnProperty.call(store, key) ? store[key] : null),
      setItem: (key, value) => {
        store[key] = String(value);
      },
      removeItem: (key) => {
        delete store[key];
      },
    },
    overrides
  );
}

global.window = { localStorage: makeFakeLocalStorage() };

const require = createRequire(import.meta.url);
const SafeStorage = require("../../app/static/js/safe-storage.js");

let passed = 0;
function check(name, fn) {
  fn();
  passed++;
  console.log("ok -", name);
}

check("getString/setString round-trip", () => {
  SafeStorage.setString("k", "v");
  assert.equal(SafeStorage.getString("k"), "v");
});

check("getString: null when the key was never set", () => {
  assert.equal(SafeStorage.getString("missing-key"), null);
});

check("removeString: clears a previously-set key", () => {
  SafeStorage.setString("gone", "x");
  SafeStorage.removeString("gone");
  assert.equal(SafeStorage.getString("gone"), null);
});

check("getJSON/setJSON round-trip an object", () => {
  SafeStorage.setJSON("obj", { a: 1, b: [2, 3] });
  assert.deepEqual(SafeStorage.getJSON("obj"), { a: 1, b: [2, 3] });
});

check("getJSON: null when nothing is stored", () => {
  assert.equal(SafeStorage.getJSON("missing-json-key"), null);
});

check("getJSON: null on malformed JSON instead of throwing", () => {
  window.localStorage.setItem("bad-json", "{not json");
  assert.equal(SafeStorage.getJSON("bad-json"), null);
});

check("getString: null when localStorage.getItem throws (private mode)", () => {
  var real = window.localStorage;
  window.localStorage = makeFakeLocalStorage({
    getItem: () => {
      throw new Error("SecurityError");
    },
  });
  try {
    assert.equal(SafeStorage.getString("anything"), null);
  } finally {
    window.localStorage = real;
  }
});

check("setString: doesn't throw when localStorage.setItem throws (quota)", () => {
  var real = window.localStorage;
  window.localStorage = makeFakeLocalStorage({
    setItem: () => {
      throw new Error("QuotaExceededError");
    },
  });
  try {
    assert.doesNotThrow(() => SafeStorage.setString("k", "v"));
  } finally {
    window.localStorage = real;
  }
});

console.log(`\n${passed} passed`);
