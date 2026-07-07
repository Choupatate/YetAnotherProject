"""Login/logout and the @login_required decorator.

Single shared password, no accounts, no roles, no password reset.
"""

import hmac
import time
from functools import wraps

from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

bp = Blueprint("auth", __name__)


def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if not session.get("authed"):
            return redirect(url_for("auth.login", next=request.path))
        return view(*args, **kwargs)

    return wrapped_view


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        password = request.form.get("password", "")
        correct = hmac.compare_digest(password, current_app.config["PASSWORD"])
        if correct:
            session.clear()
            session["authed"] = True
            session.permanent = True
            next_url = request.args.get("next") or url_for("pages.timeline")
            return redirect(next_url)
        time.sleep(1)
        flash("Incorrect password.", "error")
    return render_template("login.html")


@bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("auth.login"))
