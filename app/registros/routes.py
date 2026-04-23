from datetime import datetime
from decimal import Decimal, InvalidOperation

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user

from app.extensions import db
from app.models import Entry, Supplier, Category, Subcategory

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


def parse_date_ddmmyyyy(value):
    """
    Convierte una fecha en formato dd/mm/yyyy a objeto date.
    """
    try:
        return datetime.strptime(value, "%d/%m/%Y").date()
    except ValueError:
        return None


def parse_amount(value):
    """
    Convierte valores como $1,234.56 o 1,234.56 a Decimal.
    """
    if not value:
        return None

    cleaned = (
        value.replace("$", "")
        .replace(",", "")
        .replace(" ", "")
        .strip()
    )

    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return None


def generate_unique_key(application_year):
    """
    Genera claves tipo APL-2026-000001.
    """
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
        .join(Category, Entry.category_id == Category.id)
        .outerjoin(Subcategory, Entry.subcategory_id == Subcategory.id)
        .order_by(Entry.application_date.desc(), Entry.id.desc())
        .all()
    )

    return render_template("registros/index.html", registros=registros)


@registros_bp.route("/nuevo", methods=["GET", "POST"])
@login_required
def nuevo():
    proveedores = Supplier.query.filter_by(is_active=True).order_by(Supplier.business_name.asc()).all()
    rubros = Category.query.filter_by(is_active=True).order_by(Category.name.asc()).all()

    if request.method == "POST":
        fecha_texto = request.form.get("application_date", "").strip()
        supplier_id = request.form.get("supplier_id", "").strip()
        category_id = request.form.get("category_id", "").strip()
        subcategory_id = request.form.get("subcategory_id", "").strip()
        amount_texto = request.form.get("amount", "").strip()
        operation_folio = request.form.get("operation_folio", "").strip().upper()
        concept = request.form.get("concept", "").strip().upper()
        comments = request.form.get("comments", "").strip().upper()

        application_date = parse_date_ddmmyyyy(fecha_texto)
        amount = parse_amount(amount_texto)

        if not application_date:
            flash("La fecha debe tener el formato dd/mm/yyyy.", "danger")
            return redirect(url_for("registros.nuevo"))

        if not supplier_id or not category_id:
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
            category_id=int(category_id),
            subcategory_id=int(subcategory_id) if subcategory_id else None,
            amount=amount,
            operation_folio=operation_folio or None,
            concept=concept,
            comments=comments or None,
            created_by=current_user.id
        )

        db.session.add(registro)
        db.session.commit()

        flash(f"Registro {unique_key} creado correctamente.", "success")
        return redirect(url_for("registros.index"))

    return render_template(
        "registros/form.html",
        registro=None,
        proveedores=proveedores,
        rubros=rubros,
        modo="nuevo"
    )


@registros_bp.route("/editar/<int:registro_id>", methods=["GET", "POST"])
@login_required
def editar(registro_id):
    registro = Entry.query.get_or_404(registro_id)

    proveedores = Supplier.query.filter_by(is_active=True).order_by(Supplier.business_name.asc()).all()
    rubros = Category.query.filter_by(is_active=True).order_by(Category.name.asc()).all()

    if request.method == "POST":
        fecha_texto = request.form.get("application_date", "").strip()
        supplier_id = request.form.get("supplier_id", "").strip()
        category_id = request.form.get("category_id", "").strip()
        subcategory_id = request.form.get("subcategory_id", "").strip()
        amount_texto = request.form.get("amount", "").strip()
        operation_folio = request.form.get("operation_folio", "").strip().upper()
        concept = request.form.get("concept", "").strip().upper()
        comments = request.form.get("comments", "").strip().upper()

        application_date = parse_date_ddmmyyyy(fecha_texto)
        amount = parse_amount(amount_texto)

        if not application_date:
            flash("La fecha debe tener el formato dd/mm/yyyy.", "danger")
            return redirect(url_for("registros.editar", registro_id=registro.id))

        if not supplier_id or not category_id:
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
        registro.category_id = int(category_id)
        registro.subcategory_id = int(subcategory_id) if subcategory_id else None
        registro.amount = amount
        registro.operation_folio = operation_folio or None
        registro.concept = concept
        registro.comments = comments or None

        db.session.commit()

        flash("Registro actualizado correctamente.", "success")
        return redirect(url_for("registros.index"))

    subrubros_actuales = (
        Subcategory.query
        .filter_by(category_id=registro.category_id, is_active=True)
        .order_by(Subcategory.name.asc())
        .all()
    )

    return render_template(
        "registros/form.html",
        registro=registro,
        proveedores=proveedores,
        rubros=rubros,
        subrubros_actuales=subrubros_actuales,
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


@registros_bp.route("/api/subrubros/<int:rubro_id>")
@login_required
def api_subrubros(rubro_id):
    subrubros = (
        Subcategory.query
        .filter_by(category_id=rubro_id, is_active=True)
        .order_by(Subcategory.name.asc())
        .all()
    )

    data = [
        {
            "id": subrubro.id,
            "name": subrubro.name
        }
        for subrubro in subrubros
    ]

    return jsonify(data)