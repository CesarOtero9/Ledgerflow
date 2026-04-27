from datetime import datetime
from decimal import Decimal, InvalidOperation

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user

from app.extensions import db
from app.models import Entry, Supplier, BudgetItem

registros_bp = Blueprint("registros", __name__, url_prefix="/registros")


MESES_ES = {
    1: "ENERO",
    2: "FEBRERO",
    3: "MARZO",
    4: "ABRIL",
    5: "MAYO",
    6: "JUNIO",
    7: "JULIO",
    8: "AGOSTO",
    9: "SEPTIEMBRE",
    10: "OCTUBRE",
    11: "NOVIEMBRE",
    12: "DICIEMBRE",
}


def parse_date(value):
    if not value:
        return None

    value = value.strip()

    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue

    return None


def parse_amount(value):
    if not value:
        return None

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
        return None


def natural_code_key(item_code):
    try:
        return tuple(int(part) for part in item_code.split("."))
    except ValueError:
        return tuple(item_code.split("."))


def get_sorted_budget_items():
    return sorted(
        BudgetItem.query.filter_by(is_active=True).all(),
        key=lambda x: natural_code_key(x.item_code)
    )


def generate_unique_key(application_year):
    prefix = f"APL-{application_year}-"

    last_entry = (
        Entry.query
        .filter(Entry.unique_key.like(f"{prefix}%"))
        .order_by(Entry.id.desc())
        .first()
    )

    if not last_entry:
        next_number = 1
    else:
        try:
            last_number = int(last_entry.unique_key.split("-")[-1])
            next_number = last_number + 1
        except (ValueError, IndexError):
            next_number = 1

    return f"{prefix}{next_number:06d}"


@registros_bp.route("/")
@login_required
def index():
    registros = (
        Entry.query
        .join(Supplier, Entry.supplier_id == Supplier.id)
        .outerjoin(BudgetItem, Entry.budget_item_id == BudgetItem.id)
        .order_by(Entry.application_date.desc(), Entry.id.desc())
        .all()
    )

    return render_template("registros/index.html", registros=registros)


@registros_bp.route("/nuevo", methods=["GET", "POST"])
@login_required
def nuevo():
    proveedores = Supplier.query.filter_by(is_active=True).order_by(Supplier.business_name.asc()).all()
    budget_items = get_sorted_budget_items()

    if request.method == "POST":
        fecha_texto = request.form.get("application_date", "").strip()
        supplier_id = request.form.get("supplier_id", "").strip()
        budget_item_id = request.form.get("budget_item_id", "").strip()
        amount_texto = request.form.get("amount", "").strip()
        operation_folio = request.form.get("operation_folio", "").strip().upper()
        concept = request.form.get("concept", "").strip().upper()
        comments = request.form.get("comments", "").strip().upper()

        application_date = parse_date(fecha_texto)
        amount = parse_amount(amount_texto)

        if not application_date:
            flash("La fecha debe tener formato válido.", "danger")
            return redirect(url_for("registros.nuevo"))

        if not supplier_id or not budget_item_id:
            flash("El proveedor y el rubro son obligatorios.", "danger")
            return redirect(url_for("registros.nuevo"))

        if amount is None or amount <= 0:
            flash("El monto debe ser mayor a cero.", "danger")
            return redirect(url_for("registros.nuevo"))

        if not concept:
            flash("El concepto es obligatorio.", "danger")
            return redirect(url_for("registros.nuevo"))

        month_number = application_date.month
        year = application_date.year
        month_name = MESES_ES[month_number]

        unique_key = generate_unique_key(year)

        registro = Entry(
            unique_key=unique_key,
            application_date=application_date,
            application_month=month_name,
            application_month_number=month_number,
            application_year=year,
            supplier_id=int(supplier_id),
            budget_item_id=int(budget_item_id),
            amount=amount,
            operation_folio=operation_folio or None,
            concept=concept,
            comments=comments or None,
            created_by=current_user.id,
            category_id=None,
            subcategory_id=None
        )

        db.session.add(registro)
        db.session.commit()

        flash(f"Registro {unique_key} creado correctamente.", "success")
        return redirect(url_for("registros.index"))

    return render_template(
        "registros/form.html",
        registro=None,
        proveedores=proveedores,
        budget_items=budget_items,
        modo="nuevo"
    )


@registros_bp.route("/editar/<int:registro_id>", methods=["GET", "POST"])
@login_required
def editar(registro_id):
    registro = Entry.query.get_or_404(registro_id)

    proveedores = Supplier.query.filter_by(is_active=True).order_by(Supplier.business_name.asc()).all()
    budget_items = get_sorted_budget_items()

    if request.method == "POST":
        fecha_texto = request.form.get("application_date", "").strip()
        supplier_id = request.form.get("supplier_id", "").strip()
        budget_item_id = request.form.get("budget_item_id", "").strip()
        amount_texto = request.form.get("amount", "").strip()
        operation_folio = request.form.get("operation_folio", "").strip().upper()
        concept = request.form.get("concept", "").strip().upper()
        comments = request.form.get("comments", "").strip().upper()

        application_date = parse_date(fecha_texto)
        amount = parse_amount(amount_texto)

        if not application_date:
            flash("La fecha debe tener formato válido.", "danger")
            return redirect(url_for("registros.editar", registro_id=registro.id))

        if not supplier_id or not budget_item_id:
            flash("El proveedor y el rubro son obligatorios.", "danger")
            return redirect(url_for("registros.editar", registro_id=registro.id))

        if amount is None or amount <= 0:
            flash("El monto debe ser mayor a cero.", "danger")
            return redirect(url_for("registros.editar", registro_id=registro.id))

        if not concept:
            flash("El concepto es obligatorio.", "danger")
            return redirect(url_for("registros.editar", registro_id=registro.id))

        month_number = application_date.month
        year = application_date.year
        month_name = MESES_ES[month_number]

        registro.application_date = application_date
        registro.application_month = month_name
        registro.application_month_number = month_number
        registro.application_year = year
        registro.supplier_id = int(supplier_id)
        registro.budget_item_id = int(budget_item_id)
        registro.amount = amount
        registro.operation_folio = operation_folio or None
        registro.concept = concept
        registro.comments = comments or None
        registro.category_id = None
        registro.subcategory_id = None

        db.session.commit()

        flash("Registro actualizado correctamente.", "success")
        return redirect(url_for("registros.index"))

    return render_template(
        "registros/form.html",
        registro=registro,
        proveedores=proveedores,
        budget_items=budget_items,
        modo="editar"
    )


@registros_bp.route("/eliminar/<int:registro_id>", methods=["POST"])
@login_required
def eliminar(registro_id):
    registro = Entry.query.get_or_404(registro_id)

    db.session.delete(registro)
    db.session.commit()

    flash("Registro eliminado correctamente.", "success")
    return redirect(url_for("registros.index"))