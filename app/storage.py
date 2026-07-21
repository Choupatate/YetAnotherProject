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
THUMB_MAX_EDGE = 320
JPEG_QUALITY = 85
VERSIONS_DIRNAME = ".versions"
MAX_VERSIONS = 20
MEMO_ALLOWED_EXTENSIONS = ("webm", "m4a", "mp3", "ogg")


class InvalidStoryId(ValueError):
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
    people: list = None
    tags: list = None
    sources: list = None

    def __post_init__(self):
        if self.people is None:
            self.people = []
        if self.tags is None:
            self.tags = []
        if self.sources is None:
            self.sources = []


def is_valid_story_id(story_id: str) -> bool:
    return bool(story_id) and ".." not in story_id and bool(STORY_ID_RE.match(story_id))


def is_valid_filename(filename: str) -> bool:
    return bool(filename) and ".." not in filename and bool(FILENAME_RE.match(filename))


def thumb_filename(filename: str) -> str:
    """The small-thumbnail sibling of an image filename, e.g.
    "photo-003.jpg" -> "photo-003.thumb.jpg" (see `save_image_to`)."""
    name, ext = filename.rsplit(".", 1)
    return f"{name}.thumb.{ext}"


def original_filename_from_thumb(filename: str) -> Optional[str]:
    """Inverse of `thumb_filename`, for the `_serve_media` fallback that
    serves the full-size photo when a thumbnail hasn't been generated for it
    (photos uploaded before thumbnails existed). None if `filename` isn't a
    thumb-shaped name."""
    if ".thumb." not in filename:
        return None
    return filename.replace(".thumb.", ".", 1)


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


def people_dir(stories_dir) -> Path:
    """The "cast of the book" (FEATURES.md F14) lives in a fixed
    subdirectory of the stories root, same as every other story folder."""
    return Path(stories_dir) / "people"


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
        people=_parse_string_list(metadata.get("people")),
        tags=_parse_string_list(metadata.get("tags"), max_items=MAX_TAGS, max_length=MAX_TAG_LENGTH),
        sources=_parse_sources(metadata.get("sources")),
    )


MAX_TAGS = 20
MAX_TAG_LENGTH = 40


def _parse_string_list(value, max_items=None, max_length=None) -> list:
    """Tolerant parsing of a frontmatter list-of-strings field (`people`,
    `tags`): anything that isn't a list of non-empty strings is dropped
    rather than raised (files outlive edits), duplicates are removed."""
    if not isinstance(value, list):
        return []
    result = []
    for v in value:
        if not isinstance(v, str):
            continue
        v = v.strip()
        if not v:
            continue
        if max_length:
            v = v[:max_length]
        if v not in result:
            result.append(v)
    if max_items:
        result = result[:max_items]
    return result


def _parse_sources(value) -> list:
    """Tolerant parsing of a frontmatter `sources` field: a list of
    `{"url": ..., "note": ...}` dicts. Malformed entries (missing/blank
    url) are dropped rather than raised (files outlive edits)."""
    if not isinstance(value, list):
        return []
    result = []
    for v in value:
        if not isinstance(v, dict):
            continue
        url = v.get("url")
        if not isinstance(url, str) or not url.strip():
            continue
        note = v.get("note")
        result.append({
            "url": url.strip(),
            "note": note.strip() if isinstance(note, str) else "",
        })
    return result


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
        if entry.name == "people":
            # FEATURES.md F14: people live in their own subtree, sorted
            # separately via app/people.py — silently not a story.
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


def stories_featuring(stories_dir, person_slug: str) -> list[Story]:
    """Stories whose `people` field includes `person_slug`, date-ascending —
    used by the person page's "Appears in" section."""
    return [s for s in list_stories(stories_dir) if person_slug in s.people]


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


def readable_page_stories(stories_dir) -> list[Story]:
    """`readable_stories` narrowed to `kind == "story"` — the candidate set
    for anything that turns pages (F15 random, F2 reading order): instants
    (F13) are a different, feed-like kind and never page-turn targets."""
    return [s for s in readable_stories(list_stories(stories_dir)) if s.kind == "story"]


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
                  kind: str = "story", people: Optional[list] = None,
                  tags: Optional[list] = None, sources: Optional[list] = None) -> None:
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
    if people:
        post["people"] = people
    if tags:
        post["tags"] = tags
    if sources:
        post["sources"] = sources
    index_path = Path(stories_dir) / story_id / "index.md"
    tmp_path = index_path.with_suffix(".md.tmp")
    tmp_path.write_text(frontmatter.dumps(post) + "\n", encoding="utf-8")
    os.replace(tmp_path, index_path)


def create_story(stories_dir, title: str, story_date: date_cls, body: str = "",
                  author: Optional[str] = None, draft: bool = False,
                  unlock: Optional[date_cls] = None, archived: bool = False,
                  kind: str = "story", people: Optional[list] = None,
                  tags: Optional[list] = None, sources: Optional[list] = None) -> str:
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
                 draft=draft, unlock=unlock, archived=archived, kind=kind,
                 people=people, tags=tags, sources=sources)
    return story_id


def save_story(stories_dir, story_id: str, title: str, story_date: date_cls,
               body: str, cover: Optional[str] = None, author: Optional[str] = None,
               draft: bool = False, unlock: Optional[date_cls] = None,
               archived: bool = False, people: Optional[list] = None,
               tags: Optional[list] = None, sources: Optional[list] = None) -> None:
    """Update an existing story's content in place. The story_id never changes.

    `cover`/`author`/`people`/`tags`/`sources` of None means "leave
    unchanged"; an empty value clears the field (frontmatter key is omitted
    for falsy values). `draft`/`unlock`/`archived` are always set wholesale
    from the given value (their editor controls are always present on the
    form, so there is nothing to "leave unchanged"). `kind` is not a
    parameter here at all — it is set once at creation and always carried
    over from the existing story. The content about to be overwritten is
    snapshotted into `.versions/` first (see `list_versions`/
    `restore_version`), so an accidental bad edit or overwrite is never
    unrecoverable.
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
    if people is None:
        people = existing.people
    if tags is None:
        tags = existing.tags
    if sources is None:
        sources = existing.sources
    _write_index(stories_dir, story_id, title, story_date, created, datetime.now(), cover, body,
                 author=author, draft=draft, unlock=unlock, archived=archived,
                 kind=existing.kind, people=people, tags=tags, sources=sources)


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


def _prune_versions(versions_dir: Path) -> None:
    files = sorted(versions_dir.glob("*.md"))
    for f in files[: max(0, len(files) - MAX_VERSIONS)]:
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
        people=old.people or [], tags=old.tags or [], sources=old.sources or [],
    )


def _next_photo_number(dir_path: Path) -> int:
    max_n = 0
    for f in dir_path.glob("photo-*"):
        m = re.match(r"photo-(\d+)\.", f.name)
        if m:
            max_n = max(max_n, int(m.group(1)))
    return max_n + 1


def save_image_to(dir_path: Path, file_storage) -> str:
    """Re-encode an uploaded image with Pillow and store it in `dir_path`,
    alongside a small `.thumb.` sibling (see `thumb_filename`) for the
    avatar-sized contexts (timeline, family lists) that don't need the
    full-size photo.

    Returns the new filename (photo-NNN.<ext>). Never deletes existing
    images. Shared by stories and people (FEATURES.md F14) so resize/EXIF/
    naming behavior is identical either way.
    """
    image = Image.open(file_storage.stream)
    is_png = (image.format or "").upper() == "PNG"
    image = ImageOps.exif_transpose(image)
    number = _next_photo_number(dir_path)
    image.thumbnail((MAX_IMAGE_EDGE, MAX_IMAGE_EDGE))

    thumb = image.copy()
    thumb.thumbnail((THUMB_MAX_EDGE, THUMB_MAX_EDGE))

    if is_png:
        filename = f"photo-{number:03d}.png"
        image.save(dir_path / filename, format="PNG")
        thumb.save(dir_path / thumb_filename(filename), format="PNG")
    else:
        filename = f"photo-{number:03d}.jpg"
        image.convert("RGB").save(dir_path / filename, format="JPEG", quality=JPEG_QUALITY)
        thumb.convert("RGB").save(
            dir_path / thumb_filename(filename), format="JPEG", quality=JPEG_QUALITY
        )

    return filename


def save_image(stories_dir, story_id: str, file_storage) -> str:
    """Re-encode an uploaded image and store it in a story's folder."""
    story_path = _story_dir(stories_dir, story_id)
    if not story_path.is_dir():
        raise FileNotFoundError(story_id)
    return save_image_to(story_path, file_storage)


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
