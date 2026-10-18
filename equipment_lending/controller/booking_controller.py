from flask import abort, flash, g, redirect, render_template, request, url_for

from ..service import AccessDeniedError, ValidationError
from . import bp
from .dependencies import booking_service, equipment_service
from .security import admin_required, login_required


@bp.route("/equipment/<int:equipment_id>/book", methods=("GET", "POST"))
@login_required
def create_booking(equipment_id):
    equipment = equipment_service.find_by_id(equipment_id)
    if equipment is None:
        abort(404)
    if request.method == "POST":
        try:
            booking_service.create_booking(
                g.user["id"],
                equipment_id,
                request.form.get("start_date", ""),
                request.form.get("end_date", ""),
                request.form.get("purpose", ""),
            )
        except ValidationError as error:
            flash(str(error), "error")
        else:
            flash("Booking request submitted for staff review.", "success")
            return redirect(url_for("main.my_bookings"))
    return render_template("booking_form.html", equipment=equipment)


@bp.get("/my-bookings")
@login_required
def my_bookings():
    return render_template(
        "my_bookings.html", bookings=booking_service.find_for_user(g.user["id"])
    )


@bp.post("/bookings/<int:booking_id>/cancel")
@login_required
def cancel_booking(booking_id):
    try:
        booking_service.cancel_booking(booking_id, g.user["id"])
    except AccessDeniedError:
        abort(403)
    except ValidationError as error:
        flash(str(error), "error")
    else:
        flash("Booking cancelled.", "success")
    return redirect(url_for("main.my_bookings"))


@bp.get("/admin/bookings")
@admin_required
def admin_bookings():
    return render_template(
        "admin_bookings.html", bookings=booking_service.find_all()
    )


@bp.post("/admin/bookings/<int:booking_id>/<new_status>")
@admin_required
def update_booking_status(booking_id, new_status):
    try:
        booking_service.change_status(
            booking_id, new_status, request.form.get("admin_note", "")
        )
    except ValidationError as error:
        flash(str(error), "error")
    else:
        flash(f"Booking changed to {new_status}.", "success")
    return redirect(url_for("main.admin_bookings"))
