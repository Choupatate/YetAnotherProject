"""Family accounts (FEATURES.md F19): the public request/approve flow,
admin account management, self-service password change, and delegated
write-links. Registers onto the same `pages` blueprint `routes_pages.py`
defines — see that module's docstring/bottom-of-file import for why these
live in a separate file without a separate blueprint.
"""

import hmac
import time
from datetime import date, datetime

from flask import abort, current_app, flash, redirect, render_template, request, session, url_for

from . import accounts, people, storage, write_links
from .auth import admin_required, delegate_required, login_required, set_session_for_account
from .routes_pages import _people_dir, bp


@bp.route("/request-account", methods=["GET", "POST"])
def request_account():
    """Public, unauthenticated (FEATURES.md F19 Phase 2): anyone who knows
    the invite code (STORYBOOK_PASSWORD, repurposed once accounts mode is
    on — it no longer logs anyone in) can queue a request. The very first
    request ever submitted auto-approves as admin, bound to a brand-new
    Person from its display name — there's no admin yet to review it, and
    already knowing the invite code is the only proof of ownership this
    self-hosted app has."""
    if not current_app.config["ACCOUNTS_ENABLED"]:
        abort(404)
    stories_dir = current_app.config["STORIES_DIR"]

    if request.method == "POST":
        invite_code = request.form.get("invite_code", "")
        display_name = (request.form.get("display_name") or "").strip()
        username = (request.form.get("username") or "").strip().lower()
        password = request.form.get("password") or ""
        note = request.form.get("note") or ""

        if not hmac.compare_digest(invite_code, current_app.config["PASSWORD"]):
            time.sleep(1)
            flash("Incorrect invite code.", "error")
        else:
            try:
                pending = accounts.create_pending_request(
                    stories_dir, username, password, display_name, note
                )
            except ValueError as exc:
                flash(str(exc), "error")
            else:
                auto_approved = accounts.approve_if_first(stories_dir, pending.username)
                return render_template(
                    "request_account.html", submitted=True, auto_approved=auto_approved
                )

    return render_template("request_account.html", submitted=False)


@bp.route("/admin/accounts")
@admin_required
def admin_accounts():
    stories_dir = current_app.config["STORIES_DIR"]
    people_dir = storage.people_dir(stories_dir)
    people_by_slug = {p.slug: p for p in people.list_people(people_dir)}
    unbound_people = [p for p in people_by_slug.values() if accounts.get_account(people_dir, p.slug) is None]
    rows = [
        {"account": a, "person": people_by_slug.get(a.person_slug)}
        for a in accounts.list_accounts(people_dir)
    ]
    link_rows = [
        {"link": link, "person": people_by_slug.get(link.person_slug)}
        for link in write_links.list_all_active(people_dir)
    ]
    return render_template(
        "admin_accounts.html", rows=rows, pending=accounts.list_pending(stories_dir),
        link_rows=link_rows, roles=accounts.ROLES, unbound_people=unbound_people,
    )


def _admin_mutate_account(person_slug, mutator, *args, on_success=None):
    """Shared shape for a POST-only admin account action: call `mutator`
    as `mutator(people_dir, person_slug, *args)`, flash and redirect on
    ValueError/FileNotFoundError (a bad slug, an invalid value, or a
    guard like the last-admin lockout) exactly like every other admin
    action here, then redirect to the accounts list either way. Optional
    `on_success` runs only after a real mutation, for the one route
    (link-person) that also needs to touch the caller's own session."""
    try:
        mutator(_people_dir(), person_slug, *args)
    except (ValueError, FileNotFoundError) as exc:
        flash(str(exc), "error")
    else:
        if on_success:
            on_success()
    return redirect(url_for("pages.admin_accounts"))


@bp.route("/admin/accounts/<person_slug>/disable", methods=["POST"])
@admin_required
def admin_disable_account(person_slug):
    return _admin_mutate_account(person_slug, accounts.set_status, "disabled")


@bp.route("/admin/accounts/<person_slug>/enable", methods=["POST"])
@admin_required
def admin_enable_account(person_slug):
    return _admin_mutate_account(person_slug, accounts.set_status, "active")


@bp.route("/admin/accounts/<person_slug>/role", methods=["POST"])
@admin_required
def admin_set_role(person_slug):
    role = request.form.get("role") or ""
    return _admin_mutate_account(person_slug, accounts.set_role, role)


@bp.route("/admin/accounts/<person_slug>/link-person", methods=["POST"])
@admin_required
def admin_set_account_person(person_slug):
    """Re-bind an account to a different (unbound) Person — the fix for an
    account that ended up attached to the wrong Person, most commonly the
    very first account auto-creating a brand-new Person instead of
    reusing one that already existed (see accounts.set_person)."""
    target_slug = request.form.get("target_person_slug") or ""

    def _sync_own_session():
        if session.get("person_slug") == person_slug:
            session["person_slug"] = target_slug

    return _admin_mutate_account(
        person_slug, accounts.set_person, target_slug, on_success=_sync_own_session
    )


@bp.route("/admin/accounts/<person_slug>/reset-password", methods=["GET", "POST"])
@admin_required
def admin_reset_password(person_slug):
    """An admin setting a new password directly — the only recovery path
    for a family member who's forgotten theirs, since this app has no
    email and therefore no self-service reset flow. Unlike a self-service
    change, this never needs the old password."""
    people_dir = _people_dir()
    account = accounts.get_account(people_dir, person_slug)
    if account is None:
        abort(404)
    person = people.get_person(people_dir, person_slug)

    if request.method == "POST":
        new_password = request.form.get("new_password") or ""
        confirm_password = request.form.get("confirm_password") or ""
        error = None
        if new_password != confirm_password:
            error = "Passwords don't match."
        else:
            try:
                accounts.set_password(people_dir, person_slug, new_password)
            except ValueError as exc:
                error = str(exc)
        if error:
            flash(error, "error")
        else:
            return redirect(url_for("pages.admin_accounts"))

    return render_template(
        "admin_reset_password.html", account=account,
        person_name=person.name if person else account.username,
    )


def _bind_and_create(people_dir, person_slug, new_person_name):
    """Shared validation for admin_new_account/admin_review_pending: pick
    an existing unbound Person or create a new one from a name. Returns
    (resolved_person_slug, error_message_or_None)."""
    unbound_slugs = {
        p.slug for p in people.list_people(people_dir) if accounts.get_account(people_dir, p.slug) is None
    }
    if not person_slug and not new_person_name:
        return None, "Pick an existing family member, or enter a name for a new one."
    if person_slug and person_slug not in unbound_slugs:
        return None, "That family member already has an account."
    if not person_slug:
        person_slug = people.create_person(people_dir, new_person_name)
    return person_slug, None


@bp.route("/admin/accounts/new", methods=["GET", "POST"])
@admin_required
def admin_new_account():
    """Admin-direct account creation, bypassing the request queue entirely
    — for a family member who won't submit their own request."""
    people_dir = _people_dir()
    unbound_people = [
        p for p in people.list_people(people_dir) if accounts.get_account(people_dir, p.slug) is None
    ]

    if request.method == "POST":
        person_slug = request.form.get("person_slug") or None
        new_person_name = (request.form.get("new_person_name") or "").strip()
        username = (request.form.get("username") or "").strip().lower()
        password = request.form.get("password") or ""
        role = request.form.get("role") or "family"

        error = None
        if role not in accounts.ROLES:
            error = "Invalid role."
        else:
            person_slug, error = _bind_and_create(people_dir, person_slug, new_person_name)

        if error is None:
            try:
                accounts.create_account(
                    people_dir, person_slug, username, password, role,
                    approved_by=session.get("account_username"),
                )
            except (ValueError, FileNotFoundError) as exc:
                error = str(exc)

        if error:
            flash(error, "error")
        else:
            return redirect(url_for("pages.admin_accounts"))

    return render_template(
        "admin_new_account.html", unbound_people=unbound_people, roles=accounts.ROLES
    )


@bp.route("/admin/accounts/pending/<username>", methods=["GET", "POST"])
@admin_required
def admin_review_pending(username):
    stories_dir = current_app.config["STORIES_DIR"]
    people_dir = storage.people_dir(stories_dir)
    pending = accounts.get_pending(stories_dir, username)
    if pending is None:
        abort(404)
    unbound_people = [
        p for p in people.list_people(people_dir) if accounts.get_account(people_dir, p.slug) is None
    ]

    if request.method == "POST":
        person_slug = request.form.get("person_slug") or None
        new_person_name = (request.form.get("new_person_name") or "").strip()
        role = request.form.get("role") or "family"

        error = None
        if role not in accounts.ROLES:
            error = "Invalid role."
        else:
            person_slug, error = _bind_and_create(people_dir, person_slug, new_person_name)

        if error is None:
            try:
                accounts.approve_pending(
                    stories_dir, username, role, person_slug=person_slug,
                    approved_by=session.get("account_username"),
                )
            except (ValueError, FileNotFoundError) as exc:
                error = str(exc)

        if error:
            flash(error, "error")
        else:
            return redirect(url_for("pages.admin_accounts"))

    return render_template(
        "admin_review_pending.html", pending=pending, unbound_people=unbound_people,
        roles=accounts.ROLES,
    )


@bp.route("/admin/accounts/pending/<username>/reject", methods=["POST"])
@admin_required
def admin_reject_pending(username):
    accounts.reject_pending(current_app.config["STORIES_DIR"], username)
    return redirect(url_for("pages.admin_accounts"))


# --- Account self-service (password change) ---------------------------------


def _own_account_or_404():
    """Guard shared by every /account/* route: accounts mode on and a real
    (non-delegate) account logged in — session["person_slug"] is only ever
    set by those. Returns the people_dir for convenience."""
    if not current_app.config["ACCOUNTS_ENABLED"] or not session.get("person_slug"):
        abort(404)
    return _people_dir()


@bp.route("/account")
@login_required
def account_home():
    _own_account_or_404()
    return render_template("account_home.html")


@bp.route("/account/password", methods=["GET", "POST"])
@login_required
def account_password():
    people_dir = _own_account_or_404()
    success = False

    if request.method == "POST":
        current_password = request.form.get("current_password") or ""
        new_password = request.form.get("new_password") or ""
        confirm_password = request.form.get("confirm_password") or ""

        error = None
        if accounts.verify_login(people_dir, session["account_username"], current_password) is None:
            error = "Current password is incorrect."
        elif new_password != confirm_password:
            error = "New passwords don't match."
        else:
            try:
                accounts.set_password(people_dir, session["person_slug"], new_password)
            except ValueError as exc:
                error = str(exc)

        if error:
            flash(error, "error")
        else:
            # Refresh this session's own session_version — set_password just
            # bumped it, and without this the very next request would lock
            # out the person who just successfully changed their password,
            # not only (as intended) every other already-open session.
            account = accounts.get_account_by_username(people_dir, session["account_username"])
            set_session_for_account(account)
            success = True

    return render_template("account_password.html", success=success)


# --- Delegated write-links (FEATURES.md F19 Phase 3) ------------------------


def _link_status(link):
    """The one-word status account_write_links.html/admin_accounts.html
    show — computed here rather than with date math in Jinja."""
    if link.revoked:
        return "revoked"
    if link.single_use and link.used_at:
        return "used"
    if link.expires_at and datetime.now() > link.expires_at:
        return "expired"
    return "active"


@bp.route("/account/write-links", methods=["GET", "POST"])
@login_required
def account_write_links():
    """A logged-in account holder's own share-to-write links: create one,
    see history, revoke."""
    people_dir = _own_account_or_404()
    person_slug = session["person_slug"]
    new_link_url = None

    if request.method == "POST":
        label = (request.form.get("label") or "").strip() or None
        single_use = "single_use" in request.form
        expires_raw = (request.form.get("expires_days") or "").strip()
        expires_in_days = int(expires_raw) if expires_raw.isdigit() else None
        link, token = write_links.create_link(
            people_dir, person_slug, label=label,
            expires_in_days=expires_in_days, single_use=single_use,
        )
        new_link_url = url_for("pages.use_write_link", token=token, _external=True)

    link_rows = [
        {"link": link, "status": _link_status(link)}
        for link in write_links.list_links(people_dir, person_slug)
    ]
    return render_template(
        "account_write_links.html", link_rows=link_rows, new_link_url=new_link_url
    )


@bp.route("/account/write-links/<person_slug>/<link_id>/revoke", methods=["POST"])
@login_required
def revoke_write_link(person_slug, link_id):
    if session.get("role") != "admin" and session.get("person_slug") != person_slug:
        abort(404)
    try:
        write_links.revoke_link(_people_dir(), person_slug, link_id)
    except FileNotFoundError:
        abort(404)
    if session.get("person_slug") == person_slug:
        return redirect(url_for("pages.account_write_links"))
    return redirect(url_for("pages.admin_accounts"))


@bp.route("/w/<token>")
def use_write_link(token):
    """Opening a valid link always starts a fresh delegate session,
    discarding whatever session (if any) was there before — never lets a
    logged-in account holder's own session bleed into a scoped delegate
    one, or vice versa."""
    if not current_app.config["ACCOUNTS_ENABLED"]:
        abort(404)
    link = write_links.find_by_token(_people_dir(), token)
    if link is None or not write_links.is_link_valid(link):
        return render_template("write_link_invalid.html"), 404
    session.clear()
    session["delegate_person_slug"] = link.person_slug
    session["delegate_link_id"] = link.id
    return redirect(url_for("pages.delegate_write"))


def _neutralize_html(text):
    """Escape raw `<`/`>` so a delegate write-link submission can never
    inject a `<script>` (or any other tag) that later renders unescaped —
    render_markdown() passes raw HTML straight through and every template
    renders the result with `|safe`, which REVIEW.md accepted only because
    "the only author is the trusted password-holder." A write-link
    (FEATURES.md F19 Phase 3) is deliberately handed to someone who is NOT
    an account holder, so that assumption doesn't hold on this path —
    unlike every other place a story is created. Markdown syntax itself
    never needs a literal `<`/`>`, so this can't break normal formatting."""
    return text.replace("<", "&lt;").replace(">", "&gt;")


@bp.route("/w/write", methods=["GET", "POST"])
@delegate_required
def delegate_write():
    """The delegate's entire world: write one story, submit, done. No
    photos (kept deliberately text-only to avoid the multi-step upload
    flow the real editor needs), no nav into the rest of the book, no
    editing anything after submission — a multi-use link lets someone
    come back and submit another new story, not revise a previous one."""
    people_dir = _people_dir()
    person_slug = session["delegate_person_slug"]
    link_id = session["delegate_link_id"]
    person = people.get_person(people_dir, person_slug)
    if person is None:
        abort(404)

    if request.method == "POST":
        title = (request.form.get("title") or "").strip()
        date_raw = request.form.get("date") or ""
        body = _neutralize_html(request.form.get("markdown") or "")

        error = None
        try:
            story_date = date.fromisoformat(date_raw)
        except ValueError:
            error = "Enter a valid date."
        if not title:
            error = "Enter a title."

        if error:
            flash(error, "error")
        else:
            story_id = storage.create_story(
                current_app.config["STORIES_DIR"], title, story_date, body, author=person.name
            )
            write_links.mark_used(people_dir, person_slug, link_id, story_id)
            link = write_links.get_link(people_dir, person_slug, link_id)
            if link.single_use:
                session.clear()
            return render_template("delegate_thanks.html", person_name=person.name)

    return render_template("delegate_write.html", person_name=person.name, today=date.today())
