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

# Feature batch 3 — F11..F15 (voices, instants, people, rituals)

**Prerequisite: batch 2 (F0, F2–F10) must be fully implemented and merged
first.** F12 relies on the shared partial and exclusion lists from F0/F2/F10;
F14 relies on `readable_stories()`.

Same ground rules as batch 2: all decisions are made here — implement, don't
redesign. **No new runtime dependencies** (stdlib + browser APIs + what's
already installed only). The one apparent exception, transcription (F11), is
*not* an exception: it is an optional offline script with its own separate
requirements file, and **nothing in `app/` may ever import it**. The app must
run, test, and deploy exactly as before with that script deleted.

One shared architectural rule for this batch: **no new storage formats.** An
instant is a story with one extra frontmatter key. A person is the same
folder-with-`index.md`-and-photos shape stories already use. A voice memo and
its transcript are two plain files in the story folder. `stories/` remains the
single backup unit and stays fully readable with a file browser.

**Implementation order (respect it):**
F12 instants → F14 random → F15 prompts → F11 voice → F13 people.
Commit per feature; bare `pytest` green before each commit.

---

## F12. Instants — photo + one line, fifteen seconds on a phone

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
  else 400. (F12's capture flow needs to set the cover explicitly.)

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
  an instant's own page shows no prev/next), and F14 random. They are
  **included in**: the timeline, F5 "years ago today" banners, and F10's
  `/book` — where they render compactly (photo + line as a captioned figure,
  no drop cap, no page-break-before; they are interludes, not chapters).
- Tests: kind round-trips through create/read and survives an edit-PUT;
  invalid kind → 400; cover-PUT validation; timeline shows the compact
  entry; prev/next skips instants; random never returns one; book includes
  it compactly.

## F14. Au hasard — open a page at random

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

## F15. Graines d'histoires — against the blank page

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

## F11. La voix — voice memos on stories

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

## F13. Personnages — the cast of the book

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
optional in batch 2's markup — keep it that way). Prompts (F15) do not
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
  unmodified (except the 413 limit test, updated per F11).
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
