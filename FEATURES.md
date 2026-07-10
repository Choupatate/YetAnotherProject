# Feature spec — F1: Authors ("two voices, one book")

Follow-up feature to be implemented **after** the fixes in `REVIEW.md`. Same
ground rules as `PLAN.md`: all decisions are made here — implement, don't
redesign. No new dependencies. Everything stays plain markdown on disk.

## What it is

Multiple family members (e.g. Papa and Maman) write stories in the **same
shared timeline** — one book, several narrators. Each story carries its
author, and each author has their own color so the two voices are clearly
distinguishable at a glance on the timeline and on story pages.

There are still **no accounts**: one shared password, one login. The author is
a label on the story, not an identity system. Do not add users, permissions,
or per-author passwords.

## 1. Configuration

New env var, documented in `.env.example` and the README config table:

```
STORYBOOK_AUTHORS="Papa:#d9a441,Maman:#7ba7d9"
```

- Comma-separated `Name:#hexcolor` pairs. Name is a display string (unicode
  allowed, no commas or colons); color is a CSS hex color chosen by that
  author.
- Parse in `create_app()` into `app.config["AUTHORS"]`: an ordered list of
  `{"name": ..., "color": ...}` dicts. On a malformed entry, raise
  `RuntimeError` at startup with a message showing the expected format (fail
  fast, like the SECRET_KEY check).
- **If unset or empty, the entire feature is invisible**: no selector in the
  editor, no bylines, no legend — the app behaves exactly as today. All
  templates and JS must guard on this.
- README should advise picking mid-brightness colors that read well on both
  the dark and light background, and state that renaming an author in the env
  var does not rewrite existing files (see §2).

## 2. Storage (frontmatter)

- New **optional** frontmatter field on `index.md`: `author: Papa` (the plain
  name string, not the color — colors live only in config so they can be
  retuned anytime).
- `Story` dataclass gets `author: Optional[str] = None`.
- `_write_index()` / `create_story()` / `save_story()` pass it through;
  omit the key entirely when the story has no author.
- **Unknown author names must never break anything.** A story whose `author`
  is not in the configured list (author renamed, config lost, file copied
  from elsewhere) renders with the byline text but the neutral default accent
  color. The files outlive the config; tolerate drift silently.

## 3. API

- `POST /api/stories` and `PUT /api/stories/<id>` accept an optional
  `author` string.
- Validation: if `STORYBOOK_AUTHORS` is configured and a non-empty `author`
  is provided, it must be one of the configured names → otherwise 400 JSON
  error (the UI is a picker; anything else is a bug or tampering). Empty /
  missing author is always allowed. If no authors are configured, ignore the
  field entirely.

## 4. Editor UI

- Below the date input, a row of **author chips** (one `<button type="button">`
  per configured author): the author's name with a small filled dot in their
  color. Tapping selects (one at a time; tapping the selected chip deselects
  → story saved without author). Selected chip gets a visible border in the
  author color + `aria-pressed="true"`. Rendered server-side from config;
  hidden entirely when no authors configured.
- Preselection order: the story's existing `author` when editing; otherwise
  `localStorage["storybook-author"]` if it matches a configured name;
  otherwise none. On change, store the choice in `localStorage` — each
  parent's phone remembers who they are, so after the first time it's
  zero-tap.
- `editor.js` includes the selected author in both create and update payloads.
  This must also apply to the auto-create that happens on first image upload
  (`ensureStoryId`), and the fallback textarea editor path must support the
  chips identically (they live outside the editor widget, so this should be
  free — verify it).

## 5. Story page

- Byline appears inside the existing date line:
  `JUNE 18, 2023 · MAMAN`, where the author name is preceded by a small
  colored dot (author's color) and the name uses the same small-caps style as
  the date. No author → date line unchanged.
- The `<hr class="story__flourish">` under the title takes the author's color
  (neutral accent when no/unknown author). Subtle, but it tints the whole
  page's mood toward its narrator.

## 6. Timeline — the "clear visual split"

This is the heart of the feature. Three coordinated cues, all driven by a
single inline `style="--author-color: #7ba7d9"` custom property set on the
entry when the story has a configured author (entries without an author keep
the neutral accent via the variable's fallback):

1. **The dot** on the spine is filled with the author's color and slightly
   enlarged (visible at arm's length — this is the primary cue).
2. **The author's name** appears after the date in the entry's date line
   (`Jun 18 · Maman`), in the author's color, same small size as the date.
3. **A legend** at the top of the timeline (only when ≥1 author configured):
   one chip per author — colored dot + name — so the color mapping is
   self-explanatory to a reader who has never seen the app. Static, not a
   filter (filtering is out of scope; add to "Ideas for later" if tempted).

Implementation notes: pass the configured author→color mapping into the
template from the route (build a dict once); do not inline hex values in CSS —
everything reads `var(--author-color, var(--accent))`.

## 7. Seed + tests + docs

- `scripts/seed_demo.py`: give the existing sample stories a mix of two
  authors and one story with no author, so the timeline demonstrates the
  split out of the box (seed works regardless of env config since unknown
  authors degrade gracefully).
- Tests to add:
  - config parsing (valid, malformed → RuntimeError, unset → feature off),
  - author round-trip through create/update API and frontmatter,
  - API 400 on unknown author when list configured; accepted when list not
    configured,
  - story/timeline pages render byline and legend when configured, and render
    identically to today when not,
  - unknown author on disk → page renders, neutral color.
- Update README (config table, a short "Several narrators" paragraph) and
  `.env.example`.

## Definition of done

- With `STORYBOOK_AUTHORS` unset: pixel-identical behavior to before (no
  selector, no legend, no bylines); all pre-existing tests untouched and green.
- With two authors configured: creating a story from a phone as "Maman" takes
  zero extra taps after the first visit; the timeline shows both voices
  clearly split by color with a legend; `index.md` on disk contains
  `author: Maman` and nothing about colors.
- Bare `pytest` green from a clean checkout.

---

# Feature batch 2 — F2..F10 (reading experience, rituals, durability)

Same ground rules: all decisions are made here — implement, don't redesign.
**No new dependencies** (stdlib + what's already vendored only). Every feature
is invisible/off when its configuration is absent, and every new piece of
story state is a plain optional frontmatter field — the files stay readable
forever without the app.

Where this batch conflicts with `PLAN.md` §11 ("out of scope for v1"), this
document supersedes it: print/PDF export (F10), a lightbox (F7), and a web app
manifest without a service worker (F9) are now in scope. Update the README's
"Ideas for later" section accordingly when done.

**Implementation order (respect it — later features build on earlier ones):**
F0 groundwork → F6 drafts → F4 sealed letters → F2 reading order → F3 age →
F5 on this day → F7 lightbox → F8 export → F9 manifest → F10 book view.
Commit per feature; bare `pytest` green before each commit.

---

## F0. Groundwork: story visibility (required by F2, F4, F5, F6, F10)

Two new **optional** frontmatter fields, parsed tolerantly (bad values are
treated as absent, never crash — same philosophy as unknown authors):

```yaml
draft: true          # boolean; absent means published
unlock: 2040-06-18   # ISO date; absent means not sealed
```

- `Story` dataclass gains `draft: bool = False` and
  `unlock: Optional[date] = None`. `_write_index()` writes each key only when
  set (`draft` only when true).
- New helpers in `storage.py` (pure, unit-tested):
  - `is_sealed(story, today)` → `story.unlock is not None and story.unlock > today`
  - `readable_stories(stories, today)` → published (non-draft), non-sealed,
    date-ascending — the canonical "pages of the book" used by F2, F5, F10.
- `POST/PUT /api/stories` accept optional `draft` (bool) and `unlock`
  (ISO string or `""`/absent to clear). Invalid `unlock` → 400 JSON error.
- Editor UI (both Toast and fallback paths — these live outside the widget):
  - a "Draft" toggle chip styled like the author chips, `aria-pressed`,
    placed on the same row as the author chips, right-aligned;
  - a "Seal until" `<input type="date">` (optional, clearable) next to the
    story date input, with a short label. Both sent on create and update,
    preserved when editing.

## F2. Reading order — previous / next story

The book gets page turning. On the story page footer, between "‹ Timeline"
and "Edit":

- `‹ <previous title>` and `<next title> ›` links, neighbors taken from
  `readable_stories()` (drafts and sealed letters are skipped). Truncate
  titles over ~40 chars with an ellipsis. First/last story: omit that side.
- Add `<link rel="prev">` / `<link rel="next">` in `<head>`.
- Keyboard: on the story page, plain (no modifier) `ArrowLeft`/`ArrowRight`
  navigate to prev/next unless focus is in an input/textarea/contenteditable.
  ~15 lines in a new `app/static/js/story.js`, loaded only by `story.html`.
- Layout: footer becomes a two-row grid on narrow screens (prev/next row above
  the Timeline/Edit row); tap targets ≥ 44px.
- Tests: middle story has both links in order; first/last omit one; a draft
  and a sealed story between two published ones are skipped; a draft story's
  own page renders without prev/next.

## F3. Age at each memory

New optional env `STORYBOOK_BIRTHDATE=YYYY-MM-DD` (the child's birth date;
document in `.env.example` + README). Invalid value → `RuntimeError` at
startup (fail fast, like STORYBOOK_AUTHORS). When unset, nothing changes.

- New pure helper `age_label(birthdate, on_date)` in a new `app/dates.py`:
  - `on_date < birthdate` → `"before you were born"`
  - under 1 month → `"N days old"` (`"1 day old"` singular)
  - under 1 year → `"N months old"` (full months, day-adjusted)
  - otherwise → `"N years old"` (floor; `"1 year old"` singular)
- Story page date line becomes `JUNE 18, 2023 · 2 YEARS OLD · PAPA` (age
  between date and author, same small-caps style, separated by the existing
  `·`). Timeline entries append it after the author: `Jun 18 · Papa · 2 years
  old` — smaller/dimmer than the date so rows don't get noisy.
- Sealed entries and the sealed page do NOT show age (the envelope stays
  minimal).
- Tests: each `age_label` branch incl. day-adjustment edge (born the 20th,
  story on the 19th of a later month), and page rendering with/without the
  env var.

## F4. Sealed letters ("open when you're 18")

A story with a future `unlock` date is a sealed envelope: visible as an
object, unreadable as text. **State plainly in the README**: the seal is
ceremonial, not cryptographic — anyone with the password (or the disk) can
open the file; the point is ritual, not security.

- Story page (`GET /story/<id>`) while sealed renders a dedicated
  `sealed.html` instead: centered column with an inline-SVG envelope (~64px,
  stroked in the author's color, neutral accent otherwise), then
  `A sealed letter{% if author %} from {{ author }}{% endif %}`, then
  `It opens on June 18, 2040.` and a `‹ Timeline` link. No title, no body, no
  cover, no age, no Edit link (authors reach editing via `/edit/<id>`
  directly, which keeps working — note this in the README paragraph).
- Timeline entry while sealed: keeps its chronological position; the dot is
  replaced by a small envelope glyph in the author color; text is
  `A sealed letter · opens June 18, 2040` (no title, no thumb); links to the
  sealed page. After the unlock date passes, the entry automatically becomes
  a normal entry — no action needed.
- Excluded from: prev/next (F2), on-this-day (F5), `/book` (F10), covers.
- Tests: sealed story page shows envelope not body; timeline shows envelope
  entry; unlock date in the past renders normally (freeze "today" by passing
  it into helpers — do not monkeypatch datetime globally; thread `today`
  through route → helper as a parameter with `date.today()` default).

## F5. "X years ago today"

On the timeline, when any readable story (per F0) from a previous year has
today's month and day: a quiet banner between the nav and the legend —
one line per match, newest first, capped at 3:

> 3 years ago today — [First bike ride](/story/...)

- Wording exactly: `{N} year{s} ago today — <linked title>`. Numeral, not
  spelled out.
- Style: small, warm, subtle — a left-accent-bordered box using the story
  author's color when present; no icon, no dismiss button, no animation.
- Feb 29 stories surface on Mar 1 in non-leap years (implement by "matches
  today" OR "story is Feb 29 and today is Mar 1 in a non-leap year").
- Tests: match, no-match, multiple matches capped at 3 and ordered, Feb 29
  rule, drafts/sealed never surface. Thread `today` as in F4.

## F6. Drafts

- `draft: true` stories are excluded from the timeline list, legend counts,
  F2 navigation, F5 banners, and F10's book. Their story page renders
  normally but with a small `DRAFT` pill next to the date line, and their
  direct URL keeps working (everyone with the password is family; no reader/
  author split exists).
- When ≥1 draft exists, the timeline shows a discreet `Drafts (N)` link under
  the legend → new page `GET /drafts` (`drafts.html`): a plain list of
  title + date + author dot, each linking to the story page, sorted by
  `updated` descending. When 0 drafts, no link and `/drafts` shows an empty
  state.
- Editor: the Draft chip (F0) defaults to off for new stories, reflects the
  saved value when editing.
- Tests: excluded everywhere listed; pill renders; drafts page lists and
  sorts; chip round-trips through the API.

## F7. Tap-to-zoom photos (lightbox)

Dependency-free, ~50 lines JS + CSS, loaded only on the story page
(`story.js` from F2 is the home for it):

- Tapping any `.story__body figure img` or the cover opens a full-viewport
  overlay: near-opaque background (`rgba(0,0,0,.92)`), image centered with
  `max-width/max-height: 100%; object-fit: contain`, the `<figcaption>` text
  (when present) in small italic below.
- Closes on: tap/click anywhere, `Escape`, or browser Back (push a history
  state on open; close on `popstate` — on a phone the back gesture is the
  natural exit).
- While open: `overflow: hidden` on `<body>`; focus moves to the overlay
  (`role="dialog"`, `aria-label` from the caption or "Photo"); restore focus
  on close. Fade-in ≤150ms, none under `prefers-reduced-motion`.
- No zoom/pinch handling, no prev/next arrows, no thumbnails strip — one
  photo, full screen, done. (Pinch-zoom still works via native browser
  gesture on the overlay image.)

## F8. One-tap backup

- `GET /export` (login required): streams a zip of the entire stories
  directory. Stdlib `zipfile` with `ZIP_STORED` (photos are already
  compressed), built into a `tempfile.TemporaryFile`, then `send_file` with
  `download_name=f"storybook-backup-{date.today().isoformat()}.zip"`.
  Skip `*.tmp` leftovers. Folder structure inside the zip = exactly the
  on-disk layout.
- UI: a small footer line at the bottom of the timeline:
  `Download everything (.zip)` — quiet text link, not a button.
- Tests: zip round-trip (create stories → export → open zip in test → same
  files/bytes), `.tmp` excluded, auth required.

## F9. Home-screen install (manifest, no service worker)

- New optional env `STORYBOOK_TITLE` (default `"Storybook"`): used in the nav
  brand, `<title>` suffix, manifest `name`, and the F10 book cover. This is
  how the app becomes "Le livre de <son's name>" on two phones. Document it.
- `GET /manifest.webmanifest` served by a tiny route (it needs the title from
  config): `name`/`short_name` from `STORYBOOK_TITLE`, `display: standalone`,
  `start_url: /`, `background_color`/`theme_color` = the dark background hex
  from `main.css`, icons: 192px and 512px PNG.
- Icons: `scripts/make_icons.py` (Pillow, run manually, outputs committed to
  `app/static/icons/`): dark rounded-square background using the theme's
  near-black, a simple stylized open book in the accent amber (exact shape at
  implementer's discretion — keep it geometric and legible at 48px). Generate
  192, 512, and 180 (`apple-touch-icon.png`).
- `base.html` head: `<link rel="manifest">`,
  `<link rel="apple-touch-icon" ...>`, and two `<meta name="theme-color">`
  (one per `prefers-color-scheme` via the `media` attribute).
- Explicitly NO service worker, no offline caching — revisit only if ever
  needed.
- Tests: manifest route returns valid JSON with the configured title; head
  contains the links.

## F10. The book view (`/book`) — read it all, print it all

One page containing every readable story (F0 ordering), for two uses: reading
the whole book start-to-finish on screen, and printing to PDF/paper.

- `GET /book` (login required), `book.html`:
  - **Cover section**: `STORYBOOK_TITLE`, then `Stories from {min year} to
    {max year}`, then the authors as name + dot (when configured). Vertically
    centered, full first page when printed (`page-break-after: always`).
  - **Stories**: each rendered with the same header structure as
    `story.html` (date line with age/author, title, flourish, cover image,
    body — extract a shared Jinja partial `_story_article.html` and reuse it
    in both templates rather than duplicating) separated on screen by a
    small centered ornament (`· · ·`).
  - A floating `Print / save as PDF` button (bottom right, hidden in print)
    calling `window.print()`.
- Print stylesheet (in `main.css` under `@media print`, applies to every
  page but matters here): force the light palette (white background, near-
  black text) regardless of theme; hide nav, minimap, legend, footers,
  buttons, flash messages; each `/book` story starts on a new page
  (`break-before: page`); body ~11pt serif, `line-height 1.5`; images
  `max-width: 100%`, `max-height: 22cm`, `break-inside: avoid`; `<mark>`
  prints with a light amber background and black text; `@page { margin:
  20mm }`.
- Link to it: a small `Read as a book` link next to the timeline's export
  link (F8 footer line).
- Performance note: at family scale (hundreds of stories) rendering
  everything on one page is fine; do not paginate, do not lazy-render.
- Tests: `/book` contains all readable stories in order and excludes drafts
  and sealed letters; cover shows configured title and year range; the shared
  partial keeps `story.html` rendering identical (existing page tests stay
  green).

---

## Batch definition of done

- Each feature off/invisible when unconfigured; with nothing configured
  beyond F1, every pre-batch test still passes unmodified.
- Full manual pass on a 390px viewport, dark theme: turn pages through three
  stories with a draft and a sealed letter interleaved; seal a story from the
  editor and see the envelope on the timeline; tap a photo full screen and
  exit with the back gesture; download the zip; `/book` prints a clean PDF
  with a cover page.
- No external requests from any page (re-check with browser devtools — this
  is checked after every batch, forever).
- Bare `pytest` green from a clean checkout.

---

## F11. HEIC/HEIF photo uploads (Android & iPhone originals)

The family's photo library is stored in compressed HEIF/HEIC (Android default
in their case; also iPhone originals via Files/AirDrop). Pillow alone cannot
decode these — uploads currently fail with `400 Could not process image`.
This is an ingestion-only change: **stored output remains plain JPEG**, so
the durability contract is untouched.

- Add `pillow-heif` to `requirements.txt`, pinned like the other deps. This
  is a deliberate exception to the minimal-dependencies rule, approved
  because every one of the family's photos is HEIF; do not add any other
  format plugin alongside it.
- In `app/storage.py`, at module import:

  ```python
  from pillow_heif import register_heif_opener
  register_heif_opener()
  ```

  That is the whole integration: `Image.open()` then handles `.heic`/`.heif`
  and the existing pipeline (EXIF transpose → resize → `convert("RGB")` →
  JPEG q85) applies unchanged. Verify `ImageOps.exif_transpose` still
  corrects orientation for HEIF (pillow-heif exposes EXIF; add a test).
- HEIF is not PNG, so the `is_png` branch stays false → output is
  `photo-NNN.jpg`. Correct; do not add a HEIF-passthrough.
- Tests (`tests/test_storage.py`): generate a real HEIC fixture in the test
  itself with pillow-heif (`Image.new(...).save(tmp / "x.heic")` after
  registering), including one with an EXIF orientation tag; upload through
  `POST /api/stories/<id>/images` in `tests/test_api.py` and assert a valid
  JPEG lands in the story folder with corrected orientation and long edge
  ≤ 2000px.
- README: add HEIC/HEIF to a short "supported photo formats" line (JPEG,
  PNG, WebP, AVIF, GIF/TIFF/BMP, HEIC/HEIF — everything except PNG is stored
  as JPEG).
