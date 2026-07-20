# CLAUDE.md

Guidance for Claude Code (or any AI agent) working in this repository.

## What this is

Storybook is a private, self-hosted memory journal: a parent writes stories
(text + photos) for their child, and the family reads them later as a
chronological timeline and book-like story pages. It's a Flask app with
**no database** — every story is a folder of a markdown file (with
frontmatter) plus its images/audio, living under `stories/`. Delete the app
entirely and the `stories/` folder is still fully readable with a text
editor and a file browser.

Read these before making non-trivial changes, in this order:
- `README.md` — how to run it, configuration, feature tour.
- `PLAN.md` — the original design spec the app was built from.
- `FEATURES.md` — the running log of every feature added since, in F-number
  order (F0, F1, F2, ...). Each entry documents the feature, the design
  decisions, and often the edge cases handled. **This is the most detailed
  and current source of truth for how a given feature actually behaves.**
- `REVIEW.md` — a past production-readiness audit and the fixes it drove.
  Historical record, not necessarily reflecting the current code.

When you finish a feature or fix worth documenting, add a section to
`FEATURES.md` following the existing style rather than leaving it
undocumented.

## Philosophy (do not violate these without discussing it first)

- **The data outlives the app.** Plain markdown + image files, human-readable
  forever. Never introduce a database or a binary/proprietary storage format.
- **No runtime network dependencies.** Everything needed to run is vendored
  under `app/static/vendor/` or served locally — no CDN links, no external
  fonts, no analytics beacons. (`editor.js` explicitly disables Toast UI's
  `usageStatistics` ping for this reason — never re-enable it.) If you vendor
  a new third-party library, document its version and provenance in a banner
  comment the way `toastui-editor-all.min.js` does.
- **Boring, minimal dependencies; no build step; no JS framework.** Plain
  `<script>` tags, UMD modules where code needs to run in both the browser
  and Node (see `tree-logic.js`, `safe-storage.js`). Don't introduce a
  bundler, transpiler, or framework to solve a problem that plain JS/CSS
  already solves.
- **Mobile-first.** Every screen, especially the editor, must work from a
  phone. Check narrow viewports, not just desktop, for any UI change.
- **Book, not blog.** No feeds, reactions, comment sections, or engagement
  mechanics. Restraint and typography over features.
- Deliberately out of scope (see README's "Ideas for later"):
  comments/reactions, search, tags, RSS, email, video, encryption at rest,
  i18n, offline support/service worker, story deletion. Don't add these
  speculatively — if one becomes worth doing, it belongs in a discussion
  first, not a surprise PR. (Multi-user accounts were on this list too,
  until F19 shipped them as an opt-in feature — see `app/accounts.py`
  below.)

## Architecture

- `app/__init__.py` — `create_app()` factory; all config comes from
  `STORYBOOK_*` env vars (see `.env.example`), nothing is hardcoded.
- `app/auth.py` — login/logout and the `@login_required`/`@admin_required`/
  `@delegate_required` decorators, gating every page and API route except
  `/manifest.webmanifest` (must stay public for home-screen install) and
  `/login` itself. Two modes, selected by `STORYBOOK_ACCOUNTS` (F19): off
  (default) is the original single shared password, no accounts, no roles;
  on switches to per-person username/password accounts (`app/accounts.py`,
  admin/family roles) plus an optional narrower delegate session
  (`app/write_links.py`) for a bearer-token link that only unlocks
  submitting one attributed story, nothing else.
- `app/storage.py` — **all filesystem read/write for stories lives here**.
  Pure functions that take `stories_dir` explicitly (no hidden global
  state), which is what makes them easy to test against a tmp directory.
  This is the module to read before touching how stories/people/images are
  persisted.
- `app/people.py` / `app/kinship.py` — the "cast of the book" (F14) and the
  family tree graph + kinship-label computation (F18) that sits on top of
  `people.py`'s data.
- `app/routes_pages.py` — HTML page routes (Blueprint `pages`).
- `app/routes_api.py` — JSON API routes (Blueprint `api`, under `/api`),
  consumed by the editor and tree JS. Every mutating endpoint validates its
  inputs explicitly (see the `_validate_*` helpers) rather than trusting the
  client — follow that pattern for any new endpoint.
- `app/epub.py`, `app/rendering.py`, `app/dates.py`, `app/prompts.py` — book
  export, markdown-to-HTML rendering, age-label computation, and story
  prompts, respectively.
- `app/static/js/tree-logic.js` — pure, dependency-free tree math (BFS
  ancestor walks, chain validation) for the family-chart-based views;
  `tree-graph-logic.js` is the same idea for the "Everyone" view's own DAG
  layout (generation layering, row ordering, edge grouping). Both are
  unit-tested directly under Node (`tests/js/tree_logic_test.mjs`,
  `tests/js/tree_graph_logic_test.mjs`), alongside `safe-storage.js` (the
  localStorage wrapper) and `fetch-json.js` (the shared fetch/JSON-response
  helper) and their own test files. Keep new dependency-free logic in a
  module like these rather than inline in `tree.js`/`editor.js`, so it
  stays testable without a browser.
- `app/static/vendor/` — vendored third-party JS (family-chart, d3, Toast UI
  Editor). Treat as read-only/generated; if you need to update one, redo the
  vendoring process documented in its banner comment, don't hand-edit it.

## Data-safety conventions (follow these for any new filesystem/upload code)

- Never build a filesystem path from user input without validating it first.
  Use/extend `storage.is_valid_story_id` / `is_valid_filename` (strict
  allowlist regexes, reject `..`) — see `story_media`/`person_media` in
  `routes_pages.py` for the pattern: validate, then check existence, then
  serve via `send_from_directory`.
- Uploaded images are always re-encoded with Pillow (`storage.save_image_to`)
  before being written to disk — never save an uploaded file's bytes
  verbatim. Uploaded audio is restricted to an explicit extension allowlist
  (`MEMO_ALLOWED_EXTENSIONS`).
- Writes to `index.md` go through a write-tmp-then-`os.replace` pattern for
  atomicity, and `save_story` snapshots the previous version into
  `.versions/` first. Preserve both properties in any code that writes story
  content.
- Zip extraction (`import_backup`) validates every member path before
  extracting anything (zip-slip protection) and is all-or-nothing (a
  collision aborts with nothing written). Keep that all-or-nothing guarantee
  if you touch import/export.
- `story_media`/`person_media` set a one-year `Cache-Control` max-age on
  `.jpg`/`.png` files (`_media_max_age` in `routes_pages.py`), safe only
  because `save_image_to` never overwrites or reuses a photo's filename.
  Voice memos are deliberately excluded from that long cache: `delete_memo`
  can free up a `memo-NNN` number that a later upload then reuses for
  different audio, so their filename isn't a stable cache key. If you add a
  new media type, work out whether its filename is truly immutable before
  putting it in `_LONG_CACHE_EXTENSIONS`.

## Running it

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then edit STORYBOOK_PASSWORD and STORYBOOK_SECRET_KEY
python run.py           # dev server, debug on, http://127.0.0.1:5000
```

`STORYBOOK_SECRET_KEY` (not `SECRET_KEY`) is the Flask session-signing key;
the app refuses to start without one once `STORYBOOK_PASSWORD` is set. See
`.env.example` for every other `STORYBOOK_*` variable.

## Testing

```bash
pytest              # full suite: Python tests + four JS test files run via subprocess
node tests/js/tree_logic_test.mjs         # pure-function tree logic tests directly
node tests/js/tree_graph_logic_test.mjs   # "Everyone" view DAG layout tests directly
node tests/js/safe_storage_test.mjs       # localStorage wrapper tests directly
node tests/js/fetch_json_test.mjs         # fetch/JSON-response helper tests directly
```

- Python tests live in `tests/*.py`, one file per feature area; `conftest.py`
  has the shared app/client fixtures.
- Client-side logic that can be written dependency-free (no DOM) belongs in
  a UMD module under `app/static/js/` with a matching `tests/js/*.mjs` file,
  wired into pytest via a `subprocess.run(["node", ...])` wrapper
  (`pytest.mark.skipif` if Node isn't available) — see
  `tests/test_tree_logic_js.py` for the pattern. Don't write DOM-dependent
  logic that can't be unit tested this way if a dependency-free version is
  feasible.
- There is no browser/E2E test suite in CI. For UI changes, manually verify
  in a real browser (Playwright is preinstalled in this environment at
  `/opt/pw-browsers/chromium`) before calling a UI change done — pytest
  green does not mean the feature works.
- CI (`.github/workflows/tests.yml`) runs `pytest` on every push/PR. Keep it
  green.

## Working conventions

- `ruff check .` runs in CI (config in `pyproject.toml`) — run it locally
  before pushing Python changes. No formatter or JS/CSS linter is
  configured; match the existing style by hand elsewhere: 4-space Python,
  no trailing whitespace, docstrings on non-obvious modules/functions in
  the style already used (see `storage.py`), minimal comments elsewhere.
- Dependencies in `requirements.txt` are pinned to exact versions
  (`flask==3.1.3`, etc.) — pin any new dependency the same way, and prefer
  not adding one at all given the "boring, minimal dependencies" rule above.
- This repository is public. Never commit real story content, real photos,
  a populated `.env`, or any credential — `stories/*` is gitignored except
  `.gitkeep` specifically so a real family's data can never accidentally
  land in git history. If you ever need sample content, use
  `scripts/seed_demo.py`, not real data.
