// localStorage can throw on getItem/setItem (private browsing, quota
// exceeded) and getItem can return non-JSON garbage, so every caller
// needs the same try/catch shape. Centralized here instead of tree.js,
// editor.js, and author-chips.js each reimplementing it independently.
(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory();
  } else {
    root.SafeStorage = factory();
  }
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  function getString(key) {
    try {
      return window.localStorage.getItem(key);
    } catch (e) {
      return null;
    }
  }

  function setString(key, value) {
    try {
      window.localStorage.setItem(key, value);
    } catch (e) {
      // Private mode, quota exceeded, etc. — the value just won't be
      // remembered next visit; nothing else depends on it.
    }
  }

  function removeString(key) {
    try {
      window.localStorage.removeItem(key);
    } catch (e) {}
  }

  function getJSON(key) {
    var raw = getString(key);
    if (!raw) return null;
    try {
      return JSON.parse(raw);
    } catch (e) {
      return null;
    }
  }

  function setJSON(key, value) {
    setString(key, JSON.stringify(value));
  }

  return {
    getString: getString,
    setString: setString,
    removeString: removeString,
    getJSON: getJSON,
    setJSON: setJSON,
  };
});
