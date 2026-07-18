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

---

# Feature batch 3 — F12..F16 (voices, instants, people, rituals)

**Prerequisite: batch 2 (F0, F2–F10) and F11 are implemented; this batch
builds on them.** F13 relies on the shared partial and exclusion lists from
F0/F2/F10; F15 relies on `readable_stories()`.

Same ground rules as batch 2: all decisions are made here — implement, don't
redesign. **No new runtime dependencies** (stdlib + browser APIs + what's
already installed only). The one apparent exception, transcription (F12), is
*not* an exception: it is an optional offline script with its own separate
requirements file, and **nothing in `app/` may ever import it**. The app must
run, test, and deploy exactly as before with that script deleted.

One shared architectural rule for this batch: **no new storage formats.** An
instant is a story with one extra frontmatter key. A person is the same
folder-with-`index.md`-and-photos shape stories already use. A voice memo and
its transcript are two plain files in the story folder. `stories/` remains the
single backup unit and stays fully readable with a file browser.

**Implementation order (respect it):**
F13 instants → F15 random → F16 prompts → F12 voice → F14 people.
Commit per feature; bare `pytest` green before each commit.

---

## F13. Instants — photo + one line, fifteen seconds on a phone

A low-friction capture mode: one photo, one sentence, done. Instants live on
the timeline alongside stories but visually lighter, so real stories keep
their weight.

### Storage

New **optional** frontmatter key, parsed tolerantly like `draft`/`unlock`:

```yaml
kind: instant        # absent or any unrecognized value means "story"
```

- `Story` dataclass gains `kind: str = "story"`. `_write_index()` writes the
  key only when it is `"instant"`.
- An instant is otherwise a completely normal story folder: `title` is the
  line truncated to 60 chars (or `"Instant"` when the line is empty), `cover`
  is the photo, the body is the one line of text as a single markdown
  paragraph. Nothing else.

### API

- `POST /api/stories` accepts optional `kind`: `"story"` (default) or
  `"instant"`; any other value → 400 JSON error. `PUT` does not accept
  `kind` — it is set at creation and preserved on update.
- If `PUT /api/stories/<id>` does not already accept a `cover` field, add it:
  optional filename, must match `FILENAME_RE` and exist in the story folder,
  else 400. (F13's capture flow needs to set the cover explicitly.)

### Capture UI

- `GET /new-instant` (login required) → `instant.html`: a deliberately tiny
  form — photo `<input type="file" accept="image/*">` (no `capture`
  attribute, so the phone offers both camera and gallery), a single-line text
  input (placeholder `One line…`, maxlength 200), a date input defaulting to
  today, the author chips (same markup/localStorage behavior as the editor —
  extract the chip logic if needed rather than duplicating it), and one Save
  button. No Toast UI, no draft/seal controls.
- New `app/static/js/instant.js` (~60 lines), loaded only by `instant.html`.
  On save: `POST /api/stories` with `{title, date, kind: "instant",
  markdown: line, author}` (title derived from the line per the storage rule)
  → upload the photo via the existing images endpoint → `PUT` with
  `cover: <filename>` → redirect to `/`. Photo is required (block save with
  a message if missing); the line is optional. Disable the Save button while
  in flight. All fetches go through the `response.ok` error pattern from
  `editor.js`.
- Timeline header: next to `+ New story`, a secondary (outline-style) button
  `+ Instant` → `/new-instant`.

### Rendering

- Timeline: instants render as compact entries — small square thumbnail
  (~56px), the line in body-text style (no title styling, no title at all),
  then the usual date + author dot. Clearly quieter than a story entry.
- Story page for an instant (`/story/<id>`) works as normal (cover + line);
  `/edit/<id>` opens the full editor (kind is preserved through save — see
  API rule above).
- Instants are **excluded from**: F2 prev/next (page-turning is for stories;
  an instant's own page shows no prev/next), and F15 random. They are
  **included in**: the timeline, F5 "years ago today" banners, and F10's
  `/book` — where they render compactly (photo + line as a captioned figure,
  no drop cap, no page-break-before; they are interludes, not chapters).
- Tests: kind round-trips through create/read and survives an edit-PUT;
  invalid kind → 400; cover-PUT validation; timeline shows the compact
  entry; prev/next skips instants; random never returns one; book includes
  it compactly.

## F15. Au hasard — open a page at random

- `GET /random` (login required): pick uniformly from
  `readable_stories(...)` filtered to `kind == "story"`, excluding the story
  id in the optional `?not=<id>` query param; 302 to `/story/<id>`. No
  eligible story → 302 to `/`.
- Entry points, exact labels:
  - timeline footer line (where F8/F10 links live): `Open a page at random`;
  - story page footer, on the prev/next row: a centered `At random` link
    between the two arrows, carrying `?not=<current id>`.
- Tests: redirects to an eligible story; with 2+ eligible stories and `?not`,
  never returns the excluded id; drafts, sealed letters, and instants are
  never chosen; empty case → timeline.

## F16. Graines d'histoires — against the blank page

A gentle writing prompt shown only when starting a new, empty story. Never
inserted into the text, never generated — a plain list of questions in a
plain text file.

### Prompt source

- Default list shipped at `app/prompts/default.txt` — the exact 56 lines in
  the appendix at the bottom of this document, verbatim, one prompt per line,
  UTF-8. (They are in French — the family's writing language. The UI chrome
  around them stays in English like the rest of the app.)
- Override: if `<stories_dir>/prompts.txt` exists and contains at least one
  valid line, it is used **instead** (not merged). Lines are stripped; blank
  lines and lines starting with `#` are ignored. This file belongs to the
  family and travels with their backup.
- New `app/prompts.py`: `load_prompts(stories_dir) -> list[str]` implementing
  the above, unit-tested (default, override, override-empty falls back,
  comments skipped).

### Editor UI

- Only on `/new` (no story id) and only until the story is first saved: above
  the editor widget, a single line in small italic muted type — the prompt
  text — followed by a small `↻` button (`aria-label="Another idea"`). No
  label, no icon, no box. Tapping `↻` shows another prompt (random, not
  sequential, no repeat until the list is exhausted).
- The server injects the initial prompt and the full list into the template
  as `<script type="application/json">`; cycling is client-side in
  `editor.js` (~15 lines). Nothing is ever inserted into the editor content.
- Hidden entirely when editing an existing story or when the list is empty.
- Tests: `load_prompts` cases above; `/new` page contains a prompt;
  `/edit/<id>` does not.

## F12. La voix — voice memos on stories

The story in your own voice. Recording uses the browser's built-in
`MediaRecorder` — no library. Unlimited length.

### Storage

- Audio files live in the story folder next to the photos:
  `memo-001.webm`, `memo-002.m4a`, … — same `NNN` numbering scheme as
  photos (next free number, per-story). Allowed extensions:
  `.webm .m4a .mp3 .ogg`.
- Optional transcript sidecar: same stem, `.txt` (`memo-001.txt`), plain
  UTF-8 text. **The app only ever reads sidecars; it never writes or
  generates them.** A sidecar can be produced by the offline script below or
  typed by hand — the app cannot tell the difference and must not care.
- Discovery: no frontmatter. `storage.py` gains
  `list_memos(story_dir) -> list[Memo]` (a small dataclass: `filename`,
  `transcript: Optional[str]`), sorted by filename; filenames must match
  `memo-\d{3}\.(webm|m4a|mp3|ogg)`.

### Server

- Raise `MAX_CONTENT_LENGTH` to `128 * 1024 * 1024` (long memos; ~9 h of
  Opus). Update the 413 handler message to "max 128 MB" and the item-3 test.
- `POST /api/stories/<id>/memos` (multipart `file`): validate the extension
  against the allowlist using the uploaded filename (the client names the
  blob `memo.webm` or `memo.m4a` from the recorder's actual mimetype);
  store as the next `memo-NNN.<ext>`; return `{"filename": ...}` 201.
  Invalid extension → 400 JSON.
- `DELETE /api/stories/<id>/memos/<filename>` (filename must match the memo
  pattern above, 404 if absent): removes the audio file **and its sidecar if
  present**, returns 204. (Accidental pocket recordings are common; this is
  the one deletion the app supports, and it stays memo-scoped.)
- Playback goes through the existing `/story/<id>/media/<filename>` route —
  `send_from_directory` already answers Range requests (verify with a test
  asserting a 206 on a `Range: bytes=0-3` request; iOS Safari requires Range
  support for audio seeking).

### Recorder UI (editor page, both Toast and fallback paths)

- A "Voice" section below the editor widget: a record button, an elapsed
  `mm:ss` timer, pause/resume, and stop. On stop, upload immediately (via
  `ensureStoryId()`, same as images), then append the new memo to the list.
- Use `MediaRecorder` with `audio/webm;codecs=opus` when
  `MediaRecorder.isTypeSupported` says so, else `audio/mp4` (iOS) — file
  extension `.webm`/`.m4a` accordingly. Call `recorder.start(1000)` and
  collect chunks so long recordings don't produce one giant final buffer.
  No client-side length cap.
- Below the controls, the story's existing memos: an `<audio controls
  preload="none">` player each, plus a delete button with a
  `confirm("Delete this recording?")` guard.
- Feature-detect: if `navigator.mediaDevices?.getUserMedia` or
  `window.MediaRecorder` is missing, hide the record controls but still show
  existing memos. If the user denies the mic permission, show a one-line
  message in the section, not an alert loop.
- **README note (required):** microphone capture only works in a secure
  context — HTTPS or `localhost`. On plain LAN HTTP the record button will
  not appear; playback still works everywhere. Recommend HTTPS via the
  reverse proxy for this feature.

### Story page

- After the story body, before the footer: a "Listen" section (small-caps
  heading, same style as the date line) — one `<audio controls
  preload="none">` per memo, in order. When a memo has a transcript sidecar,
  a `<details><summary>Transcript</summary>` below its player with the text
  as paragraphs. Section absent when the story has no memos. Sealed stories
  never show memos (the envelope stays sealed).

### Offline transcription (optional, never imported by the app)

- `scripts/transcribe_memos.py`: walks a stories dir, finds memos without a
  `.txt` sidecar, transcribes with `faster-whisper`, writes the sidecar.
  CLI: `python scripts/transcribe_memos.py ./stories --language fr --model
  small` (both flags with those defaults). Print per-file progress; skip and
  warn on failure, never crash the batch.
- Its dependencies go in `requirements-transcribe.txt` **only** — never in
  `requirements.txt`, never imported anywhere under `app/`. Add a README
  section: what it does, that it downloads a model on first run (hundreds of
  MB), that it is meant to be run occasionally from a laptop against the
  stories folder (or a copy of it — sidecars can be copied back), and that
  transcripts are ordinary text files anyone can also just write by hand.
- No tests for the script itself (its deps aren't installed in CI); test the
  app-side behavior only (sidecar shown when present, absent when not).

### Tests

Upload happy path (file lands as `memo-001.webm`, 201) and numbering after
an existing memo; bad extension → 400; delete removes audio + sidecar → 204,
unknown filename → 404, traversal-shaped filename → 400/404; `list_memos`
ordering and pattern strictness; story page with/without memos and
with/without sidecar; Range → 206; auth required on all memo endpoints.

## F14. Personnages — the cast of the book

Real books introduce their characters. One page per recurring person — who
they are *to him*.

### Storage

- `stories/people/<slug>/index.md` + photos, inside the existing stories
  dir — **one backup folder, unchanged**. `list_stories()` must skip the
  `people/` entry silently (explicitly, no "malformed folder" warning; add a
  test).
- Frontmatter: `name` (required), `relation` (optional free text, e.g.
  `"your grandmother"`), `photo` (optional filename in the same folder — the
  portrait), plus `created`/`updated` like stories. Body: free markdown
  about the person. Slug from `name` via the existing `slugify`, same `-2`
  collision rule; photos via the **same** image pipeline (refactor
  `save_image` so stories and people share it — resize/EXIF/naming
  identical, `photo-NNN` numbering).
- New `app/people.py` mirroring `storage.py`'s shape: `list_people`,
  `get_person`, `create_person`, `update_person` — pure functions taking the
  people dir, same atomic-write rule, same tolerant parsing (missing `name`
  → skip with a logged warning).

### Routes & pages

- `GET /people` → `people.html`: a card grid — portrait (square,
  `object-fit: cover`, subtle rounded corners; a neutral initial-letter
  placeholder when no photo), name, relation. Sorted by `created` ascending
  (the order they entered the book). Empty state: one quiet sentence and the
  New button. Header: `+ New person`.
- `GET /people/<slug>` → `person.html`: styled like a story page — relation
  as the small-caps line where the date goes, name as the title, portrait as
  the cover, body below. Footer: `‹ People` and `Edit`.
- `GET /people/<slug>/media/<filename>`: same validation/serving as story
  media.
- `GET /new-person`, `GET /edit-person/<slug>`: the editor page, reused (see
  below).
- API: `POST /api/people` (`{name, relation, markdown}`, name required →
  400 when blank), `PUT /api/people/<slug>`,
  `POST /api/people/<slug>/images` (returns `{"filename": ...}`; the first
  uploaded image becomes `photo` automatically if `photo` is not yet set).
- Nav: a `People` link in the top nav, always visible (it is the only way to
  discover the feature; the empty state explains it).
- Markdown image srcs in a person body must resolve to the person's media
  route: generalize the existing image-rewriting treeprocessor to take a
  media base path instead of hardcoding `/story/<id>/media/`.

### Editor reuse — do not fork editor.js

Parametrize instead of duplicating: `editor.js` currently hardcodes
`/api/stories...` endpoints. Change it to read its endpoints from the form's
data attributes (`data-create-url`, `data-update-url-template`,
`data-image-url-template`, `data-redirect-template`), with the story
editor template supplying today's values — behavior identical. The person
editor template supplies the people endpoints, omits the date input, the
author chips, the draft/seal controls, and the voice section, and relabels
the title input `Name` plus one extra plain text input `Relation`.
`editor.js` must tolerate all of those being absent (most already are
optional in batch 2's markup — keep it that way). Prompts (F16) do not
appear on person pages.

### Linking, deletion, book

- Stories link to people manually in markdown
  (`[Mamie](/people/mamie)`) — no auto-linking, no mention syntax; state
  this in the README.
- No person deletion (consistent with stories).
- People do **not** appear in `/book` or on the timeline in this batch.

### Tests

CRUD happy paths; blank name → 400; slug collision; people dir skipped by
`list_stories` without warning; person media traversal rejected; first image
becomes portrait; pages render (grid, person page, empty state); auth
required; story editor still works against its own endpoints (existing
editor tests stay green).

---

## Batch 3 definition of done

- With batch 3 deployed and nothing new configured: timeline, stories, and
  all batch-2 features behave exactly as before until someone records a
  memo, saves an instant, or creates a person. Every pre-batch-3 test passes
  unmodified (except the 413 limit test, updated per F12).
- Manual pass on a real phone (390px, dark): capture an instant end-to-end
  in under 20 seconds; record a 2-minute memo over HTTPS, play it back with
  seeking, delete a junk take; drop a hand-written `memo-001.txt` next to a
  memo and see the transcript appear; create two people and visit their
  pages; tap "Open a page at random" three times.
- `stories/` inspected by hand afterwards: instants, memos, sidecars, and
  people are all obvious, readable files in obvious places.
- No external requests from any page — including while recording.
- Bare `pytest` green from a clean checkout.

---

## Appendix — `app/prompts/default.txt` (copy verbatim, one per line)

```
Qu'est-ce qui t'a fait rire aux éclats cette semaine ?
Raconte le petit rituel du soir en ce moment, minute par minute.
Quel mot inventes-tu ou écorches-tu en ce moment ? Qui te comprend à ta place ?
Décris un dimanche matin ordinaire de cette période de ta vie.
Qu'est-ce que tu refuses catégoriquement de manger en ce moment — et la tête que tu fais ?
Raconte la dernière conversation surprenante qu'on a eue avec toi.
Quel jouet (ou objet improbable) ne te quitte jamais en ce moment ?
Raconte ta première rencontre avec quelqu'un qui compte aujourd'hui dans ta vie.
Qu'est-ce qui te fait peur en ce moment, et comment on te rassure ?
Décris ta chambre telle qu'elle est aujourd'hui, comme si on la faisait visiter.
Raconte le jour où on a appris que tu allais arriver.
Comment on a choisi ton prénom — et ceux qu'on a failli te donner.
Raconte ta naissance, du point de vue de celui ou celle qui écrit.
À quoi ressemblait la maison le jour où tu es arrivé ?
Quelle chanson te calme (ou te déchaîne) en ce moment ?
Raconte une bêtise récente qu'on n'a pas réussi à gronder sans rire.
Qu'est-ce que tu fais en ce moment qui ressemble trait pour trait à ton père ou ta mère ?
Raconte le trajet qu'on fait le plus souvent ensemble, et ce que tu y regardes.
Quel livre on te lit en boucle, et à quel moment tu ris ou tournes la page ?
Décris tes mains, tes pieds, tes cheveux en ce moment — ils changent si vite.
Raconte un moment récent où tu as été incroyablement courageux.
Qu'est-ce que tu dis au réveil, en ce moment ?
Raconte la dernière fois qu'on a dansé ou chanté ensemble dans la cuisine.
Quel est ton plat préféré du moment, et comment tu le manges ?
Raconte une visite chez tes grands-parents, telle qu'elle s'est vraiment passée.
Qu'est-ce qu'on aimerait que tu saches sur cette période de notre vie de parents ?
Raconte une nuit difficile — honnêtement — et ce qu'on s'est dit à trois heures du matin.
Décris ton rire. Vraiment. Qu'on l'entende en le lisant.
Quelle est ta cachette ou ton coin préféré de la maison en ce moment ?
Raconte tes premiers pas (ou le premier « presque »).
Quel a été ton premier mot — et le contexte exact ?
Raconte un anniversaire (le tien ou celui de quelqu'un d'autre) vu par toi.
Qu'est-ce que tu collectionnes ou accumules mystérieusement en ce moment ?
Raconte une grosse colère récente, et ce qui se passait vraiment derrière.
Décris comment tu t'endors, et ce qu'il faut absolument pour y arriver.
Raconte la première fois qu'on t'a vu te faire un ami.
Qu'est-ce que tu réclames « encore ! » sans jamais te lasser ?
Raconte une sortie récente — marché, forêt, piscine — avec un détail que toi seul as remarqué.
Quelles sont les personnes que tu réclames par leur nom en ce moment ?
Raconte le moment de la journée qu'on préfère secrètement passer avec toi.
Qu'est-ce que la saison actuelle change à tes journées — flaques, neige, cerises ?
Raconte un objet de famille qu'on veut te transmettre, et son histoire.
Qu'est-ce qu'on faisait, nous, à ton âge ? Raconte un souvenir d'enfance en miroir.
Raconte la dernière fois que tu nous as impressionnés sans le savoir.
Décris un repas complet avec toi en ce moment, du début motivé à la fin par terre.
Quelle expression ou grimace fais-tu qu'on veut absolument ne pas oublier ?
Raconte comment tu accueilles les gens qui passent la porte.
Qu'est-ce que tu fais quand tu crois qu'on ne te regarde pas ?
Raconte une promesse qu'on se fait à ton sujet en ce moment.
Quel métier ou quelle passion déclares-tu vouloir faire plus tard, cette semaine ?
Raconte la dernière photo qu'on a prise de toi : ce qu'il y a autour, avant, après.
Qu'est-ce qui a été difficile pour nous cette semaine, et pourquoi ça valait le coup quand même ?
Raconte le bain en ce moment : la logistique, les inondations, les jouets.
Décris ta voix en ce moment, les phrases que tu répètes, ton accent à toi.
Raconte une tradition familiale qu'on est en train d'inventer avec toi.
Qu'est-ce qu'on voudrait te dire aujourd'hui, si tu pouvais tout comprendre ?
```

# F17. Le style du ranch — hand-drawn visual identity

The interface gets a set of hand-engraved western-storybook illustrations
(generated once, committed as static files — the app never fetches anything).
The processed assets are already committed under `app/static/img/`:

| file | size | where it goes |
|---|---|---|
| `tumbleweed.jpg` | 900×488 | 404 page |
| `sealed-letter.jpg` | 576×495 | sealed-story page |
| `empty-chest.jpg` | 653×729 | drafts + archived empty states |
| `person-oval.jpg` | 600×732 | person placeholder + people empty state |
| `instant-camera.jpg` | 522×652 | /new-instant decorative accent |
| `book-frame.jpg` | 715×897 | /book cover ornament |
| `rope-divider.png` | 1000×144, transparent | flourishes/dividers |
| `lasso-ring.png` | 320×320, transparent, centered | loading spinner |

Also committed: `login-campfire.jpg` (856×735) — the login-page
illustration, reused for the empty-timeline state — and the leather-journal
app icon regenerated over the old placeholder icons at
`app/static/icons/icon-512.png`, `icon-192.png`, and
`apple-touch-icon.png` (same filenames; the manifest and templates need no
path changes). Wire the login page and empty-timeline placements like every
other card: the login page shows the campfire card between the subtitle and
the password field (max-width 20rem), the empty timeline shows it above the
"No stories yet" line.

## The paper-card treatment (the key to theming)

Every JPEG illustration carries its own cream paper background, so it is
displayed as a "paper card pinned to the page": a shared `.illo` class —
background the same cream as the illustrations (sample it from any of the
JPEGs; they are consistent), padding ~0.75rem, a thin border using the
light theme's border color regardless of theme, border-radius 4px, a soft
shadow, and a slight rotation (default -1.2deg; add `.illo--tilt-right`
with +1deg to alternate). The card stays cream in ALL themes — in dark
mode it reads as a photograph card in an album, which is the intent. The
transparent PNGs (`rope-divider.png`, `lasso-ring.png`) are NOT cards —
they sit directly on the page background in every theme.

Every decorative `<img>` gets `alt=""`, `loading="lazy"`,
`decoding="async"`, and explicit `width`/`height` attributes (no layout
shift). Displayed sizes are roughly half the pixel size (they are 2×
assets). Total added weight per page stays under ~150 KB — each page uses
at most one or two illustrations.

## Placements

- **404**: tumbleweed card above the existing message, max-width 20rem.
- **Sealed page**: sealed-letter card replaces the inline envelope SVG,
  max-width 18rem; keep the title and "opens on" line unchanged.
- **Drafts / Archived when empty**: chest card, max-width 14rem, above a
  one-line empty message (add one if missing, e.g. "Nothing here — drafts
  you start will wait in this chest.").
- **People**: grid placeholder portraits use `person-oval.jpg` as the tile
  image with the person's initial rendered on top (absolutely positioned
  over the oval's center, current font/color); people empty state shows the
  same oval card with the existing empty text.
- **/new-instant**: camera, small (max-height 9rem), centered above the
  photo picker, hidden on viewports under 700px tall so the form stays
  above the fold — the 20-second flow must not get slower or longer.
- **/book cover**: `book-frame.jpg` centered on the cover page with the
  book title, year range, and author legend overlaid INSIDE the frame
  opening (absolute positioning over the image); frame max-width 24rem on
  screen. In print (`@media print`) keep it — it prints beautifully — but
  verify the title stays inside the opening at A4.
- **Flourishes**: the `· · ·` separator in /book and the `story__flourish`
  hr on story pages become `rope-divider.png` (`width: 240px` in book,
  `160px` on story pages, centered; keep an `<hr>`/role for semantics).
- **Spinner**: `.lasso-spinner` = `lasso-ring.png` at 40×40, CSS
  `animation: spin 1.4s linear infinite`. Under
  `prefers-reduced-motion: reduce`, no rotation — pulse opacity instead.
  Show it: on /new-instant next to the disabled Save while uploading, on
  /import while the restore request runs, and in the editor save bar while
  saving. Never block input with it; it is an indicator only.

## Rules

No new dependencies. No external requests (re-verify after — the images
are local static files). The story/instant/person markdown format is
untouched — this feature is chrome only. `pytest` green; update any test
that asserts on the sealed page's SVG or the flourish markup.

Definition of done: phone-width pass of 404, sealed, drafts (empty),
people (with and without portraits), /new-instant, /book (screen + printed
PDF), a story page, in all three themes — paper cards read as cards on
dark; transparent rope elements show no cream box; no horizontal scroll;
no cumulative layout shift when images load; zero external requests.

# F18. L'arbre — the family tree

A genealogical tree built on the people pages (F14), designed in three
layers with different life expectancies: facts in frontmatter (forever),
a Python kinship engine with a JSON contract (life of the app), and a
vendored JS renderer (replaceable). The renderer — family-chart 0.9.0 +
d3 7.9.0 — is **already committed** under `app/static/vendor/familychart/`
and `app/static/vendor/d3/` (pinned, licensed, audited for zero network
calls; see VENDORED.md there). Do not fetch anything from npm.

Ground rules: no new pip dependencies; the vendored JS is the only new
front-end code source; every new frontmatter field is optional and
tolerantly parsed; the whole feature is invisible until the first family
link exists; the backup format does not change.

## Layer 1 — facts in frontmatter (`stories/people/<slug>/index.md`)

New optional fields, all slugs referring to other people:

```yaml
parents: [papi-georges, mamie-lise]   # this person's parents
partners: [claire]                    # spouses/companions (symmetric)
friend_of: [papa]                     # for friends: whose friend they are
gender: m                             # m | f, only used to pick label words
```

- Store ONLY these atomic facts. Never store computed kinship ("uncle",
  "cousin") — it is always derived. The existing free-text `relation`
  field stays and, when present, wins over any computed label.
- `parents` is the single source of parent/child truth; children are
  computed by reverse lookup. Cap of 2 parents enforced on write; extra
  entries on disk are read tolerantly.
- `partners` is symmetric: the API writes both sides; reads take the
  union of both directions so a hand-edited single side still works.
- Dangling or unknown slugs anywhere: ignored silently. Files outlive
  edits.
- `Person` dataclass gains `parents`, `partners`, `friend_of` (lists,
  default empty) and `gender` (optional). Writers omit empty fields.

## Config

`STORYBOOK_CHILD=<slug>` (optional, alongside STORYBOOK_BIRTHDATE in
.env.example + README): the anchor person all kinship labels are relative
to. Unset or slug not found → no kinship labels, everything else works.
The child should get his own person page — document that in the README
("create a person for your child and point STORYBOOK_CHILD at it").
When the book is inherited, the heir re-points this one line and every
label re-anchors to the next generation.

## Layer 2 — kinship engine (`app/kinship.py`, new, stdlib only)

- `build_graph(people) -> Graph`: nodes by slug; parent and partner edges
  (partner edges from the union of both sides).
- `children_of`, `siblings_of` (share ≥1 parent), `partners_of` helpers.
- `kinship_label(graph, anchor_slug, person_slug) -> str | None`:
  BFS from anchor over parent/child edges, classify by (steps up, steps
  down), gendered word when `gender` is set:
  - up n: parent / grandparent / great-grandparent / (n-2)×"great-" —
    m: father→"your father", grandfather…; f: mother…; absent: parent…
  - down n: son/daughter/child, grandson… (used when anchor is an
    ancestor of the person's descendants view — labels are always about
    the PERSON relative to the anchor: "your uncle", "your cousin")
  - up 1 + down 1: brother / sister / sibling
  - up 2 + down 1: uncle / aunt / "aunt or uncle"
  - up n≥3 + down 1: great-uncle / great-aunt (one "great-" per extra step)
  - up 2 + down 2: cousin; anything deeper or unequal: "cousin"
  - up 1 + down 2 does not exist from a child anchor; nephews/nieces
    (down via sibling) appear when the anchor changes generations:
    sibling's child = nephew / niece / "niece or nephew"
  - partner of a labeled relative, not otherwise related: "X's husband /
    wife / partner" using the closest labeled relative's short label
    (e.g. "your uncle's wife"). One hop only — beyond that, no label.
  - unreachable from anchor: None.
- Cycle guard: `would_create_cycle(graph, child, new_parent) -> bool`
  (a person cannot be their own ancestor).
- All label text in English, matching the app UI. Unit-test the label
  table exhaustively with a fixture family of ~15 people including a
  great-grandmother, an uncle by marriage, and a half-sibling.

## API

- `PUT /api/people/<slug>` (and POST create) accepts `parents`,
  `partners`, `friend_of` (lists of slugs) and `gender` ("m"/"f"/"").
  Validation, each → 400 with a clear message: unknown slug; self
  reference; >2 parents; parent cycle (use the cycle guard); gender not
  in {m, f, ""}.
  Partner symmetry: when partners change, update the other person's file
  too (add/remove the reverse link); their `updated` timestamp changes —
  that is correct and version history (F8) records it.
- `GET /api/tree` (login required): the Layer-2/3 contract —
  ```json
  { "anchor": "milo",
    "people": [ { "id": "papi-georges", "name": "Papi Georges",
      "gender": "m", "photo": "/people/papi-georges/media/photo-001.jpg",
      "url": "/people/papi-georges", "kinship": "your grandfather",
      "rels": { "parents": ["henri"], "partners": ["mamie-lise"],
                "children": ["papa", "remi"] } } ] }
  ```
  `anchor` null when unset; `photo` null when none; `kinship` null when
  no anchor or unreachable; `rels.children` computed. Friends (people
  whose only link is `friend_of`) are included with a `"friend_of":
  [...]` key instead of `kinship`. Document this contract in the README —
  it is the seam future renderers plug into.

## Person pages (works without JavaScript)

- A "Family" section after the body, computed server-side: Parents,
  Partner, Children, Siblings — name links to their pages, portraits as
  small inline thumbs where available. Rendered only when non-empty.
- The kinship label: when an anchor is set and `relation` (free text) is
  absent, the small-caps line above the name uses the computed label
  ("YOUR GREAT-GRANDMOTHER"). Free-text `relation` always wins.
- Friend pages: the small-caps line reads "Friend of Papa" (linked),
  from `friend_of` + the same relation-wins rule.

## Person editor — filling the tree in

A "Family" fieldset below Relation, shown only when at least one other
person exists: three pickers (Parents — up to two, Partner, Friend of),
each a row of person-chips reusing the author-chip look (portrait thumb +
name, tap to toggle), plus a Gender segmented control (M / F / unset).
editor.js includes the values in the person PUT payload. No drag-and-drop
tree editing — the pickers are the entire editing surface.

## Layer 3 — the /tree page

- `GET /tree` (login required): page with a full-height chart container,
  loading the vendored `d3.min.js`, `family-chart.min.js`,
  `family-chart.css`, and a new `app/static/js/tree.js` (~80 lines) that
  fetches `/api/tree`, maps it to family-chart's Datum format
  (`{id, data: {label, avatar, gender}, rels: {parents, spouses,
  children}}`; gender absent → "M" is NOT assumed, pass the field only
  when known and default the card styling to neutral), and calls
  `f3.createChart('#FamilyChart', data)` with `setCardHtml()`, card
  display = name, `cardImageField` avatar (fallback: the
  `person-oval.jpg` asset), main id = anchor (else first person),
  `setSingleParentEmptyCard(false)`, vertical orientation, transition
  ~600ms. Card click navigates to the person's page; the mini re-root
  control (library default) stays enabled so any family member can
  become the center. Hide the library's edit/add-relative UI — editing
  happens only in the person editor.
- Ranch restyle in main.css (scoped under `.page-tree .f3`): cream card
  faces (`--card` tokens per theme), umber connectors, gold border on the
  main card, Georgia/serif labels, neutralize the library's pink/blue
  gender fills in ALL themes. The dark theme shows dark cards with cream
  portraits — cards here are chart cards, not F17 paper cards.
- Below the chart, a plain HTML list "Friends & others": friends (with
  "friend of X") and people with no links at all. Nothing is ever
  invisible just because it is unlinked.
- Discoverability: a "Family tree" link on the /people page header, shown
  only when at least one person has parents or partners; same condition
  for showing nothing at /tree except a gentle empty state ("Link two
  people in the person editor and the tree will grow here.").
- Print: `@media print` hides the chart and shows the "Friends & others"
  list plus a note to use the app for the interactive tree (a dedicated
  print layout is a future feature — do not attempt it here).

### View scopes (added after dogfooding)

The hourglass layout only ever shows the main person's direct line, so
collateral relatives (aunts, uncles, cousins) become visible by rooting
the layout at an ancestor. A toolbar above the chart, built by tree.js
from the ancestor levels that actually exist for the focus person:

- **Direct line** — main = focus (the original behavior).
- **Grandparents' branch**, **Great-grandparents' branch**, … — one
  button per intermediate ancestor level; rooting at a grandparent shows
  aunts/uncles (their children) and cousins (their grandchildren).
- **Whole family** — rooted at the focus's deepest ancestor.
- When a level has several couples (paternal vs maternal side), "via
  Rose & Jean" chips pick the branch; couples are grouped by partner
  links, first couple is the default.
- The focus person keeps a thin gold ring (`card-inner--focus`) in
  rooted views so they stay findable; the full brand stays on
  `card-main` (the current root). The mini-tree control now moves the
  focus and resets to Direct line.
- The toolbar is hidden when the focus has no recorded ancestors, and
  hidden in print with the chart.

### The moving survey map (added after dogfooding)

The R5.7 map background was a static CSS JPEG on the container, so it
stayed put while the chart panned underneath. Replaced by an SVG
`<pattern>` filling a large rect injected as the first child of the
chart's `g.view` pan/zoom group — it translates and scales in lockstep
with the tree. The pattern holds two seamless 1024px raster tiles
(`tree-map-tile-dark.jpg` dark leather, `tree-map-tile.jpg` parchment;
image-model art post-processed to tile: vignette flattened, edges
torus-blended along the measured 128px grid period, ornament patched
out); CSS shows the tile matching the theme (`tree-map-img--dark/
light`), the container keeps only the base leather/parchment color.
The old full-bleed `tree-map.jpg` / `tree-map-dark.jpg` are no longer
referenced.

### Second dogfooding round: editor hint, recenter, kinship on cards,
### honest branch depth, remembered view

- **Empty-editor hint.** When `/new-person` or `/edit-person/<slug>`
  has no `other_people` yet, the Family fieldset used to simply not
  render — someone filling in their very first person had no clue it
  existed. `person_editor.html` now renders `<p class="editor__family-hint">`
  in its place: "Add another person and you'll be able to link parents,
  a partner, and gender here…". The hint's class deliberately avoids the
  literal substring `editor-family` so it doesn't trip the existing
  "fieldset absent" tests, which assert that exact string is nowhere in
  the response.
- **Recenter button.** `family-chart` auto-fits the tree to the viewport
  on every `updateTree()` (a d3-zoom transform on `#f3Canvas`, exposed
  as `canvas.__zoomObj`), but a reader who pans/zooms away has no way
  back short of reloading. `tree.js` snapshots that transform via
  `d3.zoomTransform(canvas)` ~650ms after each render settles (matching
  `setTransitionTime(600)`) and a pinned `.tree__recenter-btn` in the
  chart's corner re-applies it with `canvas.__zoomObj.transform`.
- **Kinship labels on cards.** `/api/tree` already computed
  `kinship` per person (F18 Layer 2); it just wasn't surfaced in the
  chart. Cards now show it in small caps under the name
  (`.f3-card-kinship`, with a `title` attribute so a long label like
  "your great-great-grandmother" is still readable via hover/long-press
  when the 12rem card truncates it). Card width bumped 10rem → 12rem so
  the common cases ("your grandfather", "your cousin") fit without
  truncating.
- **Honest branch depth ("Whole family" bug fix).** The view-scope
  toolbar's level buttons used to re-root at `levels[lv-1][0]` — the
  first ancestor at that depth from ANY branch, regardless of which
  branch the reader had already drilled into. Clicking "Whole family"
  while looking at the maternal grandparents could silently jump to an
  unrelated paternal great-grandmother. Fixed by tracking a `chain[]` of
  the ancestor selected at each depth (extended via
  `TreeLogic.chainToLevel`, which walks the first parent one generation
  at a time from whichever root is already selected) — level buttons now
  extend the CURRENT branch, and a branch that runs out of recorded
  ancestors just stops there instead of jumping elsewhere. `viewLevel`
  is always derived from `chain.length`, so the toolbar's pressed state
  reflects what's actually on screen (if "Whole family" only reaches
  depth 2 on this branch, the depth-2 button shows pressed, not
  "Whole family"). The pure chain/level logic (`ancestorLevels`,
  `coupleGroups`, `levelLabel`, `chainToLevel`) was extracted out of
  `tree.js` into `app/static/js/tree-logic.js`, a dependency-free
  UMD module, specifically so it could be unit-tested (see Tests below)
  — this is also what made the original arbitrary-pick bug easy to spot
  and fix with confidence.
- **Remembered view.** The chosen `{focusId, chain}` is saved to
  `localStorage["storybook-tree-view"]` on every view change and
  restored on the next `/tree` visit (only when `focusId` still matches
  and every chain entry still resolves to a real person — a deleted
  person or a changed `STORYBOOK_CHILD` just falls back to Direct line).
  Silently no-ops when localStorage is unavailable (private browsing,
  quota) — nothing else depends on it.
### Code-review fixes round

A recall-focused review of the second dogfooding round above turned up
several real bugs and duplication in the same view-scope/map-background
code, before any of it shipped to a wider audience. Fixed:

- **Branch-chip chain corruption.** Switching branches used to patch
  only the deepest chain entry (`chain.slice(0, viewLevel - 1)
  .concat([group[0]])`), which is wrong whenever the new couple is on a
  different lineage than what's already in the chain (paternal vs.
  maternal) — clicking a maternal grandparents chip while chain was
  `['papa', 'papi-jean']` produced `['papa', 'papi-paul']`, and
  papi-paul isn't papa's parent. `tree-logic.js` gained `ancestorPath`
  (walks the parent graph from focus to find the REAL chain reaching a
  target ancestor), and the branch-chip handler now uses that instead
  of patching.
- **Stale localStorage chains.** `restoreSavedView` used to accept a
  saved chain as long as every id still existed as *some* person,
  never checking the links were still parent/child — so an edited
  parent link could restore an internally inconsistent view instead of
  falling back to Direct line as documented. `tree-logic.js` gained
  `isValidChain`; an invalid saved chain is now discarded entirely.
- **Toolbar level-1 gap.** The level-button loop skipped level 1
  whenever the tree went deeper than one generation (it looked
  redundant with Direct line), but a branch that dead-ends after one
  generation can legitimately leave `viewLevel` at 1 — with no button
  for it, nothing showed pressed. The loop now always includes level 1
  (given its own "Parents' branch" label, fixing an old off-by-one
  where `levelLabel(1, deepest)` collided with level 2's label).
- **Keyboard focus loss.** `renderToolbar()` rebuilds every button via
  `innerHTML = ""` on each click, which silently dropped keyboard
  focus to `<body>`. It now remembers whether focus was inside the
  toolbar before rebuilding and restores it to whichever button ends
  up pressed.
- **Focus-person gold ring never rendered.** `.card-inner--focus`'s
  border/box-shadow lost a CSS specificity tie to the older, more
  specific `div.card-inner` rule, so the ring was always overridden.
  Fixed by matching that rule's specificity.
- **Map background double-fetch.** Both theme tiles were always
  inserted into the SVG pattern, with CSS `display:none` hiding the
  inactive one — which doesn't stop the browser fetching/decoding it.
  Only the active theme's tile is injected now, with a
  `MutationObserver` on `data-theme` and a `prefers-color-scheme`
  listener to swap it live if the reader changes theme mid-session.
- **Recenter timing.** The 650ms snapshot delay was guessed to match
  `setTransitionTime(600)`, but the vendored bundle's fit transition
  adds its own 100ms pre-delay before that duration starts — settling
  at ~700ms, not 600ms. Bumped to 720ms so Recenter doesn't capture a
  still-interpolating transform.
- **Pedigree collapse.** `ancestorLevels`'s single, all-levels `seen`
  map meant an ancestor reachable via two lineages at different depths
  (a remarriage or cousin match) was silently dropped from the deeper
  occurrence. Dedup now happens only within a level, with a
  generation-count cap standing in for the removed cycle guard.
- **escapeHtml() didn't escape quotes** — fine for text content, not
  safe for the `title=`/`href=` attribute contexts this round started
  using it in. Now escapes `"` and `'` too.
- **Decorative SVG map elements** (the injected `<image>`/`<rect>`)
  now carry `aria-hidden="true"`, matching how the old CSS background
  was invisible to assistive tech by construction.
- **installMapBackground()** now `console.warn`s instead of silently
  no-op'ing if the vendored bundle's internal SVG structure
  (`svg.main_svg` / `g.view`) ever stops matching, so a future
  vendored-library upgrade that breaks it is at least debuggable.
- **Cleanup:** `.tree__view-btn`/`.tree__recenter-btn` now compose
  with the existing `.btn` class instead of re-declaring its
  flex-centering/font/cursor from scratch. A new
  `app/static/js/safe-storage.js` (same dependency-free UMD shape as
  `tree-logic.js`) centralizes the try/catch-wrapped localStorage
  access that `tree.js`, `editor.js`'s autosave, and `author-chips.js`
  each used to reimplement independently.

Tests: `tests/js/tree_logic_test.mjs` gained coverage for
`ancestorPath`, `isValidChain`, the level-1 label, and the pedigree-
collapse case; a new `tests/js/safe_storage_test.mjs` covers the
storage wrapper (including simulated private-mode/quota failures).

### Multi-branch rendering round

The branch-chip toggle above let a reader see one ancestor couple's
descendants at a time, but never two at once — so paternal and maternal
grandparents (or any two couples at the same depth) could never appear
together on screen, only reached one at a time. Rooting the chart
directly at the focus person (level 0, "Direct line") was never actually
broken this way: a person has at most two parents, so a pedigree rooted
at them already recurses through both sides simultaneously. The gap was
specific to levels ≥ 1, which exist to reveal *lateral* relatives
(aunts/uncles/cousins) by re-rooting at a specific ancestor to show
*their* descendants — and one ancestor's descendants are a different,
disjoint subtree from their partner-couple's counterpart on the other
side. No single-root hourglass can show two disjoint subtrees in one
drawing.

Fixed by replacing the single chart + branch-chip switcher with one
independent `family-chart` instance **per ancestor couple** at the
chosen level, rendered together — stacked on phones, a `repeat(auto-fit,
minmax(20rem, 1fr))` grid from `700px` up (`.tree__panels` /
`.tree__panel` in `main.css`), each captioned "via Name & Name" and each
fully interactive (its own pan/zoom, mini-tree re-root, Recenter). Level
0 is untouched — still the single big chart. This reuses the
already-vendored, network-audited `family-chart` + `d3` bundle as
multiple independent mounts; no new dependency, no vendored-file changes.

This also deleted code rather than adding much: with every couple at a
level shown at once, there's no more "which branch is selected" to
track, so `tree-logic.js`'s `ancestorPath`, `isValidChain`, and
`chainToLevel` — and the `chain[]`/branch-chip machinery in `tree.js`
built around them — are gone. View state is now just `{focusId,
viewLevel}`; `ancestorLevels` and `coupleGroups` (unchanged) are enough
to compute which panels a level needs on every render. Charts are always
torn down and rebuilt on a level or focus change rather than re-rooted
in place — the same "just rebuild it" approach `renderToolbar()` already
used — since the number of panels needed can change between any two
levels. One consequence: the injected ranch-map SVG pattern/image ids
(`tree-map-grid-*`) are now suffixed per panel, since `url(#id)`
resolves against the whole document and several simultaneous panels
would otherwise fight over one id; the `MutationObserver`/
`prefers-color-scheme` listener that refreshes them on a theme change
was hoisted to run once for the page instead of once per chart instance,
which would have leaked a new observer on every rebuild.

Tests: `tests/js/tree_logic_test.mjs` dropped the now-dead
`ancestorPath`/`isValidChain`/`chainToLevel` coverage and gained a
`coupleGroups` case asserting the paternal and maternal branches land in
separate groups, which is what the multi-panel view depends on.

### Print outline round — closing the print/PDF gap

`/tree` never had a print representation of the family itself — only
"Friends & others" and a static note survived `@media print`, since the
interactive chart obviously can't. Rather than trying to make an SVG
chart survive print, the note is replaced with a plain-text generation
outline, server-rendered (works without JS, like every other family
page): headings such as "Great-grandparents' generation" / "Parents'
generation" / "Milo's generation" / "Children's generation", oldest
first, each listing names with their existing computed kinship label
("Papi Paul — your grandfather").

Each in-family person gets a **generation offset** relative to
`STORYBOOK_CHILD`: positive toward ancestors, negative toward
descendants, 0 for the anchor's own generation. This is measured from
each person's own nearest common ancestor with the anchor (`kinship.py`'s
existing `_blood_updown`, extracted out of `_blood_kinship` — same
`(up, down)` pair `kinship_label` already computes, just exposed as a new
`generation_offset()` alongside it) — deliberately **not** a structural
"depth from the deepest recorded root," which would misfile a grandparent
a whole generation off whenever their own parents aren't recorded (the
fixture family already has exactly this shape on the maternal side). An
offset bucket like "Parents' generation" intentionally mixes real parents
with aunts/uncles (same net distance) — that's colloquially accurate, not
a bug, and the per-person kinship label still gives the precise relation.
A person reachable only via one hop of partnership (e.g. an uncle's wife
with no blood link of her own) inherits her partner's offset, mirroring
`kinship_label`'s existing "your uncle's wife" fallback; someone
reachable by neither blood nor that one hop (an isolated in-law couple
with no connection to the family's blood graph) lands in a final "Other
family" bucket rather than silently vanishing. Without `STORYBOOK_CHILD`
set, generation math doesn't apply — everyone in-family lands in one
plain "Family" bucket, same as kinship labels already disappearing
app-wide without an anchor.

`routes_pages.py`'s `tree_page()` folds this into the loop that already
built the `others` list (no second pass over `all_people`), bucketing by
`kinship.generation_offset()` and sorting real offsets descending
(oldest generation first) before rendering. `tree.html` renders it as
`.tree__print-outline`, `display: none` on screen and forced to `display:
block` inside `main.css`'s existing `@media print` block, the same
shape `.tree__print-note` used before it.

Tests: `tests/test_kinship.py` gained a `generation_offset` table
parametrized against the same 16-person fixture the kinship-label table
already uses (including the great-uncle/uncle's-wife/cousin cases, plus
an isolated-partner-pair case for the "no path at all" `None` result) and
a `generation_group_label` table; `tests/test_family_pages.py` gained
`/tree` cases for the anchored multi-generation outline, the unanchored
single-bucket fallback, and confirming friends/unlinked people never leak
into the outline.

### Tests (second round)

`tests/js/tree_logic_test.mjs` — plain Node, no framework or npm
dependency, exercises `tree-logic.js`'s pure functions against a small
fixture family (three generations plus one paternal-only
great-grandmother), including the specific regression case: switching to
a branch with no recorded parents and then clicking "Whole family" must
stay on that branch rather than jumping to the other side's deeper
ancestor. Wired into the pytest suite via `tests/test_tree_logic_js.py`,
which shells out to `node` and skips (not fails) if it isn't on `PATH` —
GitHub's `ubuntu-latest` runners ship Node by default, so this still
runs in CI without adding a Node setup step. Server-rendered pieces
(the empty-editor hint, `tree-logic.js` load order) are covered in
`tests/test_family_pages.py` the normal way.

### "Everyone" round — one canvas for the whole family

Real dogfooding feedback: neither existing view actually shows everyone
at once. "Direct line" is one chart, but only the focus's own ancestors —
no siblings, aunts, uncles, or cousins. "Whole family" reveals those, but
splits every ancestor couple at the deepest level into its own separate
side-by-side panel — paternal and maternal branches are two disconnected
charts a reader has to pan/zoom individually, and a family with more than
two branches gets more scattered panels, not fewer.

Closed by adding a fourth toolbar option, "Everyone", that renders every
branch in **one** `family-chart` instance instead of one per couple.
`family-chart` only ever draws the ancestors-and-descendants of a single
`main_id`; there's no library-native way to hand it several disjoint
lineages at once. The fix is a synthetic, hidden root: `tree.js` computes
one representative id per otherwise-disjoint blood lineage
(`TreeLogic.rootAncestors`) and adds one extra card, `EVERYONE_ROOT_ID`
(`"__everyone__"` — can't collide with a real slug, since
`storage.slugify()` strips every non a-z0-9 character server-side)
listing those ids as its `rels.children`. Rooting the chart there makes
it recurse down through every lineage in a single pass; the root's own
card is hidden via a `[data-id="__everyone__"]` CSS rule in `main.css`,
but the connector lines above each real branch still draw, reading as
one shared family rather than implying a fake shared ancestor.

**Picking the roots correctly was the actual difficulty.** A naive "every
person with no recorded parents" filter is wrong: it also catches anyone
who married into an otherwise-connected lineage but whose own parents
just were never recorded (a very common case, not a different family
branch). Including them as a *second*, independent root would draw their
married-in partner's entire descendant subtree a second time, for no
reason — since they'd already be pulled in automatically as their
partner's spouse once the partner's own (recorded) lineage is rooted.
`TreeLogic.rootAncestors(ids, parentsOf, partnersOf)` fixes this: a
parentless person only becomes an explicit root if *every* one of their
partners is *also* parentless (an unresearched-further couple, or no
partner at all); a parentless person whose partner has recorded parents
is excluded, since that partner's own branch will surface them via
`family-chart`'s existing automatic spouse-pairing. Couples where both
(or neither) qualify still dedupe to one representative via the existing
`coupleGroups`.

**Marriages that genuinely bridge two disjoint lineages still duplicate
by design** — a couple, and everyone below them, is drawn once per side,
because a family is a DAG (a child has two distinct parent lineages), not
a strict tree, and no single-root hierarchy can show both without
repeating the join point. `family-chart` treats this as a first-class
case (it flags every repeat past the first via `node.duplicate`, distinct
from `node.data.id`, which is never itself suffixed); `cardInnerHtml`
surfaces that flag as a small "also shown elsewhere" note so a repeated
card doesn't read as a different person. In practice this affects far
fewer people than expected: verified against a two-grandparent-branch
demo family, only the *shared children* (e.g. Milo, reachable as a real
`rels.children` entry from both his father's blood branch and his
mother's) duplicated — the married-in parents themselves (Papa, Maman)
each appeared exactly once, correctly positioned under their own birth
family, since `family-chart`'s spouse-pairing adds a partner as an
annotation card only, without re-walking into their ancestry a second
time.

The toolbar's existing hide condition (no button row at all when focus
has no recorded ancestors) is loosened slightly: "Everyone" is worth
showing whenever more than one root branch exists anywhere in the family,
even if focus personally has none. `viewLevel` gained a third shape
(the literal string `"all"`, alongside the existing numeric levels and
`0`) — `restoreSavedView`'s localStorage round-trip and `renderView`'s
level-clamping both had to account for it explicitly rather than assuming
a number.

No backend changes: `/api/tree` already returns the entire family graph
(every in-family person, not just those reachable from one focus), which
is exactly what building a merged dataset needs — this is a purely
client-side addition.

Tests: `tests/js/tree_logic_test.mjs` gained three `rootAncestors` cases
(the motivating bug fixed — a parentless person whose partner has
recorded parents is excluded; a couple where neither has recorded parents
dedupes to one root; an unpartnered parentless ancestor is always a
root). Manually verified end-to-end (Playwright, a seeded two-branch demo
family): the "Everyone" button renders every person in one canvas with
correct kinship labels and a visible connecting bar across both branches;
duplicate cards carry the "also shown elsewhere" note and both the
original and duplicate navigate to the correct person page on click; the
hidden root card is confirmed `display: none` while its connectors still
render; existing Direct line / branch levels are unaffected (same card
counts as before); phone-width viewport wraps the toolbar and scales the
chart the same way the existing levels already do, no new mobile-specific
work needed.

## Tests

Kinship label table (the fixture family), cycle rejection, partner
symmetry round-trip through the API, tolerant parsing of dangling slugs,
/api/tree contract shape (including friends and anchor-unset), person
page Family section rendering, tree page 200 + contains the vendored
script tags, feature fully invisible (no Family fieldset, no tree link)
when no links exist. Bare pytest green.

## Definition of done

Phone-width pass in all three themes: link up a three-generation family
of ~10 people through the editor pickers only; the tree renders with
portraits, expands a collapsed uncle branch, re-roots on a grandparent
and back; person pages show correct computed labels ("your uncle", "your
great-grandmother") and the free-text override still wins; JS disabled →
person pages still show the full Family section; zero external network
requests with the tree page open (the vendored bundle must be re-audited
by watching the network panel during pan/zoom/expand); hand-inspect one
person's index.md — the only new lines are the plain optional fields.

---

## Performance round: photo thumbnails and markdown parser reuse

Two contained optimizations found during a codebase-wide audit, no
behavior change beyond what's noted below.

**Dedicated avatar thumbnails.** `storage.save_image_to` (shared by F11's
photo pipeline) now generates a second, small copy alongside the existing
full-size re-encode: `photo-NNN.thumb.<ext>`, capped at
`THUMB_MAX_EDGE = 320` (vs. `MAX_IMAGE_EDGE = 2000` for the full photo),
same PNG-vs-JPEG-q85 rule as the full image. Before this, the small
avatar-style contexts — `.timeline__thumb` (72px/56px story-cover
thumbnails) and the `photo_thumb` macro's `.person-family__thumb`/
`.family-chip__thumb` (32px/24px) — were downloading the full 2000px
photo just to paint a tiny circle, real bandwidth waste on a mobile-first
app. `timeline.html` and `routes_pages._person_ref` now point at
`thumb_filename(...)` for those contexts only; every other photo usage
(story/person cover, book pages, epub, lightbox, the body of a story)
is untouched and still serves the full-size image.

Photos uploaded before this change have no `.thumb.` sibling on disk yet.
Rather than a migration, `_serve_media` (the shared story_media/
person_media handler) falls back to serving the full-size original when
a requested `.thumb.` filename doesn't exist on disk — the same "files
outlive app changes" tolerance the rest of storage.py already follows
elsewhere (e.g. `_parse_unlock`). `storage.thumb_filename` /
`original_filename_from_thumb` are the pure filename transforms behind
this; `_next_photo_number`'s `photo-*` glob already tolerates the new
`.thumb.` sibling since it matches the same leading `photo-NNN.` prefix.

**Markdown parser reuse.** `rendering.render_markdown` used to construct
a brand-new `markdown.Markdown()` instance (full extension chain,
including the story-image treeprocessor) on every single call — real
waste given `/book` and `/book.epub` call it once per readable story in a
loop. It now keeps one parser per thread in a `threading.local()` (not a
single shared module-global — a threaded production WSGI deployment must
never have two requests racing on the same parser's `media_base`/parse
state), resetting it between conversions via the documented `md.reset()`
API and updating the story-image treeprocessor's `media_base` in place
before each `.convert()` call.

Tests: `tests/test_storage.py` gained thumbnail-file assertions on the
existing JPEG/PNG upload tests plus a `thumb_filename`/
`original_filename_from_thumb` round-trip test; `tests/test_pages.py`
gained a `_serve_media` fallback-to-full-size test and a stronger
cover-thumbnail URL assertion; `tests/test_family_pages.py`'s family-thumb
test updated to expect the `.thumb.` URL; `tests/test_rendering.py`
gained a test that repeated calls with different `media_base` values
never leak into each other now that the parser is reused.

---

# Feature spec — F19: family accounts, admin approval, delegated writing

Multi-user accounts is one of the items README's "Ideas for later" lists as
deliberately out of scope, "if any of these become worth doing, they belong
here first, not as a surprise addition." This is that discussion, written up
before implementation the way F1 was. Same ground rule as F1: no accounts
system should make this feel less like a book and more like a web app with
users — restraint over features, still no comments/reactions/search/tags,
still one shared timeline, still plain files on disk, nothing here changes
that.

## Why this is a bigger deal than it sounds, and how the design resolves it

Storybook's whole design rests on: no database, one trust level, one shared
password, "book not blog." Real accounts pull against all three. That's not
a reason to avoid it, but it means the design should be the least new
machinery that satisfies the actual requirement, not a generic auth system
bolted on. Three choices carry that principle through the whole feature:

1. **Fully opt-in, off by default**, gated by `STORYBOOK_ACCOUNTS` — same
   pattern as `STORYBOOK_AUTHORS`/`STORYBOOK_BIRTHDATE`. A family that wants
   the one-shared-password simplicity forever just never sets it, and
   nothing about their install changes, ever.
2. **An account is not a new identity system — it's a login bolted onto an
   existing Person.** `people.py` already models "the cast of the book."
   Every account (admin or family) is required to bind to a Person, so "who
   can log in" and "who this book is about" stay the same graph instead of
   becoming two things an admin has to keep in sync.
3. **Still no database.** Credentials live in plain files under `stories/`,
   same as everything else — readable, backed up with everything else,
   survives the app being deleted. (A password hash is safe to sit in a
   plain file; the plaintext never is.)

## Roles

| Role | Bound to a Person? | Can do |
|---|---|---|
| **Admin** | Yes, always | Everything Family can do, plus: create accounts, bind them to a Person (existing or new), disable/re-enable accounts |
| **Family** | Yes, always | Full read/write on the whole timeline/tree/book — unchanged from today's single-password trust model, not a permissions system; manage their own password; (Phase 3) create/revoke their own delegated write-links |
| **Delegate** (Phase 3, write-link) | No — scoped to whoever granted the link | Submit one new story, attributed to the granting Person. Nothing else. |

Admin isn't a separate kind of identity, it's a capability flag on a
Person-bound account — in practice the person who deploys the app approves
themselves as the first admin and usually also writes stories.

**Permissions decision, stated explicitly since it's a values call and not
derivable from anything above:** once someone has an approved Family
account, they can edit/delete *any* story, exactly like today. The account
system answers who gets in the door and how they're attributed, not who can
touch what once they're in — a permission-walled model would be a bigger,
more blog-like feature than anything else in this app.

## Data model

`app/accounts.py`, same shape as `people.py`: pure functions taking the
people directory as their first argument, no hidden state.

```
stories/
  people/
    papa/
      index.md          # existing Person file, untouched
      account.json       # only exists if papa has an account
    milo/
      index.md            # a Person with no account.json is just a person —
                           # most people in the book never log in
```

Credentials live in a sibling file, not new `index.md` frontmatter keys:
`index.md` is read by every page render, kinship walk, and tree JSON build,
so keeping the password hash out of it shrinks the blast radius of any
future bug that logs or dumps a `Person`. Plain JSON, not YAML: this is
small structured data with no prose body, and stdlib `json` avoids leaning
on python-frontmatter's transitive PyYAML dependency for something new.
Hashing is `werkzeug.security` (`generate_password_hash`/
`check_password_hash`) — already installed transitively via Flask, so this
is one dependency avoided, not added.

```json
{
  "username": "papa",
  "password_hash": "scrypt:...",
  "role": "admin",
  "status": "active",
  "created_at": "2026-07-20T18:32:00",
  "approved_by": null
}
```

## Authentication & sessions

`auth.login()` grows a second mode selected by `STORYBOOK_ACCOUNTS`. Off:
untouched, single shared password. On: username+password, verified via
`accounts.verify_login`, setting `session["account_username"]`,
`session["person_slug"]`, `session["role"]`.

`login_required` re-checks the account's `status` from disk on every
request when accounts mode is on, rather than trusting the session cookie
alone — sessions here are client-signed with no server-side store, so a
disabled account must lock out immediately, not whenever its 90-day cookie
happens to expire. `admin_required` layers a role check on top.

**Bootstrap:** the first account has no admin to create it. `STORYBOOK_PASSWORD`
never logs anyone in once accounts mode is on — instead it's the invite
code required on the public request form (Phase 2), and the very first
request ever submitted auto-approves as admin instead of joining the
pending queue. This needed no separate bootstrap env var: already knowing
the shared password is already the proof-of-ownership the app needs.
(Phase 1, before the request form existed, used a simpler stopgap: the
shared password logged in directly as a one-time bootstrap admin session.
Phase 2 replaced that outright rather than keeping both paths alive —
see the Phase 2 round below.)

## Delegated write-links (Phase 3 — "give access to someone so they write
for them")

A family/admin account holder generates a share-to-write link (a
`secrets.token_urlsafe` bearer token, stored hashed) from their own account
page. Opening it sets a session scoped to submitting one story attributed to
the granting Person — deliberately *not* `session["authed"]`, so it's
structurally distinct from a real login and can't reach anything else in the
app. No username, no password, no admin approval to get one — matching "no
account access as such" literally. Revocable at any time by the person who
issued it or by an admin. Considered and rejected: a delegate-created
sub-login (reads like exactly what "no account access as such" rules out),
and literally sharing one's own login (no audit trail, revoking it logs the
owner out of their own devices too).

Two scope trims from the original idea, made for proportionality rather
than found necessary along the way: **no editing after submission** (a
multi-use link lets someone come back and write *another new* story, not
revise a previous one — tracking per-story edit authorization for a
one-shot contribution is real complexity for a marginal case, and the
person who granted the link can always fix a typo themselves afterward),
and **text-only, no photos** (the real editor's photo upload is a
multi-step JS flow built around a story already having an id to attach
images to; reusing it for a scoped delegate session was a much bigger lift
than the rest of Phase 3 combined). Both are easy to revisit later if the
text-only cameo-contribution case turns out not to be enough.

## Interaction with existing features

- **F1 Authors** (`STORYBOOK_AUTHORS`) is superseded automatically the
  moment `STORYBOOK_ACCOUNTS` is on (Phase 4): an account's bound Person
  becomes the author directly, with its own `author_color` replacing the
  env-config color. `STORYBOOK_AUTHORS` itself is never read in that mode
  — left set or unset, it makes no difference — so there's no forced
  migration step; an install that never turns accounts on keeps F1 exactly
  as it always was.
- **F14 People / F18 kinship-tree**: no changes. Accounts are additive
  metadata on Persons that already exist; `kinship.py`, `tree.js`, and the
  family-chart rendering stay completely account-unaware.
- Existing installs: with `STORYBOOK_ACCOUNTS` unset, zero behavior change,
  zero migration required, `story.author` strings keep rendering exactly as
  they do today.

## Security checklist

- `hmac.compare_digest` for the shared/bootstrap password (already the
  pattern), `check_password_hash`'s constant-time comparison for account
  passwords.
- `verify_login` hashes a dummy password on an unknown-username lookup so
  that path costs roughly the same CPU time as a real check, keeping
  username validity untimeable.
- Failed logins keep the existing `time.sleep(1)` throttle; a per-account
  lockout counter is a reasonable future addition but deliberately not a
  dependency like Flask-Limiter — one household, not internet scale.
- State-changing routes (create/disable account) are POST-only, relying on
  the existing `SESSION_COOKIE_SAMESITE="Lax"` — this app has no CSRF
  tokens anywhere today and F19 doesn't introduce a token system just for
  itself, but the stakes of a gap are higher now (CSRF could create/disable
  an account, not just re-submit an already-known password), worth
  revisiting if a request-based public flow (Phase 2) ships.
- Usernames are validated against a strict allowlist (`^[a-z0-9-]{3,32}$`),
  same spirit as `storage.is_valid_story_id`.

## Phasing

1. **Data model + `app/accounts.py` + admin/family login** (done). No
   public request flow yet — an admin creates every account directly, for
   dogfooding.
2. **Public request/approve flow** (done) — a "request an account" form
   gated by the shared password as an invite code, a pending queue, admin
   approve/reject binding to a Person.
3. **Delegated write-links** (done).
4. **F1 retirement path** (done) — `author_color` on Person,
   `STORYBOOK_AUTHORS` superseded automatically in accounts mode.

---

### Phase 1 implementation round

Built exactly as specified above, feature-flagged behind
`STORYBOOK_ACCOUNTS` (default off — every existing test and install is
unaffected; the whole suite passes with the flag never set).

- **`app/accounts.py`** (new): `Account` dataclass, `create_account`,
  `get_account`/`get_account_by_username`, `list_accounts`,
  `any_accounts_exist`, `is_username_taken`/`is_valid_username`,
  `set_status`, `verify_login` — as specified, JSON sibling files under
  `people/<slug>/account.json`.
- **`app/auth.py`**: `login()` branches on `ACCOUNTS_ENABLED` and whether
  any account exists yet (bootstrap); `login_required` re-validates account
  status from disk each request when accounts mode is on; new
  `admin_required` (404s a non-admin rather than revealing the admin
  section exists, consistent with this app having no 403 pattern anywhere
  else).
- **`app/routes_pages.py`**: `/admin/accounts` (list, admin-only),
  `/admin/accounts/new` (GET/POST — also the bootstrap admin's landing
  page; creating an account while bootstrapped upgrades the current
  session in place rather than requiring a second login),
  `/admin/accounts/<slug>/disable` and `/enable`.
- **Templates**: `login.html` grows a conditional username field (bootstrap
  mode shows the old password-only form with an explanatory note); new
  `admin_accounts.html` (list + enable/disable) and
  `admin_new_account.html` (bind to an existing unbound Person or create a
  new one, username/password/role); `base.html` nav gains an "Accounts"
  link, visible only to a logged-in admin when accounts mode is on.
- **`app/__init__.py`**: `STORYBOOK_ACCOUNTS=1` → `config["ACCOUNTS_ENABLED"]`,
  same fail-open pattern as the other optional `STORYBOOK_*` vars (no value
  is a hard requirement, no startup `RuntimeError` path needed since there's
  nothing to parse/validate at boot, unlike `STORYBOOK_AUTHORS`/
  `STORYBOOK_BIRTHDATE`).

Tests: `tests/test_accounts.py` (new) — the pure `app/accounts.py` API:
round-trip creation, username validation/lowercasing/uniqueness, password
length, disable/enable, `verify_login` for correct/wrong/unknown/disabled.
`tests/test_account_auth.py` (new) — the full HTTP flow: bootstrap login,
first-admin creation, shared password retiring afterward, family-account
login, 404 on admin routes for non-admins and for logged-out visitors,
binding to an existing unbound Person vs. creating a new one, duplicate-
username/no-person-selected validation errors, and the immediate-lockout
behavior (an already-active session is redirected to `/login` on its very
next request after an admin disables it, not after its cookie expires).
Manually verified end-to-end over HTTP (curl, a fresh `STORYBOOK_ACCOUNTS=1`
install): bootstrap → first admin → second (family) account → role-gating
→ disable → immediate lockout → re-login refused while disabled, all
matching the automated tests.

At the time, Phases 2-4 (the public request/approve flow, delegated
write-links, and F1 retirement) were not yet built — see their own rounds
below for what shipped since.

---

### Phase 2 implementation round

Built as specified, and **replaces** Phase 1's shared-password bootstrap
login outright rather than keeping both paths alive — once a public
request form exists, a second "or just type the shared password into
`/login`" bootstrap route would be redundant machinery and a second thing
to reason about securely. `auth.login()` is simpler after this round than
it was after Phase 1: no more bootstrap branch, no more session
self-upgrade mid-request — it always expects username+password when
accounts mode is on, full stop.

- **`app/accounts.py`**: new `PendingRequest` dataclass and
  `list_pending`/`get_pending`/`create_pending_request`/`reject_pending`/
  `approve_pending`/`is_username_reserved`, stored as one shared
  `stories/pending_accounts.json` (not one-file-per-request — a request
  queue is meant to be reviewed and cleared quickly, never expected to
  pile into the hundreds unnoticed, so a single small file is simpler than
  an index). These take `stories_dir`, not `people_dir` like the rest of
  the module — the queue lives at the stories root since a pending request
  has no Person to be a sibling of yet. `approve_pending` requires exactly
  one of an existing unbound Person slug or a new person's name, creates
  the Person if needed, writes the real `account.json`, and removes the
  request from the queue in the same call.
- **`app/auth.py`**: `login()` loses the bootstrap branch entirely —
  `STORYBOOK_PASSWORD` now only matters when accounts mode is *off*. A
  `no_accounts_yet` hint (still computed, just for copy on the login page)
  is all that's left of the old bootstrap flag.
- **`app/routes_pages.py`**: `/request-account` (GET/POST, public — 404s
  when accounts mode is off) creates a pending request after checking the
  invite code with `hmac.compare_digest`; auto-approves as admin inline
  when `accounts.any_accounts_exist()` is still false. `/admin/accounts`
  now also lists the pending queue. `/admin/accounts/pending/<username>`
  (GET/POST, admin-only) reviews and approves one request;
  `/admin/accounts/pending/<username>/reject` removes it. The
  bind-to-existing-or-new-person validation that both this and
  `admin_new_account` need was pulled into a shared `_bind_and_create`
  helper rather than duplicated.
- **Templates**: new `request_account.html` (the public form, plus a
  submitted/auto-approved confirmation state instead of redirecting away)
  and `admin_review_pending.html`; `admin_accounts.html` gained a pending
  section above the accounts list; the "pick an existing Person or create
  one" fieldset used by both `admin_new_account.html` and
  `admin_review_pending.html` was pulled into a `person_picker` macro in
  `_macros.html` rather than duplicated a third time; `login.html` lost
  its bootstrap-specific form branch and gained a "request one"/"request
  the first one" link instead.

Tests: `tests/test_accounts.py` gained the pending-request API — round
trip, validation (bad username/short password/blank name), uniqueness
enforced *across* pending and bound accounts together, approve binding to
a new vs. existing person, reject, and the "exactly one of person_slug/
new_person_name" contract. `tests/test_account_auth.py`'s bootstrap tests
were rewritten around `/request-account` (the old login-based bootstrap
helper no longer exists): first request auto-approves as admin and
creates its Person; a second request goes to the pending queue instead;
wrong invite code and duplicate-pending-username are rejected; admin
approve (both binding shapes) and reject; a non-admin family account gets
404 reviewing a pending request; the shared password never logs anyone in
once accounts mode is on, before or after any account exists. Manually
verified end-to-end over HTTP (curl and Playwright, a fresh
`STORYBOOK_ACCOUNTS=1` install): first request auto-approves as admin →
shared password stops working → second request queues → admin sees it on
`/admin/accounts` → approves, binding to a brand-new Person → that account
logs in and is correctly 404'd from admin routes → a third request is
rejected and disappears from the queue.

At the time, delegated write-links (Phase 3) and F1 retirement (Phase 4)
were not yet built — see their own rounds below for what shipped since.

---

### Phase 3 implementation round

Built with the two scope trims noted above (no post-submission editing,
text-only). New standalone module rather than folding into
`app/accounts.py`: a write-link isn't a credential or an identity, it's a
capability token with its own lifecycle (expiry, single-use, revocation,
usage tracking) — different enough in shape to earn its own file.

- **`app/write_links.py`** (new): `WriteLink` dataclass and
  `create_link`/`list_links`/`get_link`/`revoke_link`/`mark_used`/
  `find_by_token`/`is_link_valid`/`list_all_active`, stored as
  `people/<slug>/write_links.json`. Tokens are hashed with plain SHA-256
  (`hashlib`, not `werkzeug.security`'s slow password hash) — a
  `secrets.token_urlsafe(32)` token already has ~192 bits of entropy, so a
  fast deterministic hash is the right tool, the same reasoning GitHub/GitLab
  use for personal access tokens. Each link also gets its own non-secret
  `id` (`secrets.token_hex(8)`) used everywhere a link needs to be
  referenced (revoke URLs, admin lists) so the real bearer token is never
  echoed back anywhere after the moment it's created.
- **`app/auth.py`**: new `delegate_required`, parallel to `login_required`/
  `admin_required` — checks `session["delegate_person_slug"]`/
  `["delegate_link_id"]` and re-validates the link's status from disk on
  *every* request (not just at the initial `/w/<token>` hit), so a
  revoked/expired/used-up link locks out an already-open delegate session
  immediately, same reasoning as the disabled-account check from Phase 1.
- **`app/routes_pages.py`**: `/account/write-links` (GET/POST, any logged-in
  account — create a link, see history, revoke); `/account/write-links/
  <person_slug>/<link_id>/revoke` (owner or admin only); `/w/<token>`
  (public — validates and opens a delegate session, `session.clear()`-ing
  first so a real account holder accidentally opening their own share link
  can't end up with mixed session state); `/w/write` (delegate-only — the
  entire delegate experience, one form, no nav out).
- **`admin_accounts.html`** gained a third section, "Active write-links"
  (only currently-valid ones — revoked/expired/used links aren't
  actionable and would just be dashboard noise), so an admin can shut down
  a link they didn't issue themselves.
- **Templates**: `account_write_links.html`, `delegate_write.html`,
  `delegate_thanks.html`, `write_link_invalid.html` — all deliberately
  thin, no site-nav links out of the delegate ones (they inherit
  `base.html`'s nav, which already hides every link behind
  `session.get('authed')`, and a delegate session never sets that, so this
  needed no special-casing in the shared template).
- A delegate-created story's `author` field is set to the granting
  Person's name directly, bypassing F1's `STORYBOOK_AUTHORS`-membership
  check entirely (that check lives in the `/api/stories` route layer, not
  in `storage.create_story` itself, and this flow calls the latter
  directly) — it renders as a plain neutral-color byline if the name isn't
  a configured F1 author, exactly the graceful fallback F1 already
  documented for a renamed/removed author.

Tests: `tests/test_write_links.py` (new) — the pure `write_links.py` API:
round-trip creation, expiry math, `is_link_valid`'s three failure modes
(revoked/expired/used-up-single-use) versus a multi-use link staying valid
after one use, `find_by_token` only matching a real token, and
`list_all_active` excluding everything not currently valid.
`tests/test_write_link_routes.py` (new) — the full HTTP surface: creating a
link and seeing its URL exactly once, single-use-checkbox semantics, owner
and admin revocation, a non-owner family account correctly 404'd trying to
revoke someone else's link, the `/w/<token>` → `/w/write` handoff, a
submitted story landing in `storage.list_stories` with the right author, a
single-use link refusing a second submission (and the token itself going
dead), a multi-use link accepting a second story, revoking a link locking
out an already-open delegate session immediately, a delegate session unable
to reach any real app route, and opening a link clearing a pre-existing
real login session. Manually verified end-to-end (curl and Playwright,
screenshots): create a labeled single-use link → open it in a fresh
browser context → submit a story → it appears correctly on the real
timeline with the right author byline → re-opening the same link shows
"isn't valid anymore" → the delegate's nav bar never showed anything but
the app title, confirming the scoping is structural (inherited from
`base.html`'s existing `authed` guard) rather than something that had to
be bolted on per-page.

At the time, F1 retirement (Phase 4) was not yet built — see its own round
below for what shipped since, and F19 is now fully built out end to end.

---

### Phase 4 implementation round

Built as specified: real accounts supersede F1 the moment
`STORYBOOK_ACCOUNTS` is on, with no config migration required and zero
change to F1 itself when accounts mode stays off.

- **`app/people.py`**: `Person` gains `author_color: Optional[str]`, an
  optional hex color, same validation shape
  (`is_valid_author_color`/`_parse_author_color`) and "unset = neutral,
  malformed on disk = drop to None" tolerance as every other optional
  field here. Threaded through `create_person`/`update_person`/
  `_write_index` exactly like `gender` — `None` leaves it unchanged on
  update, `""` clears it.
- **`app/routes_api.py`**: `_validate_author` now short-circuits to
  `(None, None)` whenever accounts mode is on, *before* even looking at
  `STORYBOOK_AUTHORS` — a client-submitted `author` is never trusted once
  real identity exists, closing what would otherwise be a spoofing gap (a
  family account claiming to have written as someone else). A new
  `_author_name_for_current_account()` resolves the actual author from
  `session["person_slug"]` and is applied only in `create_story` — never
  in `update_story`, so editing a story can never silently reassign who
  wrote it. `_validate_author_color`, mirroring `_validate_gender` exactly,
  wired into both person create/update handlers.
- **`app/routes_pages.py`**: `_authors_and_colors()` branches on
  `ACCOUNTS_ENABLED` — in accounts mode, "authors" becomes every Person
  with a bound account (not `STORYBOOK_AUTHORS`), colored by their own
  `author_color` or a new `DEFAULT_AUTHOR_COLOR` fallback. That fallback
  matters because `timeline.html`'s legend chip renders
  `--author-color: {{ a.color }}` unconditionally (unlike the per-story
  byline lookups, which already guard on the color being present) — every
  entry handed to it must have a real value, and a freshly-approved
  account has no `author_color` yet until someone visits their person
  page. Reusing this one function's output is what let every other F1
  render path (timeline legend/dots, book, story byline) work in accounts
  mode with *zero* template changes.
- **Templates**: `editor.html`/`instant.html`'s existing
  `{% if authors %}` guard around the chip picker gained `and not
  config.ACCOUNTS_ENABLED` — picking an author from a hand-picked list
  makes no sense once attribution is automatic from the session.
  `person_editor.html` gained a native `<input type="color">` for
  `author_color`, shown only in accounts mode.
- **`app/static/js/editor.js`**: one new line reading the color input into
  the shared story/person payload builder — no other JS changes needed.
  The author-chip-picker JS (`author-chips.js`) already treated a missing
  root element as "no chips" gracefully (empty array, `getSelected()`
  stays `null`), from before this feature existed, so hiding the chip
  markup server-side was sufficient on its own; the client keeps sending
  an empty `author` field harmlessly, and the server ignores it anyway.

Tests: `tests/test_people.py` and `tests/test_family_api.py` gained
`author_color` round-trip/validation/clear-on-empty-string/malformed-
frontmatter-tolerance cases, mirroring the existing `gender` ones exactly.
`tests/test_accounts_authorship.py` (new) covers the actual behavior
change: creating a story auto-attributes to the logged-in account;
a spoofed client-submitted `author` is silently overridden; instants get
the same treatment; editing a story never reassigns its author even when
a different account holder makes the edit; the timeline legend shows
account holders with the default color when unset and a person's own
color once they set one; the chip picker is absent from both the story
and instant editors in accounts mode; the color picker only appears on
the person editor in accounts mode; and — the regression guard for
everything above — F1's picker and validation are completely unaffected
on an install that never turns `STORYBOOK_ACCOUNTS` on. Manually verified
end-to-end (Playwright): created a story with no chip picker visible,
confirmed it auto-attributed to "Papa," set a custom byline color through
the actual JS-driven person editor (not just the API directly), and
watched that exact color render on the real timeline's legend and byline.

F19 is now fully built: admin/family accounts, the public request/approve
queue, delegated write-links, and real per-account authorship superseding
F1 — all gated behind one `STORYBOOK_ACCOUNTS` flag, every install that
leaves it unset unaffected by any of it.

---

### Follow-up round: self-service password change and role management

Two gaps found by explicitly auditing "is everything actually reachable
from the web UI, with no need to hand-edit `account.json`" after F19
shipped: there was no way to change your own password, and no way to
promote/demote an existing account's role. Both required manual file
editing to work around — exactly what this whole module exists to avoid.
Closed in this round, plus one related footgun caught while building the
fix (see below).

- **`app/accounts.py`**: `Account` gains `session_version: int = 0`.
  `set_password(people_dir, person_slug, new_password)` re-hashes and
  **bumps** `session_version` — the point of changing a password is that
  every other already-open session for that account stops working too,
  not just that a new password now also happens to log in. `set_role`
  promotes/demotes, validating the role like `create_account` already
  does. Both `set_role` and the pre-existing `set_status` gained a shared
  `_active_admin_count()` guard: **neither will demote nor disable the
  last active admin.** That specific footgun wasn't part of the original
  ask — it surfaced while writing `set_role` (a demote is symmetrically
  as dangerous as a disable, and `set_status` already had the exact same
  unguarded lockout risk from Phase 1) — fixed in the same round rather
  than filed as a separate gap, since it's the identical failure mode
  this whole round exists to close.
- **`app/auth.py`**: `login_required`'s existing per-request re-check
  (previously just account status) now also compares
  `session["session_version"]` against the account's current value, so a
  password change invalidates other sessions on their very next request —
  same reasoning and same code path as the disabled-account check from
  Phase 1, just one more field. New `set_session_for_account()` factors
  out the "populate a fresh session" logic `login()` already had, so the
  self-service password-change route can refresh *its own* session's
  `session_version` after changing it — without that, the very session
  that requested the change would immediately lock itself out on its next
  request, which is not what "change your own password" should do to you.
- **`app/routes_pages.py`**: `/account` (a small hub, replacing the bare
  "Write links" nav link with "Account"), `/account/password`
  (self-service — requires the current password, matching password-change
  UX conventions generally, and refreshes the session as above),
  `/admin/accounts/<slug>/reset-password` (admin-set, no current password
  needed — the only account-recovery path this app has, since it has no
  email), `/admin/accounts/<slug>/role`. `admin_disable_account` — which
  could previously crash with an unhandled 500 the moment `set_status`
  gained its guard — now catches `ValueError`/`FileNotFoundError` and
  flashes instead, same pattern every other admin action here already
  used.
- **Templates**: new `account_home.html`, `account_password.html`,
  `admin_reset_password.html`; `admin_accounts.html`'s account rows gained
  an inline role `<select>` + "Set" button and a "Reset password" link
  alongside the existing disable/enable action.

Tests: `tests/test_accounts.py` gained `set_password`/`set_role` coverage
(hash change, session_version bump, validation) and the last-admin guard
for both `set_role` and `set_status` (including a disabled admin not
counting as "remaining"). `tests/test_account_self_service.py` (new)
covers the full HTTP surface: wrong-current-password and mismatched-
confirmation rejections, a successful change keeping the *current* session
logged in while logging out a *second* open session for the same account,
admin reset without needing the old password (and it also invalidates
open sessions), non-admins 404'd from both admin routes, and — the
regression tests for the crash this round fixed — demoting or disabling
the only admin redirects with a flash message rather than a 500. Manually
verified end-to-end (Playwright): changed a password through the actual
form and confirmed the session survived; promoted a family account to
admin, demoted the original admin now that a second one existed, then
attempted to demote the last remaining admin and watched the guard
message render correctly instead of crashing.

### Follow-up round: re-link an account to a different person

A gap surfaced by real deployment, not by design review: `/request-account`
auto-approves the very first submitted request as admin, and since there's
no admin yet at that point to pick from the family, it always binds the
new account to a brand-new Person built from the display name
(`request_account`'s `new_person_name=pending.display_name`) — even when
the real family member already had a Person page from before accounts
were turned on. Result: a duplicate Person, with no way to fix it short of
hand-editing `account.json`.

- **`app/accounts.py`**: `set_person(people_dir, person_slug,
  new_person_slug)` moves an account's `account.json` from one Person's
  folder to another's — `account.person_slug` is reassigned and the file
  rewritten at the new path via the existing `_write_account`, then the
  old path is unlinked. Deliberately never deletes the old Person itself
  (this app has no person-deletion machinery anywhere, by design — see
  the "book, not blog" restraint in `CLAUDE.md`); it's simply left
  unbound afterward, same as any family member who never gets an
  account. Raises `FileNotFoundError` for an unknown source/target slug,
  `ValueError` if the target Person already has its own account, and is
  a no-op when the two slugs match.
- **`app/routes_pages.py`**: `admin_accounts()` now also collects
  `unbound_people` (Persons with no `account.json`); new
  `/admin/accounts/<slug>/link-person` (admin-only, POST) calls
  `set_person` and flashes on error, matching every other admin account
  action's error-handling shape. If the account being re-linked is the
  *current* session's own account (true for the common case — the
  bootstrap admin fixing their own duplicate), it updates
  `session["person_slug"]` in place so the session doesn't keep pointing
  at the stale Person until the next login; unlike a password change,
  nothing else about the session (role, username, session_version)
  changes, so a full `set_session_for_account()` reset isn't needed here.
- **`app/templates/admin_accounts.html`**: each account row gets a second
  inline form (visible only when at least one unbound Person exists) — a
  `<select>` defaulted to the currently-linked Person plus every unbound
  Person as alternatives, and a "Link" button.

Tests: `tests/test_accounts.py` covers `set_person` moving the file
correctly, the same-slug no-op, rejecting a target that already has an
account, and rejecting unknown slugs. `tests/test_account_self_service.py`
covers the route: an admin re-linking their own just-bootstrapped account
onto a pre-existing Person (the motivating scenario, reproduced end-to-end:
bootstrap, create a second "real" Person, re-link, confirm the old
duplicate has no account and the new Person does, and the session stays
logged in against the new Person), the already-has-an-account rejection,
and non-admins 404ing.

---

## UI audit round: nav overflow, admin row overflow, book cover frame

A user report ("top bar buttons getting out of scope") drove a full
manual/automated pass over every page, at six viewport widths (360px to
1440px) and both themes, using a seeded demo family with deliberately
adversarial content (a hyphenated long name, a long friend name, a long
custom `STORYBOOK_TITLE`) rather than the short defaults every earlier
round happened to test with. Three real bugs found and fixed, all
CSS-only:

- **`.site-nav__actions` had no `flex-wrap`.** F19 added two more nav
  links ("Accounts", "Account"), which — combined with the pre-existing
  "People", "+ New story", "+ Instant" — pushed the row's total width
  past what fits at phone widths. `.site-nav` itself already wraps
  between the brand row and the actions row, but the actions row's own
  five items had no fallback once *they* didn't fit on one line, so the
  last two buttons were pushed off-screen rather than wrapping to a
  second line. This is the bug reported. Fixed by giving
  `.site-nav__actions` the same `flex-wrap: wrap` every other
  multi-button row in this app already uses (`.site-nav`,
  `.tree__views-row`, `.admin__row`), plus `justify-content: flex-end`
  so a wrapped second line still reads as right-aligned rather than
  snapping to the left edge.
- **`admin_accounts.html`'s "Link" person-picker `<select>` had no width
  constraint.** Its options are real person names (arbitrary length,
  unlike the fixed-length "Admin"/"Family" role `<select>` next to it),
  so a longer name sized the native control past the available row
  width — flexbox's default `min-width: auto` stops a flex item
  shrinking below its content size even inside an already-wrapping
  parent (`.admin__row` wraps fine, but a single overlong child can't
  shrink to make room for wrapping to help). Fixed with `min-width: 0`
  on both the form and the select, plus `max-width` +
  `text-overflow: ellipsis` so a long name truncates instead of
  stretching the row.
- **The book cover's decorative rope frame (`book-frame.jpg`) has a much
  tighter text-safe interior than its CSS `inset` assumed**, and only
  the title had any responsive sizing — the date range and author line
  were fixed-size regardless of viewport, so they hit their tightest
  relative fit exactly on narrow screens. Measured the image's actual
  rope-free interior directly (sampling pixel rows/columns in Python via
  Pillow for "cream vs. rope" color, not eyeballing) rather than guessing
  at percentages: horizontally ~18.3%–20.7% inset, vertically
  ~14.5%–16.2%, both narrower than the previous `inset: 20% 13%`.
  Verified the touching wasn't a narrow-viewport-only regression — the
  default short "Storybook" title never touches at any width, but a
  longer custom title (the exact example `STORYBOOK_TITLE="Le livre de
  Milo"` given in `.env.example`) touched the border even on a 1200px
  desktop viewport, so this was a real gap for anyone using that
  documented customization, not an artifact of stress-testing. Fixed
  `inset: 22% 20%`, gave `.book-cover__range` and `.book-cover__authors`
  their own `clamp()` responsive font-sizes (previously only
  `.book-cover__title` had one) so every line shrinks together with the
  frame instead of just the title, and trimmed the title's own clamp
  ceiling (2.25rem → 1.75rem) so it keeps a visible margin from the rope
  instead of exactly filling its box at the largest size.

No template or JS changes — every fix lives entirely in `main.css`.
Verified via an automated Playwright sweep (108 checks: 18 pages × 6
viewport widths, checking `document.documentElement.scrollWidth` for
horizontal overflow and flagging any `.site-nav` descendant whose
bounding box crosses the viewport edge) going from 36 flagged checks
before the fixes to 0 after, plus manual screenshot review of every page
in both themes and a pixel-level before/after comparison of the book
cover. `pytest` (660 tests) and `ruff check .` unaffected, as expected
for a CSS-only change.

---

## Whole-codebase dedup round

A follow-up to the UI audit above: a broader sweep for duplication
accumulated across the F19 accounts rounds and the tree "Everyone" view,
in the spirit of the earlier "Dedup" rounds. Three findings, all verified
against the full suite before and after:

- **`app/routes_pages.py`: a real bug, found via the duplication itself.**
  `admin_disable_account`, `admin_set_role`, and `admin_set_account_person`
  all shared the same shape — call an `accounts.py` mutator, catch
  `(ValueError, FileNotFoundError)`, flash, redirect to `/admin/accounts`
  — but `admin_enable_account`, the fourth route in the same family,
  called `accounts.set_status(...)` directly with no error handling at
  all. `POST /admin/accounts/<unknown-slug>/enable` would raise an
  unhandled `FileNotFoundError` straight into a 500, the exact crash the
  F19 follow-up round had already fixed for the *disable* route but never
  revisited for *enable*. New `_admin_mutate_account(person_slug,
  mutator, *args, on_success=None)` gives all four routes the shared
  shape (the `on_success` hook covers link-person's extra "sync the
  caller's own session" step), closing the gap as a side effect of
  removing the duplication rather than as a separate fix. New regression
  test: `test_enabling_an_unknown_account_fails_gracefully_not_a_500`.
- **`admin_accounts.html`: four identical single-button POST forms**
  (Reject/Disable/Enable/Revoke — `<form method="post" action="...">
  <button>Label</button></form>`) were hand-written inline instead of
  using `_macros.html`, which every sibling admin template already
  imports. New `action_button_form(action_url, label)` macro; visually
  verified identical rendering before/after.
- **Test helper triplication.** `_bootstrap_admin`, `_login`, and
  `_people_dir` — byte-identical, ~143 call sites total — were
  copy-pasted across `test_account_auth.py`, `test_account_self_service.py`,
  `test_write_link_routes.py`, and `test_accounts_authorship.py`, one
  pair added fresh in each F19 round rather than reused from the last.
  `test_account_auth.py`'s own `_bootstrap_admin` was already just
  `_request_account(...)` with its defaults — the two were never
  actually different functions, just written twice. Moved all four
  (`_people_dir`, `_request_account`, `_bootstrap_admin`, `_login`) to
  `tests/conftest.py` as plain module-level functions (not
  `@pytest.fixture`s — they take an explicit `client` argument rather
  than needing pytest's injection) and imported them into each file via
  `from tests.conftest import ...`, matching the existing implicit-namespace-package
  import style (`tests/` has no `__init__.py`; `pythonpath = ["."]` in
  `pyproject.toml` already makes `from tests.conftest import X` work).
  Deliberately left every call site untouched — the ~143 calls to
  `_bootstrap_admin(...)`/`_login(...)` didn't need to change at all,
  since the imported names keep their original identifiers; only the
  definitions moved. `people_dir` already existed as a *fixture* in
  conftest.py for the plain `stories_dir`-based tests — deliberately
  didn't try to unify it with the accounts files' `_people_dir(app)`
  plain function despite the overlap, since that would mean touching
  every one of those ~143 call sites' function signatures for a
  same-value, different-shape rename; not worth the regression risk for
  a test-only readability win.

`pytest` (661 tests, +1 for the new regression test) and `ruff check .`
green throughout; the test-helper move was verified as a pure
relocation by running the full suite immediately after, with no other
changes in the same commit.

## Fresh-eyes audit round: a stored-XSS regression, a stale doc, an admin-bootstrap race

A from-scratch read of the whole codebase (no prior context on this
project), looking for anything a first pass would miss. Three findings,
the first a real vulnerability, all fixed and covered by regression tests:

- **Stored XSS via write-links, verified end to end.** `render_markdown()`
  passes raw HTML straight through, and every template renders the result
  with `{{ body_html|safe }}`. `REVIEW.md` explicitly accepted this:
  "Raw HTML in markdown is rendered (`|safe`). Acceptable: the only author
  is the trusted password-holder. Do not add a sanitizer dependency." That
  held until F19 Phase 3 added delegated write-links — a bearer link any
  account holder can hand to someone with **no account at all** ("no
  account access as such") to submit exactly one story. The delegate's
  submission was never distinguished from a trusted author's before
  reaching `render_markdown`, so a write-link holder could plant
  `<script>...</script>` in a story body and have it execute unescaped in
  whichever family member or admin later opened it — a real privilege
  path from "someone handed a share link" to "runs script in an admin's
  authenticated session." Reproduced live with the test client (bootstrap
  admin → create a link → submit a story containing a `<script>` tag as an
  anonymous delegate → load the story as the admin → raw tag present in
  the response) before fixing it. Fixed narrowly, without touching the
  rendering pipeline trusted authors rely on (REVIEW.md's "do not add a
  sanitizer dependency" stands for everyone else): new
  `_neutralize_html()` in `routes_pages.py` escapes `<`/`>` in the
  delegate's submitted body before it ever reaches `storage.create_story`,
  applied only on the `/w/write` path. Markdown syntax never needs a
  literal `<`/`>`, so this can't break normal formatting for that flow.
  New regression test:
  `test_delegate_submission_cannot_inject_raw_html`.
- **Stale doc.** `README.md`'s backup section still said "the app's 32 MB
  upload limit" — `MAX_CONTENT_LENGTH` was raised to `128 * 1024 * 1024`
  a while back (see the Performance round above) for long voice memos,
  and the 413 handler's own message was updated at the time, but this one
  README sentence never was.
- **TOCTOU race in first-admin bootstrap.** `request_account()` did
  `auto_approved = not accounts.any_accounts_exist(...)` then a separate
  `accounts.approve_pending(...)` call. Two people who both know the
  invite code and submit within the same instant, before any account
  exists yet, could both observe "no accounts yet" and both auto-approve
  as admin — breaking the documented "the very first request ever
  submitted is special" invariant. New `accounts.approve_if_first()`
  does the check-and-act under a module-level `threading.Lock`, closing
  the window (the app runs as a single process under waitress by
  default, so an in-memory lock is sufficient — this doesn't cover a
  hypothetical multi-process deployment, which isn't how this app is
  deployed). New regression test:
  `test_approve_if_first_only_approves_once_for_two_simultaneous_requests`.

`pytest` (663 tests, +2) and `ruff check .` green throughout.
