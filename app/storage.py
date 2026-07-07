"""All filesystem read/write for stories lives here.

Every function takes the stories root directory as its first argument (no
hidden global state), which keeps this module pure and easy to test against a
tmp directory.
"""

import logging
import os
import re
import unicodedata
from dataclasses import dataclass
from datetime import date as date_cls
from datetime import datetime
from pathlib import Path
from typing import Optional

import frontmatter
from PIL import Image, ImageOps

logger = logging.getLogger(__name__)

STORY_ID_RE = re.compile(r"^[a-z0-9-]+$")
FILENAME_RE = re.compile(r"^[a-z0-9._-]+$")

MAX_IMAGE_EDGE = 2000
JPEG_QUALITY = 85


class InvalidStoryId(ValueError):
    pass


class InvalidFilename(ValueError):
    pass


@dataclass
class Story:
    id: str
    title: str
    date: date_cls
    created: datetime
    updated: datetime
    cover: Optional[str] = None
    body: Optional[str] = None


def is_valid_story_id(story_id: str) -> bool:
    return bool(story_id) and ".." not in story_id and bool(STORY_ID_RE.match(story_id))


def is_valid_filename(filename: str) -> bool:
    return bool(filename) and ".." not in filename and bool(FILENAME_RE.match(filename))


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
        body=post.content if include_body else None,
    )


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
                  created: datetime, updated: datetime, cover: Optional[str], body: str) -> None:
    post = frontmatter.Post(body)
    post["title"] = title
    post["date"] = story_date.isoformat()
    post["created"] = created.isoformat()
    post["updated"] = updated.isoformat()
    if cover:
        post["cover"] = cover
    index_path = Path(stories_dir) / story_id / "index.md"
    tmp_path = index_path.with_suffix(".md.tmp")
    tmp_path.write_text(frontmatter.dumps(post) + "\n", encoding="utf-8")
    os.replace(tmp_path, index_path)


def create_story(stories_dir, title: str, story_date: date_cls, body: str = "") -> str:
    """Create a new story folder, returning its story_id (the folder name).

    On slug collision, append -2, -3, ... to the slug.
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
    _write_index(stories_dir, story_id, title, story_date, now, now, None, body)
    return story_id


def save_story(stories_dir, story_id: str, title: str, story_date: date_cls,
               body: str, cover: Optional[str] = None) -> None:
    """Update an existing story's content in place. The story_id never changes."""
    if not is_valid_story_id(story_id):
        raise InvalidStoryId(story_id)
    existing = get_story(stories_dir, story_id)
    if existing is None:
        raise FileNotFoundError(story_id)
    created = existing.created or datetime.now()
    if cover is None:
        cover = existing.cover
    _write_index(stories_dir, story_id, title, story_date, created, datetime.now(), cover, body)


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
