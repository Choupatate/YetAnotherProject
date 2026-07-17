"""Tests for FEATURES.md F18 Layer 2: the kinship engine (app/kinship.py).

A single fixture family of 16 people, anchored on "milo" (the child), used
to exhaustively exercise the label table — including a great-grandmother,
a great-uncle, an uncle by marriage, a half-sibling, a nephew, a cousin,
a friend, and a fully unlinked person.
"""

import pytest

from app import kinship
from app.people import Person


def _p(slug, name, parents=None, partners=None, friend_of=None, gender=None):
    return Person(
        slug=slug,
        name=name,
        created=None,
        updated=None,
        parents=parents or [],
        partners=partners or [],
        friend_of=friend_of or [],
        gender=gender,
    )


@pytest.fixture
def family():
    people = [
        _p("adele", "Great-Grandma Adele", gender="f"),
        _p("georges", "Papi Georges", parents=["adele"], partners=["lise"], gender="m"),
        _p("grandoncle-henri", "Great-Uncle Henri", parents=["adele"], gender="m"),
        _p("lise", "Mamie Lise", partners=["georges"], gender="f"),
        _p("papa", "Papa", parents=["georges", "lise"], gender="m"),
        _p("tante-claire", "Tante Claire", parents=["georges", "lise"], gender="f"),
        _p("oncle-paul", "Oncle Paul", parents=["georges", "lise"], partners=["tante-rose"], gender="m"),
        _p("tante-rose", "Tante Rose", partners=["oncle-paul"], gender="f"),
        _p("cousin-lea", "Cousin Lea", parents=["oncle-paul", "tante-rose"], gender="f"),
        _p("maman", "Maman", gender="f"),
        _p("milo", "Milo", parents=["papa", "maman"], gender="m"),
        _p("soeur-emma", "Soeur Emma", parents=["papa", "maman"], gender="f"),
        _p("neveu-theo", "Neveu Theo", parents=["soeur-emma"], gender="m"),
        _p("autre-maman", "Autre Maman", gender="f"),
        _p("demi-frere", "Demi-Frere", parents=["papa"], gender="m"),
        _p("ami-jean", "Ami Jean", friend_of=["papa"], gender="m"),
        _p("solo-gaston", "Solo Gaston"),
    ]
    return kinship.build_graph(people)


# --- build_graph / helpers ---------------------------------------------------


def test_children_of(family):
    assert set(kinship.children_of(family, "papa")) == {"milo", "soeur-emma", "demi-frere"}


def test_children_of_none(family):
    assert kinship.children_of(family, "solo-gaston") == []


def test_siblings_of_shares_both_parents(family):
    assert "soeur-emma" in kinship.siblings_of(family, "milo")


def test_siblings_of_shares_one_parent_half_sibling(family):
    assert "demi-frere" in kinship.siblings_of(family, "milo")


def test_siblings_of_no_parents_returns_empty(family):
    assert kinship.siblings_of(family, "maman") == []


def test_partners_of_symmetric_from_either_side(family):
    assert kinship.partners_of(family, "georges") == ["lise"]
    assert kinship.partners_of(family, "lise") == ["georges"]


def test_partners_of_reads_union_of_single_sided_link():
    # Only one side lists the partner on disk — reads still take the union.
    people = [
        _p("a", "A", partners=["b"]),
        _p("b", "B"),
    ]
    graph = kinship.build_graph(people)
    assert kinship.partners_of(graph, "b") == ["a"]


def test_build_graph_ignores_dangling_slugs():
    people = [_p("a", "A", parents=["ghost"], partners=["ghost"], friend_of=["ghost"])]
    graph = kinship.build_graph(people)
    assert graph.parents["a"] == []
    assert graph.partners["a"] == set()
    assert graph.friend_of["a"] == []


# --- would_create_cycle ------------------------------------------------------


def test_cycle_self_parent_rejected(family):
    assert kinship.would_create_cycle(family, "milo", "milo") is True


def test_cycle_descendant_as_parent_rejected(family):
    # adele is milo's great-grandmother; making milo a parent of adele
    # would put adele both above and below herself.
    assert kinship.would_create_cycle(family, "adele", "milo") is True


def test_cycle_unrelated_parent_allowed(family):
    assert kinship.would_create_cycle(family, "solo-gaston", "papa") is False


def test_cycle_direct_parent_reassignment_allowed(family):
    assert kinship.would_create_cycle(family, "milo", "georges") is False


# --- kinship_label: the label table -----------------------------------------


LABELS = [
    ("papa", "your father"),
    ("maman", "your mother"),
    ("georges", "your grandfather"),
    ("lise", "your grandmother"),
    ("adele", "your great-grandmother"),
    ("grandoncle-henri", "your great-uncle"),
    ("soeur-emma", "your sister"),
    ("demi-frere", "your brother"),
    ("oncle-paul", "your uncle"),
    ("tante-claire", "your aunt"),
    ("tante-rose", "your uncle's wife"),
    ("cousin-lea", "your cousin"),
    ("neveu-theo", "your nephew"),
    ("ami-jean", None),
    ("solo-gaston", None),
    ("autre-maman", None),
]


@pytest.mark.parametrize("slug,expected", LABELS)
def test_kinship_label_table(family, slug, expected):
    assert kinship.kinship_label(family, "milo", slug) == expected


def test_kinship_label_self_is_none(family):
    assert kinship.kinship_label(family, "milo", "milo") is None


def test_kinship_label_no_anchor_is_none(family):
    assert kinship.kinship_label(family, None, "papa") is None


def test_kinship_label_unknown_anchor_is_none(family):
    assert kinship.kinship_label(family, "nobody", "papa") is None


def test_kinship_label_unknown_person_is_none(family):
    assert kinship.kinship_label(family, "milo", "nobody") is None


def test_kinship_label_reverse_direction_from_grandparent(family):
    # Labels are always about the person relative to the anchor, so
    # re-anchoring flips the direction: milo is georges's grandson.
    assert kinship.kinship_label(family, "georges", "milo") == "your grandson"


def test_kinship_label_great_grandchild_reverse(family):
    assert kinship.kinship_label(family, "adele", "milo") == "your great-grandson"


def test_kinship_label_friend_only_link_has_no_kinship(family):
    assert kinship.kinship_label(family, "milo", "ami-jean") is None


# --- generation_offset: the printable outline's bucketing --------------------


OFFSETS = [
    ("papa", 1),
    ("maman", 1),
    ("georges", 2),
    ("lise", 2),
    ("adele", 3),
    ("grandoncle-henri", 2),  # great-uncle: same generation bucket as grandparents
    ("soeur-emma", 0),
    ("demi-frere", 0),
    ("oncle-paul", 1),  # uncle: same generation bucket as parents
    ("tante-claire", 1),
    ("tante-rose", 1),  # uncle's wife, via the one-hop partner fallback
    ("cousin-lea", 0),
    ("neveu-theo", -1),
    ("ami-jean", None),
    ("solo-gaston", None),
]


@pytest.mark.parametrize("slug,expected", OFFSETS)
def test_generation_offset_table(family, slug, expected):
    assert kinship.generation_offset(family, "milo", slug) == expected


def test_generation_offset_self_is_zero(family):
    assert kinship.generation_offset(family, "milo", "milo") == 0


def test_generation_offset_no_anchor_is_none(family):
    assert kinship.generation_offset(family, None, "papa") is None


def test_generation_offset_unknown_anchor_is_none(family):
    assert kinship.generation_offset(family, "nobody", "papa") is None


def test_generation_offset_none_when_no_blood_path_even_via_partner():
    # A couple linked only to each other, with no blood connection to the
    # anchor at all — the one-hop partner fallback only reaches a partner
    # who is THEMSELVES blood-related to the anchor, not an equally
    # disconnected one.
    people = [
        _p("milo", "Milo"),
        _p("a", "A", partners=["b"]),
        _p("b", "B", partners=["a"]),
    ]
    graph = kinship.build_graph(people)
    assert kinship.generation_offset(graph, "milo", "a") is None


# --- generation_group_label ---------------------------------------------------


def test_generation_group_label_table():
    assert kinship.generation_group_label(0, "Milo") == "Milo’s generation"
    assert kinship.generation_group_label(1, "Milo") == "Parents’ generation"
    assert kinship.generation_group_label(2, "Milo") == "Grandparents’ generation"
    assert kinship.generation_group_label(3, "Milo") == "Great-grandparents’ generation"
    assert kinship.generation_group_label(4, "Milo") == "Great-great-grandparents’ generation"
    assert kinship.generation_group_label(-1, "Milo") == "Children’s generation"
    assert kinship.generation_group_label(-2, "Milo") == "Grandchildren’s generation"
    assert kinship.generation_group_label(-3, "Milo") == "Great-grandchildren’s generation"
