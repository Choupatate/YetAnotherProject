# Implementation Plan — "Storybook": a private memory journal for my son

This document is the **complete specification** for building this project. It is written
to be followed by an AI coding model (or any developer) **without making new architecture
decisions**. All decisions are already made and recorded here. If something is genuinely
ambiguous, choose the simplest option consistent with the Design Principles below and note
the choice in the commit message — do not redesign.

---

## 1. What we are building (product vision)

A private, self-hosted web app where a parent writes **memories/stories** (text + photos)
for their child, and the child (or the family) reads them later.

Two core experiences:

1. **The Timeline** — the home screen. A chronological "history bar" showing every story
   as a point in time. It is a *window* onto the stories: you scan the years, you tap a
   story, you enter it.
2. **The Story** — a single memory, presented **like a page of a book**, not like a blog
   post. Generous typography, comfortable reading column, images woven into the text.
   Beautiful in dark mode (dark is the default theme).

The parent can **create and edit stories entirely from a mobile phone**, using a rich-text
editor (bold, italic, highlights, headings, photos). Everything is **stored as plain
markdown files + image files on disk** — no database.

## 2. Design principles (apply everywhere, in priority order)

1. **The data outlives the app.** Stories are plain `.md` files and ordinary image files
   in a human-readable folder structure. A person in 2045 with no software except a file
   browser must be able to read everything. Never store content in a database, never in
   proprietary formats, never only in the cloud.
2. **Boring, minimal dependencies.** Python + Flask + Jinja on the server. Vanilla JS on
   the client except the one vendored editor library. No React/Vue/Svelte, no build step,
   no CSS framework. Every dependency must be justified; when in doubt, write the 30 lines
   yourself.
3. **No runtime network dependencies.** All JS/CSS/fonts are vendored into the repo
   (committed files). The app must work fully on a LAN with no internet.
4. **Mobile-first.** Every screen is designed for a phone first, then enhanced for
   desktop. The author does all writing from a phone.
5. **Book, not blog.** No card grids of excerpts, no "read more" teasers, no comment
   sections, no reactions, no infinite feeds. Restraint and typography.

## 3. Tech stack (fixed — do not substitute)

| Layer | Choice | Notes |
|---|---|---|
| Language | Python 3.12+ | |
| Web framework | Flask | with Jinja2 templates (bundled with Flask) |
| Markdown → HTML | `markdown` package | with extensions listed in §6.3 |
| Frontmatter parsing | `python-frontmatter` | YAML frontmatter |
| WSGI server (prod) | `waitress` | pure-Python, boring |
| Image handling | `Pillow` | resizing/re-encoding uploads |
| Rich editor (client) | **Toast UI Editor** (vendored UMD bundle + CSS) | markdown-native WYSIWYG, works on mobile, no build step |
| CSS | Hand-written, single file, CSS custom properties | no framework |
| Fonts | System font stacks only (see §8.1) | no font files, maximally durable |
| Auth | Single shared password → signed session cookie | see §7 |
| Tests | `pytest` | |

`requirements.txt` must contain only: `flask`, `python-frontmatter`, `markdown`,
`pymdown-extensions`, `waitress`, `pillow`, and (dev) `pytest`.

Vendoring Toast UI Editor: download `toastui-editor-all.min.js` and
`toastui-editor.min.css` + `theme/toastui-editor-dark.css` (latest 3.x release) once and
commit them under `app/static/vendor/toastui/`. If the download is unavailable in the
build environment, create the files as clearly-marked placeholders, make the editor page
degrade to the fallback described in §9.6, and note it in the commit message — do not
pull from a CDN at runtime.

## 4. Repository layout (create exactly this)

```
.
├── PLAN.md                     # this file
├── README.md                   # how to run, how to back up, philosophy
├── requirements.txt
├── run.py                      # dev entry point (flask dev server, debug on)
├── serve.py                    # prod entry point (waitress)
├── Dockerfile                  # python:3.12-slim, runs serve.py
├── .env.example                # documents the env vars in §7
├── app/
│   ├── __init__.py             # create_app() factory; loads config from env
│   ├── auth.py                 # login/logout, @login_required decorator
│   ├── storage.py              # ALL filesystem read/write for stories lives here
│   ├── rendering.py            # markdown → HTML, incl. ==highlight== support
│   ├── routes_pages.py         # GET pages: timeline, story, editor, login
│   ├── routes_api.py           # POST/PUT JSON+upload endpoints used by the editor
│   ├── templates/
│   │   ├── base.html           # <html> shell, theme, nav, flash messages
│   │   ├── login.html
│   │   ├── timeline.html       # home: the chronological bar + story entries
│   │   ├── story.html          # the "book page" reading view
│   │   └── editor.html         # create/edit a story (Toast UI Editor)
│   └── static/
│       ├── css/main.css        # all styles; CSS variables for theming
│       ├── js/timeline.js      # timeline interactions (vanilla JS)
│       ├── js/editor.js        # editor page glue: init, save, upload, highlight btn
│       └── vendor/toastui/     # vendored editor JS+CSS (committed)
├── stories/                    # CONTENT lives here (gitignored except .gitkeep)
│   └── .gitkeep
└── tests/
    ├── conftest.py             # app fixture with a tmp stories dir
    ├── test_storage.py
    ├── test_rendering.py
    ├── test_api.py
    └── test_pages.py
```

Add a `.gitignore` for `stories/*` (keep `.gitkeep`), `__pycache__`, `.env`, `.venv`.

## 5. Content storage format (the most important contract in the app)

Each story is a **folder**:

```
stories/
└── 2026-07-14-first-bike-ride/
    ├── index.md
    ├── photo-001.jpg
    └── photo-002.jpg
```

- Folder name: `YYYY-MM-DD-<slug>` where the date is the **story date** (when the memory
  happened, not when it was written) and slug is derived from the title (lowercase ASCII,
  hyphens, max 60 chars). Folder name = story ID used in URLs.
- `index.md` = YAML frontmatter + markdown body:

```markdown
---
title: "Your first bike ride"
date: 2026-07-14          # story date, ISO
created: 2026-07-20T21:04:00
updated: 2026-07-21T08:12:00
cover: photo-001.jpg       # optional; filename within the folder
---

The story text in **markdown**, with ==highlights==, *italics*, headings,
and images referenced by bare relative filename:

![The big moment](photo-001.jpg)
```

Rules for `storage.py` (implement as pure functions taking the stories root as a param):

- `list_stories()` → all stories, parsed frontmatter only (do not render bodies), sorted
  by `date` ascending. Tolerate and skip malformed folders with a logged warning — never
  crash the timeline because one file is broken.
- `get_story(story_id)` / `save_story(...)` / `create_story(title, date, body)` (generates
  the folder name; on slug collision append `-2`, `-3`, …).
- `save_image(story_id, file_storage)` → re-encode with Pillow (strip EXIF orientation by
  applying it, resize to max 2000px long edge, JPEG quality 85; keep PNG for PNGs),
  name it `photo-NNN.<ext>` with the next free number, return the filename.
- Never delete images on story save (unreferenced images are harmless; durability wins).
- Story deletion: **do not implement** in v1. No delete buttons anywhere.
- Path safety: reject any `story_id` or filename that doesn't match a strict regex
  (`^[a-z0-9-]+$` for ids, `^[a-z0-9._-]+$` for filenames, no `..`), 404 otherwise.

## 6. Server behavior

### 6.1 Page routes (`routes_pages.py`, all behind login except `/login`)

| Route | Renders |
|---|---|
| `GET /` | `timeline.html` with all stories grouped by year |
| `GET /story/<story_id>` | `story.html` with rendered HTML body |
| `GET /story/<story_id>/media/<filename>` | serves an image from the story folder (with path-safety checks) |
| `GET /new` | `editor.html` in create mode |
| `GET /edit/<story_id>` | `editor.html` pre-loaded with raw markdown + frontmatter |
| `GET /login`, `POST /login`, `POST /logout` | auth |

### 6.2 API routes (`routes_api.py`, JSON, behind login)

| Route | Body → Result |
|---|---|
| `POST /api/stories` | `{title, date, markdown}` → creates story, returns `{id}` |
| `PUT /api/stories/<story_id>` | `{title, date, markdown, cover?}` → saves; updates `updated`; returns `{id}` (id never changes after creation, even if title/date change) |
| `POST /api/stories/<story_id>/images` | multipart file → `{filename}` |

Return proper HTTP errors as JSON `{error: "..."}`; validate title non-empty and date
ISO-parseable.

### 6.3 Markdown rendering (`rendering.py`)

Use `markdown` with extensions: `pymdownx.caret`, `pymdownx.tilde`, `pymdownx.mark`
(gives `==text==` → `<mark>`), `smarty`, `tables`, `sane_lists`, plus a tree-processor or
post-step that rewrites bare image srcs (`photo-001.jpg`) to
`/story/<story_id>/media/photo-001.jpg`. Wrap images in `<figure>`, alt text becomes
`<figcaption>` when non-empty.

## 7. Configuration & auth

Env vars (document in `.env.example`, read in `create_app()`):

- `STORYBOOK_STORIES_DIR` (default `./stories`)
- `STORYBOOK_PASSWORD` (required in prod; if unset, dev mode allows login with `dev`)
- `STORYBOOK_SECRET_KEY` (Flask session signing; required in prod, random default in dev)

Auth model: one shared password, `POST /login` compares with `hmac.compare_digest`, sets
`session["authed"] = True` permanent for 90 days. `@login_required` on everything else.
No accounts, no roles, no password reset. Rate-limit login naively (sleep 1s on failure).

## 8. UI specification

### 8.1 Global look (base.html + main.css)

- **Dark theme is the default and the primary design target.** Provide a light theme via
  `prefers-color-scheme` and a manual toggle (stored in `localStorage`, applied via
  `data-theme` attribute on `<html>`).
- All colors defined once as CSS custom properties on `:root` / `[data-theme]`.
  Dark palette guidance: near-black warm background (#141210 range), warm off-white text
  (#e8e2d9 range), one accent (candle-light amber, #d9a441 range) used sparingly for the
  timeline spine, links, and `<mark>` highlights (highlight = translucent amber background,
  readable text). Aim for a "reading by lamplight" feel, not a neon dashboard. Check all
  text ≥ WCAG AA contrast.
- Fonts, system stacks only:
  - Story body & titles (serif): `Iowan Old Style, Palatino Linotype, Palatino, Georgia, serif`
  - UI chrome (sans): `system-ui, -apple-system, Segoe UI, Roboto, sans-serif`
- Minimal top nav: app name (left), `+ New story` button and theme toggle (right). On the
  story page the nav fades to near-invisible; content is king.
- Viewport meta, `<html lang>`, semantic landmarks, focus styles. Tap targets ≥ 44px.

### 8.2 Timeline page (`timeline.html` + `timeline.js`)

This is the "history bar": a **vertical timeline** (vertical because mobile-first; a
horizontal bar is unusable on phones).

- A continuous vertical spine line (accent color, subtle) down the left side (~24px from
  edge on mobile, centered-left on desktop with content to the right).
- Stories in chronological order (oldest first — a book reads forward). Each story is a
  node on the spine: a small filled dot, connected to an entry showing **date (small,
  accent), title (serif, prominent)**, and — only if the story has a `cover` — a small
  rounded thumbnail (~72px). No body excerpts. The whole entry is one `<a>` to the story.
- **Year markers**: when the year changes, a larger label on the spine (e.g. `2026`) —
  these make the bar feel like flipping through chapters of years.
- `timeline.js` (progressive enhancement only; page fully works without JS):
  - A thin fixed "minimap" on the right edge: proportional year ticks; tapping a year
    smooth-scrolls to it. Highlight the current year while scrolling
    (IntersectionObserver).
  - Subtle fade-in of entries as they enter the viewport (CSS class toggle; respect
    `prefers-reduced-motion`).
- Empty state (no stories yet): a centered, warm invitation — one sentence and the
  `+ New story` button.

### 8.3 Story page (`story.html`) — the book page

- Single centered column, `max-width: 42rem`, generous side padding on mobile.
- Header: date in small caps/accent above, then the title in large serif (clamp ~2–3rem),
  then a thin horizontal rule flourish. If `cover` is set, show it full-column-width under
  the header with rounded corners.
- Body typography: serif, `font-size: 1.125rem` mobile / `1.1875rem` desktop,
  `line-height: 1.7`, paragraphs spaced by margin (no indent), `text-wrap: pretty` where
  supported. Optional tasteful drop cap on the first paragraph via `::first-letter`
  (skip if it degrades — test with a paragraph starting with a quote mark; if fragile, drop it).
- `<mark>` styled as the amber highlight; `<figure>` images full column width, rounded,
  with small italic captions; blockquotes with a thin accent left border.
- Footer of the story: small `‹ Timeline` link and, for the logged-in author, a discreet
  `Edit` link. Nothing else. No metadata clutter, no tags, no share buttons.

### 8.4 Editor page (`editor.html` + `editor.js`)

- Fields: **Title** (large borderless text input, serif, looks like writing a chapter
  title), **Date** (`<input type="date">`, defaults to today), then the **Toast UI
  Editor** in WYSIWYG mode, dark theme CSS when app theme is dark, `initialValue` = the
  raw markdown when editing.
- Toolbar: keep only heading, bold, italic, strike, quote, ul/ol, image, link — plus a
  **custom Highlight button** that wraps/unwraps the selection in `==` (insert via the
  editor API around the current selection).
- Image button → hook Toast UI's `addImageBlobHook`: upload the blob to
  `POST /api/stories/<id>/images`, insert `![](photo-NNN.jpg)` (bare filename). For a
  **new, never-saved story**, the first image upload triggers an auto-create first
  (POST `/api/stories` with current title-or-"Untitled" + date) so there's a folder to
  upload into; the page then switches to edit mode for that id (history.replaceState).
- Save: single prominent Save button (fixed bottom bar on mobile, above the keyboard);
  calls create or update with `editor.getMarkdown()`; on success navigate to the story
  page. Warn on `beforeunload` if there are unsaved changes.
- The editor page is the one place where a heavier JS component is allowed. Everything
  else stays HTML+CSS+small JS.

## 9. Build order (phases with acceptance criteria — implement in this order, commit per phase)

### Phase 1 — Skeleton & storage
`create_app()` factory, config, `storage.py` + full `test_storage.py` coverage
(create/list/get/save, slug collision, malformed folder skipped, path-safety rejections),
`rendering.py` + `test_rendering.py` (`==x==` → `<mark>`, image src rewrite, figure/
figcaption). ✅ `pytest` green.

### Phase 2 — Auth + base shell
Login page, session, `@login_required`, `base.html` with theme system + toggle.
✅ Unauthenticated request to `/` redirects to `/login`; correct password logs in; theme
toggle persists across reloads.

### Phase 3 — Timeline + story pages (read path)
Both pages fully styled per §8.2/§8.3, seeded by hand-creating 3 sample story folders in a
script `scripts/seed_demo.py` (varied: with/without cover, multiple years, one long text).
✅ Timeline shows year markers and entries; story page renders markdown with highlights
and captioned images; both look right at 375px and 1200px widths; pages work with JS
disabled.

### Phase 4 — Editor (write path)
API routes + editor page per §8.4, `test_api.py` (create, update, upload incl. path-safety
and validation errors). ✅ From a phone-sized viewport: create a story with title, date,
bold/italic/highlight text and an uploaded photo, save, land on the story page, verify the
`.md` file on disk is clean markdown with `==` and bare image filename; edit it again and
save.

### Phase 5 — Polish & ship
Empty state, flash messages, 404 page, minimap scrolling, reduced-motion, favicon (simple
inline-SVG book), `Dockerfile`, `README.md` (run instructions incl. Docker, backup advice:
"back up the `stories/` folder — that is everything"), final `pytest` + a manual pass of
the checklist in §10. ✅ All checklist items pass.

## 10. Final acceptance checklist

- [ ] All content on disk is plain markdown + images; no database files exist.
- [ ] `rm -rf` the app, keep `stories/` → files remain fully human-readable.
- [ ] Full create→upload→save→read→edit cycle works on a 375px viewport.
- [ ] Dark theme is default, light theme works, toggle persists.
- [ ] Timeline & story pages render without JavaScript.
- [ ] No network requests to any external domain (check devtools).
- [ ] `pytest` green; app boots with `python run.py` and with Docker.
- [ ] Login required everywhere; wrong password rejected; path traversal attempts 404.

## 11. Out of scope for v1 (do NOT build)

Multi-user accounts, comments/reactions, search, tags, RSS, email, PDF/print export,
image galleries/lightboxes, video, encryption at rest, i18n, PWA/service worker, story
deletion. If tempted, add a note to `README.md`'s "Ideas for later" section instead.
