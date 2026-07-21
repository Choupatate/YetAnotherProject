"""All filesystem read/write for people (FEATURES.md F14) lives here,
mirroring storage.py's shape: pure functions taking the people directory as
their first argument, no hidden global state.
"""

import logging
import os
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

import frontmatter

from . import storage

logger = logging.getLogger(__name__)

DEFAULT_PHOTO_SEPIA = 30

# Same shape as __init__.py's STORYBOOK_AUTHORS color regex — duplicated
# rather than imported, since importing from the app package's __init__
# into a module it itself imports would invert the dependency direction.
_AUTHOR_COLOR_RE = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")


@dataclass
class Person:
    slug: str
    name: str
    created: datetime
    updated: datetime
    relation: Optional[str] = None
    photo: Optional[str] = None
    photo_sepia: Optional[int] = None
    body: Optional[str] = None
    parents: list = None
    partners: list = None
    friend_of: list = None
    gender: Optional[str] = None
    author_color: Optional[str] = None
    sources: list = None

    def __post_init__(self):
        if self.parents is None:
            self.parents = []
        if self.partners is None:
            self.partners = []
        if self.friend_of is None:
            self.friend_of = []
        if self.sources is None:
            self.sources = []


def _parse_slug_list(value) -> list:
    """Tolerant parsing of a frontmatter list-of-slugs field: anything that
    isn't a list of non-empty strings is treated as empty (files outlive
    edits — a malformed field never breaks the page)."""
    if not isinstance(value, list):
        return []
    return [v for v in value if isinstance(v, str) and v]


def is_valid_photo_sepia(value) -> bool:
    """A photo_sepia is a whole-number percentage, 0-100 (bool is not an int
    here even though it subclasses one — a stray `true`/`false` in the
    frontmatter should not silently become 0 or 1)."""
    return isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= 100


def _parse_photo_sepia(value) -> Optional[int]:
    """Malformed values silently drop to None (files outlive edits); the
    caller applies DEFAULT_PHOTO_SEPIA when a photo exists but this is
    unset."""
    return value if is_valid_photo_sepia(value) else None


def is_valid_author_color(value) -> bool:
    """A CSS hex color, 3 or 6 digits — same shape __init__.py already
    requires of STORYBOOK_AUTHORS colors (FEATURES.md F19 Phase 4: this is
    the per-person replacement for that env-config color)."""
    return isinstance(value, str) and bool(_AUTHOR_COLOR_RE.match(value))


def _parse_author_color(value) -> Optional[str]:
    """Malformed values silently drop to None (files outlive edits) —
    the byline/legend just render neutral for that person, same
    graceful-degradation F1 already used for an unmatched author name."""
    return value if is_valid_author_color(value) else None


def _parse_sources(value) -> list:
    """Tolerant parsing of a frontmatter `sources` field: a list of
    `{"url": ..., "note": ...}` dicts. Malformed entries (missing/blank
    url) are dropped rather than raised (files outlive edits). Duplicated
    from storage.py's version rather than imported, same convention as
    _AUTHOR_COLOR_RE above."""
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


def _parse_post(slug: str, post: frontmatter.Post, include_body: bool) -> Optional[Person]:
    metadata = post.metadata
    name = metadata.get("name")
    if not name:
        return None
    created = metadata.get("created")
    if isinstance(created, str):
        created = datetime.fromisoformat(created)
    updated = metadata.get("updated")
    if isinstance(updated, str):
        updated = datetime.fromisoformat(updated)
    gender = metadata.get("gender") or None
    if gender not in ("m", "f", None):
        gender = None
    photo = metadata.get("photo") or None
    photo_sepia = _parse_photo_sepia(metadata.get("photo_sepia"))
    if photo and photo_sepia is None:
        photo_sepia = DEFAULT_PHOTO_SEPIA
    return Person(
        slug=slug,
        name=name,
        created=created,
        updated=updated,
        relation=metadata.get("relation") or None,
        photo=photo,
        photo_sepia=photo_sepia,
        body=post.content if include_body else None,
        parents=_parse_slug_list(metadata.get("parents")),
        partners=_parse_slug_list(metadata.get("partners")),
        friend_of=_parse_slug_list(metadata.get("friend_of")),
        gender=gender,
        author_color=_parse_author_color(metadata.get("author_color")),
        sources=_parse_sources(metadata.get("sources")),
    )


def list_people(people_dir) -> list[Person]:
    """All people, sorted by created ascending (the order they entered the
    book). A folder without a `name` is skipped with a logged warning — same
    tolerant-parsing philosophy as storage.list_stories.
    """
    people_dir = Path(people_dir)
    people_list = []
    if not people_dir.is_dir():
        return people_list

    for entry in people_dir.iterdir():
        if not entry.is_dir() or not storage.is_valid_story_id(entry.name):
            continue
        index_path = entry / "index.md"
        if not index_path.is_file():
            continue
        try:
            post = frontmatter.load(index_path)
            person = _parse_post(entry.name, post, include_body=False)
        except Exception:
            logger.warning("Skipping malformed person folder: %s", entry.name, exc_info=True)
            continue
        if person is None:
            logger.warning("Skipping person folder with no name: %s", entry.name)
            continue
        people_list.append(person)

    people_list.sort(key=lambda p: p.created or datetime.min)
    return people_list


def get_person(people_dir, slug: str) -> Optional[Person]:
    """Full person including raw markdown body. None if missing/invalid/malformed."""
    if not storage.is_valid_story_id(slug):
        return None
    index_path = Path(people_dir) / slug / "index.md"
    if not index_path.is_file():
        return None
    try:
        post = frontmatter.load(index_path)
        return _parse_post(slug, post, include_body=True)
    except Exception:
        logger.warning("Failed to load person: %s", slug, exc_info=True)
        return None


def _write_index(people_dir, slug: str, name: str, created: datetime, updated: datetime,
                  relation: Optional[str], photo: Optional[str], body: str,
                  parents: Optional[list] = None, partners: Optional[list] = None,
                  friend_of: Optional[list] = None, gender: Optional[str] = None,
                  photo_sepia: Optional[int] = None, author_color: Optional[str] = None,
                  sources: Optional[list] = None) -> None:
    post = frontmatter.Post(body)
    post["name"] = name
    post["created"] = created.isoformat()
    post["updated"] = updated.isoformat()
    if relation:
        post["relation"] = relation
    if photo:
        post["photo"] = photo
    if photo and photo_sepia is not None:
        post["photo_sepia"] = photo_sepia
    if parents:
        post["parents"] = list(parents)
    if partners:
        post["partners"] = list(partners)
    if friend_of:
        post["friend_of"] = list(friend_of)
    if gender:
        post["gender"] = gender
    if author_color:
        post["author_color"] = author_color
    if sources:
        post["sources"] = sources
    index_path = Path(people_dir) / slug / "index.md"
    tmp_path = index_path.with_suffix(".md.tmp")
    tmp_path.write_text(frontmatter.dumps(post) + "\n", encoding="utf-8")
    os.replace(tmp_path, index_path)


def create_person(people_dir, name: str, relation: Optional[str] = None, body: str = "",
                   parents: Optional[list] = None, partners: Optional[list] = None,
                   friend_of: Optional[list] = None, gender: Optional[str] = None,
                   author_color: Optional[str] = None, sources: Optional[list] = None) -> str:
    """Create a new person folder, returning its slug (the folder name).

    On slug collision, append -2, -3, ... (same rule as storage.create_story).
    """
    people_dir = Path(people_dir)
    people_dir.mkdir(parents=True, exist_ok=True)
    base_slug = storage.slugify(name)
    slug = base_slug
    suffix = 1
    while (people_dir / slug).exists():
        suffix += 1
        slug = f"{base_slug}-{suffix}"

    person_path = people_dir / slug
    person_path.mkdir(parents=True)
    now = datetime.now()
    _write_index(people_dir, slug, name, now, now, relation, None, body,
                 parents=parents, partners=partners, friend_of=friend_of, gender=gender,
                 author_color=author_color, sources=sources)
    return slug


def update_person(people_dir, slug: str, name: str, relation: Optional[str] = None,
                   body: str = "", photo: Optional[str] = None,
                   parents: Optional[list] = None, partners: Optional[list] = None,
                   friend_of: Optional[list] = None, gender: Optional[str] = None,
                   photo_sepia: Optional[int] = None, author_color: Optional[str] = None,
                   sources: Optional[list] = None) -> None:
    """Update an existing person's content in place. The slug never changes.

    `photo` of None means "leave unchanged"; an empty string clears it.
    `parents`/`partners`/`friend_of`/`gender`/`author_color`/`sources` of
    None means "leave unchanged" — pass an empty string/list to clear them.
    `photo_sepia` of None means "leave unchanged" — pass an explicit int
    (including 0) to set it.
    """
    if not storage.is_valid_story_id(slug):
        raise storage.InvalidStoryId(slug)
    existing = get_person(people_dir, slug)
    if existing is None:
        raise FileNotFoundError(slug)
    created = existing.created or datetime.now()
    if photo is None:
        photo = existing.photo
    if photo_sepia is None:
        photo_sepia = existing.photo_sepia
    if parents is None:
        parents = existing.parents
    if partners is None:
        partners = existing.partners
    if friend_of is None:
        friend_of = existing.friend_of
    if gender is None:
        gender = existing.gender
    if author_color is None:
        author_color = existing.author_color
    if sources is None:
        sources = existing.sources
    _write_index(people_dir, slug, name, created, datetime.now(), relation, photo, body,
                 parents=parents, partners=partners, friend_of=friend_of, gender=gender,
                 photo_sepia=photo_sepia, author_color=author_color, sources=sources)
