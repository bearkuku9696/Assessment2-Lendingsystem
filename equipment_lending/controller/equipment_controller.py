from flask import abort, flash, redirect, render_template, request, url_for

from . import bp
from .dependencies import equipment_service
from .security import admin_required


def equipment_form_values():
    fields = ("name", "category", "description", "location", "status")
    return tuple(request.form[field].strip() for field in fields)


@bp.get("/")
def index():
    search = request.args.get("search", "").strip()
    category = request.args.get("category", "").strip()
    status = request.args.get("status", "").strip()
    return render_template(
        "index.html",
        equipment=equipment_service.find_all(search, category, status),
        categories=equipment_service.find_categories(),
        search=search,
        selected_category=category,
        selected_status=status,
    )


@bp.get("/admin/equipment")
@admin_required
def admin_equipment():
    return render_template(
        "admin_equipment.html", equipment=equipment_service.find_all()
    )


@bp.route("/admin/equipment/new", methods=("GET", "POST"))
@admin_required
def add_equipment():
    if request.method == "POST":
        equipment_service.create(*equipment_form_values())
        flash("Equipment added.", "success")
        return redirect(url_for("main.admin_equipment"))
    return render_template("equipment_form.html", item=None)


@bp.route("/admin/equipment/<int:equipment_id>/edit", methods=("GET", "POST"))
@admin_required
def edit_equipment(equipment_id):
    item = equipment_service.find_by_id(equipment_id)
    if item is None:
        abort(404)
    if request.method == "POST":
        equipment_service.update(equipment_id, *equipment_form_values())
        flash("Equipment updated.", "success")
        return redirect(url_for("main.admin_equipment"))
    return render_template("equipment_form.html", item=item)
