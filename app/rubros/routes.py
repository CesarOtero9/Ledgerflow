from decimal import Decimal, InvalidOperation

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from sqlalchemy import func

from app.extensions import db
from app.models import Category, Subcategory, Entry

rubros_bp = Blueprint("rubros", __name__, url_prefix="/rubros")


def parse_amount(value):
    if not value:
        return Decimal("0.00")

    cleaned = (
        value.replace("$", "")
        .replace(",", "")
        .replace("MXN", "")
        .replace(" ", "")
        .strip()
    )

    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return Decimal("0.00")


@rubros_bp.route("/")
@login_required
def index():
    rubros = Category.query.order_by(Category.name.asc()).all()
    return render_template("rubros/index.html", rubros=rubros)


@rubros_bp.route("/nuevo", methods=["GET", "POST"])
@login_required
def nuevo():
    if request.method == "POST":
        name = request.form.get("name", "").strip().upper()
        description = request.form.get("description", "").strip()

        if not name:
            flash("El nombre del rubro es obligatorio.", "danger")
            return redirect(url_for("rubros.nuevo"))

        existing = Category.query.filter_by(name=name).first()

        if existing:
            flash("Ya existe un rubro con ese nombre.", "warning")
            return redirect(url_for("rubros.nuevo"))

        rubro = Category(
            name=name,
            description=description or None,
            is_active=True
        )

        db.session.add(rubro)
        db.session.commit()

        flash("Rubro registrado correctamente.", "success")
        return redirect(url_for("rubros.index"))

    return render_template("rubros/form.html", rubro=None, modo="nuevo")


@rubros_bp.route("/editar/<int:rubro_id>", methods=["GET", "POST"])
@login_required
def editar(rubro_id):
    rubro = Category.query.get_or_404(rubro_id)

    if request.method == "POST":
        name = request.form.get("name", "").strip().upper()
        description = request.form.get("description", "").strip()
        is_active = True if request.form.get("is_active") == "on" else False

        if not name:
            flash("El nombre del rubro es obligatorio.", "danger")
            return redirect(url_for("rubros.editar", rubro_id=rubro.id))

        existing = Category.query.filter(
            Category.name == name,
            Category.id != rubro.id
        ).first()

        if existing:
            flash("Otro rubro ya tiene ese nombre.", "warning")
            return redirect(url_for("rubros.editar", rubro_id=rubro.id))

        rubro.name = name
        rubro.description = description or None
        rubro.is_active = is_active

        db.session.commit()

        flash("Rubro actualizado correctamente.", "success")
        return redirect(url_for("rubros.index"))

    return render_template("rubros/form.html", rubro=rubro, modo="editar")


@rubros_bp.route("/desactivar/<int:rubro_id>", methods=["POST"])
@login_required
def desactivar(rubro_id):
    rubro = Category.query.get_or_404(rubro_id)
    rubro.is_active = False

    for subrubro in rubro.subcategories:
        subrubro.is_active = False

    db.session.commit()

    flash("Rubro y subrubros desactivados correctamente.", "success")
    return redirect(url_for("rubros.index"))


@rubros_bp.route("/activar/<int:rubro_id>", methods=["POST"])
@login_required
def activar(rubro_id):
    rubro = Category.query.get_or_404(rubro_id)
    rubro.is_active = True

    db.session.commit()

    flash("Rubro activado correctamente.", "success")
    return redirect(url_for("rubros.index"))


@rubros_bp.route("/<int:rubro_id>/subrubros")
@login_required
def subrubros(rubro_id):
    rubro = Category.query.get_or_404(rubro_id)

    subrubros = (
        Subcategory.query
        .filter_by(category_id=rubro.id)
        .order_by(Subcategory.name.asc())
        .all()
    )

    stats = {}

    for subrubro in subrubros:
        paid_amount = (
            db.session.query(func.coalesce(func.sum(Entry.amount), 0))
            .filter(Entry.subcategory_id == subrubro.id)
            .scalar()
        )

        budget = float(subrubro.budget_amount or 0)
        paid = float(paid_amount or 0)
        remaining = budget - paid

        if budget > 0:
            percentage = round((paid / budget) * 100, 2)
        else:
            percentage = 0

        if percentage >= 100:
            status = "danger"
        elif percentage >= 80:
            status = "warning"
        else:
            status = "success"

        stats[subrubro.id] = {
            "budget": budget,
            "paid": paid,
            "remaining": remaining,
            "percentage": percentage,
            "status": status
        }

    total_budget = sum(item["budget"] for item in stats.values())
    total_paid = sum(item["paid"] for item in stats.values())
    total_remaining = total_budget - total_paid

    if total_budget > 0:
        total_percentage = round((total_paid / total_budget) * 100, 2)
    else:
        total_percentage = 0

    summary = {
        "total_budget": total_budget,
        "total_paid": total_paid,
        "total_remaining": total_remaining,
        "total_percentage": total_percentage
    }

    return render_template(
        "rubros/subrubros.html",
        rubro=rubro,
        subrubros=subrubros,
        stats=stats,
        summary=summary
    )


@rubros_bp.route("/<int:rubro_id>/subrubros/nuevo", methods=["GET", "POST"])
@login_required
def nuevo_subrubro(rubro_id):
    rubro = Category.query.get_or_404(rubro_id)

    if request.method == "POST":
        name = request.form.get("name", "").strip().upper()
        description = request.form.get("description", "").strip()
        budget_text = request.form.get("budget_amount", "").strip()
        budget_amount = parse_amount(budget_text)

        if not name:
            flash("El nombre del subrubro es obligatorio.", "danger")
            return redirect(url_for("rubros.nuevo_subrubro", rubro_id=rubro.id))

        existing = Subcategory.query.filter_by(
            category_id=rubro.id,
            name=name
        ).first()

        if existing:
            flash("Ya existe un subrubro con ese nombre dentro de este rubro.", "warning")
            return redirect(url_for("rubros.nuevo_subrubro", rubro_id=rubro.id))

        subrubro = Subcategory(
            category_id=rubro.id,
            name=name,
            description=description or None,
            budget_amount=budget_amount,
            is_active=True
        )

        db.session.add(subrubro)
        db.session.commit()

        flash("Subrubro registrado correctamente.", "success")
        return redirect(url_for("rubros.subrubros", rubro_id=rubro.id))

    return render_template(
        "rubros/subrubro_form.html",
        rubro=rubro,
        subrubro=None,
        modo="nuevo"
    )


@rubros_bp.route("/subrubros/editar/<int:subrubro_id>", methods=["GET", "POST"])
@login_required
def editar_subrubro(subrubro_id):
    subrubro = Subcategory.query.get_or_404(subrubro_id)
    rubro = subrubro.category

    if request.method == "POST":
        name = request.form.get("name", "").strip().upper()
        description = request.form.get("description", "").strip()
        budget_text = request.form.get("budget_amount", "").strip()
        budget_amount = parse_amount(budget_text)
        is_active = True if request.form.get("is_active") == "on" else False

        if not name:
            flash("El nombre del subrubro es obligatorio.", "danger")
            return redirect(url_for("rubros.editar_subrubro", subrubro_id=subrubro.id))

        existing = Subcategory.query.filter(
            Subcategory.category_id == rubro.id,
            Subcategory.name == name,
            Subcategory.id != subrubro.id
        ).first()

        if existing:
            flash("Otro subrubro ya tiene ese nombre dentro de este rubro.", "warning")
            return redirect(url_for("rubros.editar_subrubro", subrubro_id=subrubro.id))

        subrubro.name = name
        subrubro.description = description or None
        subrubro.budget_amount = budget_amount
        subrubro.is_active = is_active

        db.session.commit()

        flash("Subrubro actualizado correctamente.", "success")
        return redirect(url_for("rubros.subrubros", rubro_id=rubro.id))

    return render_template(
        "rubros/subrubro_form.html",
        rubro=rubro,
        subrubro=subrubro,
        modo="editar"
    )


@rubros_bp.route("/subrubros/desactivar/<int:subrubro_id>", methods=["POST"])
@login_required
def desactivar_subrubro(subrubro_id):
    subrubro = Subcategory.query.get_or_404(subrubro_id)
    rubro_id = subrubro.category_id

    subrubro.is_active = False
    db.session.commit()

    flash("Subrubro desactivado correctamente.", "success")
    return redirect(url_for("rubros.subrubros", rubro_id=rubro_id))


@rubros_bp.route("/subrubros/activar/<int:subrubro_id>", methods=["POST"])
@login_required
def activar_subrubro(subrubro_id):
    subrubro = Subcategory.query.get_or_404(subrubro_id)
    rubro_id = subrubro.category_id

    subrubro.is_active = True
    db.session.commit()

    flash("Subrubro activado correctamente.", "success")
    return redirect(url_for("rubros.subrubros", rubro_id=rubro_id))