from decimal import Decimal, InvalidOperation

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from sqlalchemy import func

from app.extensions import db
from app.models import BudgetItem, Entry

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


def normalize_code(code):
    return code.strip().replace(" ", "")


def get_level_from_code(item_code):
    if not item_code:
        return 1
    return item_code.count(".") + 1


def get_parent_code(item_code):
    parts = item_code.split(".")

    if len(parts) == 1:
        return None

    return ".".join(parts[:-1])


def natural_code_key(item_code):
    """
    Convierte códigos como:
    1 -> (1,)
    1.1 -> (1, 1)
    1.10 -> (1, 10)
    10 -> (10,)
    para ordenarlos jerárquicamente de forma natural.
    """
    try:
        return tuple(int(part) for part in item_code.split("."))
    except ValueError:
        # fallback por si algún código no es totalmente numérico
        return tuple(item_code.split("."))


def get_all_budget_items_sorted():
    items = BudgetItem.query.all()
    return sorted(items, key=lambda x: natural_code_key(x.item_code))


def build_tree_rows():
    items = get_all_budget_items_sorted()
    rows = []

    for item in items:
        paid_amount = (
            db.session.query(func.coalesce(func.sum(Entry.amount), 0))
            .filter(Entry.budget_item_id == item.id)
            .scalar()
        )

        budget = float(item.budget_amount or 0)
        paid = float(paid_amount or 0)
        remaining = budget - paid

        if budget > 0:
            percentage = round((paid / budget) * 100, 2)
        else:
            percentage = 0

        children_budget_sum = (
            db.session.query(func.coalesce(func.sum(BudgetItem.budget_amount), 0))
            .filter(BudgetItem.parent_id == item.id)
            .scalar()
        )

        children_budget_sum = float(children_budget_sum or 0)

        if len(item.children) > 0:
            is_budget_match = round(children_budget_sum, 2) == round(budget, 2)
        else:
            is_budget_match = True

        rows.append({
            "item": item,
            "paid": paid,
            "remaining": remaining,
            "percentage": percentage,
            "children_budget_sum": children_budget_sum,
            "is_budget_match": is_budget_match
        })

    return rows


@rubros_bp.route("/")
@login_required
def index():
    rows = build_tree_rows()
    return render_template("rubros/index.html", rows=rows)


@rubros_bp.route("/nuevo", methods=["GET", "POST"])
@login_required
def nuevo():
    if request.method == "POST":
        item_code = normalize_code(request.form.get("item_code", ""))
        item_name = request.form.get("item_name", "").strip().upper()
        budget_amount = parse_amount(request.form.get("budget_amount", "").strip())

        if not item_code or not item_name:
            flash("El número y el nombre del rubro son obligatorios.", "danger")
            return redirect(url_for("rubros.nuevo"))

        existing = BudgetItem.query.filter_by(item_code=item_code).first()
        if existing:
            flash("Ya existe un rubro con ese número.", "warning")
            return redirect(url_for("rubros.nuevo"))

        level = get_level_from_code(item_code)
        parent_code = get_parent_code(item_code)
        parent = None

        if parent_code:
            parent = BudgetItem.query.filter_by(item_code=parent_code).first()

            if not parent:
                flash(
                    f"No se puede crear {item_code} porque no existe su padre {parent_code}.",
                    "danger"
                )
                return redirect(url_for("rubros.nuevo"))

        item = BudgetItem(
            item_code=item_code,
            item_name=item_name,
            parent_id=parent.id if parent else None,
            level=level,
            budget_amount=budget_amount,
            is_active=True
        )

        db.session.add(item)
        db.session.commit()

        flash("Rubro registrado correctamente.", "success")
        return redirect(url_for("rubros.index"))

    available_items = get_all_budget_items_sorted()
    return render_template("rubros/form.html", item=None, modo="nuevo", available_items=available_items)


@rubros_bp.route("/editar/<int:item_id>", methods=["GET", "POST"])
@login_required
def editar(item_id):
    item = BudgetItem.query.get_or_404(item_id)

    if request.method == "POST":
        item_code = normalize_code(request.form.get("item_code", ""))
        item_name = request.form.get("item_name", "").strip().upper()
        budget_amount = parse_amount(request.form.get("budget_amount", "").strip())
        is_active = True if request.form.get("is_active") == "on" else False

        if not item_code or not item_name:
            flash("El número y el nombre del rubro son obligatorios.", "danger")
            return redirect(url_for("rubros.editar", item_id=item.id))

        existing = BudgetItem.query.filter(
            BudgetItem.item_code == item_code,
            BudgetItem.id != item.id
        ).first()

        if existing:
            flash("Otro rubro ya tiene ese número.", "warning")
            return redirect(url_for("rubros.editar", item_id=item.id))

        level = get_level_from_code(item_code)
        parent_code = get_parent_code(item_code)
        parent = None

        if parent_code:
            parent = BudgetItem.query.filter_by(item_code=parent_code).first()

            if not parent:
                flash(
                    f"No se puede guardar {item_code} porque no existe su padre {parent_code}.",
                    "danger"
                )
                return redirect(url_for("rubros.editar", item_id=item.id))

            if parent.id == item.id:
                flash("Un rubro no puede ser su propio padre.", "danger")
                return redirect(url_for("rubros.editar", item_id=item.id))

        if parent:
            current = parent
            while current:
                if current.id == item.id:
                    flash("No puedes asignar como padre a uno de sus descendientes.", "danger")
                    return redirect(url_for("rubros.editar", item_id=item.id))
                current = current.parent

        item.item_code = item_code
        item.item_name = item_name
        item.parent_id = parent.id if parent else None
        item.level = level
        item.budget_amount = budget_amount
        item.is_active = is_active

        db.session.commit()

        flash("Rubro actualizado correctamente.", "success")
        return redirect(url_for("rubros.index"))

    available_items = get_all_budget_items_sorted()
    return render_template("rubros/form.html", item=item, modo="editar", available_items=available_items)


@rubros_bp.route("/desactivar/<int:item_id>", methods=["POST"])
@login_required
def desactivar(item_id):
    item = BudgetItem.query.get_or_404(item_id)
    item.is_active = False
    db.session.commit()

    flash("Rubro desactivado correctamente.", "success")
    return redirect(url_for("rubros.index"))


@rubros_bp.route("/activar/<int:item_id>", methods=["POST"])
@login_required
def activar(item_id):
    item = BudgetItem.query.get_or_404(item_id)
    item.is_active = True
    db.session.commit()

    flash("Rubro activado correctamente.", "success")
    return redirect(url_for("rubros.index"))