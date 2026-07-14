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


@dataclass
class Person:
    slug: str
    name: str
    created: datetime
    updated: datetime
    relation: Optional[str] = None
    photo: Optional[str] = None
    photo_focus: Optional[str] = None
    body: Optional[str] = None
    parents: list = None
    partners: list = None
    friend_of: list = None
    gender: Optional[str] = None

    def __post_init__(self):
        if self.parents is None:
            self.parents = []
        if self.partners is None:
            self.partners = []
        if self.friend_of is None:
            self.friend_of = []


def _parse_slug_list(value) -> list:
    """Tolerant parsing of a frontmatter list-of-slugs field: anything that
    isn't a list of non-empty strings is treated as empty (files outlive
    edits — a malformed field never breaks the page)."""
    if not isinstance(value, list):
        return []
    return [v for v in value if isinstance(v, str) and v]


_PHOTO_FOCUS_RE = re.compile(r"^(\d{1,3})% (\d{1,3})%$")


def is_valid_photo_focus(value) -> bool:
    """A photo_focus is a CSS object-position pair 'X% Y%' with each 0-100."""
    if not isinstance(value, str):
        return False
    match = _PHOTO_FOCUS_RE.match(value)
    if not match:
        return False
    return all(0 <= int(g) <= 100 for g in match.groups())


def _parse_photo_focus(value) -> Optional[str]:
    """Malformed values silently drop to None (files outlive edits)."""
    return value if is_valid_photo_focus(value) else None


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
    return Person(
        slug=slug,
        name=name,
        created=created,
        updated=updated,
        relation=metadata.get("relation") or None,
        photo=metadata.get("photo") or None,
        photo_focus=_parse_photo_focus(metadata.get("photo_focus")),
        body=post.content if include_body else None,
        parents=_parse_slug_list(metadata.get("parents")),
        partners=_parse_slug_list(metadata.get("partners")),
        friend_of=_parse_slug_list(metadata.get("friend_of")),
        gender=gender,
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
                  photo_focus: Optional[str] = None) -> None:
    post = frontmatter.Post(body)
    post["name"] = name
    post["created"] = created.isoformat()
    post["updated"] = updated.isoformat()
    if relation:
        post["relation"] = relation
    if photo:
        post["photo"] = photo
    if photo_focus:
        post["photo_focus"] = photo_focus
    if parents:
        post["parents"] = list(parents)
    if partners:
        post["partners"] = list(partners)
    if friend_of:
        post["friend_of"] = list(friend_of)
    if gender:
        post["gender"] = gender
    index_path = Path(people_dir) / slug / "index.md"
    tmp_path = index_path.with_suffix(".md.tmp")
    tmp_path.write_text(frontmatter.dumps(post) + "\n", encoding="utf-8")
    os.replace(tmp_path, index_path)


def create_person(people_dir, name: str, relation: Optional[str] = None, body: str = "",
                   parents: Optional[list] = None, partners: Optional[list] = None,
                   friend_of: Optional[list] = None, gender: Optional[str] = None) -> str:
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
                 parents=parents, partners=partners, friend_of=friend_of, gender=gender)
    return slug


def update_person(people_dir, slug: str, name: str, relation: Optional[str] = None,
                   body: str = "", photo: Optional[str] = None,
                   parents: Optional[list] = None, partners: Optional[list] = None,
                   friend_of: Optional[list] = None, gender: Optional[str] = None,
                   photo_focus: Optional[str] = None) -> None:
    """Update an existing person's content in place. The slug never changes.

    `photo` of None means "leave unchanged"; an empty string clears it.
    `parents`/`partners`/`friend_of`/`gender`/`photo_focus` of None means
    "leave unchanged"; an empty string clears `photo_focus`.
    """
    if not storage.is_valid_story_id(slug):
        raise storage.InvalidStoryId(slug)
    existing = get_person(people_dir, slug)
    if existing is None:
        raise FileNotFoundError(slug)
    created = existing.created or datetime.now()
    if photo is None:
        photo = existing.photo
    if photo_focus is None:
        photo_focus = existing.photo_focus
    if parents is None:
        parents = existing.parents
    if partners is None:
        partners = existing.partners
    if friend_of is None:
        friend_of = existing.friend_of
    if gender is None:
        gender = existing.gender
    _write_index(people_dir, slug, name, created, datetime.now(), relation, photo, body,
                 parents=parents, partners=partners, friend_of=friend_of, gender=gender,
                 photo_focus=photo_focus)
