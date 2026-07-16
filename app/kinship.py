"""The kinship engine (FEATURES.md F18, Layer 2): pure functions over a
Graph built from people.py's Person records. Stdlib only. Computes nothing
that isn't derivable from `parents` and `partners` edges — kinship words
("uncle", "cousin") are never stored, only ever derived here.
"""

from collections import deque
from dataclasses import dataclass
from typing import Optional


@dataclass
class Graph:
    nodes: dict  # slug -> Person
    parents: dict  # slug -> list[str], dangling slugs already filtered out
    partners: dict  # slug -> set[str], union of both directions
    friend_of: dict  # slug -> list[str], dangling slugs already filtered out


def build_graph(people) -> Graph:
    nodes = {p.slug: p for p in people}
    parents = {}
    friend_of = {}
    partners = {slug: set() for slug in nodes}
    for p in people:
        parents[p.slug] = [s for s in (p.parents or []) if s in nodes and s != p.slug]
        friend_of[p.slug] = [s for s in (p.friend_of or []) if s in nodes]
    for p in people:
        for partner_slug in (p.partners or []):
            if partner_slug in nodes and partner_slug != p.slug:
                partners[p.slug].add(partner_slug)
                partners[partner_slug].add(p.slug)
    return Graph(nodes=nodes, parents=parents, partners=partners, friend_of=friend_of)


def children_of(graph: Graph, slug: str) -> list:
    """Reverse lookup of `parents`, in the same order people were passed to
    build_graph (their creation order)."""
    return [s for s in graph.nodes if slug in graph.parents.get(s, [])]


def siblings_of(graph: Graph, slug: str) -> list:
    """People sharing at least one parent with `slug`, excluding `slug`."""
    my_parents = set(graph.parents.get(slug, []))
    if not my_parents:
        return []
    return [
        s for s in graph.nodes
        if s != slug and set(graph.parents.get(s, [])) & my_parents
    ]


def partners_of(graph: Graph, slug: str) -> list:
    linked = graph.partners.get(slug, set())
    return [s for s in graph.nodes if s in linked]


def would_create_cycle(graph: Graph, child: str, new_parent: str) -> bool:
    """True if setting `new_parent` as a parent of `child` would make
    `child` its own ancestor — i.e. `child` is already an ancestor of
    `new_parent` (or they are the same person)."""
    if child == new_parent:
        return True
    seen = set()
    stack = [new_parent]
    while stack:
        current = stack.pop()
        if current == child:
            return True
        if current in seen:
            continue
        seen.add(current)
        stack.extend(graph.parents.get(current, []))
    return False


def _ancestor_depths(graph: Graph, slug: str) -> dict:
    """slug -> {ancestor_slug: steps up}, including {slug: 0}. BFS over
    parent edges only (partners never contribute to blood distance)."""
    depths = {slug: 0}
    queue = deque([slug])
    while queue:
        current = queue.popleft()
        for parent in graph.parents.get(current, []):
            if parent not in depths:
                depths[parent] = depths[current] + 1
                queue.append(parent)
    return depths


def _gender_word(graph: Graph, slug: str, m_word: str, f_word: str, neutral_word: str) -> str:
    person = graph.nodes.get(slug)
    gender = getattr(person, "gender", None) if person else None
    if gender == "m":
        return m_word
    if gender == "f":
        return f_word
    return neutral_word


def _label_for_updown(graph: Graph, person_slug: str, up: int, down: int) -> Optional[str]:
    if up == 0 and down == 0:
        return None
    if down == 0:
        if up == 1:
            return _gender_word(graph, person_slug, "your father", "your mother", "your parent")
        base = _gender_word(graph, person_slug, "grandfather", "grandmother", "grandparent")
        return f"your {'great-' * (up - 2)}{base}"
    if up == 0:
        if down == 1:
            return _gender_word(graph, person_slug, "your son", "your daughter", "your child")
        base = _gender_word(graph, person_slug, "grandson", "granddaughter", "grandchild")
        return f"your {'great-' * (down - 2)}{base}"
    if up == 1 and down == 1:
        return _gender_word(graph, person_slug, "your brother", "your sister", "your sibling")
    if down == 1 and up >= 2:
        base = _gender_word(graph, person_slug, "uncle", "aunt", "aunt or uncle")
        return f"your {'great-' * (up - 2)}{base}"
    if up == 1 and down >= 2:
        base = _gender_word(graph, person_slug, "nephew", "niece", "niece or nephew")
        return f"your {'great-' * (down - 2)}{base}"
    return "your cousin"


def _blood_updown(graph: Graph, anchor_slug: str, person_slug: str) -> Optional[tuple]:
    """(steps up from anchor, steps down to person) via their nearest
    shared blood ancestor — or None if anchor/person don't share one.
    Deliberately per-pair: two ancestors "at the same depth" on paper can
    have very different recorded depths of their OWN ancestry (one side
    researched further back than the other), so this must be measured
    from each person's own distance to the shared ancestor, never from a
    global "depth from the deepest recorded root" — that would misplace
    whichever ancestor's own parents happen to be unrecorded."""
    if anchor_slug == person_slug:
        return None
    if anchor_slug not in graph.nodes or person_slug not in graph.nodes:
        return None
    anchor_depths = _ancestor_depths(graph, anchor_slug)
    person_depths = _ancestor_depths(graph, person_slug)
    common = set(anchor_depths) & set(person_depths)
    if not common:
        return None
    best = min(common, key=lambda a: (anchor_depths[a] + person_depths[a], a))
    return anchor_depths[best], person_depths[best]


def _blood_kinship(graph: Graph, anchor_slug: str, person_slug: str) -> Optional[str]:
    updown = _blood_updown(graph, anchor_slug, person_slug)
    if updown is None:
        return None
    return _label_for_updown(graph, person_slug, updown[0], updown[1])


def kinship_label(graph: Graph, anchor_slug: Optional[str], person_slug: str) -> Optional[str]:
    """The label for `person_slug` relative to `anchor_slug` — always about
    the person, from the anchor's point of view ("your uncle"), never the
    reverse. None when unset, unreachable, or self."""
    if not graph or not anchor_slug or anchor_slug not in graph.nodes:
        return None
    if person_slug not in graph.nodes or anchor_slug == person_slug:
        return None

    label = _blood_kinship(graph, anchor_slug, person_slug)
    if label is not None:
        return label

    # One hop: partner of a labeled blood relative, e.g. "your uncle's wife".
    for partner_slug in sorted(graph.partners.get(person_slug, ())):
        relative_label = _blood_kinship(graph, anchor_slug, partner_slug)
        if relative_label:
            word = _gender_word(graph, person_slug, "husband", "wife", "partner")
            return f"{relative_label}'s {word}"
    return None


def generation_offset(graph: Graph, anchor_slug: Optional[str], person_slug: str) -> Optional[int]:
    """How many generations `person_slug` sits from `anchor_slug`: positive
    toward ancestors, negative toward descendants, 0 for the anchor's own
    generation (siblings, cousins, the anchor themself). Used to group the
    printable family outline by generation rather than exact relation —
    "Parents' generation" is meant to include aunts/uncles alongside
    parents, which share the same net distance. None when unset or
    unreachable by blood or one hop of partnership (mirrors
    `kinship_label`'s "your uncle's wife" fallback)."""
    if not graph or not anchor_slug or anchor_slug not in graph.nodes:
        return None
    if person_slug not in graph.nodes:
        return None
    if anchor_slug == person_slug:
        return 0

    updown = _blood_updown(graph, anchor_slug, person_slug)
    if updown is not None:
        return updown[0] - updown[1]

    for partner_slug in sorted(graph.partners.get(person_slug, ())):
        partner_updown = _blood_updown(graph, anchor_slug, partner_slug)
        if partner_updown is not None:
            return partner_updown[0] - partner_updown[1]
    return None


def generation_group_label(offset: int, anchor_name: str) -> str:
    """A heading for a bucket of people at `offset` generations from the
    anchor, e.g. "Grandparents' generation" or "Milo's generation"."""
    if offset == 0:
        return f"{anchor_name}’s generation"
    great = "great-" * (abs(offset) - 2)
    if offset > 0:
        word = "parents" if offset == 1 else f"{great}grandparents"
        possessive = f"{word}’"
    else:
        word = "children" if offset == -1 else f"{great}grandchildren"
        possessive = f"{word}’s"
    return f"{possessive[0].upper()}{possessive[1:]} generation"
