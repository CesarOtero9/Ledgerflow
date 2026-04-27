from decimal import Decimal
from datetime import datetime

from flask import Blueprint, render_template, request
from flask_login import login_required
from sqlalchemy import func

from app.extensions import db
from app.models import Entry, Supplier, BudgetItem

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

    budget_items = (
        BudgetItem.query
        .filter_by(is_active=True)
        .order_by(BudgetItem.item_code.asc())
        .all()
    )

    entry_filters = []

    if selected_year:
        entry_filters.append(Entry.application_year == selected_year)

    if selected_month:
        entry_filters.append(Entry.application_month_number == selected_month)

    if selected_budget_item_id:
        entry_filters.append(Entry.budget_item_id == selected_budget_item_id)

    if selected_supplier_id:
        entry_filters.append(Entry.supplier_id == selected_supplier_id)

    budget_query = BudgetItem.query.filter(BudgetItem.is_active == True)

    if selected_budget_item_id:
        selected_item = BudgetItem.query.get(selected_budget_item_id)
        if selected_item:
            # Incluye el nodo seleccionado y todos sus descendientes por prefijo
            budget_query = budget_query.filter(
                BudgetItem.item_code == selected_item.item_code
            )
    else:
        selected_item = None

    total_paid = (
        db.session.query(func.coalesce(func.sum(Entry.amount), 0))
        .filter(*entry_filters)
        .scalar()
    )

    total_entries = (
        db.session.query(func.count(Entry.id))
        .filter(*entry_filters)
        .scalar()
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

    total_budget = (
        db.session.query(func.coalesce(func.sum(BudgetItem.budget_amount), 0))
        .select_from(BudgetItem)
        .filter(BudgetItem.is_active == True)
        .filter(
            BudgetItem.id == selected_budget_item_id if selected_budget_item_id else True
        )
        .scalar()
    )

    total_budget_float = money_to_float(total_budget)
    total_paid_float = money_to_float(total_paid)
    total_remaining = total_budget_float - total_paid_float

    if total_budget_float > 0:
        budget_percentage = round((total_paid_float / total_budget_float) * 100, 2)
    else:
        budget_percentage = 0

    budget_status = get_budget_status(budget_percentage)

    latest_entries = (
        Entry.query
        .join(Supplier, Entry.supplier_id == Supplier.id)
        .outerjoin(BudgetItem, Entry.budget_item_id == BudgetItem.id)
        .filter(*entry_filters)
        .order_by(Entry.application_date.desc(), Entry.id.desc())
        .limit(8)
        .all()
    )

    monthly_rows = (
        db.session.query(
            Entry.application_year,
            Entry.application_month_number,
            Entry.application_month,
            func.coalesce(func.sum(Entry.amount), 0).label("total")
        )
        .filter(*entry_filters)
        .group_by(
            Entry.application_year,
            Entry.application_month_number,
            Entry.application_month
        )
        .order_by(
            Entry.application_year.asc(),
            Entry.application_month_number.asc()
        )
        .all()
    )

    monthly_chart = {
        "labels": [f"{row.application_month[:3]} {row.application_year}" for row in monthly_rows],
        "values": [money_to_float(row.total) for row in monthly_rows]
    }

    budget_item_rows = (
        db.session.query(
            BudgetItem.item_code,
            BudgetItem.item_name,
            func.coalesce(func.sum(Entry.amount), 0).label("total")
        )
        .join(Entry, Entry.budget_item_id == BudgetItem.id)
        .filter(*entry_filters)
        .group_by(BudgetItem.item_code, BudgetItem.item_name)
        .order_by(func.sum(Entry.amount).desc())
        .all()
    )

    category_chart = {
        "labels": [f"{row.item_code} - {row.item_name}" for row in budget_item_rows],
        "values": [money_to_float(row.total) for row in budget_item_rows]
    }

    supplier_rows = (
        db.session.query(
            Supplier.business_name,
            func.count(Entry.id).label("operations"),
            func.coalesce(func.sum(Entry.amount), 0).label("total"),
            func.coalesce(func.avg(Entry.amount), 0).label("average")
        )
        .join(Entry, Entry.supplier_id == Supplier.id)
        .filter(*entry_filters)
        .group_by(Supplier.business_name)
        .order_by(func.sum(Entry.amount).desc())
        .limit(15)
        .all()
    )

    supplier_3d_chart = {
        "suppliers": [row.business_name for row in supplier_rows],
        "operations": [int(row.operations) for row in supplier_rows],
        "totals": [money_to_float(row.total) for row in supplier_rows],
        "averages": [money_to_float(row.average) for row in supplier_rows],
    }

    month_item_rows = (
        db.session.query(
            Entry.application_year,
            Entry.application_month_number,
            Entry.application_month,
            BudgetItem.item_name,
            func.coalesce(func.sum(Entry.amount), 0).label("total")
        )
        .join(BudgetItem, Entry.budget_item_id == BudgetItem.id)
        .filter(*entry_filters)
        .group_by(
            Entry.application_year,
            Entry.application_month_number,
            Entry.application_month,
            BudgetItem.item_name
        )
        .order_by(
            Entry.application_year.asc(),
            Entry.application_month_number.asc(),
            BudgetItem.item_name.asc()
        )
        .all()
    )

    unique_months = []
    unique_items = []

    for row in month_item_rows:
        month_label = f"{row.application_month[:3]} {row.application_year}"
        if month_label not in unique_months:
            unique_months.append(month_label)
        if row.item_name not in unique_items:
            unique_items.append(row.item_name)

    z_matrix = []
    for item_name in unique_items:
        item_values = []
        for month in unique_months:
            total_value = 0.0
            for row in month_item_rows:
                row_month_label = f"{row.application_month[:3]} {row.application_year}"
                if row_month_label == month and row.item_name == item_name:
                    total_value = money_to_float(row.total)
                    break
            item_values.append(total_value)
        z_matrix.append(item_values)

    surface_3d_chart = {
        "months": unique_months,
        "categories": unique_items,
        "z": z_matrix
    }

    breakdown_items = (
        BudgetItem.query
        .filter(BudgetItem.is_active == True)
        .order_by(BudgetItem.item_code.asc())
        .all()
    )

    subcategory_breakdown = []

    for item in breakdown_items:
        paid_filters_for_item = list(entry_filters)
        paid_filters_for_item = [
            f for f in paid_filters_for_item
            if "entries.budget_item_id" not in str(f)
        ]

        paid_amount = (
            db.session.query(func.coalesce(func.sum(Entry.amount), 0))
            .filter(*paid_filters_for_item)
            .filter(Entry.budget_item_id == item.id)
            .scalar()
        )

        budget = money_to_float(item.budget_amount)
        paid = money_to_float(paid_amount)
        remaining = budget - paid

        if budget > 0:
            percentage = round((paid / budget) * 100, 2)
        else:
            percentage = 0

        status = get_budget_status(percentage)

        subcategory_breakdown.append({
            "category_name": item.item_code,
            "subcategory_name": item.item_name,
            "budget": budget,
            "paid": paid,
            "remaining": remaining,
            "percentage": percentage,
            "status_label": status["label"],
            "status_class": status["class"],
        })

    subcategory_budget_chart = {
        "labels": [f'{item["category_name"]} - {item["subcategory_name"]}' for item in subcategory_breakdown],
        "budgets": [item["budget"] for item in subcategory_breakdown],
        "paids": [item["paid"] for item in subcategory_breakdown],
        "percentages": [item["percentage"] for item in subcategory_breakdown],
    }

    budget_summary = {
        "total_budget": total_budget_float,
        "total_paid": total_paid_float,
        "total_remaining": total_remaining,
        "percentage": budget_percentage,
        "status_label": budget_status["label"],
        "status_class": budget_status["class"],
        "status_message": budget_status["message"],
    }

    filters = {
        "year": selected_year,
        "month": selected_month,
        "budget_item_id": selected_budget_item_id,
        "supplier_id": selected_supplier_id,
    }

    return render_template(
        "dashboard.html",
        total_amount=total_paid_float,
        total_entries=total_entries,
        total_suppliers_used=total_suppliers_used,
        total_categories_used=total_budget_items_used,
        latest_entries=latest_entries,
        monthly_chart=monthly_chart,
        category_chart=category_chart,
        supplier_3d_chart=supplier_3d_chart,
        surface_3d_chart=surface_3d_chart,
        subcategory_budget_chart=subcategory_budget_chart,
        budget_summary=budget_summary,
        subcategory_breakdown=subcategory_breakdown,
        filters=filters,
        available_years=available_years,
        months=MESES_ES,
        suppliers=suppliers,
        budget_items=budget_items,
    )