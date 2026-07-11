# Production-readiness review — instructions for fixes

Reviewed against `PLAN.md` on 2026-07-07, on a live instance (full auth → create →
upload → render → edit cycle exercised with curl and real Chromium at 390px and
1280px, light and dark).

**Overall verdict: the implementation is faithful to the plan and high quality.**
All 49 tests pass, the storage format on disk is exactly as specified, path
traversal is correctly rejected, image re-encoding/resizing works, the timeline
and story pages work without JavaScript, and the story page's book styling
(drop cap, figures, `==highlight==` → amber `<mark>`) matches the vision.

Two gaps were **already fixed in the commit that adds this file** (they required
network access the build environment didn't have):

- ✅ The real Toast UI Editor 3.2.2 is now vendored at
  `app/static/vendor/toastui/` (standalone bundle built from the official npm
  package with esbuild; provenance and rebuild instructions are in the file
  banner). The WYSIWYG editor loads, the custom highlight button works, and the
  textarea fallback remains for safety.
- ✅ `usageStatistics: false` added to the Editor options in
  `app/static/js/editor.js`. Without it, Toast UI **sends a hit to
  google-analytics.com on every editor load** — verified live. This must never
  be removed; it violates the "no external requests" principle (PLAN §2.3,
  checklist §10).

The items below are the remaining fixes, in priority order. Complete each one,
run the full test suite, and commit per item or in small groups. Do not
introduce new dependencies for any of these.

---

## 1. Open redirect in login (security — fix first)

`app/auth.py`: `next_url = request.args.get("next")` is followed blindly.
Verified live: `POST /login?next=https://evil.example.com` → 302 to the external
site. Fix by only accepting local paths:

```python
next_url = request.args.get("next", "")
if not next_url.startswith("/") or next_url.startswith("//") or "\\" in next_url:
    next_url = url_for("pages.timeline")
```

Add regression tests: `next=https://evil.example.com`, `next=//evil.example.com`,
and a legitimate `next=/edit/some-id` all behave correctly.

## 2. Fail fast when SECRET_KEY is missing in production (security)

`app/__init__.py` currently generates a random `SECRET_KEY` when the env var is
unset — even when `STORYBOOK_PASSWORD` is set (i.e. production). PLAN §7 says
required in prod; the random fallback silently logs everyone out on every
restart and breaks if a second process is ever started. In `create_app()`:

```python
if password and not secret_key:
    raise RuntimeError(
        "STORYBOOK_SECRET_KEY must be set when STORYBOOK_PASSWORD is set. "
        "Generate one with: python -c 'import secrets; print(secrets.token_hex(32))'"
    )
```

Keep the random fallback for dev mode (no password set). Add a test.

## 3. Request size limit (security/robustness)

There is no `MAX_CONTENT_LENGTH`; a 60 MB upload was read in full before being
rejected (verified live). In `create_app()` set
`MAX_CONTENT_LENGTH=32 * 1024 * 1024`, and register an error handler that
returns JSON for the API:

```python
@app.errorhandler(413)
def too_large(error):
    if request.path.startswith("/api/"):
        return jsonify({"error": "File too large (max 32 MB)."}), 413
    return render_template("404.html"), 413  # or a small dedicated message
```

Add a test posting >32 MB to the images endpoint expecting 413.

## 4. Session cookie hardening (security)

In `create_app()` config: `SESSION_COOKIE_SAMESITE="Lax"` and
`SESSION_COOKIE_HTTPONLY=True` (explicit). `SameSite=Lax` also closes the
cross-site multipart-form CSRF hole on `POST /api/stories/<id>/images`.
Add `STORYBOOK_COOKIE_SECURE` env var (default off; when `1`, set
`SESSION_COOKIE_SECURE=True`) and document it in `.env.example` and the README's
configuration table with a note: "set to 1 when serving over HTTPS."

## 5. `pytest` fails from a clean checkout (broken README instruction)

`pytest` → `ModuleNotFoundError: No module named 'app'`; only
`python -m pytest` works. Add a `pyproject.toml` at the repo root:

```toml
[tool.pytest.ini_options]
pythonpath = ["."]
```

Verify bare `pytest` passes afterwards.

## 6. Atomic story writes (durability)

`storage._write_index()` writes `index.md` in place; a crash mid-write corrupts
the story — the one file this project promises never to lose. Write to a temp
file in the same directory, then `os.replace()`:

```python
tmp_path = index_path.with_suffix(".md.tmp")
tmp_path.write_text(frontmatter.dumps(post) + "\n", encoding="utf-8")
os.replace(tmp_path, index_path)
```

Also make `list_stories()` ignore `*.tmp` leftovers (it already only reads
`index.md`, so just confirm with a test).

## 7. Editor JS swallows API errors

In `app/static/js/editor.js`, `ensureStoryId()` and `uploadImage()` call
`response.json()` without checking `response.ok`. If creation fails (e.g. the
413 from item 3), `data.id` is `undefined` and follow-up requests go to
`/api/stories/undefined`. In both functions: if `!response.ok`, parse the JSON
error if possible, `window.alert` the message, and reject the promise so
callers stop. Keep it dependency-free.

## 8. Pin dependency versions (durability)

`requirements.txt` is fully unpinned; a fresh install years from now will pull
incompatible majors. Pin exact versions of the six runtime deps + pytest to the
currently-installed versions (`pip freeze | grep -i -E 'flask|frontmatter|markdown|pymdown|waitress|pillow|pytest'`).

## 9. Docker hygiene

Add a `.dockerignore` (`.git`, `.venv`, `stories`, `tests`, `__pycache__`,
`*.pyc`, `.env`, `.pytest_cache`) so local content/secrets never end up in the
image. In the `Dockerfile`, create and switch to a non-root user before `CMD`,
and make sure `/data/stories` stays writable by that user.

## 10. README updates

- Replace the "A note on the editor" section: the real editor **is now
  vendored**; keep a short paragraph on how to rebuild the bundle (see the
  banner comment in `toastui-editor-all.min.js`) and that the textarea fallback
  still exists.
- Document `STORYBOOK_COOKIE_SECURE` (item 4).
- Add one sentence under "Running it": the app must be served over HTTPS or on
  a trusted LAN, since the single password otherwise travels in cleartext.

## Accepted as-is (no action, for the record)

- Raw HTML in markdown is rendered (`|safe`). Acceptable: the only author is
  the trusted password-holder. Do not add a sanitizer dependency.
- `strftime('%-d')` is glibc-only — fine for the Linux/Docker deployment target.
- Timeline thumbnails load the full 2000px image. Fine at family scale;
  thumbnail generation goes to "Ideas for later" if it ever matters.
- `time.sleep(1)` on failed login blocks one waitress thread — fine at this
  scale, per plan.

## Definition of done

- All items 1–10 implemented, each with tests where indicated.
- Bare `pytest` green from a clean checkout.
- Manual verification per PLAN §10 checklist still passes (especially: no
  request to any external domain from any page — check the editor page
  specifically).

---

# Live review round 2 (2026-07-10) — batch F0/F2–F10

Verified on a live instance with real Chromium at 390px, dark theme, with
authors, birthdate, and title configured, plus one draft, one sealed letter,
and one archived story on disk. **Everything functional passed**: anniversary
banner, ages, sealed envelope page, drafts/archived pages, prev/next +
keyboard arrows, lightbox (closes on back gesture), autosave recovery banner
with restore, `/book` printed to a correct 6-page PDF (cover alone on page 1,
drafts/sealed excluded), valid EPUB, manifest, export zip (complete: includes
sealed, drafts, and `.versions/`), per-save version snapshots + restore. Zero
external requests, zero JS console errors. The unspecced additions (history,
archive, import, EPUB, autosave, search, CI) were reviewed and are accepted.

Two layout defects to fix, both measured on a 390px viewport:

## R2.1 Timeline entry title gets crushed when metadata is long

With `Jun 18 · Papa · 2 years old` plus a cover thumbnail, the title column
measures **55px wide** and wraps one word per line ("First / bike / ride").
Fix the `.timeline__entry` layout so the title never drops below a readable
width on narrow screens: stack the entry vertically at small widths — meta
line (date · author · age) on its own row, title on the next row at full
width, thumbnail below or floated right at a fixed size. The title is the
element a reader scans; it wins over the thumbnail. Verify with the longest
realistic combo (long month-day, long author name, "11 months old", thumb)
at 360px and 390px.

## R2.2 Minimap year labels overlap entry thumbnails

The fixed right-edge minimap renders on top of `.timeline__thumb` images
(geometrically confirmed overlap). Either reserve a right gutter for the
minimap on viewports where it is shown (padding-right on the timeline list
equal to the minimap's width), or hide the minimap below a width breakpoint
where the gutter would cost too much reading width — pick whichever preserves
more title width at 390px, and make sure tap targets stay ≥ 44px if kept.

Definition of done: both fixed; a Playwright-measured title box ≥ 60% of the
content column width at 390px with full metadata; no bounding-box
intersection between `.minimap` and any timeline entry element; bare `pytest`
green; no visual change at desktop widths beyond the reserved gutter.

# Live review round 3 — 2026-07-11, batch 3 (F12–F16) on main at 4daef11

Reviewed on a real Chromium at 390×844 (mobile emulation, touch), with a fake
microphone for real MediaRecorder recording. What passed, end to end: bare
pytest green (352 tests); instant capture in well under 20s with the photo
becoming the cover and a compact timeline entry; a real recorded memo
(pause/resume, timer, upload as `memo-001.webm`), playing back on the story
page with HTTP Range → 206; a hand-written `memo-001.txt` sidecar appearing
as the transcript; memo Delete removing both the audio and the sidecar (and
nothing else); two people created (portrait cover + initial-letter
placeholder), relation line, People nav link, `people/` skipped by the
timeline; /random six times never landing on an instant, story-footer link
carrying `?not=`; prompts cycling on /new and absent after first save; 413
with the new 128 MB limit; HEIC upload converted to JPEG; sealed story body
hidden; /book printed to an A4 PDF with one story per page and instants as
inline captioned figures; EPUB a valid zip. **Zero external network requests
across the entire run, including while recording.** The stories/ folder on
disk is exactly the promised plain format.

Two defects to fix, both regressions visible on every page or every editor
visit:

## R3.1 Nav overflows the viewport at phone width

Batch 3 added "People" and "+ Instant" to `.site-nav__actions`. At 390px the
nav row no longer fits: `document.documentElement.scrollWidth` is 399px vs a
390px viewport, the theme toggle's right edge sits at 399px (half clipped
off-screen), and the "+ New story" label wraps onto two lines inside its
button. Every page now scrolls sideways by ~9px. Fix the nav so nothing
overflows at 360–414px: let `.site-nav` wrap onto two rows at a small-width
breakpoint (brand + theme toggle on the first row, the action buttons on the
second), or shorten the button labels at that breakpoint — either is fine,
but button labels must not wrap internally (`white-space: nowrap`) and every
tap target stays ≥ 44px. Definition of done: at 360, 390, and 414px wide, on
the timeline, a story page, /people, and the editor,
`document.documentElement.scrollWidth <= clientWidth`, and the theme toggle
is fully inside the viewport.

## R3.2 CSS defeats the `hidden` attribute: recovery banner and recorder buttons always visible

The autosave recovery banner (`#editor-recovery`), the voice Pause button,
and the voice Stop button all carry the `hidden` attribute but render
visible on a completely fresh editor page, because class rules
(`.editor__recovery { display: flex }`, `.btn { display: inline-flex }`)
override the UA stylesheet's `[hidden] { display: none }`. Measured:
`el.hidden === true` yet computed display `flex` for all three. The worst
symptom is user-facing: every visit to /new or /edit shows "You have an
unsaved draft from ." with an empty timestamp even when no draft exists.
Fix globally, not per-element — add `[hidden] { display: none !important; }`
near the top of main.css — then check every current user of the `hidden`
attribute (recovery banner, voice pause/stop/timer/message, timeline search
empty-state) still shows and hides correctly when its JS toggles it, since
they toggle the attribute rather than a class. Add a fresh-page check to the
manual pass: /new on a clean browser shows no recovery banner and only the
Record button. Definition of done: on a fresh /edit page, computed display
is `none` for `#editor-recovery`, `#voice-pause-btn`, `#voice-stop-btn`;
recording still reveals pause/stop/timer; a genuinely stored autosave still
shows the banner with a real timestamp; bare pytest green.
