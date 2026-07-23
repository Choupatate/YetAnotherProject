// Reads the CSRF token base.html embeds in a <meta> tag and attaches it as
// the X-CSRFToken header Flask-WTF's CSRFProtect checks on JSON/fetch()
// requests (a native <form> instead carries a hidden csrf_token input —
// see _macros.html and every server-rendered form template).
(function () {
  function withToken(options) {
    var meta = document.querySelector('meta[name="csrf-token"]');
    var token = meta ? meta.getAttribute("content") : "";
    var headers = Object.assign({}, (options && options.headers) || {}, { "X-CSRFToken": token });
    return Object.assign({}, options || {}, { headers: headers });
  }

  window.CsrfFetch = { withToken: withToken };
})();
