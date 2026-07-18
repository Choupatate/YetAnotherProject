# Storybook

A private, self-hosted memory journal. A parent writes stories (text + photos) for
their child; the family reads them later as a chronological timeline and as
book-like story pages.

Everything is stored as plain **markdown files and images on disk** — no database.
If you delete the app entirely and keep the `stories/` folder, every story is still
fully readable with nothing more than a file browser and a text editor.

Three themes are available from the toggle in the top-right corner: dark (the
default), light, and manuscript — a warm, aged-paper look with a subtly grained
texture (a self-contained inline SVG filter, no image assets or network requests)
where the timeline, story, and editor each render as a page resting on a desk.

See `PLAN.md` for the full design specification this app was built from, and
`REVIEW.md` for the production-readiness review it was subsequently audited
against.

## Running it

### Locally (dev server)

Requires Python 3.12+.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then edit STORYBOOK_PASSWORD and STORYBOOK_SECRET_KEY
python run.py
```

The dev server runs at `http://127.0.0.1:5000` with debug mode on. If
`STORYBOOK_PASSWORD` is unset, the dev password is `dev`.

**Serve this app over HTTPS, or only on a trusted LAN.** The single shared
password is sent as a plain form field on every login; without HTTPS (or a
network you already trust) it travels in cleartext.

To try it out with sample content:

```bash
python scripts/seed_demo.py ./stories
```

### Locally (production-style, waitress)

```bash
STORYBOOK_PASSWORD=... STORYBOOK_SECRET_KEY=... python serve.py
```

Serves on `http://0.0.0.0:5011` by default (set `PORT` to change it).

### Docker

```bash
docker build -t storybook .
docker run -p 5011:5011 \
  -e STORYBOOK_PASSWORD=... \
  -e STORYBOOK_SECRET_KEY=... \
  -v storybook-data:/data/stories \
  storybook
```

The container stores stories under `/data/stories`; mount a volume there so content
survives container recreation.

### Docker Compose (e.g. Synology)

Clone this repo directly into the folder where you want everything to live,
e.g. `/volume2/Media/StoryBook`, then:

```bash
cp .env.example .env   # then edit STORYBOOK_PASSWORD and STORYBOOK_SECRET_KEY
docker compose up -d --build
```

`docker-compose.yml` reads `STORYBOOK_PASSWORD`, `STORYBOOK_SECRET_KEY`, and
`STORYBOOK_COOKIE_SECURE` from `.env` in the same directory (Compose loads it
automatically — no `env_file:` needed) and bind-mounts the `stories/` subfolder
of that same clone to `/data/stories` in the container — keeping code and data
under one folder without mixing story files into the git working tree. On
Synology, either run this from an SSH session with Docker installed, or point
Container Manager's project at this repo folder. Adjust the host path in
`docker-compose.yml` if you cloned somewhere other than
`/volume2/Media/StoryBook`.

### Configuration

All configuration is via environment variables — see `.env.example`:

| Variable | Purpose |
|---|---|
| `STORYBOOK_STORIES_DIR` | Where story folders live (default `./stories`) |
| `STORYBOOK_PASSWORD` | The one shared password. Required in production. |
| `STORYBOOK_SECRET_KEY` | Flask session-signing secret. Required whenever `STORYBOOK_PASSWORD` is set — the app refuses to start otherwise. |
| `STORYBOOK_COOKIE_SECURE` | Set to `1` when serving over HTTPS to mark the session cookie `Secure`. Default off, for local/LAN HTTP use. |
| `STORYBOOK_AUTHORS` | Optional. Comma-separated `Name:#hexcolor` pairs for several narrators (see below). Unset by default. |
| `STORYBOOK_BIRTHDATE` | Optional. The child's birth date (`YYYY-MM-DD`). Shows the child's age at each memory (see below). Unset by default. |
| `STORYBOOK_TITLE` | Optional. The app's display name — nav, page titles, install manifest, book cover. Defaults to `Storybook`. |
| `STORYBOOK_CHILD` | Optional. The slug of the person page the family tree's kinship labels are computed relative to (see below). Unset by default. |
| `STORYBOOK_ACCOUNTS` | Optional. Set to `1` for per-person username/password accounts with an admin role, instead of one shared password (see below). Unset by default. |

### Family accounts (optional, off by default)

Set `STORYBOOK_ACCOUNTS=1` to replace the one-shared-password login with
real per-person accounts: an **admin** role that creates accounts and
binds each one to a family member's person page, and a **family** role
that can read/write the whole book like today, plus manage its own
password. Leaving it unset keeps the app exactly as it's always been —
this is additive, not a replacement, for families who don't need it.

`STORYBOOK_PASSWORD` never logs anyone in once this is on — instead it
becomes the invite code required on the **Request an account** page
(linked from the login page), so a stranger who finds the URL can't queue
requests without knowing it. Anyone who submits one picks their own
username and password up front; an admin then reviews it from
**Accounts** in the nav (visible to admins only) and either approves it —
binding it to an existing family member or creating a new one on the
spot, with an admin or family role — or rejects it. Admins can also create
an account directly, skipping the request queue, for a family member who
won't submit their own. The very first request ever submitted is special:
with no admin yet to review it, it auto-approves immediately as admin,
bound to a brand-new person page built from the display name — if that
duplicates a person who already existed, an admin can re-link the account
to the existing person page from **Accounts** at any time, leaving the
duplicate in place but unbound rather than deleting anything.

Disabling an account, resetting its password, or changing its role (from
the same page) all take effect immediately, not whenever its browser
session would otherwise expire — and there's always at least one admin
left standing: demoting or disabling the last one is refused rather than
locking everyone out. Every account holder can change their own password
from **Account** in the nav, which also logs out any other device they're
signed into; there's no email in this app, so if someone forgets their
password an admin resetting it from **Accounts** is the only way back in.

Any account holder can also generate a **write link** from **Account** →
**Write links** — a one-off URL that lets someone write a single story for
them without an account of their own (no username, no password, nothing
else in the book visible to them). Links can be single-use or reusable,
optionally expire, and are revocable at any time by whoever created them
or by an admin.

With accounts on, every story a family member writes is automatically
attributed to them — no picker needed, and it can't be spoofed by another
account. Each person can set their own byline color on their person page
(**Byline color**), replacing what `STORYBOOK_AUTHORS` does below; a
family member with no color set yet gets a neutral default rather than no
color at all.

### Several narrators

Set `STORYBOOK_AUTHORS` (e.g. `"Papa:#d9a441,Maman:#7ba7d9"`) to let more than
one family member write in the same shared timeline. Each story picks up an
author from a row of chips in the editor — remembered per device after the
first pick, so it's zero-tap after that — and the two voices are then clearly
split by color on the timeline (colored dot, name, and a small legend) and on
the story page (a colored byline and title flourish). Pick mid-brightness
colors that read well on both the dark and light themes.

There are still no accounts or per-author passwords — one shared login, same
as always. The author is just a label on the story. This whole section is
superseded automatically the moment `STORYBOOK_ACCOUNTS` is on — see above —
`STORYBOOK_AUTHORS` is simply never read in that mode, whether or not it's
still set. Leaving `STORYBOOK_AUTHORS` unset (and accounts off) disables the
whole feature: no picker, no bylines, no legend, identical
to running without it. Renaming an author in this variable does not rewrite
already-saved stories; a story whose `author` no longer matches a configured
name still shows its byline, just in the neutral default color.

### Instants — a lighter way to capture

"+ Instant" (next to "+ New story") is a deliberately tiny capture form: one
photo, one optional line, done in about fifteen seconds on a phone. Instants
render as compact, quieter entries on the timeline (small thumbnail, no
title styling) and as small captioned figures in `/book` — interludes, not
chapters — while a full story page (and the full editor, for touch-ups)
still works normally at their direct URL. They're just a story with one
extra frontmatter key (`kind: instant`); nothing new to back up.

### People — the cast of the book

"People" in the nav (always visible, whether or not you've added anyone
yet) is a small cast page: a portrait, a name, and how they relate to the
child — "your grandmother", "your godfather" — with a free-text page of
their own for a longer bio, in the same editor as stories. The grid on
`/people` shows everyone in the order they were added, each as a square
portrait (or a plain initial when there's no photo yet).

People live in `stories/people/<slug>/` — still inside the one stories
folder, still one backup. Stories link to a person by hand with an
ordinary Markdown link (`[Mamie](/people/mamie)`); there's no
auto-linking or `@mention` syntax, so a name in a story stays plain text
unless you deliberately link it. People don't show up on the timeline or
in `/book` — this is a reference page, not another kind of memory — and,
like stories, there's no way to delete one once added.

A portrait's crop is baked into the uploaded image itself: the person
editor's dedicated Photo panel lets you pan and zoom the source photo
against an oval guide (drag to pan, works with touch; a slider and +/-
buttons to zoom) before it's ever uploaded, so there's no separate stored
focus point to keep in sync across the very differently-shaped places a
portrait renders. A portrait can also optionally record `photo_sepia`
(0-100, defaults to 30 whenever a photo exists), a manually-set sepia tone
percentage — drag the slider or type a number in the same panel — applied
everywhere the portrait renders (the people grid, the person page, family
thumbnails, the tree) so real photos read as part of the same hand-drawn,
paper-and-ink book as the illustrations, instead of clashing with it.
Uploading a new photo always resets the tone back to the default, since a
new photo needs a fresh one.

### The family tree

Person pages can optionally record `parents` (up to two), `partners`
(symmetric — linking one side writes both), `friend_of`, and `gender`.
These are plain facts, never computed labels: relations like "uncle" or
"cousin" are always derived from them at read time, never stored. Fill
them in through the "Family" fieldset in the person editor — chip pickers
reusing the author-chip look, shown once at least one other person exists.

Set `STORYBOOK_CHILD` to the slug of your child's person page and every
"YOUR ___" line on a person page, and the whole `/tree` chart, computes
labels relative to that anchor ("your grandmother", "your great-uncle",
"your uncle's wife" for an in-law one hop out). Leave it unset and
everything still works, just without the "your ___" wording. When the
book is inherited, re-point this one line at the next generation.

`/tree`'s toolbar switches between **Direct line** (just your own
ancestors), one button per **ancestor branch** (aunts/uncles/cousins,
one small chart per couple), and **Everyone** — the whole family as a
single graph, generation by generation, every person exactly once
regardless of how many marriages or half-siblings connect them.

`GET /api/tree` (login required) is the seam future renderers plug into —
the vendored chart on `/tree` is just today's consumer:

```json
{
  "anchor": "milo",
  "people": [
    {
      "id": "papi-georges",
      "name": "Papi Georges",
      "gender": "m",
      "photo": "/people/papi-georges/media/photo-001.jpg",
      "photo_sepia": 30,
      "url": "/people/papi-georges",
      "kinship": "your grandfather",
      "rels": { "parents": [], "partners": ["mamie-lise"], "children": ["papa"] }
    },
    {
      "id": "ami-jean",
      "name": "Ami Jean",
      "gender": null,
      "photo": null,
      "photo_sepia": null,
      "url": "/people/ami-jean",
      "friend_of": ["papa"]
    }
  ]
}
```

`anchor` is `null` when `STORYBOOK_CHILD` is unset or points at a slug
that doesn't exist. Anyone linked into the family graph (has a parent,
partner, or child) gets a `kinship` label (`null` when there's no anchor
or they're unreachable from it) and a `rels` object. Everyone else —
friends and people with no links at all — gets a `friend_of` list instead
(empty for a fully unlinked person).

### Voice memos

A "Voice" section on the story editor lets you record directly in the
browser — record, pause/resume, stop — with no length limit; recordings
upload as soon as you stop and appear in the list right away, each with
its own delete button (the one deletion this app supports, undoable only
by re-recording). On the story page, a "Listen" section plays back every
memo in order. Files are ordinary `memo-001.webm`/`memo-002.m4a`/... in
the story folder, same numbering scheme as photos.

**Microphone capture only works in a secure context** — HTTPS, or
`localhost`. Over plain LAN HTTP the record button simply won't appear
(playback still works everywhere), so if you're running Storybook on your
home network rather than on the same machine as the browser, put a
reverse proxy with a certificate in front of it to use this feature.

Drop a plain-text file named after a memo with a `.txt` extension next to
it (e.g. `memo-001.txt`) and its contents show up as a "Transcript" under
that recording — the app never writes these itself, so anyone can type
one by hand, or generate them offline:

#### Offline transcription

`scripts/transcribe_memos.py` walks a stories folder, finds memos that
don't have a transcript yet, and writes one using
[faster-whisper](https://github.com/SYSTRAN/faster-whisper) — entirely
offline, nothing is uploaded anywhere:

```
pip install -r requirements-transcribe.txt
python scripts/transcribe_memos.py ./stories --language fr --model small
```

Its dependencies are intentionally kept out of `requirements.txt` and are
never imported by the app itself — this is a tool you run occasionally
from a laptop against the stories folder (or a copy of it; the resulting
`.txt` sidecars can be copied back), not something the server needs. The
first run downloads a model (hundreds of MB), so expect it to take a
while the first time.

### Age at each memory

Set `STORYBOOK_BIRTHDATE` to the child's birth date and every story and
timeline entry shows the age at that memory — `JUNE 18, 2023 · 2 YEARS OLD ·
PAPA` on the story page, `Jun 18 · Papa · 2 years old` (smaller, dimmer) on
the timeline. Ages before the birth date read "before you were born"; sealed
letters never show an age, keeping the envelope minimal. Leave the variable
unset to disable the feature entirely.

### Home-screen install

Storybook can be added to a phone's home screen like a native app (a
`manifest.webmanifest`, sized icons, and standalone display mode) — set
`STORYBOOK_TITLE` (e.g. `"Le livre de Milo"`) so it shows up under your own
title rather than "Storybook". There is deliberately **no service worker and
no offline caching** — every visit still talks to the server, it just looks
like an app when launched. Regenerate the icons with
`python scripts/make_icons.py` if you change the design; the outputs are
committed under `app/static/icons/`.

### Sealed letters

Setting a "Seal until" date on a story in the editor turns it into a sealed
envelope until that date: the timeline shows only an envelope glyph and an
"opens on" date (no title, no photo), and the story page itself shows the
same envelope instead of the text. **The seal is ceremonial, not
cryptographic** — anyone with the shared password (or direct access to the
disk) can still open and read the file; the point is the ritual of an
unopened letter, not access control. Authors reach editing via `/edit/<id>`
directly, which keeps working on a sealed story — only the reading view is
blocked. Once the unlock date passes, the entry becomes a normal story
automatically, with no action needed.

### Archiving a story

The "Archive" chip in the editor (next to "Draft") is a softer alternative
to deletion, which this app deliberately doesn't have. An archived story
disappears from the timeline, drafts list, book, prev/next navigation, and
"years ago today" banner — same as a draft — but the file is never touched:
it's still fully readable at its direct URL (with a small "ARCHIVED" pill),
still listed on a dedicated `/archived` page (linked from the timeline when
at least one story is archived), and un-archiving is just toggling the chip
back off.

### Version history

Every save keeps the version it's about to overwrite: before writing new
content, the previous `index.md` is copied into a hidden `.versions/`
subfolder inside that story's own directory (the last 20 are kept; older
ones are pruned automatically). "View history" on the edit page lists them
newest-first with a one-tap Restore — restoring goes through the same save
path, so it snapshots the current version too, meaning you can never lose
content by restoring, only add another point to the timeline. This is a
local safety net for "I pasted over the wrong paragraph" or "I clicked save
before finishing a rewrite," not a full undo/redo history — there's no diff
view, just full-version snapshots.

### Autosave and crash recovery

Separately from server-side version history (which only records content
you've actually saved), the editor also autosaves the current title, date,
and body to the browser's `localStorage` a couple of seconds after you stop
typing. If you close the tab, lose your connection, or the browser crashes
before your first manual save, reopening that story (or `/new`, for a story
you never got to save at all) shows a small banner offering to restore it.
This never touches the server or other devices — it's purely a per-browser
safety net for the gap between typing and clicking Save.

### Opening a page at random

"Open a page at random" on the timeline, and "At random" on every story
page's footer, jump to a uniformly random readable story — drafts, sealed
letters, and instants are never picked (page-turning is for real stories).
The story-page link excludes the page you're already on, so tapping it
repeatedly always moves somewhere new.

### Writing prompts

A new story starts with a quiet idea to answer or ignore: a small italic
line above the editor ("Qu'est-ce qui t'a fait rire aux éclats cette
semaine ?" and 55 others in the same spirit), with a &#8635; button next to
it for another one. It only appears before a story's first save — editing
an existing story never shows it — and it is never inserted into the text
itself, it's just there for inspiration. To use your own list instead of
the shipped one, drop a `prompts.txt` file in the stories folder, one
prompt per line (blank lines and `#`-prefixed comments are ignored); it
replaces the default list entirely rather than adding to it.

### Finding a story

A search box above the timeline filters entries by title (and author) as
you type — purely client-side, filtering what's already rendered, no
server round-trip. A "Jump to the latest" link next to it scrolls straight
to the newest entry, useful once there are enough stories that reading
chronologically from the top isn't how you want to start.

### Reading it as a book

`/book` (linked from the bottom of the timeline as "Read as a book") renders
every readable story on one page, oldest first, with a title cover and a
small ornament between entries — drafts and sealed letters are excluded, same
as the timeline. It doubles as a print layout: the floating "Print / save as
PDF" button calls the browser's native print dialog, which (via a dedicated
print stylesheet) forces the light palette, hides all navigation and buttons,
and starts each story on its own page — "save as PDF" in the print dialog
gives a clean, book-like PDF of the whole thing. "Download as PDF" on the
timeline is the same flow made one tap shorter: it opens `/book` and
triggers that print dialog automatically, so you land straight on "save as
PDF" without needing to notice the floating Print button. There's no
server-generated PDF file — that would mean adding a real dependency (a PDF
library, or shelling out to a headless browser), which this project
deliberately avoids; the browser's own print-to-PDF is free, reliable, and
already produces the same clean layout.

### Downloading as an EPUB

"Download as EPUB" (next to "Read as a book" on the timeline) streams the
same readable stories as a real `.epub` file — a minimal, hand-built EPUB3
(stdlib `zipfile` and string templates, no new dependency) with a cover
page, a chapter per story, embedded photos, and a table of contents, openable
in Apple Books, Kindle (after conversion), calibre, or any other e-reader
app. Unlike `/book`, this needs no browser and no print step.

## Backing up

**Back up the `stories/` folder. That is everything.** There is no database, no
other state to preserve. Copying that one directory (e.g. with `rsync`, a nightly
`tar`, or syncing it to cloud storage) is a complete backup. Restoring is just
putting the folder back. For a one-tap copy from the app itself, the timeline's
"Download everything (.zip)" link (`/export`) streams the same directory as a
zip file.

To restore one, "Import a backup" (`/import`, also linked from the timeline)
uploads that same zip back in. It's deliberately strict: the import only
succeeds if **none** of the zip's stories already exist in this app's
stories folder — any collision aborts the whole import with nothing written,
rather than risk silently overwriting newer edits. This makes it a good fit
for disaster recovery (restoring into a fresh, empty install) or merging in
stories from a different device that don't already exist here; it is not a
sync tool. Very large backups may exceed the app's 128 MB upload limit — for
those, copy the zip's contents directly onto the `stories/` folder (or the
Docker volume) instead of going through the web UI.

## Running the tests

```bash
pip install -r requirements.txt
pytest
```

CI also runs `ruff check .` (a linter, config in `pyproject.toml`) — run it locally
before pushing if you want to catch the same issues early.

## Philosophy

- The data outlives the app: plain markdown + image files, human-readable forever.
- Boring, minimal dependencies; no build step; no JS framework.
- No runtime network dependencies — everything needed to run is vendored or local.
- Mobile-first: every screen, especially the editor, is designed to be used from a
  phone.
- Book, not blog: no feeds, no reactions, no comment sections. Restraint and
  typography.

## A note on the editor

The real [Toast UI Editor](https://github.com/nhn/tui.editor) (3.2.2) is vendored
at `app/static/vendor/toastui/` — a standalone browser bundle built from the
official npm package with `esbuild`, since the upstream CDN's `-all` bundle isn't
published on npm. Rebuild instructions and provenance are in the banner comment
at the top of `toastui-editor-all.min.js`. Its usage-analytics ping (a request to
`google-analytics.com` on every load) is disabled via `usageStatistics: false` in
`editor.js` — do not remove that option, it would violate the no-external-requests
principle (see `PLAN.md` §2.3 and the acceptance checklist in §10).

If `window.toastui` isn't available for any reason (e.g. the vendored files are
replaced with placeholders again), `editor.js` automatically falls back to a
plain `<textarea>` with a minimal formatting toolbar (heading, bold, italic,
strikethrough, quote, lists, link, highlight, and image upload) covering the same
functionality.

Supported photo formats: JPEG, PNG, WebP, AVIF, GIF, TIFF, BMP, and HEIC/HEIF
(iPhone and Android originals, via `pillow-heif`) — everything except PNG is
re-encoded to JPEG on upload; PNG is kept as PNG. The uploaded file is never
kept, only the re-encoded copy.

## Ideas for later

Out of scope for v1, deliberately: multi-user accounts, comments/reactions,
search, tags, RSS, email, video, encryption at rest, i18n, offline support
(no service worker — see "Home-screen install" above), and story deletion.
If any of these become worth doing, they belong here first, not as a
surprise addition.

(PDF/print export, a photo lightbox, and home-screen install were originally
listed here too; they shipped as the book view, F7, and F9 — see above.)
