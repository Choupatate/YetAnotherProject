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

Serves on `http://0.0.0.0:8000` by default (set `PORT` to change it).

### Docker

```bash
docker build -t storybook .
docker run -p 8000:8000 \
  -e STORYBOOK_PASSWORD=... \
  -e STORYBOOK_SECRET_KEY=... \
  -v storybook-data:/data/stories \
  storybook
```

The container stores stories under `/data/stories`; mount a volume there so content
survives container recreation.

### Docker Compose (e.g. Synology)

```bash
cp .env.example .env   # then edit STORYBOOK_PASSWORD and STORYBOOK_SECRET_KEY
docker compose up -d --build
```

`docker-compose.yml` reads `STORYBOOK_PASSWORD`, `STORYBOOK_SECRET_KEY`, and
`STORYBOOK_COOKIE_SECURE` from `.env` in the same directory (Compose loads it
automatically — no `env_file:` needed) and bind-mounts `/volume2/Media/StoryBook`
on the host to `/data/stories` in the container. On Synology, either run this
from an SSH session with Docker installed, or point Container Manager's project
at this repo folder. Adjust the host path in `docker-compose.yml` if your
shares live elsewhere.

### Configuration

All configuration is via environment variables — see `.env.example`:

| Variable | Purpose |
|---|---|
| `STORYBOOK_STORIES_DIR` | Where story folders live (default `./stories`) |
| `STORYBOOK_PASSWORD` | The one shared password. Required in production. |
| `STORYBOOK_SECRET_KEY` | Flask session-signing secret. Required whenever `STORYBOOK_PASSWORD` is set — the app refuses to start otherwise. |
| `STORYBOOK_COOKIE_SECURE` | Set to `1` when serving over HTTPS to mark the session cookie `Secure`. Default off, for local/LAN HTTP use. |

## Backing up

**Back up the `stories/` folder. That is everything.** There is no database, no
other state to preserve. Copying that one directory (e.g. with `rsync`, a nightly
`tar`, or syncing it to cloud storage) is a complete backup. Restoring is just
putting the folder back.

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
search, tags, RSS, email, PDF/print export, image galleries/lightboxes, video,
encryption at rest, i18n, PWA/offline support, and story deletion. If any of
these become worth doing, they belong here first, not as a surprise addition.
