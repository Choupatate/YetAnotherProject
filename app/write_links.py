"""Delegated write-links (FEATURES.md F19 Phase 3): a bearer token a
family/admin account holder can hand to someone else so that person can
submit one story attributed to them, without a username or password of
their own — "no account access as such." Stored per person, a sibling of
account.json: people/<slug>/write_links.json. Pure functions taking the
people directory as their first argument, same shape as the rest of this
app.

Tokens are hashed with plain SHA-256 before being stored, not a slow
password hash — unlike a human-chosen password, a `secrets.token_urlsafe`
token already has ~192 bits of entropy, so a fast, deterministic hash is
the right tool (the same reasoning GitHub/GitLab use for personal access
tokens): it just needs to not be reversible from the stored value, not to
resist brute force on a weak input.
"""

import hashlib
import json
import logging
import os
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from . import storage

logger = logging.getLogger(__name__)

WRITE_LINKS_FILENAME = "write_links.json"
TOKEN_BYTES = 32


@dataclass
class WriteLink:
    id: str  # non-secret identifier for revoke/list URLs — never the token itself
    person_slug: str
    token_hash: str
    label: Optional[str]
    created_at: Optional[datetime]
    expires_at: Optional[datetime]
    single_use: bool
    used_at: Optional[datetime]
    used_by_story_id: Optional[str]
    revoked: bool


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _links_path(people_dir, person_slug: str) -> Path:
    return Path(people_dir) / person_slug / WRITE_LINKS_FILENAME


def _parse_dt(value) -> Optional[datetime]:
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None
    return None


def _link_from_dict(person_slug: str, data: dict) -> WriteLink:
    return WriteLink(
        id=data.get("id"),
        person_slug=person_slug,
        token_hash=data.get("token_hash"),
        label=data.get("label"),
        created_at=_parse_dt(data.get("created_at")),
        expires_at=_parse_dt(data.get("expires_at")),
        single_use=bool(data.get("single_use", True)),
        used_at=_parse_dt(data.get("used_at")),
        used_by_story_id=data.get("used_by_story_id"),
        revoked=bool(data.get("revoked", False)),
    )


def list_links(people_dir, person_slug: str) -> list[WriteLink]:
    """Every write-link this person has ever issued, newest first —
    including expired/used/revoked ones, so they still show in their own
    history. Tolerant of a missing/malformed file, same as account.json."""
    path = _links_path(people_dir, person_slug)
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        logger.warning("Failed to load %s for %s", WRITE_LINKS_FILENAME, person_slug, exc_info=True)
        return []
    links = [_link_from_dict(person_slug, d) for d in data]
    links.sort(key=lambda link: link.created_at or datetime.min, reverse=True)
    return links


def _write_links(people_dir, person_slug: str, links: list[WriteLink]) -> None:
    path = _links_path(people_dir, person_slug)
    data = [
        {
            "id": link.id,
            "token_hash": link.token_hash,
            "label": link.label,
            "created_at": (link.created_at or datetime.now()).isoformat(),
            "expires_at": link.expires_at.isoformat() if link.expires_at else None,
            "single_use": link.single_use,
            "used_at": link.used_at.isoformat() if link.used_at else None,
            "used_by_story_id": link.used_by_story_id,
            "revoked": link.revoked,
        }
        for link in links
    ]
    tmp_path = path.with_suffix(".json.tmp")
    tmp_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp_path, path)


def get_link(people_dir, person_slug: str, link_id: str) -> Optional[WriteLink]:
    for link in list_links(people_dir, person_slug):
        if link.id == link_id:
            return link
    return None


def is_link_valid(link: WriteLink) -> bool:
    """False once revoked, past its expiry, or (for a single-use link)
    already used — the three ways a link stops working."""
    if link.revoked:
        return False
    if link.expires_at and datetime.now() > link.expires_at:
        return False
    if link.single_use and link.used_at:
        return False
    return True


def create_link(
    people_dir, person_slug: str, label: Optional[str] = None,
    expires_in_days: Optional[int] = None, single_use: bool = True,
) -> tuple[WriteLink, str]:
    """Issue a new link. Returns (link_record, raw_token) — the raw token
    is only ever available here, at creation time; only its hash is
    persisted, so it can never be shown or recovered again."""
    if not (Path(people_dir) / person_slug).is_dir():
        raise FileNotFoundError(person_slug)

    token = secrets.token_urlsafe(TOKEN_BYTES)
    link = WriteLink(
        id=secrets.token_hex(8),
        person_slug=person_slug,
        token_hash=_hash_token(token),
        label=(label or "").strip() or None,
        created_at=datetime.now(),
        expires_at=(datetime.now() + timedelta(days=expires_in_days)) if expires_in_days else None,
        single_use=single_use,
        used_at=None,
        used_by_story_id=None,
        revoked=False,
    )
    links = list_links(people_dir, person_slug)
    links.append(link)
    _write_links(people_dir, person_slug, links)
    return link, token


def revoke_link(people_dir, person_slug: str, link_id: str) -> None:
    links = list_links(people_dir, person_slug)
    match = next((link for link in links if link.id == link_id), None)
    if match is None:
        raise FileNotFoundError(link_id)
    match.revoked = True
    _write_links(people_dir, person_slug, links)


def mark_used(people_dir, person_slug: str, link_id: str, story_id: str) -> None:
    links = list_links(people_dir, person_slug)
    match = next((link for link in links if link.id == link_id), None)
    if match is None:
        raise FileNotFoundError(link_id)
    match.used_at = datetime.now()
    match.used_by_story_id = story_id
    _write_links(people_dir, person_slug, links)


def find_by_token(people_dir, token: str) -> Optional[WriteLink]:
    """Scan every person's write_links.json for a token hash match — a
    small, bounded scan across a handful of family members' link lists,
    same cost class as accounts.get_account_by_username."""
    if not token:
        return None
    token_hash = _hash_token(token)
    people_dir = Path(people_dir)
    if not people_dir.is_dir():
        return None
    for entry in people_dir.iterdir():
        if not entry.is_dir() or not storage.is_valid_story_id(entry.name):
            continue
        for link in list_links(people_dir, entry.name):
            if link.token_hash == token_hash:
                return link
    return None


def list_all_active(people_dir) -> list[WriteLink]:
    """Every currently-valid link across every person — the admin
    dashboard's oversight view (an admin can revoke a link they didn't
    issue, e.g. if the family member who created it is unreachable).
    Revoked/expired/used links are omitted; they're not actionable."""
    people_dir = Path(people_dir)
    result = []
    if not people_dir.is_dir():
        return result
    for entry in people_dir.iterdir():
        if not entry.is_dir() or not storage.is_valid_story_id(entry.name):
            continue
        for link in list_links(people_dir, entry.name):
            if is_link_valid(link):
                result.append(link)
    result.sort(key=lambda link: link.created_at or datetime.min, reverse=True)
    return result
