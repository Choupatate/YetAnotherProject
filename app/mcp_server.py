"""MCP server exposing Storybook's stories/people to AI tools (FEATURES.md
F32): a read-write "authoring" surface an assistant like Claude can use to
help write and organize a family's journal.

This is a separate entrypoint from the Flask app (see `mcp_server.py` at the
repo root) and is meant to run as a local stdio subprocess, launched
directly by an MCP client (Claude Desktop, Claude Code, ...) on the same
machine the `stories/` folder lives on. It never listens on a network port
and has no login of its own — the trust boundary is the same as running the
app locally in the first place: whoever can launch this process already has
filesystem access to `stories/`. Do not run this anywhere reachable over a
network.

Every write goes through the same `storage.py`/`people.py` functions the web
editor uses underneath (atomic index.md writes, `.versions/` snapshots,
image re-encoding via Pillow, symmetric partner/union syncing) — this module
only adds MCP-shaped argument validation and tool wiring on top; it never
touches a story/person file directly itself.

Config is read from the same `STORYBOOK_STORIES_DIR`/`STORYBOOK_AUTHORS`/
`STORYBOOK_BIRTHDATE`/`STORYBOOK_TITLE` environment variables as
`app/__init__.py`'s `create_app()`, so a single `.env` serves both the web
app and this server. Values are duplicated/re-parsed here rather than
imported from `app/__init__.py` to avoid depending on that module's
internals — the same convention `people.py` already follows for
`_AUTHOR_COLOR_RE` (see its comment) and does not require the Flask app to
ever be constructed.
"""

import base64
import binascii
import io
import os
import random
from datetime import date as date_cls
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from mcp.server.fastmcp import FastMCP

from . import dates, kinship, life_events, people, prompts, storage

mcp = FastMCP(
    "storybook",
    instructions=(
        "Tools for reading and writing a private family journal (Storybook). "
        "Stories are dated entries with a title and markdown body; people are "
        "the family/friends who can be tagged in a story and linked into a "
        "family tree. Call get_journal_context first to see what's already "
        "there (recent stories, today's birthdays/anniversaries, whether it's "
        "been a while since the last entry) before creating new content."
    ),
)


# --- Config -----------------------------------------------------------


def _stories_dir() -> Path:
    return Path(os.environ.get("STORYBOOK_STORIES_DIR", "./stories")).resolve()


def _people_dir() -> Path:
    return storage.people_dir(_stories_dir())


def _configured_author_names() -> set:
    """The set of valid `author` values from STORYBOOK_AUTHORS
    ("Name:#hex,Name:#hex"), tolerantly parsed: a malformed entry is just
    skipped rather than raising, since a bad author name here should not stop
    an otherwise-valid story from being created (unlike app/__init__.py's
    fail-at-startup version of this same parsing)."""
    names = set()
    for entry in (os.environ.get("STORYBOOK_AUTHORS") or "").split(","):
        name, _, _color = entry.strip().partition(":")
        name = name.strip()
        if name:
            names.add(name)
    return names


def _configured_birthdate() -> Optional[date_cls]:
    value = os.environ.get("STORYBOOK_BIRTHDATE")
    if not value:
        return None
    try:
        return date_cls.fromisoformat(value)
    except ValueError:
        return None


def _configured_title() -> str:
    return os.environ.get("STORYBOOK_TITLE") or "Storybook"


# --- Validation (framework-free mirror of routes_api.py/routes_api_people.py) --

_SOURCE_MAX = 20
_SOURCE_NOTE_MAX = 200
_SOURCE_URL_MAX = 500
_UNION_KINDS = ("wedding", "pacs", "union")
_UNION_MAX = 10


def _validate_date(value: str, label: str) -> date_cls:
    try:
        return date_cls.fromisoformat(value)
    except (TypeError, ValueError):
        raise ValueError(f"{label} must be an ISO date (YYYY-MM-DD), got {value!r}.")


def _validate_tags(tags: Optional[list]) -> Optional[list]:
    if tags is None:
        return None
    cleaned = []
    seen = set()
    for item in tags:
        if not isinstance(item, str):
            continue
        item = item.strip()[: storage.MAX_TAG_LENGTH]
        if not item or item in seen:
            continue
        seen.add(item)
        cleaned.append(item)
    if len(cleaned) > storage.MAX_TAGS:
        raise ValueError(f"At most {storage.MAX_TAGS} tags allowed.")
    return cleaned


def _validate_milestone(milestone: Optional[str]) -> Optional[str]:
    if milestone is None:
        return None
    return milestone.strip()[: storage.MAX_MILESTONE_LENGTH]


def _validate_sources(sources: Optional[list]) -> Optional[list]:
    if sources is None:
        return None
    cleaned = []
    for item in sources:
        if not isinstance(item, dict):
            continue
        url = (item.get("url") or "").strip()
        if not url:
            continue
        if urlparse(url).scheme.lower() not in ("http", "https"):
            raise ValueError("Source links must be http:// or https:// URLs.")
        note = (item.get("note") or "").strip()
        cleaned.append({"url": url[:_SOURCE_URL_MAX], "note": note[:_SOURCE_NOTE_MAX]})
    if len(cleaned) > _SOURCE_MAX:
        raise ValueError(f"At most {_SOURCE_MAX} sources allowed.")
    return cleaned


def _validate_story_people(story_people: Optional[list], valid_slugs: set) -> Optional[list]:
    if story_people is None:
        return None
    cleaned = []
    seen = set()
    for slug in story_people:
        if not isinstance(slug, str) or slug in seen:
            continue
        if slug not in valid_slugs:
            raise ValueError(f"Unknown person: {slug}.")
        seen.add(slug)
        cleaned.append(slug)
    return cleaned


def _validate_slug_list(field_name: str, value: Optional[list], valid_slugs: set,
                         self_slug: Optional[str], max_len: Optional[int] = None) -> Optional[list]:
    if value is None:
        return None
    cleaned = []
    seen = set()
    label = {"parents": "parent", "partners": "partner", "friend_of": "friend"}[field_name]
    for slug in value:
        if not isinstance(slug, str) or not slug.strip():
            continue
        slug = slug.strip()
        if slug in seen:
            continue
        seen.add(slug)
        if self_slug is not None and slug == self_slug:
            raise ValueError(f"A person cannot be their own {label}.")
        if slug not in valid_slugs:
            raise ValueError(f"Unknown person: {slug}.")
        cleaned.append(slug)
    if max_len is not None and len(cleaned) > max_len:
        raise ValueError(f"A person can have at most {max_len} parents.")
    return cleaned


def _validate_gender(gender: Optional[str]) -> Optional[str]:
    if gender is None:
        return None
    gender = gender.strip()
    if gender not in ("m", "f", ""):
        raise ValueError("Gender must be 'm', 'f', or empty.")
    return gender


def _validate_unions(unions: Optional[list], valid_partner_slugs: set) -> Optional[list]:
    if unions is None:
        return None
    cleaned = []
    seen_partners = set()
    for item in unions:
        if not isinstance(item, dict):
            continue
        partner = item.get("partner")
        if not isinstance(partner, str) or partner not in valid_partner_slugs:
            raise ValueError(f"Union partner must be one of the person's partners: {partner!r}.")
        if partner in seen_partners:
            continue
        kind = item.get("kind")
        if kind not in _UNION_KINDS:
            raise ValueError(f"Union kind must be one of {_UNION_KINDS}.")
        since = _validate_date(item.get("since"), "Union 'since'")
        until = _validate_date(item["until"], "Union 'until'") if item.get("until") else None
        if until is not None and until < since:
            raise ValueError("A union's 'until' date can't be before its 'since' date.")
        seen_partners.add(partner)
        cleaned.append({"partner": partner, "kind": kind, "since": since, "until": until})
    if len(cleaned) > _UNION_MAX:
        raise ValueError(f"At most {_UNION_MAX} unions allowed.")
    return cleaned


class _Base64Upload:
    """Adapts a decoded image payload to the `.stream` interface
    `storage.save_image_to` expects from a Werkzeug FileStorage."""

    def __init__(self, data: bytes):
        self.stream = io.BytesIO(data)


def _decode_image(image_base64: str) -> "_Base64Upload":
    if image_base64.startswith("data:") and "," in image_base64:
        image_base64 = image_base64.split(",", 1)[1]
    try:
        data = base64.b64decode(image_base64, validate=True)
    except (binascii.Error, ValueError):
        raise ValueError("image_base64 is not valid base64 data.")
    if not data:
        raise ValueError("image_base64 is empty.")
    return _Base64Upload(data)


# --- Symmetric family-data sync (mirrors routes_api_people.py's private --
# --- helpers of the same name, duplicated rather than imported so this ---
# --- module never needs to import a Flask-route file) --------------------


def _sync_partner_symmetry(people_dir: Path, slug: str, old_partners: list, new_partners: Optional[list]):
    if new_partners is None:
        return
    added = set(new_partners) - set(old_partners)
    removed = set(old_partners) - set(new_partners)
    for other_slug in added | removed:
        other = people.get_person(people_dir, other_slug)
        if other is None:
            continue
        other_partners = set(other.partners)
        if other_slug in added:
            other_partners.add(slug)
        else:
            other_partners.discard(slug)
        people.update_person(
            people_dir, other_slug, other.name, relation=other.relation,
            body=other.body or "", partners=sorted(other_partners),
        )


def _sync_union_symmetry(people_dir: Path, slug: str, old_unions: list, new_unions: Optional[list]):
    if new_unions is None:
        return
    old_by_partner = {u["partner"]: u for u in old_unions}
    new_by_partner = {u["partner"]: u for u in new_unions}
    for other_slug in set(old_by_partner) | set(new_by_partner):
        other = people.get_person(people_dir, other_slug)
        if other is None:
            continue
        other_unions = [u for u in other.unions if u["partner"] != slug]
        if other_slug in new_by_partner:
            entry = new_by_partner[other_slug]
            other_unions.append({
                "partner": slug, "kind": entry["kind"],
                "since": entry["since"], "until": entry["until"],
            })
        people.update_person(
            people_dir, other_slug, other.name, relation=other.relation,
            body=other.body or "", unions=other_unions,
        )


# --- Serialization helpers ----------------------------------------------


def _story_summary(s: storage.Story) -> dict:
    return {
        "id": s.id, "title": s.title, "date": s.date.isoformat(), "kind": s.kind,
        "draft": s.draft, "sealed": storage.is_sealed(s), "archived": s.archived,
        "milestone": s.milestone, "tags": s.tags, "people": s.people, "author": s.author,
    }


def _story_detail(s: storage.Story) -> dict:
    return {**_story_summary(s), "body": s.body or "", "cover": s.cover, "sources": s.sources}


def _person_summary(p: people.Person) -> dict:
    return {
        "slug": p.slug, "name": p.name, "relation": p.relation, "gender": p.gender,
        "born": p.born.isoformat() if p.born else None,
        "died": p.died.isoformat() if p.died else None,
    }


def _person_detail(p: people.Person) -> dict:
    return {
        **_person_summary(p), "body": p.body or "", "parents": p.parents,
        "partners": p.partners, "friend_of": p.friend_of, "sources": p.sources,
        "unions": [
            {
                "partner": u["partner"], "kind": u["kind"], "since": u["since"].isoformat(),
                "until": u["until"].isoformat() if u["until"] else None,
            }
            for u in p.unions
        ],
    }


# --- Read tools -----------------------------------------------------------


@mcp.tool()
def list_stories(tag: Optional[str] = None, person_slug: Optional[str] = None,
                  milestones_only: bool = False, include_drafts: bool = False,
                  since: Optional[str] = None, until: Optional[str] = None,
                  limit: int = 50) -> list[dict]:
    """List stories (newest first), without their body text. Filter by `tag`
    (exact match), `person_slug` (a person tagged in the story), or set
    `milestones_only=True` for just the "firsts" register. Sealed
    (unlock-dated) and archived stories are never included. `since`/`until`
    are inclusive ISO dates (YYYY-MM-DD) bounding the story's own date."""
    stories = storage.list_stories(_stories_dir())
    since_date = _validate_date(since, "since") if since else None
    until_date = _validate_date(until, "until") if until else None
    result = []
    for s in stories:
        if s.archived or storage.is_sealed(s):
            continue
        if s.draft and not include_drafts:
            continue
        if tag and tag not in s.tags:
            continue
        if person_slug and person_slug not in s.people:
            continue
        if milestones_only and not s.milestone:
            continue
        if since_date and s.date < since_date:
            continue
        if until_date and s.date > until_date:
            continue
        result.append(s)
    result.sort(key=lambda s: s.date, reverse=True)
    return [_story_summary(s) for s in result[:limit]]


@mcp.tool()
def get_story(story_id: str) -> dict:
    """Full detail for one story, including its markdown body."""
    story = storage.get_story(_stories_dir(), story_id)
    if story is None:
        raise ValueError(f"No story found with id {story_id!r}.")
    return _story_detail(story)


@mcp.tool()
def list_people() -> list[dict]:
    """List everyone in the family tree/cast (no body text)."""
    return [_person_summary(p) for p in people.list_people(_people_dir())]


@mcp.tool()
def get_person(slug: str) -> dict:
    """Full detail for one person, including their bio body and family links."""
    person = people.get_person(_people_dir(), slug)
    if person is None:
        raise ValueError(f"No person found with slug {slug!r}.")
    return _person_detail(person)


@mcp.tool()
def get_journal_context() -> dict:
    """A snapshot of the journal's current state, useful to check before
    writing anything: how many stories exist, the most recent one, whether
    it's been a quiet spell since the last entry, who has a birthday or
    union anniversary today, and a random writing-prompt suggestion."""
    stories_dir = _stories_dir()
    all_stories = storage.list_stories(stories_dir)
    all_people = people.list_people(_people_dir())
    readable = storage.readable_stories(all_stories)
    today = date_cls.today()

    quiet_months = storage.months_since_last_story(all_stories, today)
    most_recent = max(all_stories, key=lambda s: s.date) if all_stories else None

    birthdate = _configured_birthdate()
    prompt_list = prompts.load_prompts(stories_dir)

    return {
        "title": _configured_title(),
        "total_stories": len(all_stories),
        "readable_stories": len(readable),
        "draft_count": sum(1 for s in all_stories if s.draft and not s.archived),
        "most_recent_story": _story_summary(most_recent) if most_recent else None,
        "months_since_last_story": quiet_months,
        "quiet_spell": quiet_months is not None and quiet_months >= storage.QUIET_SPELL_MONTHS,
        "firsts_count": len(storage.stories_with_milestones(all_stories)),
        "todays_birthdays": [
            {"slug": p.slug, "name": p.name, "turning": today.year - p.born.year}
            for p in life_events.birthdays_today(all_people, today)
        ],
        "todays_union_anniversaries": [
            {
                "person": m["person"].name, "partner": m["partner"].name,
                "kind": m["kind"], "years": today.year - m["since"].year,
            }
            for m in life_events.union_anniversaries_today(all_people, today)
        ],
        "child_age_today": dates.age_label(birthdate, today) if birthdate else None,
        "writing_prompt": random.choice(prompt_list) if prompt_list else None,
    }


# --- Write tools: stories --------------------------------------------------


@mcp.tool()
def create_story(title: str, date: str, body: str = "", tags: Optional[list[str]] = None,
                  people_slugs: Optional[list[str]] = None, sources: Optional[list[dict]] = None,
                  milestone: Optional[str] = None, author: Optional[str] = None,
                  draft: bool = False, kind: str = "story") -> dict:
    """Create a new story. `date` is an ISO date (YYYY-MM-DD) — the day the
    memory happened, not today. `kind` is "story" (a full dated entry) or
    "instant" (a lighter, feed-style capture); it can't be changed later.
    `people_slugs` are person slugs from list_people to tag in the story.
    Returns {"id": ..., "title": ...} — keep the id to call update_story or
    add_story_photo on it later."""
    if kind not in ("story", "instant"):
        raise ValueError('kind must be "story" or "instant".')
    story_date = _validate_date(date, "date")
    if not title.strip() and kind == "story":
        raise ValueError("Title is required for a story (instants may omit it).")
    if author is not None and author:
        configured = _configured_author_names()
        if configured and author not in configured:
            raise ValueError(f"Unknown author {author!r}. Configured authors: {sorted(configured)}")

    valid_slugs = {p.slug for p in people.list_people(_people_dir())}
    story_id = storage.create_story(
        _stories_dir(), title.strip() or "Instant", story_date, body,
        author=author or None, draft=draft, kind=kind,
        people=_validate_story_people(people_slugs, valid_slugs) or [],
        tags=_validate_tags(tags) or [], sources=_validate_sources(sources) or [],
        milestone=_validate_milestone(milestone) or None,
    )
    return {"id": story_id, "title": title}


@mcp.tool()
def update_story(story_id: str, title: str, date: str, body: str,
                  tags: Optional[list[str]] = None, people_slugs: Optional[list[str]] = None,
                  sources: Optional[list[dict]] = None, milestone: Optional[str] = None,
                  author: Optional[str] = None, cover: Optional[str] = None,
                  draft: Optional[bool] = None, archived: Optional[bool] = None) -> dict:
    """Update an existing story in place (its id never changes). `title`,
    `date`, and `body` are always required and always overwrite the current
    value. Every other field is left unchanged when omitted (None); pass an
    empty list/string to clear one. `draft`/`archived` default to leaving the
    current value alone rather than the web editor's "always resend" rule,
    since a partial AI-driven update should never silently un-draft or
    un-archive a story. The previous content is snapshotted first, so this
    is always safely reversible via the story's version history."""
    existing = storage.get_story(_stories_dir(), story_id)
    if existing is None:
        raise ValueError(f"No story found with id {story_id!r}.")
    story_date = _validate_date(date, "date")
    if not title.strip():
        raise ValueError("Title is required.")
    if author is not None and author:
        configured = _configured_author_names()
        if configured and author not in configured:
            raise ValueError(f"Unknown author {author!r}. Configured authors: {sorted(configured)}")

    valid_slugs = {p.slug for p in people.list_people(_people_dir())}
    cover_value = None
    if cover is not None:
        if cover and not storage.is_valid_filename(cover):
            raise ValueError("Invalid cover filename.")
        if cover and not (_stories_dir() / story_id / cover).is_file():
            raise ValueError("Cover image not found in this story's folder.")
        cover_value = cover

    storage.save_story(
        _stories_dir(), story_id, title.strip(), story_date, body,
        cover=cover_value, author=author,
        draft=existing.draft if draft is None else draft,
        archived=existing.archived if archived is None else archived,
        people=_validate_story_people(people_slugs, valid_slugs),
        tags=_validate_tags(tags), sources=_validate_sources(sources),
        milestone=_validate_milestone(milestone),
    )
    return {"id": story_id}


@mcp.tool()
def add_story_photo(story_id: str, image_base64: str) -> dict:
    """Upload a photo (base64-encoded image bytes) into a story's folder.
    It is re-encoded and thumbnailed like any web upload. Returns
    {"filename": "photo-NNN.jpg"} — reference it in the story body as
    markdown (`![caption](photo-NNN.jpg)`) via update_story, or pass it as
    update_story's `cover` to make it the story's cover photo."""
    upload = _decode_image(image_base64)
    try:
        filename = storage.save_image(_stories_dir(), story_id, upload)
    except FileNotFoundError:
        raise ValueError(f"No story found with id {story_id!r}.")
    except Exception:
        raise ValueError("Could not process image.")
    return {"filename": filename}


# --- Write tools: people ----------------------------------------------------


@mcp.tool()
def create_person(name: str, relation: Optional[str] = None, body: str = "",
                   parents: Optional[list[str]] = None, partners: Optional[list[str]] = None,
                   friend_of: Optional[list[str]] = None, gender: Optional[str] = None,
                   sources: Optional[list[dict]] = None, born: Optional[str] = None,
                   died: Optional[str] = None, unions: Optional[list[dict]] = None) -> dict:
    """Add a new person to the family tree/cast. `parents`/`partners`/
    `friend_of` are other people's slugs from list_people (at most 2
    parents). `gender` is "m", "f", or omitted. `unions` records a wedding/
    PACS/plain union with one of `partners`: each entry is
    {"partner", "kind" ("wedding"/"pacs"/"union"), "since" (ISO date),
    "until" (optional ISO date)}. Partner/union links are synced onto the
    other person's record automatically. Returns {"id": slug}."""
    name = name.strip()
    if not name:
        raise ValueError("Name is required.")
    people_dir = _people_dir()
    all_people = people.list_people(people_dir)
    valid_slugs = {p.slug for p in all_people}

    parents_v = _validate_slug_list("parents", parents, valid_slugs, self_slug=None, max_len=2)
    partners_v = _validate_slug_list("partners", partners, valid_slugs, self_slug=None)
    friend_of_v = _validate_slug_list("friend_of", friend_of, valid_slugs, self_slug=None)
    gender_v = _validate_gender(gender)
    sources_v = _validate_sources(sources)
    born_v = _validate_date(born, "born") if born else None
    died_v = _validate_date(died, "died") if died else None
    if born_v and died_v and died_v < born_v:
        raise ValueError("Death date can't be before birth date.")
    unions_v = _validate_unions(unions, set(partners_v or []))

    slug = people.create_person(
        people_dir, name, relation=(relation or "").strip() or None, body=body,
        parents=parents_v, partners=partners_v, friend_of=friend_of_v, gender=gender_v,
        sources=sources_v, born=born_v, died=died_v, unions=unions_v,
    )
    _sync_partner_symmetry(people_dir, slug, [], partners_v or [])
    _sync_union_symmetry(people_dir, slug, [], unions_v or [])
    return {"id": slug, "name": name}


@mcp.tool()
def update_person(slug: str, name: str, relation: Optional[str] = None, body: str = "",
                   parents: Optional[list[str]] = None, partners: Optional[list[str]] = None,
                   friend_of: Optional[list[str]] = None, gender: Optional[str] = None,
                   sources: Optional[list[dict]] = None, born: Optional[str] = None,
                   died: Optional[str] = None, unions: Optional[list[dict]] = None) -> dict:
    """Update an existing person in place (their slug never changes). `name`
    and `body` are always required and always overwrite the current value.
    Every other field is left unchanged when omitted (None); pass an empty
    list/string to clear one, except born/died where an explicit empty
    string clears a previously-set date. Removing a partner also removes
    any union recorded with them. Partner/union links are re-synced onto
    the other person's record automatically."""
    people_dir = _people_dir()
    existing = people.get_person(people_dir, slug)
    if existing is None:
        raise ValueError(f"No person found with slug {slug!r}.")
    name = name.strip()
    if not name:
        raise ValueError("Name is required.")

    all_people = people.list_people(people_dir)
    valid_slugs = {p.slug for p in all_people}
    parents_v = _validate_slug_list("parents", parents, valid_slugs, self_slug=slug, max_len=2)
    partners_v = _validate_slug_list("partners", partners, valid_slugs, self_slug=slug)
    friend_of_v = _validate_slug_list("friend_of", friend_of, valid_slugs, self_slug=slug)
    gender_v = _validate_gender(gender)
    sources_v = _validate_sources(sources)

    if parents_v:
        graph = kinship.build_graph(all_people)
        for parent_slug in parents_v:
            if kinship.would_create_cycle(graph, slug, parent_slug):
                raise ValueError("That would create a family-tree cycle.")

    # `born`/`died` follow people.update_person's own None/""/date convention
    # (None=leave unchanged, ""=clear, else set) — `effective_*` is only for
    # the birth-before-death check below, since that needs the value *after*
    # this update, whichever of the three cases applies.
    born_arg = _validate_date(born, "born") if born else born
    died_arg = _validate_date(died, "died") if died else died
    effective_born = existing.born if born is None else (born_arg or None)
    effective_died = existing.died if died is None else (died_arg or None)
    if effective_born and effective_died and effective_died < effective_born:
        raise ValueError("Death date can't be before birth date.")

    effective_partners = set(partners_v if partners_v is not None else existing.partners)
    unions_v = _validate_unions(unions, effective_partners)
    resolved_unions = unions_v if unions_v is not None else existing.unions
    resolved_unions = [u for u in resolved_unions if u["partner"] in effective_partners]

    people.update_person(
        people_dir, slug, name, relation=(relation or "").strip() or None, body=body,
        parents=parents_v, partners=partners_v, friend_of=friend_of_v, gender=gender_v,
        sources=sources_v, born=born_arg, died=died_arg, unions=resolved_unions,
    )
    _sync_partner_symmetry(people_dir, slug, existing.partners, partners_v)
    _sync_union_symmetry(people_dir, slug, existing.unions, resolved_unions)
    return {"id": slug}


@mcp.tool()
def set_person_photo(slug: str, image_base64: str) -> dict:
    """Upload a photo (base64-encoded image bytes) and set it as this
    person's profile photo, resetting their photo tone to the default. Same
    re-encoding/thumbnailing as any web upload."""
    people_dir = _people_dir()
    existing = people.get_person(people_dir, slug)
    if existing is None:
        raise ValueError(f"No person found with slug {slug!r}.")
    upload = _decode_image(image_base64)
    try:
        filename = storage.save_image_to(people_dir / slug, upload)
    except Exception:
        raise ValueError("Could not process image.")
    people.update_person(
        people_dir, slug, existing.name, relation=existing.relation,
        body=existing.body or "", photo=filename, photo_sepia=people.DEFAULT_PHOTO_SEPIA,
    )
    return {"filename": filename, "photo_sepia": people.DEFAULT_PHOTO_SEPIA}


if __name__ == "__main__":
    mcp.run(transport="stdio")
