from decimal import Decimal

from flask import Blueprint, render_template, request
from flask_login import login_required
from sqlalchemy import func

from app.extensions import db
from app.models import Entry, Supplier, BudgetItem

consultas_bp = Blueprint("consultas", __name__, url_prefix="/consultas")


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


def safe_int_list(values):
    result = []
    for value in values:
        try:
            if value not in ("", None, "None"):
                result.append(int(value))
        except (ValueError, TypeError):
            continue
    return result


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


def is_self_or_descendant(ancestor_code, child_code):
    return child_code == ancestor_code or child_code.startswith(f"{ancestor_code}.")


def build_scope_item_ids(selected_budget_items, all_items):
    """
    Si seleccionas un rubro padre, incluye también hijos y nietos en el scope.
    """
    if not selected_budget_items:
        return []

    selected_map = {item.id: item for item in all_items}
    selected_codes = {
        selected_map[item_id].item_code
        for item_id in selected_budget_items
        if item_id in selected_map
    }

    scope_ids = []
    for item in all_items:
        if any(is_self_or_descendant(code, item.item_code) for code in selected_codes):
            scope_ids.append(item.id)

    return scope_ids


def build_chain_summary(registros, candidate_items):
    """
    Para cada rubro candidato, suma pagos directos + pagos de todos sus descendientes.
    """
    if not registros:
        return []

    involved_codes = {
        registro.budget_item.item_code
        for registro in registros
        if registro.budget_item
    }

    relevant_items = [
        item for item in candidate_items
        if any(is_self_or_descendant(item.item_code, involved_code) for involved_code in involved_codes)
    ]

    relevant_items = sorted(relevant_items, key=lambda x: natural_code_key(x.item_code))

    summary = []

    for item in relevant_items:
        paid = sum(
            money_to_float(registro.amount)
            for registro in registros
            if registro.budget_item and is_self_or_descendant(item.item_code, registro.budget_item.item_code)
        )

        budget = money_to_float(item.budget_amount)
        remaining = budget - paid

        if budget > 0:
            percentage = round((paid / budget) * 100, 2)
        else:
            percentage = 0

        summary.append({
            "budget_item_id": item.id,
            "item_code": item.item_code,
            "item_name": item.item_name,
            "budget": budget,
            "paid": paid,
            "remaining": remaining,
            "percentage": percentage,
            "level": item.level
        })

    return summary


@consultas_bp.route("/proveedores")
@login_required
def proveedores():
    selected_year = request.args.get("year", type=int)
    selected_months = safe_int_list(request.args.getlist("months"))
    selected_suppliers = safe_int_list(request.args.getlist("suppliers"))

    years_rows = (
        db.session.query(Entry.application_year)
        .distinct()
        .order_by(Entry.application_year.desc())
        .all()
    )
    available_years = [row.application_year for row in years_rows]

    suppliers = (
        Supplier.query
        .filter_by(is_active=True)
        .order_by(Supplier.business_name.asc())
        .all()
    )

    all_budget_items = get_sorted_budget_items()

    filters = []

    if selected_year:
        filters.append(Entry.application_year == selected_year)

    if selected_months:
        filters.append(Entry.application_month_number.in_(selected_months))

    if selected_suppliers:
        filters.append(Entry.supplier_id.in_(selected_suppliers))

    registros = (
        Entry.query
        .join(Supplier, Entry.supplier_id == Supplier.id)
        .outerjoin(BudgetItem, Entry.budget_item_id == BudgetItem.id)
        .filter(*filters)
        .order_by(
            Supplier.business_name.asc(),
            Entry.application_date.asc(),
            Entry.id.asc()
        )
        .all()
    )

    total_paid = (
        db.session.query(func.coalesce(func.sum(Entry.amount), 0))
        .filter(*filters)
        .scalar()
    )

    total_records = (
        db.session.query(func.count(Entry.id))
        .filter(*filters)
        .scalar()
    )

    total_paid_float = money_to_float(total_paid)

    provider_summary_rows = (
        db.session.query(
            Supplier.business_name,
            func.coalesce(func.sum(Entry.amount), 0).label("total"),
            func.count(Entry.id).label("records")
        )
        .join(Entry, Entry.supplier_id == Supplier.id)
        .filter(*filters)
        .group_by(Supplier.business_name)
        .order_by(func.sum(Entry.amount).desc())
        .all()
    )

    provider_summary = [
        {
            "supplier_name": row.business_name,
            "total": money_to_float(row.total),
            "records": int(row.records)
        }
        for row in provider_summary_rows
    ]

    # Impacto presupuestal en cadena
    chain_summary = build_chain_summary(registros, all_budget_items)

    # Para el porcentaje general, usa los rubros raíz de la cadena para evitar doble conteo
    root_items_involved = []
    seen_roots = set()

    for row in chain_summary:
        item = next((x for x in all_budget_items if x.id == row["budget_item_id"]), None)
        if not item:
            continue

        current = item
        while current.parent:
            current = current.parent

        if current.id not in seen_roots:
            seen_roots.add(current.id)
            root_items_involved.append(current)

    total_budget = sum(money_to_float(item.budget_amount) for item in root_items_involved)

    if total_budget > 0:
        covered_percentage = round((total_paid_float / total_budget) * 100, 2)
    else:
        covered_percentage = 0

    return render_template(
        "consultas/proveedores.html",
        registros=registros,
        suppliers=suppliers,
        months=MESES_ES,
        available_years=available_years,
        selected_year=selected_year,
        selected_months=selected_months,
        selected_suppliers=selected_suppliers,
        total_paid=total_paid_float,
        total_budget=total_budget,
        total_records=total_records,
        covered_percentage=covered_percentage,
        provider_summary=provider_summary,
        chain_summary=chain_summary
    )


@consultas_bp.route("/rubros")
@login_required
def rubros():
    selected_year = request.args.get("year", type=int)
    selected_months = safe_int_list(request.args.getlist("months"))
    selected_budget_items = safe_int_list(request.args.getlist("budget_items"))
    selected_suppliers = safe_int_list(request.args.getlist("suppliers"))

    years_rows = (
        db.session.query(Entry.application_year)
        .distinct()
        .order_by(Entry.application_year.desc())
        .all()
    )
    available_years = [row.application_year for row in years_rows]

    suppliers = (
        Supplier.query
        .filter_by(is_active=True)
        .order_by(Supplier.business_name.asc())
        .all()
    )

    all_budget_items = get_sorted_budget_items()
    scope_item_ids = build_scope_item_ids(selected_budget_items, all_budget_items)

    filters = []

    if selected_year:
        filters.append(Entry.application_year == selected_year)

    if selected_months:
        filters.append(Entry.application_month_number.in_(selected_months))

    if scope_item_ids:
        filters.append(Entry.budget_item_id.in_(scope_item_ids))

    elif selected_budget_items:
        # Si se seleccionó algo pero por alguna razón no generó scope, no traigas nada
        filters.append(Entry.id == -1)

    if selected_suppliers:
        filters.append(Entry.supplier_id.in_(selected_suppliers))

    registros = (
        Entry.query
        .join(Supplier, Entry.supplier_id == Supplier.id)
        .outerjoin(BudgetItem, Entry.budget_item_id == BudgetItem.id)
        .filter(*filters)
        .order_by(
            BudgetItem.item_code.asc(),
            Entry.application_date.asc(),
            Entry.id.asc()
        )
        .all()
    )

    total_paid = (
        db.session.query(func.coalesce(func.sum(Entry.amount), 0))
        .filter(*filters)
        .scalar()
    )

    total_records = (
        db.session.query(func.count(Entry.id))
        .filter(*filters)
        .scalar()
    )

    total_paid_float = money_to_float(total_paid)

    # Candidatos para el resumen jerárquico:
    if selected_budget_items:
        candidate_items = [
            item for item in all_budget_items
            if item.id in scope_item_ids or item.id in selected_budget_items
        ]
    else:
        candidate_items = all_budget_items

    rubro_summary = build_chain_summary(registros, candidate_items)

    # Presupuesto total del resumen: solo suma rubros raíz dentro del scope mostrado para no duplicar
    visible_items_map = {item.id: item for item in candidate_items}
    involved_visible_ids = {row["budget_item_id"] for row in rubro_summary}

    top_visible_ids = set()
    for item_id in involved_visible_ids:
        item = visible_items_map.get(item_id)
        if not item:
            continue

        parent_in_scope = item.parent_id in visible_items_map
        if not parent_in_scope:
            top_visible_ids.add(item.id)

    total_budget = sum(
        money_to_float(visible_items_map[item_id].budget_amount)
        for item_id in top_visible_ids
        if item_id in visible_items_map
    )

    total_remaining = total_budget - total_paid_float

    if total_budget > 0:
        covered_percentage = round((total_paid_float / total_budget) * 100, 2)
    else:
        covered_percentage = 0

    return render_template(
        "consultas/rubros.html",
        registros=registros,
        suppliers=suppliers,
        budget_items=all_budget_items,
        months=MESES_ES,
        available_years=available_years,
        selected_year=selected_year,
        selected_months=selected_months,
        selected_budget_items=selected_budget_items,
        selected_suppliers=selected_suppliers,
        total_paid=total_paid_float,
        total_budget=total_budget,
        total_remaining=total_remaining,
        total_records=total_records,
        covered_percentage=covered_percentage,
        rubro_summary=rubro_summary
    )


@consultas_bp.route("/contadora")
@login_required
def contadora():
    selected_year = request.args.get("year", type=int)
    selected_suppliers = safe_int_list(request.args.getlist("suppliers"))

    years_rows = (
        db.session.query(Entry.application_year)
        .distinct()
        .order_by(Entry.application_year.desc())
        .all()
    )
    available_years = [row.application_year for row in years_rows]

    suppliers = (
        Supplier.query
        .filter_by(is_active=True)
        .order_by(Supplier.business_name.asc())
        .all()
    )

    filters = []

    if selected_year:
        filters.append(Entry.application_year == selected_year)

    if selected_suppliers:
        filters.append(Entry.supplier_id.in_(selected_suppliers))

    all_items = get_sorted_budget_items()

    summary_rows = []
    grand_totals = {month: 0.0 for month in range(1, 13)}
    grand_total_all = 0.0

    for item in all_items:
        row = {
            "item_code": item.item_code,
            "item_name": item.item_name,
            "total_general": 0.0,
            "months": {}
        }

        for month in range(1, 13):
            monthly_total = (
                db.session.query(func.coalesce(func.sum(Entry.amount), 0))
                .filter(*filters)
                .filter(Entry.budget_item_id == item.id)
                .filter(Entry.application_month_number == month)
                .scalar()
            )

            monthly_total = money_to_float(monthly_total)
            row["months"][month] = monthly_total
            row["total_general"] += monthly_total

            grand_totals[month] += monthly_total

        grand_total_all += row["total_general"]
        summary_rows.append(row)

    total_records = (
        db.session.query(func.count(Entry.id))
        .filter(*filters)
        .scalar()
    )

    return render_template(
        "consultas/contadora.html",
        suppliers=suppliers,
        available_years=available_years,
        selected_year=selected_year,
        selected_suppliers=selected_suppliers,
        months=MESES_ES,
        summary_rows=summary_rows,
        grand_totals=grand_totals,
        grand_total_all=grand_total_all,
        total_records=total_records
    )