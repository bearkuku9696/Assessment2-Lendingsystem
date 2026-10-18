from functools import wraps

from flask import abort, flash, g, redirect, session, url_for

from . import bp
from .dependencies import authentication_service


@bp.before_app_request
def load_logged_in_user():
    user_id = session.get("user_id")
    g.user = authentication_service.find_user(user_id) if user_id else None


def login_required(view):
    @wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            flash("Please sign in to continue.", "error")
            return redirect(url_for("main.login"))
        return view(**kwargs)

    return wrapped_view


def admin_required(view):
    @wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None or g.user["role"] != "admin":
            abort(403)
        return view(**kwargs)

    return wrapped_view
