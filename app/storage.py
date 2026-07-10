"""All filesystem read/write for stories lives here.

Every function takes the stories root directory as its first argument (no
hidden global state), which keeps this module pure and easy to test against a
tmp directory.
"""

import logging
import os
import re
import shutil
import unicodedata
import zipfile
from dataclasses import dataclass
from datetime import date as date_cls
from datetime import datetime
from pathlib import Path
from typing import Optional

import frontmatter
from PIL import Image, ImageOps
from pillow_heif import register_heif_opener

register_heif_opener()

logger = logging.getLogger(__name__)

STORY_ID_RE = re.compile(r"^[a-z0-9-]+$")
FILENAME_RE = re.compile(r"^[a-z0-9._-]+$")
VERSION_ID_RE = re.compile(r"^\d{8}T\d{6}\d{6}$")
MEMO_RE = re.compile(r"^memo-(\d{3})\.(webm|m4a|mp3|ogg)$")

MAX_IMAGE_EDGE = 2000
JPEG_QUALITY = 85
VERSIONS_DIRNAME = ".versions"
MAX_VERSIONS = 20
MEMO_ALLOWED_EXTENSIONS = ("webm", "m4a", "mp3", "ogg")


class InvalidStoryId(ValueError):
    pass


class InvalidFilename(ValueError):
    pass


class InvalidVersionId(ValueError):
    pass


class ImportCollision(ValueError):
    """Raised when a backup zip contains a story id that already exists on
    disk. Nothing is written when this is raised — see import_backup()."""

    def __init__(self, colliding_ids: list[str]):
        self.colliding_ids = colliding_ids
        noun = "story" if len(colliding_ids) == 1 else "stories"
        super().__init__(f"{len(colliding_ids)} {noun} already exist: {', '.join(colliding_ids)}")


@dataclass
class Memo:
    filename: str
    transcript: Optional[str] = None


@dataclass
class Story:
    id: str
    title: str
    date: date_cls
    created: datetime
    updated: datetime
    cover: Optional[str] = None
    author: Optional[str] = None
    draft: bool = False
    unlock: Optional[date_cls] = None
    archived: bool = False
    kind: str = "story"
    body: Optional[str] = None


def is_valid_story_id(story_id: str) -> bool:
    return bool(story_id) and ".." not in story_id and bool(STORY_ID_RE.match(story_id))


def is_valid_filename(filename: str) -> bool:
    return bool(filename) and ".." not in filename and bool(FILENAME_RE.match(filename))


def is_valid_version_id(version_id: str) -> bool:
    return bool(version_id) and bool(VERSION_ID_RE.match(version_id))


def slugify(title: str, max_len: int = 60) -> str:
    normalized = unicodedata.normalize("NFKD", title)
    ascii_only = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_only.lower()).strip("-")
    slug = re.sub(r"-{2,}", "-", slug)
    return (slug or "untitled")[:max_len].strip("-") or "untitled"


def _story_dir(stories_dir: Path, story_id: str) -> Path:
    if not is_valid_story_id(story_id):
        raise InvalidStoryId(story_id)
    return Path(stories_dir) / story_id


def _parse_post(story_id: str, post: frontmatter.Post, include_body: bool) -> Story:
    metadata = post.metadata
    title = metadata["title"]
    story_date = metadata["date"]
    if isinstance(story_date, str):
        story_date = date_cls.fromisoformat(story_date)
    elif isinstance(story_date, datetime):
        story_date = story_date.date()
    created = metadata.get("created")
    if isinstance(created, str):
        created = datetime.fromisoformat(created)
    updated = metadata.get("updated")
    if isinstance(updated, str):
        updated = datetime.fromisoformat(updated)
    return Story(
        id=story_id,
        title=title,
        date=story_date,
        created=created,
        updated=updated,
        cover=metadata.get("cover"),
        author=metadata.get("author"),
        draft=metadata.get("draft") is True,
        unlock=_parse_unlock(metadata.get("unlock")),
        archived=metadata.get("archived") is True,
        kind="instant" if metadata.get("kind") == "instant" else "story",
        body=post.content if include_body else None,
    )


def _parse_unlock(value) -> Optional[date_cls]:
    """Tolerantly parse the optional `unlock` frontmatter field. Bad values
    are treated as absent rather than crashing the story (same philosophy as
    unknown authors: files outlive config/typos)."""
    if isinstance(value, date_cls) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        try:
            return date_cls.fromisoformat(value)
        except ValueError:
            return None
    return None


def list_stories(stories_dir) -> list[Story]:
    """All stories, frontmatter only (bodies not parsed), sorted by date ascending.

    Malformed story folders are skipped with a logged warning rather than
    crashing the whole timeline.
    """
    stories_dir = Path(stories_dir)
    stories = []
    if not stories_dir.is_dir():
        return stories

    for entry in stories_dir.iterdir():
        if not entry.is_dir():
            continue
        if not is_valid_story_id(entry.name):
            continue
        index_path = entry / "index.md"
        if not index_path.is_file():
            continue
        try:
            post = frontmatter.load(index_path)
            story = _parse_post(entry.name, post, include_body=False)
        except Exception:
            logger.warning("Skipping malformed story folder: %s", entry.name, exc_info=True)
            continue
        stories.append(story)

    stories.sort(key=lambda s: (s.date, s.created or datetime.min))
    return stories


def is_sealed(story: Story, today: Optional[date_cls] = None) -> bool:
    """True while a story's unlock date is still in the future."""
    if today is None:
        today = date_cls.today()
    return story.unlock is not None and story.unlock > today


def readable_stories(stories: list[Story], today: Optional[date_cls] = None) -> list[Story]:
    """Published, unsealed, unarchived stories, date-ascending — the
    canonical "pages of the book" used by reading order, on-this-day, and
    the book view."""
    if today is None:
        today = date_cls.today()
    result = [s for s in stories if not s.draft and not s.archived and not is_sealed(s, today)]
    result.sort(key=lambda s: (s.date, s.created or datetime.min))
    return result


def _is_leap_year(year: int) -> bool:
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)


def on_this_day(stories: list[Story], today: Optional[date_cls] = None) -> list[Story]:
    """Readable stories from a previous year whose month/day matches `today`
    (FEATURES.md F5), newest first, capped at 3. A Feb 29 story surfaces on
    Mar 1 in non-leap years, since Feb 29 doesn't occur that year."""
    if today is None:
        today = date_cls.today()
    matches = []
    for s in readable_stories(stories, today):
        if s.date.year >= today.year:
            continue
        same_day = s.date.month == today.month and s.date.day == today.day
        feb29_makeup = (
            s.date.month == 2 and s.date.day == 29
            and today.month == 3 and today.day == 1
            and not _is_leap_year(today.year)
        )
        if same_day or feb29_makeup:
            matches.append(s)
    matches.sort(key=lambda s: s.date.year, reverse=True)
    return matches[:3]


def get_story(stories_dir, story_id: str) -> Optional[Story]:
    """Full story including raw markdown body. None if missing/invalid/malformed."""
    if not is_valid_story_id(story_id):
        return None
    index_path = Path(stories_dir) / story_id / "index.md"
    if not index_path.is_file():
        return None
    try:
        post = frontmatter.load(index_path)
        return _parse_post(story_id, post, include_body=True)
    except Exception:
        logger.warning("Failed to load story: %s", story_id, exc_info=True)
        return None


def _write_index(stories_dir, story_id: str, title: str, story_date: date_cls,
                  created: datetime, updated: datetime, cover: Optional[str], body: str,
                  author: Optional[str] = None, draft: bool = False,
                  unlock: Optional[date_cls] = None, archived: bool = False,
                  kind: str = "story") -> None:
    post = frontmatter.Post(body)
    post["title"] = title
    post["date"] = story_date.isoformat()
    post["created"] = created.isoformat()
    post["updated"] = updated.isoformat()
    if cover:
        post["cover"] = cover
    if author:
        post["author"] = author
    if draft:
        post["draft"] = True
    if unlock:
        post["unlock"] = unlock.isoformat()
    if archived:
        post["archived"] = True
    if kind == "instant":
        post["kind"] = "instant"
    index_path = Path(stories_dir) / story_id / "index.md"
    tmp_path = index_path.with_suffix(".md.tmp")
    tmp_path.write_text(frontmatter.dumps(post) + "\n", encoding="utf-8")
    os.replace(tmp_path, index_path)


def create_story(stories_dir, title: str, story_date: date_cls, body: str = "",
                  author: Optional[str] = None, draft: bool = False,
                  unlock: Optional[date_cls] = None, archived: bool = False,
                  kind: str = "story") -> str:
    """Create a new story folder, returning its story_id (the folder name).

    On slug collision, append -2, -3, ... to the slug. `kind` is set once
    here and never changes afterwards (see save_story).
    """
    stories_dir = Path(stories_dir)
    slug = slugify(title)
    base_id = f"{story_date.isoformat()}-{slug}"
    story_id = base_id
    suffix = 1
    while (stories_dir / story_id).exists():
        suffix += 1
        story_id = f"{base_id}-{suffix}"

    story_path = stories_dir / story_id
    story_path.mkdir(parents=True)
    now = datetime.now()
    _write_index(stories_dir, story_id, title, story_date, now, now, None, body, author=author,
                 draft=draft, unlock=unlock, archived=archived, kind=kind)
    return story_id


def save_story(stories_dir, story_id: str, title: str, story_date: date_cls,
               body: str, cover: Optional[str] = None, author: Optional[str] = None,
               draft: bool = False, unlock: Optional[date_cls] = None,
               archived: bool = False) -> None:
    """Update an existing story's content in place. The story_id never changes.

    `cover`/`author` of None means "leave unchanged"; an empty string clears
    the field (frontmatter key is omitted for falsy values). `draft`/`unlock`/
    `archived` are always set wholesale from the given value (their editor
    controls are always present on the form, so there is nothing to "leave
    unchanged"). `kind` is not a parameter here at all — it is set once at
    creation and always carried over from the existing story. The content
    about to be overwritten is snapshotted into `.versions/` first (see
    `list_versions`/`restore_version`), so an accidental bad edit or
    overwrite is never unrecoverable.
    """
    if not is_valid_story_id(story_id):
        raise InvalidStoryId(story_id)
    existing = get_story(stories_dir, story_id)
    if existing is None:
        raise FileNotFoundError(story_id)
    _snapshot_version(stories_dir, story_id)
    created = existing.created or datetime.now()
    if cover is None:
        cover = existing.cover
    if author is None:
        author = existing.author
    _write_index(stories_dir, story_id, title, story_date, created, datetime.now(), cover, body,
                 author=author, draft=draft, unlock=unlock, archived=archived,
                 kind=existing.kind)


def _versions_dir(stories_dir, story_id: str) -> Path:
    return _story_dir(stories_dir, story_id) / VERSIONS_DIRNAME


def _snapshot_version(stories_dir, story_id: str) -> None:
    """Copy the current index.md into `.versions/` before a save overwrites
    it. Silently does nothing if there's no index.md yet (first save)."""
    story_path = _story_dir(stories_dir, story_id)
    index_path = story_path / "index.md"
    if not index_path.is_file():
        return
    versions_dir = story_path / VERSIONS_DIRNAME
    versions_dir.mkdir(exist_ok=True)
    version_id = datetime.now().strftime("%Y%m%dT%H%M%S%f")
    dest = versions_dir / f"{version_id}.md"
    if dest.exists():
        return
    shutil.copyfile(index_path, dest)
    _prune_versions(versions_dir)


def _prune_versions(versions_dir: Path, keep: Optional[int] = None) -> None:
    if keep is None:
        keep = MAX_VERSIONS
    files = sorted(versions_dir.glob("*.md"))
    for f in files[: max(0, len(files) - keep)]:
        f.unlink()


def list_versions(stories_dir, story_id: str) -> list[dict]:
    """Metadata for a story's saved-over versions, newest first."""
    versions_dir = _versions_dir(stories_dir, story_id)
    if not versions_dir.is_dir():
        return []
    result = []
    for f in versions_dir.glob("*.md"):
        version_id = f.stem
        if not is_valid_version_id(version_id):
            continue
        try:
            post = frontmatter.load(f)
            title = post.metadata.get("title") or "Untitled"
        except Exception:
            title = "Untitled"
        result.append({
            "id": version_id,
            "title": title,
            "saved_at": datetime.strptime(version_id, "%Y%m%dT%H%M%S%f"),
        })
    result.sort(key=lambda v: v["id"], reverse=True)
    return result


def restore_version(stories_dir, story_id: str, version_id: str) -> None:
    """Overwrite the current story with an earlier saved-over version.

    Goes through `save_story` so the current (about-to-be-replaced) content
    is itself snapshotted first — restoring never discards anything.
    """
    if not is_valid_version_id(version_id):
        raise InvalidVersionId(version_id)
    version_path = _versions_dir(stories_dir, story_id) / f"{version_id}.md"
    if not version_path.is_file():
        raise FileNotFoundError(version_id)
    post = frontmatter.load(version_path)
    old = _parse_post(story_id, post, include_body=True)
    save_story(
        stories_dir, story_id, old.title, old.date, old.body or "",
        cover=old.cover or "", author=old.author or "",
        draft=old.draft, unlock=old.unlock, archived=old.archived,
    )


def _next_photo_number(story_path: Path) -> int:
    max_n = 0
    for f in story_path.glob("photo-*"):
        m = re.match(r"photo-(\d+)\.", f.name)
        if m:
            max_n = max(max_n, int(m.group(1)))
    return max_n + 1


def save_image(stories_dir, story_id: str, file_storage) -> str:
    """Re-encode an uploaded image with Pillow and store it in the story folder.

    Returns the new filename (photo-NNN.<ext>). Never deletes existing images.
    """
    story_path = _story_dir(stories_dir, story_id)
    if not story_path.is_dir():
        raise FileNotFoundError(story_id)

    image = Image.open(file_storage.stream)
    is_png = (image.format or "").upper() == "PNG"
    image = ImageOps.exif_transpose(image)
    number = _next_photo_number(story_path)
    image.thumbnail((MAX_IMAGE_EDGE, MAX_IMAGE_EDGE))

    if is_png:
        filename = f"photo-{number:03d}.png"
        image.save(story_path / filename, format="PNG")
    else:
        filename = f"photo-{number:03d}.jpg"
        image = image.convert("RGB")
        image.save(story_path / filename, format="JPEG", quality=JPEG_QUALITY)

    return filename


def _next_memo_number(story_path: Path) -> int:
    max_n = 0
    for f in story_path.glob("memo-*"):
        m = MEMO_RE.match(f.name)
        if m:
            max_n = max(max_n, int(m.group(1)))
    return max_n + 1


def list_memos(story_dir) -> list["Memo"]:
    """Voice memos in a story folder, sorted by filename (FEATURES.md F12).

    No frontmatter involved — memos are discovered purely from filenames
    matching `memo-NNN.<ext>`. An optional same-stem `.txt` sidecar is read
    as the transcript; the app only ever reads sidecars, never writes them.
    """
    story_dir = Path(story_dir)
    memos = []
    if not story_dir.is_dir():
        return memos
    for f in sorted(story_dir.iterdir()):
        if not f.is_file() or not MEMO_RE.match(f.name):
            continue
        sidecar = f.with_suffix(".txt")
        transcript = None
        if sidecar.is_file():
            try:
                transcript = sidecar.read_text(encoding="utf-8").strip() or None
            except OSError:
                transcript = None
        memos.append(Memo(filename=f.name, transcript=transcript))
    return memos


def save_memo(stories_dir, story_id: str, file_storage) -> str:
    """Store an uploaded voice memo as the next memo-NNN.<ext> in the story
    folder. The extension is taken from the uploaded filename (the recorder
    names its blob after its own mimetype) and must be one of
    MEMO_ALLOWED_EXTENSIONS, else ValueError.
    """
    story_path = _story_dir(stories_dir, story_id)
    if not story_path.is_dir():
        raise FileNotFoundError(story_id)

    original = file_storage.filename or ""
    ext = original.rsplit(".", 1)[-1].lower() if "." in original else ""
    if ext not in MEMO_ALLOWED_EXTENSIONS:
        raise ValueError("Unsupported audio format.")

    number = _next_memo_number(story_path)
    filename = f"memo-{number:03d}.{ext}"
    file_storage.save(story_path / filename)
    return filename


def delete_memo(stories_dir, story_id: str, filename: str) -> bool:
    """Remove a voice memo and its transcript sidecar if present.

    Returns False (caller should 404) when the filename doesn't match the
    memo pattern or doesn't exist on disk. This is the one deletion the app
    supports, and it stays memo-scoped.
    """
    story_path = _story_dir(stories_dir, story_id)
    if not MEMO_RE.match(filename):
        return False
    memo_path = story_path / filename
    if not memo_path.is_file():
        return False
    memo_path.unlink()
    sidecar = memo_path.with_suffix(".txt")
    if sidecar.is_file():
        sidecar.unlink()
    return True


def import_backup(stories_dir, zip_file) -> int:
    """Restore a backup zip produced by the /export download.

    Only ever extracts entries shaped like `<valid-story-id>/...` (rejecting
    anything else as an unsafe or unrecognized path). If ANY of those story
    ids already exist on disk, raises ImportCollision and writes nothing —
    an import either fully succeeds or has no effect at all. Returns the
    number of story folders imported.
    """
    stories_dir = Path(stories_dir)
    with zipfile.ZipFile(zip_file) as zf:
        members = []
        story_ids = set()
        for info in zf.infolist():
            name = info.filename
            if name.endswith("/"):
                continue
            if name.startswith("/") or ".." in Path(name).parts:
                raise ValueError(f"Unsafe path in backup: {name!r}")
            top = Path(name).parts[0] if Path(name).parts else ""
            if not is_valid_story_id(top):
                raise ValueError(f"Unexpected path in backup: {name!r}")
            story_ids.add(top)
            members.append(info)

        if not members:
            raise ValueError("Backup contains no stories.")

        colliding = sorted(sid for sid in story_ids if (stories_dir / sid).exists())
        if colliding:
            raise ImportCollision(colliding)

        for info in members:
            zf.extract(info, stories_dir)

    return len(story_ids)
