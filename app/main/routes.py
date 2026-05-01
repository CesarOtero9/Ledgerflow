from decimal import Decimal
from datetime import datetime

from flask import Blueprint, render_template, request
from flask_login import login_required
from sqlalchemy import func, or_

from app.extensions import db
from app.models import Entry, Supplier, BudgetItem
from app.services.dashboard_budget_helpers import build_dashboard_budget_payload


main_bp = Blueprint("main", __name__)


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


def money_to_float(value):
    if value is None:
        return 0.0
    if isinstance(value, Decimal):
        return float(value)
    return float(value)


def safe_int(value):
    try:
        if value in (None, "", "None"):
            return None
        return int(value)
    except (ValueError, TypeError):
        return None


def get_budget_status(percentage):
    if percentage >= 100:
        return {
            "label": "Excedido",
            "class": "danger",
            "message": "El presupuesto ya fue rebasado."
        }
    if percentage >= 85:
        return {
            "label": "Cerca del límite",
            "class": "warning",
            "message": "El presupuesto está en zona de atención."
        }
    if percentage >= 60:
        return {
            "label": "En seguimiento",
            "class": "info",
            "message": "El avance es moderado."
        }
    return {
        "label": "Bajo control",
        "class": "success",
        "message": "El presupuesto se mantiene saludable."
    }


@main_bp.route("/")
@login_required
def index():
    return dashboard()


@main_bp.route("/test")
def test():
    return "Ruta de prueba funcionando"


@main_bp.route("/dashboard")
@login_required
def dashboard():
    selected_year = safe_int(request.args.get("year"))
    selected_month = safe_int(request.args.get("month"))
    selected_budget_item_id = safe_int(request.args.get("budget_item_id"))
    selected_supplier_id = safe_int(request.args.get("supplier_id"))
    selected_budget_code = request.args.get("budget_code")

    current_year = datetime.now().year

    years_rows = (
        db.session.query(Entry.application_year)
        .distinct()
        .order_by(Entry.application_year.desc())
        .all()
    )
    available_years = [row.application_year for row in years_rows] or [current_year]

    suppliers = (
        Supplier.query
        .filter_by(is_active=True)
        .order_by(Supplier.business_name.asc())
        .all()
    )

    # ------------------------------------------------------------
    # 1. OBTENER TODOS LOS RUBROS
    # ------------------------------------------------------------
    all_budget_items = (
        BudgetItem.query
        .filter_by(is_active=True)
        .order_by(BudgetItem.item_code.asc())
        .all()
    )

    # Forzar inclusión del rubro seleccionado por ID, por si no estuviera en la lista.
    if selected_budget_item_id:
        selected_item = BudgetItem.query.get(selected_budget_item_id)
        if selected_item:
            if not any(item.id == selected_item.id for item in all_budget_items):
                all_budget_items.append(selected_item)

    # ------------------------------------------------------------
    # 2. FILTROS GENERALES PARA ENTRY
    # Año, mes y proveedor. El rubro jerárquico lo resuelve el helper.
    # ------------------------------------------------------------
    entry_filters = []

    if selected_year:
        entry_filters.append(Entry.application_year == selected_year)

    if selected_month:
        entry_filters.append(Entry.application_month_number == selected_month)

    if selected_supplier_id:
        entry_filters.append(Entry.supplier_id == selected_supplier_id)

    filtered_entries = Entry.query.filter(*entry_filters).all()

    # ------------------------------------------------------------
    # 3. LLAMAR AL HELPER JERÁRQUICO
    # ------------------------------------------------------------
    payload = build_dashboard_budget_payload(
        all_items=all_budget_items,
        filtered_entries=filtered_entries,
        selected_budget_item_id=selected_budget_item_id,
        selected_budget_code=selected_budget_code,
    )

    budget_summary = payload["budget_summary"]
    subcategory_breakdown = payload["subcategory_breakdown"]
    subcategory_budget_chart = payload["subcategory_budget_chart"]
    monthly_chart = payload["monthly_chart"]
    category_chart = payload["category_chart"]
    supplier_3d_chart = payload["supplier_3d_chart"]
    surface_3d_chart = payload["surface_3d_chart"]
    budget_path_nav = payload["budget_path_nav"]
    budget_children_nav = payload["budget_children_nav"]
    total_entries = payload["total_entries"]

    # ------------------------------------------------------------
    # 4. ÚLTIMOS REGISTROS FILTRADOS
    # Ahora respeta también la rama presupuestal activa.
    # Ejemplo:
    # budget_code=13.2 trae registros de:
    # 13.2, 13.2.1, 13.2.2, 13.2.3...
    # ------------------------------------------------------------
    latest_entry_filters = list(entry_filters)

    selected_code_for_latest = budget_summary.get("selected_code")

    if selected_code_for_latest:
        latest_entry_filters.append(
            or_(
                BudgetItem.item_code == selected_code_for_latest,
                BudgetItem.item_code.like(f"{selected_code_for_latest}.%")
            )
        )

    latest_entries = (
        Entry.query
        .join(Supplier, Entry.supplier_id == Supplier.id)
        .outerjoin(BudgetItem, Entry.budget_item_id == BudgetItem.id)
        .filter(*latest_entry_filters)
        .order_by(Entry.application_date.desc(), Entry.id.desc())
        .limit(8)
        .all()
    )

    total_suppliers_used = (
        db.session.query(func.count(func.distinct(Entry.supplier_id)))
        .filter(*entry_filters)
        .scalar()
    )

    total_budget_items_used = (
        db.session.query(func.count(func.distinct(Entry.budget_item_id)))
        .filter(*entry_filters)
        .scalar()
    )

    filters = {
        "year": selected_year,
        "month": selected_month,
        "budget_item_id": selected_budget_item_id,
        "budget_code": selected_budget_code,
        "supplier_id": selected_supplier_id,
    }

    # ------------------------------------------------------------
    # 5. RENDERIZAR DASHBOARD
    # ------------------------------------------------------------
    return render_template(
        "dashboard.html",

        # Navegación jerárquica
        budget_path_nav=budget_path_nav,
        budget_children_nav=budget_children_nav,

        # Datos principales del helper
        budget_summary=budget_summary,
        subcategory_breakdown=subcategory_breakdown,
        subcategory_budget_chart=subcategory_budget_chart,
        monthly_chart=monthly_chart,
        category_chart=category_chart,
        supplier_3d_chart=supplier_3d_chart,
        surface_3d_chart=surface_3d_chart,
        total_entries=total_entries,

        # Variables adicionales
        total_amount=budget_summary["total_paid"],
        total_suppliers_used=total_suppliers_used,
        total_categories_used=total_budget_items_used,
        latest_entries=latest_entries,
        filters=filters,
        available_years=available_years,
        months=MESES_ES,
        suppliers=suppliers,
        budget_items=all_budget_items,
    )