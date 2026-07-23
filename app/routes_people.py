"""People/genealogy page routes: the cast-of-the-book pages (FEATURES.md
F14) and the family tree (F18). Registers onto the same `pages` blueprint
`routes_pages.py` defines — see that module's docstring/bottom-of-file
import for why these live in a separate file without a separate blueprint.
"""

from flask import abort, current_app, render_template

from . import kinship, people, storage
from .auth import login_required
from .rendering import render_markdown
from .routes_pages import (
    DEFAULT_AUTHOR_COLOR,
    _other_people_refs,
    _people_dir,
    _person_ref,
    _serve_media,
    bp,
)


def _get_person_or_404(people_dir, slug):
    p = people.get_person(people_dir, slug)
    if p is None:
        abort(404)
    return p


def _has_family_links(graph):
    """True when at least one person has a parent or partner — the shared
    condition for showing the "Family tree" link on /people and showing the
    chart (vs. a gentle empty state) on /tree (FEATURES.md F18)."""
    return any(graph.parents.get(slug) or graph.partners.get(slug) for slug in graph.nodes)


@bp.route("/people")
@login_required
def people_page():
    all_people = people.list_people(_people_dir())
    graph = kinship.build_graph(all_people)
    return render_template(
        "people.html", people=all_people, show_tree_link=_has_family_links(graph)
    )


@bp.route("/people/<slug>")
@login_required
def person_page(slug):
    p = _get_person_or_404(_people_dir(), slug)
    body_html = render_markdown(p.body, f"/people/{slug}/media")

    all_people = people.list_people(_people_dir())
    people_by_slug = {person.slug: person for person in all_people}
    graph = kinship.build_graph(all_people)
    anchor = kinship.resolve_anchor(current_app.config.get("CHILD_SLUG"), graph)

    kinship_line = None
    friend_of_line = None
    if not p.relation:
        if anchor:
            kinship_line = kinship.kinship_label(graph, anchor, slug)
        if kinship_line is None and p.friend_of:
            friend_of_line = _person_ref(people_by_slug, p.friend_of[0])

    family = {
        "parents": [_person_ref(people_by_slug, s) for s in graph.parents.get(slug, [])],
        "partners": [_person_ref(people_by_slug, s) for s in kinship.partners_of(graph, slug)],
        "children": [_person_ref(people_by_slug, s) for s in kinship.children_of(graph, slug)],
        "siblings": [_person_ref(people_by_slug, s) for s in kinship.siblings_of(graph, slug)],
    }
    family = {key: [ref for ref in refs if ref] for key, refs in family.items()}

    stories_dir = current_app.config["STORIES_DIR"]
    appears_in = storage.readable_stories(storage.stories_featuring(stories_dir, slug))

    return render_template(
        "person.html", person=p, body_html=body_html,
        kinship_line=kinship_line, friend_of_line=friend_of_line, family=family,
        appears_in=appears_in,
    )


@bp.route("/people/<slug>/media/<filename>")
@login_required
def person_media(slug, filename):
    return _serve_media(_people_dir(), slug, filename)


@bp.route("/tree")
@login_required
def tree_page():
    all_people = people.list_people(_people_dir())
    people_by_slug = {p.slug: p for p in all_people}
    graph = kinship.build_graph(all_people)

    has_family_links = _has_family_links(graph)
    anchor = kinship.resolve_anchor(current_app.config.get("CHILD_SLUG"), graph)

    others = []
    generations = []
    if has_family_links:
        # Buckets the printable outline groups by: real generation offsets
        # when an anchor is set, one fixed key otherwise (kinship labels
        # — and so per-person generation — don't exist without an
        # anchor; everyone just lands in a single "Family" bucket).
        buckets = {}
        for p in all_people:
            if kinship.is_in_family(graph, p.slug):
                ref = _person_ref(people_by_slug, p.slug)
                if ref is None:
                    continue
                key = None
                if anchor:
                    ref["kinship"] = kinship.kinship_label(graph, anchor, p.slug)
                    key = kinship.generation_offset(graph, anchor, p.slug)
                buckets.setdefault(key, []).append(ref)
                continue
            friend_refs = [_person_ref(people_by_slug, s) for s in graph.friend_of.get(p.slug, [])]
            others.append({
                "slug": p.slug,
                "name": p.name,
                "friend_of": [ref for ref in friend_refs if ref],
            })

        if anchor:
            anchor_name = people_by_slug[anchor].name
            for offset in sorted((k for k in buckets if k is not None), reverse=True):
                generations.append({
                    "heading": kinship.generation_group_label(offset, anchor_name),
                    "people": buckets[offset],
                })
            if None in buckets:
                generations.append({"heading": "Other family", "people": buckets[None]})
        elif buckets:
            generations.append({"heading": "Family", "people": buckets[None]})

    return render_template(
        "tree.html", has_family_links=has_family_links, others=others, generations=generations,
    )


@bp.route("/new-person")
@login_required
def new_person():
    return render_template(
        "person_editor.html", person=None, other_people=_other_people_refs(),
        default_author_color=DEFAULT_AUTHOR_COLOR,
    )


@bp.route("/edit-person/<slug>")
@login_required
def edit_person(slug):
    p = _get_person_or_404(_people_dir(), slug)
    return render_template(
        "person_editor.html", person=p, other_people=_other_people_refs(exclude_slug=slug),
        default_author_color=DEFAULT_AUTHOR_COLOR,
    )
