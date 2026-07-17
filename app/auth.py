"""Login/logout and the @login_required / @admin_required /
@delegate_required decorators.

Two modes, selected by STORYBOOK_ACCOUNTS (FEATURES.md F19):

- Off (default): a single shared password, no accounts, no roles — exactly
  the original behavior, untouched.
- On: per-person username/password accounts (app/accounts.py), with an
  admin role. STORYBOOK_PASSWORD never logs anyone in here — once accounts
  mode is on, it's only the invite code required on pages.request_account,
  and the very first submitted request auto-approves as admin (see there).

A third, much narrower kind of session exists alongside those two: a
delegate session (Phase 3 write-links, app/write_links.py), opened by
visiting a bearer-token link a real account holder issued. It never sets
session["authed"], so login_required rejects it exactly like a logged-out
visitor — it only unlocks the handful of routes gated by
@delegate_required instead.
"""

import hmac
import time
from functools import wraps

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from . import accounts, storage, write_links

bp = Blueprint("auth", __name__)


def _safe_next_url(next_url):
    """Only ever redirect to a local path, never an external URL."""
    if not next_url or not next_url.startswith("/") or next_url.startswith("//") or "\\" in next_url:
        return url_for("pages.timeline")
    return next_url


def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if not session.get("authed"):
            return redirect(url_for("auth.login", next=request.path))
        if current_app.config["ACCOUNTS_ENABLED"] and session.get("account_username"):
            # Sessions are client-signed cookies with no server-side store,
            # so a disabled account must be re-checked on every request to
            # take effect immediately rather than whenever its 90-day
            # cookie happens to expire.
            people_dir = storage.people_dir(current_app.config["STORIES_DIR"])
            account = accounts.get_account_by_username(people_dir, session["account_username"])
            if account is None or account.status != "active":
                session.clear()
                return redirect(url_for("auth.login", next=request.path))
        return view(*args, **kwargs)

    return wrapped_view


def admin_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if session.get("role") != "admin":
            abort(404)
        return view(*args, **kwargs)

    return login_required(wrapped_view)


def delegate_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        person_slug = session.get("delegate_person_slug")
        link_id = session.get("delegate_link_id")
        if not person_slug or not link_id:
            abort(404)
        people_dir = storage.people_dir(current_app.config["STORIES_DIR"])
        link = write_links.get_link(people_dir, person_slug, link_id)
        if link is None or not write_links.is_link_valid(link):
            # Re-checked every request, same reasoning as login_required's
            # disabled-account check: a revoked/expired/used-up link must
            # stop working immediately, not just refuse new /w/<token> hits.
            session.clear()
            abort(404)
        return view(*args, **kwargs)

    return wrapped_view


@bp.route("/login", methods=["GET", "POST"])
def login():
    accounts_enabled = current_app.config["ACCOUNTS_ENABLED"]

    if request.method == "POST":
        if accounts_enabled:
            people_dir = storage.people_dir(current_app.config["STORIES_DIR"])
            username = request.form.get("username", "").strip().lower()
            password = request.form.get("password", "")
            account = accounts.verify_login(people_dir, username, password)
            if account:
                session.clear()
                session["authed"] = True
                session["account_username"] = account.username
                session["person_slug"] = account.person_slug
                session["role"] = account.role
                session.permanent = True
                return redirect(_safe_next_url(request.args.get("next", "")))
            time.sleep(1)
            flash("Incorrect username or password.", "error")
        else:
            password = request.form.get("password", "")
            correct = hmac.compare_digest(password, current_app.config["PASSWORD"])
            if correct:
                session.clear()
                session["authed"] = True
                session.permanent = True
                return redirect(_safe_next_url(request.args.get("next", "")))
            time.sleep(1)
            flash("Incorrect password.", "error")

    no_accounts_yet = accounts_enabled and not accounts.any_accounts_exist(
        storage.people_dir(current_app.config["STORIES_DIR"])
    )
    return render_template(
        "login.html", accounts_enabled=accounts_enabled, no_accounts_yet=no_accounts_yet
    )


@bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("auth.login"))
