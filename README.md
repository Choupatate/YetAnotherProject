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

### Several narrators

Set `STORYBOOK_AUTHORS` (e.g. `"Papa:#d9a441,Maman:#7ba7d9"`) to let more than
one family member write in the same shared timeline. Each story picks up an
author from a row of chips in the editor — remembered per device after the
first pick, so it's zero-tap after that — and the two voices are then clearly
split by color on the timeline (colored dot, name, and a small legend) and on
the story page (a colored byline and title flourish). Pick mid-brightness
colors that read well on both the dark and light themes.

There are still no accounts or per-author passwords — one shared login, same
as always. The author is just a label on the story. Leaving `STORYBOOK_AUTHORS`
unset disables the whole feature: no picker, no bylines, no legend, identical
to running without it. Renaming an author in this variable does not rewrite
already-saved stories; a story whose `author` no longer matches a configured
name still shows its byline, just in the neutral default color.

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

### Reading it as a book

`/book` (linked from the bottom of the timeline as "Read as a book") renders
every readable story on one page, oldest first, with a title cover and a
small ornament between entries — drafts and sealed letters are excluded, same
as the timeline. It doubles as a print layout: the floating "Print / save as
PDF" button calls the browser's native print dialog, which (via a dedicated
print stylesheet) forces the light palette, hides all navigation and buttons,
and starts each story on its own page — "save as PDF" in the print dialog
gives a clean, book-like PDF of the whole thing.

## Backing up

**Back up the `stories/` folder. That is everything.** There is no database, no
other state to preserve. Copying that one directory (e.g. with `rsync`, a nightly
`tar`, or syncing it to cloud storage) is a complete backup. Restoring is just
putting the folder back. For a one-tap copy from the app itself, the timeline's
"Download everything (.zip)" link (`/export`) streams the same directory as a
zip file.

## Running the tests

```bash
pip install -r requirements.txt
pytest
```

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

## Ideas for later

Out of scope for v1, deliberately: multi-user accounts, comments/reactions,
search, tags, RSS, email, video, encryption at rest, i18n, offline support
(no service worker — see "Home-screen install" above), and story deletion.
If any of these become worth doing, they belong here first, not as a
surprise addition.

(PDF/print export, a photo lightbox, and home-screen install were originally
listed here too; they shipped as the book view, F7, and F9 — see above.)
