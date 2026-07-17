// Plain-Node tests for app/static/js/fetch-json.js — no framework, no
// npm dependency, run via `node tests/js/fetch_json_test.mjs`. Wired
// into the pytest suite by test_tree_logic_js.py, which skips gracefully
// if node isn't on PATH.
import assert from "node:assert/strict";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const FetchJson = require("../../app/static/js/fetch-json.js");

// FetchJson.parse only ever touches `.ok` and `.json()` on the response
// it's given, matching the subset of the real fetch Response it needs.
function fakeResponse(ok, jsonValueOrRejection) {
  return {
    ok: ok,
    json: function () {
      if (jsonValueOrRejection instanceof Error) return Promise.reject(jsonValueOrRejection);
      return Promise.resolve(jsonValueOrRejection);
    },
  };
}

let passed = 0;
function check(name, fn) {
  return fn()
    .then(() => {
      passed++;
      console.log("ok -", name);
    });
}

async function main() {
  await check("resolves with the parsed body on an ok response", async () => {
    var data = await FetchJson.parse(fakeResponse(true, { id: "abc" }));
    assert.deepEqual(data, { id: "abc" });
  });

  await check("rejects with the server's error message on a non-ok response", async () => {
    await assert.rejects(
      FetchJson.parse(fakeResponse(false, { error: "Title is required." })),
      /Title is required\./
    );
  });

  await check("rejects with the fallback message when the body has no error field", async () => {
    await assert.rejects(
      FetchJson.parse(fakeResponse(false, {}), "Could not save."),
      /Could not save\./
    );
  });

  await check("rejects with the generic message when there's no fallback either", async () => {
    await assert.rejects(
      FetchJson.parse(fakeResponse(false, {})),
      /Something went wrong\. Please try again\./
    );
  });

  await check("a non-JSON error body still rejects with the fallback, not a JSON-parse error", async () => {
    await assert.rejects(
      FetchJson.parse(fakeResponse(false, new Error("Unexpected token <")), "Could not save."),
      /Could not save\./
    );
  });

  console.log(`\n${passed} passed`);
}

main();
