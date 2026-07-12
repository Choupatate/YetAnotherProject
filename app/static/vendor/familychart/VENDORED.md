# Vendored: family-chart 0.9.0 + d3 7.9.0

- `family-chart.min.js` — family-chart v0.9.0 (https://www.npmjs.com/package/family-chart),
  MIT/ISC licensed, UMD build, pinned. Audited before vendoring: the bundle
  contains no fetch/XMLHttpRequest/sendBeacon calls and no analytics — it
  makes zero network requests.
- `family-chart.css` — the library's stylesheet, same version.
- `../d3/d3.min.js` — D3 v7.9.0 (ISC), required peer of family-chart.

Do not upgrade casually: the pinned pair is known-good and the app must
keep working offline forever. If an upgrade is ever needed, re-run the
no-network audit (grep the new bundle for fetch/XMLHttpRequest/sendBeacon/
https URLs) before replacing these files.
