// fetch() never rejects on a 4xx/5xx response, and an error body isn't
// always valid JSON, so every caller needs the same "parse if possible,
// then check response.ok" shape. Centralized here instead of editor.js
// and instant.js each reimplementing it.
(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory();
  } else {
    root.FetchJson = factory();
  }
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  // `fallbackMessage` is used only when the response wasn't ok AND the
  // body carried no `error` field of its own.
  function parse(response, fallbackMessage) {
    return response
      .json()
      .catch(function () {
        return {};
      })
      .then(function (data) {
        if (!response.ok) {
          throw new Error(data.error || fallbackMessage || "Something went wrong. Please try again.");
        }
        return data;
      });
  }

  return { parse: parse };
});
