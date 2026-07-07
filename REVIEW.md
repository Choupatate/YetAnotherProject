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
