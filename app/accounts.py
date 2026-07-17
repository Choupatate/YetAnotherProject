"""Account credentials for people who can log into Storybook (FEATURES.md
F19), layered on top of people.py's Person model rather than a parallel
identity system: every account is bound to exactly one Person, and most
People have none (a child, a grandparent who's passed — anyone who's in the
book but never logs in). Pure functions taking the people directory as
their first argument, no hidden global state, same shape as people.py.

Credentials live in `people/<slug>/account.json`, a sibling of that
person's `index.md` rather than fields inside it — index.md is read by
every page render, kinship walk, and tree JSON; keeping the password hash
in a narrowly-read file shrinks the blast radius of any future bug that
logs or dumps a Person. Plain JSON, not YAML/frontmatter: this is small
structured data with no prose body, and stdlib `json` avoids leaning on
python-frontmatter's transitive PyYAML dependency for something new.
"""

import json
import logging
import os
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from werkzeug.security import check_password_hash, generate_password_hash

from . import people, storage

logger = logging.getLogger(__name__)

PENDING_FILENAME = "pending_accounts.json"

ROLES = ("admin", "family")
MIN_PASSWORD_LENGTH = 8
USERNAME_RE = re.compile(r"^[a-z0-9-]{3,32}$")


@dataclass
class Account:
    person_slug: str
    username: str
    password_hash: str
    role: str
    status: str  # "active" | "disabled"
    created_at: Optional[datetime] = None
    approved_by: Optional[str] = None


def is_valid_username(username: str) -> bool:
    return bool(username) and bool(USERNAME_RE.match(username))


def _account_path(people_dir, slug: str) -> Path:
    return Path(people_dir) / slug / "account.json"


def _account_from_dict(person_slug: str, data: dict) -> Account:
    created_at = data.get("created_at")
    if isinstance(created_at, str):
        try:
            created_at = datetime.fromisoformat(created_at)
        except ValueError:
            created_at = None
    return Account(
        person_slug=person_slug,
        username=data.get("username"),
        password_hash=data.get("password_hash"),
        role=data.get("role"),
        status=data.get("status", "active"),
        created_at=created_at,
        approved_by=data.get("approved_by"),
    )


def _write_account(people_dir, account: Account) -> None:
    path = _account_path(people_dir, account.person_slug)
    data = {
        "username": account.username,
        "password_hash": account.password_hash,
        "role": account.role,
        "status": account.status,
        "created_at": (account.created_at or datetime.now()).isoformat(),
        "approved_by": account.approved_by,
    }
    tmp_path = path.with_suffix(".json.tmp")
    tmp_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp_path, path)


def get_account(people_dir, person_slug: str) -> Optional[Account]:
    """The account bound to a given Person slug, if any. Tolerant of a
    missing/malformed file the same way people.get_person is — a bad
    account.json is skipped (treated as "no account"), never a crash."""
    path = _account_path(people_dir, person_slug)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return _account_from_dict(person_slug, data)
    except Exception:
        logger.warning("Failed to load account for %s", person_slug, exc_info=True)
        return None


def list_accounts(people_dir) -> list[Account]:
    """Every bound account, oldest first — the admin dashboard's source of
    truth. Scans people/*/account.json, same cost class as
    people.list_people scanning people/*/index.md."""
    people_dir = Path(people_dir)
    result = []
    if not people_dir.is_dir():
        return result
    for entry in people_dir.iterdir():
        if not entry.is_dir() or not storage.is_valid_story_id(entry.name):
            continue
        account = get_account(people_dir, entry.name)
        if account:
            result.append(account)
    result.sort(key=lambda a: a.created_at or datetime.min)
    return result


def any_accounts_exist(people_dir) -> bool:
    """True once at least one account has ever been created — the signal
    that ends bootstrap mode (see auth.login)."""
    return len(list_accounts(people_dir)) > 0


def get_account_by_username(people_dir, username: str) -> Optional[Account]:
    """Scan every bound account for a username match. Usernames are unique
    across the whole install (enforced in create_account); this is a small,
    bounded scan, not an index, because the account count here is a
    handful of family members, not a user base."""
    username = (username or "").strip().lower()
    if not username:
        return None
    for account in list_accounts(people_dir):
        if account.username == username:
            return account
    return None


def is_username_taken(people_dir, username: str) -> bool:
    return get_account_by_username(people_dir, username) is not None


def create_account(
    people_dir, person_slug: str, username: str, password: str, role: str,
    approved_by: Optional[str] = None,
) -> Account:
    """Bind a new account to an existing Person.

    Raises ValueError for a bad username/role/password, a person who
    already has an account, or a username already taken by someone else;
    FileNotFoundError if the person doesn't exist.
    """
    if role not in ROLES:
        raise ValueError(f"Invalid role: {role!r}")
    if len(password or "") < MIN_PASSWORD_LENGTH:
        raise ValueError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters.")
    username = (username or "").strip().lower()
    if not is_valid_username(username):
        raise ValueError(
            "Usernames must be 3-32 characters: lowercase letters, numbers, hyphens."
        )
    people_dir = Path(people_dir)
    if not (people_dir / person_slug).is_dir():
        raise FileNotFoundError(person_slug)
    if get_account(people_dir, person_slug) is not None:
        raise ValueError(f"{person_slug} already has an account.")
    if is_username_taken(people_dir, username):
        raise ValueError(f"Username already taken: {username!r}")

    account = Account(
        person_slug=person_slug,
        username=username,
        password_hash=generate_password_hash(password),
        role=role,
        status="active",
        created_at=datetime.now(),
        approved_by=approved_by,
    )
    _write_account(people_dir, account)
    return account


def set_status(people_dir, person_slug: str, status: str) -> None:
    """Enable/disable an account in place. Disabling takes effect
    immediately (auth.login_required re-checks status on every request,
    since sessions here are client-signed cookies with no server-side
    store to revoke)."""
    if status not in ("active", "disabled"):
        raise ValueError(f"Invalid status: {status!r}")
    account = get_account(people_dir, person_slug)
    if account is None:
        raise FileNotFoundError(person_slug)
    account.status = status
    _write_account(people_dir, account)


def verify_login(people_dir, username: str, password: str) -> Optional[Account]:
    """The matching active account if username/password are correct, else
    None — an unknown username, a wrong password, and a disabled account
    all return the same None so a caller can't distinguish them.

    Hashes a dummy password on an unknown-username lookup so that path
    costs roughly the same CPU time as a real check_password_hash call,
    rather than returning near-instantly and making username validity
    timeable.
    """
    account = get_account_by_username(people_dir, username)
    if account is None:
        check_password_hash(generate_password_hash("dummy-timing-cover"), password or "")
        return None
    if account.status != "active":
        return None
    if not check_password_hash(account.password_hash, password or ""):
        return None
    return account


# ---------------------------------------------------------------------------
# Pending requests (FEATURES.md F19 Phase 2) — a would-be account with no
# Person to bind to yet, so it can't live under people/ like a real Account.
# One small file at the stories root, not one-file-per-request: requests are
# meant to be reviewed and cleared quickly, never expected to pile into the
# hundreds unnoticed. Functions here take `stories_dir` (the parent of
# people_dir), not `people_dir` like the rest of this module, since that's
# the file's actual scope.
# ---------------------------------------------------------------------------


@dataclass
class PendingRequest:
    username: str
    password_hash: str
    display_name: str
    note: Optional[str]
    requested_at: Optional[datetime] = None


def _pending_path(stories_dir) -> Path:
    return Path(stories_dir) / PENDING_FILENAME


def _pending_from_dict(data: dict) -> PendingRequest:
    requested_at = data.get("requested_at")
    if isinstance(requested_at, str):
        try:
            requested_at = datetime.fromisoformat(requested_at)
        except ValueError:
            requested_at = None
    return PendingRequest(
        username=data.get("username"),
        password_hash=data.get("password_hash"),
        display_name=data.get("display_name"),
        note=data.get("note"),
        requested_at=requested_at,
    )


def list_pending(stories_dir) -> list[PendingRequest]:
    """Every request awaiting admin review, oldest first. Tolerant of a
    missing/malformed file — treated as "no requests," never a crash."""
    path = _pending_path(stories_dir)
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        logger.warning("Failed to load %s", PENDING_FILENAME, exc_info=True)
        return []
    result = [_pending_from_dict(d) for d in data]
    result.sort(key=lambda p: p.requested_at or datetime.min)
    return result


def _write_pending(stories_dir, pending_list: list[PendingRequest]) -> None:
    path = _pending_path(stories_dir)
    data = [
        {
            "username": p.username,
            "password_hash": p.password_hash,
            "display_name": p.display_name,
            "note": p.note,
            "requested_at": (p.requested_at or datetime.now()).isoformat(),
        }
        for p in pending_list
    ]
    tmp_path = path.with_suffix(".json.tmp")
    tmp_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp_path, path)


def get_pending(stories_dir, username: str) -> Optional[PendingRequest]:
    username = (username or "").strip().lower()
    for p in list_pending(stories_dir):
        if p.username == username:
            return p
    return None


def is_username_reserved(stories_dir, username: str) -> bool:
    """Taken by a bound account or by another request already in the
    queue — the check create_pending_request needs, since a username must
    be unique across both at once."""
    people_dir = storage.people_dir(stories_dir)
    return is_username_taken(people_dir, username) or get_pending(stories_dir, username) is not None


def create_pending_request(
    stories_dir, username: str, password: str, display_name: str, note: Optional[str] = None,
) -> PendingRequest:
    """Queue a new account request. Raises ValueError for a bad
    username/password/missing display name, or a username already taken
    (bound or pending)."""
    username = (username or "").strip().lower()
    display_name = (display_name or "").strip()
    if not is_valid_username(username):
        raise ValueError(
            "Usernames must be 3-32 characters: lowercase letters, numbers, hyphens."
        )
    if len(password or "") < MIN_PASSWORD_LENGTH:
        raise ValueError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters.")
    if not display_name:
        raise ValueError("Enter your name.")
    if is_username_reserved(stories_dir, username):
        raise ValueError(f"Username already taken: {username!r}")

    pending = PendingRequest(
        username=username,
        password_hash=generate_password_hash(password),
        display_name=display_name,
        note=(note or "").strip() or None,
        requested_at=datetime.now(),
    )
    all_pending = list_pending(stories_dir)
    all_pending.append(pending)
    _write_pending(stories_dir, all_pending)
    return pending


def reject_pending(stories_dir, username: str) -> None:
    """Drop a request from the queue — a no-op if it's already gone."""
    username = (username or "").strip().lower()
    remaining = [p for p in list_pending(stories_dir) if p.username != username]
    _write_pending(stories_dir, remaining)


def approve_pending(
    stories_dir, username: str, role: str,
    person_slug: Optional[str] = None, new_person_name: Optional[str] = None,
    approved_by: Optional[str] = None,
) -> Account:
    """Bind a pending request to a Person — either an existing one with no
    account yet, or a brand new one created from new_person_name — turning
    it into a real, active Account and removing it from the queue.

    Exactly one of person_slug/new_person_name must be given. Raises
    FileNotFoundError if the request or person_slug doesn't exist, and
    ValueError for a bad role, neither/both person args, or a person who
    already has an account.
    """
    pending = get_pending(stories_dir, username)
    if pending is None:
        raise FileNotFoundError(username)
    if role not in ROLES:
        raise ValueError(f"Invalid role: {role!r}")
    if bool(person_slug) == bool(new_person_name):
        raise ValueError("Provide exactly one of an existing person or a new person's name.")

    people_dir = storage.people_dir(stories_dir)
    if new_person_name:
        person_slug = people.create_person(people_dir, new_person_name)
    elif not (people_dir / person_slug).is_dir():
        raise FileNotFoundError(person_slug)
    elif get_account(people_dir, person_slug) is not None:
        raise ValueError(f"{person_slug} already has an account.")

    account = Account(
        person_slug=person_slug,
        username=pending.username,
        password_hash=pending.password_hash,
        role=role,
        status="active",
        created_at=datetime.now(),
        approved_by=approved_by,
    )
    _write_account(people_dir, account)
    reject_pending(stories_dir, username)
    return account
