# Storybook

A private, self-hosted memory journal. A parent writes stories (text + photos) for
their child; the family reads them later as a chronological timeline and as
book-like story pages.

Everything is stored as plain **markdown files and images on disk** — no database.
If you delete the app entirely and keep the `stories/` folder, every story is still
fully readable with nothing more than a file browser and a text editor.

See `PLAN.md` for the full design specification this app was built from.

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

### Configuration

All configuration is via environment variables — see `.env.example`:

| Variable | Purpose |
|---|---|
| `STORYBOOK_STORIES_DIR` | Where story folders live (default `./stories`) |
| `STORYBOOK_PASSWORD` | The one shared password. Required in production. |
| `STORYBOOK_SECRET_KEY` | Flask session-signing secret. Required in production. |

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

The plan for this app calls for vendoring the real
[Toast UI Editor](https://github.com/nhn/tui.editor) as a rich WYSIWYG markdown
editor. In the environment this app was built in, outbound access to the Toast UI
CDN was blocked by network policy, and the `@toast-ui/editor` npm package's own
bundle isn't a standalone browser build (it expects several peer libraries to be
loaded separately). `app/static/vendor/toastui/` currently contains clearly-marked
placeholder files instead of the real bundle, and the editor page automatically
falls back to a plain `<textarea>` with a minimal formatting toolbar (heading,
bold, italic, strikethrough, quote, lists, link, highlight, and image upload) that
covers the same functionality without the dependency.

To enable the full rich editor, download the real `toastui-editor-all.min.js`,
`toastui-editor.min.css`, and `theme/toastui-editor-dark.css` (Toast UI Editor 3.x)
and replace the placeholder files at the same paths under
`app/static/vendor/toastui/`. `editor.js` detects the real library automatically —
no code changes needed.

## Ideas for later

Out of scope for v1, deliberately: multi-user accounts, comments/reactions,
search, tags, RSS, email, PDF/print export, image galleries/lightboxes, video,
encryption at rest, i18n, PWA/offline support, and story deletion. If any of
these become worth doing, they belong here first, not as a surprise addition.
