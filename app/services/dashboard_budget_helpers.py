# app/services/dashboard_budget_helpers.py
# Versión corregida: jerarquía robusta, navegación por código y detalle con presupuestos efectivos completos

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal
import re
from typing import Any, Dict, Iterable, List, Optional, Tuple

MONTHS_ES = {
    1: "ENERO", 2: "FEBRERO", 3: "MARZO", 4: "ABRIL",
    5: "MAYO", 6: "JUNIO", 7: "JULIO", 8: "AGOSTO",
    9: "SEPTIEMBRE", 10: "OCTUBRE", 11: "NOVIEMBRE", 12: "DICIEMBRE",
}

BUDGET_ATTR_CANDIDATES = (
    "budget", "amount", "budget_amount", "assigned_budget",
    "presupuesto", "monto_presupuesto", "annual_budget",
    "monthly_budget", "total_budget", "importe_presupuesto",
)

ENTRY_AMOUNT_CANDIDATES = ("amount", "monto", "total", "importe", "paid_amount")

# False = si un padre tiene hijos, su presupuesto efectivo será la suma de sus hijos.
# True  = si un padre tiene hijos, su presupuesto efectivo será presupuesto propio + hijos.
COUNT_PARENT_OWN_BUDGET_WHEN_HAS_CHILDREN = False

_CODE_RE = re.compile(r"^\s*(\d+(?:\.\d+)*)")


def _money(value: Any) -> Decimal:
    if value is None:
        return Decimal("0")
    try:
        text = str(value).replace("$", "").replace(",", "").strip()
        return Decimal(text or "0")
    except Exception:
        return Decimal("0")


def _safe_int(value: Any) -> Optional[int]:
    try:
        if value is None or value == "" or value == "None":
            return None
        return int(value)
    except Exception:
        return None


def _get_attr(obj: Any, names: Iterable[str], default: Any = None) -> Any:
    for name in names:
        if hasattr(obj, name):
            return getattr(obj, name)
    return default


def _normalize_code(value: Any) -> str:
    """
    Normaliza códigos:
    '13.9.2'        -> '13.9.2'
    '13.9.2 - ABC'  -> '13.9.2'
    '13-9-2'        -> '13.9.2'
    """
    text = str(value or "").strip()
    match = _CODE_RE.match(text)
    if match:
        return match.group(1)

    cleaned = re.sub(r"[^\d]+", ".", text)
    cleaned = re.sub(r"\.+", ".", cleaned).strip(".")
    return cleaned


def _raw_code(item: Any) -> str:
    return str(getattr(item, "item_code", "") or "").strip()


def _code(item: Any) -> str:
    return _normalize_code(_raw_code(item))


def _name(item: Any) -> str:
    return str(getattr(item, "item_name", "") or getattr(item, "name", "") or "").strip()


def _item_id(item: Any) -> Optional[int]:
    return _safe_int(getattr(item, "id", None))


def _get_budget_value(item: Any) -> Decimal:
    return _money(_get_attr(item, BUDGET_ATTR_CANDIDATES, 0))


def _get_entry_amount(entry: Any) -> Decimal:
    return _money(_get_attr(entry, ENTRY_AMOUNT_CANDIDATES, 0))


def _entry_date(entry: Any) -> Optional[date]:
    value = getattr(entry, "application_date", None) or getattr(entry, "fecha", None) or getattr(entry, "date", None)
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return None


def _entry_supplier_name(entry: Any) -> str:
    supplier = getattr(entry, "supplier", None) or getattr(entry, "proveedor", None)
    if supplier is None:
        return "SIN PROVEEDOR"
    return str(
        getattr(supplier, "business_name", None)
        or getattr(supplier, "name", None)
        or getattr(supplier, "nombre", None)
        or "SIN PROVEEDOR"
    ).strip()


def _sort_code_key(code: str) -> Tuple:
    parts = []
    for part in str(code or "").split("."):
        if part.isdigit():
            parts.append((0, int(part)))
        else:
            parts.append((1, part.lower()))
    return tuple(parts)


def is_descendant_code(parent_code: str, child_code: str) -> bool:
    parent_code = _normalize_code(parent_code)
    child_code = _normalize_code(child_code)
    if not parent_code or not child_code:
        return False
    return child_code == parent_code or child_code.startswith(parent_code + ".")


def build_budget_tree(items: Iterable[Any]) -> Tuple[Dict[str, Any], Dict[str, List[str]], Dict[str, Optional[str]]]:
    """Construye un árbol jerárquico a partir de item_code, creando padres virtuales si faltan."""
    by_code: Dict[str, Any] = {}

    for item in items:
        code = _code(item)
        if code:
            by_code[code] = item

    # Crear nodos virtuales para padres faltantes.
    # Esto permite navegar 13 > 13.2 aunque el padre intermedio no exista físicamente.
    all_codes = list(by_code.keys())
    for code in all_codes:
        parts = code.split(".")
        for i in range(1, len(parts)):
            parent = ".".join(parts[:i])
            if parent not in by_code:
                class VirtualItem:
                    pass

                virtual = VirtualItem()
                setattr(virtual, "item_code", parent)
                setattr(virtual, "item_name", f"[Virtual] {parent}")
                setattr(virtual, "id", None)
                by_code[parent] = virtual

    children: Dict[str, List[str]] = defaultdict(list)
    parent_of: Dict[str, Optional[str]] = {code: None for code in by_code}

    for code in by_code:
        parts = code.split(".")
        parent_code = None

        for i in range(len(parts) - 1, 0, -1):
            candidate = ".".join(parts[:i])
            if candidate in by_code:
                parent_code = candidate
                break

        parent_of[code] = parent_code
        if parent_code:
            children[parent_code].append(code)

    for code in children:
        children[code].sort(key=_sort_code_key)

    return by_code, children, parent_of


def get_root_codes(items: Iterable[Any]) -> List[str]:
    by_code, _, parent_of = build_budget_tree(items)
    return sorted([code for code in by_code if parent_of.get(code) is None], key=_sort_code_key)


def calculate_effective_budgets(items: Iterable[Any]) -> Tuple[Dict[str, Decimal], Dict[str, Any], Dict[str, List[str]], Dict[str, Optional[str]]]:
    """
    Calcula presupuesto efectivo por nodo.

    Regla principal:
    - Nodo hoja: usa su presupuesto propio.
    - Nodo padre: usa la suma efectiva de sus hijos.
    - Si el padre no tiene hijos con presupuesto, usa su presupuesto propio como fallback.
    """
    by_code, children, parent_of = build_budget_tree(items)
    memo: Dict[str, Decimal] = {}

    def effective(code: str) -> Decimal:
        if code in memo:
            return memo[code]

        own = _get_budget_value(by_code[code])
        child_codes = children.get(code, [])

        if not child_codes:
            memo[code] = own
            return memo[code]

        child_total = sum((effective(child) for child in child_codes), Decimal("0"))

        if COUNT_PARENT_OWN_BUDGET_WHEN_HAS_CHILDREN:
            memo[code] = own + child_total
        else:
            memo[code] = child_total if child_total > 0 else own

        return memo[code]

    for code in by_code:
        effective(code)

    return memo, by_code, children, parent_of


def find_selected_code(all_items: Iterable[Any], selected_budget_item_id: Any = None) -> Optional[str]:
    selected_id = _safe_int(selected_budget_item_id)
    if not selected_id:
        return None

    for item in all_items:
        if _item_id(item) == selected_id:
            return _code(item)

    return None


def get_descendant_codes(all_codes: Iterable[str], selected_code: str) -> List[str]:
    selected_code = _normalize_code(selected_code)
    return sorted(
        [code for code in all_codes if is_descendant_code(selected_code, code)],
        key=_sort_code_key,
    )


def get_child_and_descendant_codes(selected_code: str, by_code: Dict[str, Any]) -> List[str]:
    """
    Devuelve el nodo seleccionado + todos sus descendientes.
    Esto es lo que usa la tabla Detalle presupuestal por rubro.
    """
    selected_code = _normalize_code(selected_code)
    if not selected_code:
        return []

    return sorted(
        [code for code in by_code if is_descendant_code(selected_code, code)],
        key=_sort_code_key,
    )


def get_entry_budget_code(entry: Any) -> str:
    item = getattr(entry, "budget_item", None) or getattr(entry, "rubro", None)
    if item is not None:
        return _code(item)

    return _normalize_code(
        getattr(entry, "budget_item_code", None)
        or getattr(entry, "rubro_code", None)
        or getattr(entry, "item_code", None)
        or ""
    )


def entry_belongs_to_branch(entry: Any, branch_code: str) -> bool:
    return is_descendant_code(branch_code, get_entry_budget_code(entry))


def make_status(percentage: float) -> Tuple[str, str, str]:
    if percentage >= 100:
        return "danger", "Excedido", "El gasto superó el presupuesto asignado."
    if percentage >= 85:
        return "warning", "Cerca del límite", "Presupuesto muy comprometido; revisar."
    if percentage >= 60:
        return "info", "En ejecución", "Avance controlado, buen ritmo."
    return "success", "Saludable", "Margen disponible, todo fluye con elegancia."


def _pct(paid: Decimal, budget: Decimal) -> float:
    if budget <= 0:
        return 0.0
    return round(float((paid / budget) * Decimal("100")), 2)


def _row_for_code(
    code: str,
    by_code: Dict[str, Any],
    effective_budgets: Dict[str, Decimal],
    paid: Decimal,
    children: Dict[str, List[str]],
    direct_paid_by_code: Optional[Dict[str, Decimal]] = None,
    direct_count_by_code: Optional[Dict[str, int]] = None,
) -> Dict[str, Any]:
    budget = effective_budgets.get(code, Decimal("0"))
    item = by_code[code]
    own_budget = _get_budget_value(item)
    child_count = len(children.get(code, []))

    direct_paid = Decimal("0")
    direct_payment_count = 0

    if direct_paid_by_code is not None:
        direct_paid = _money(direct_paid_by_code.get(code, Decimal("0")))

    if direct_count_by_code is not None:
        direct_payment_count = int(direct_count_by_code.get(code, 0) or 0)

    inherited_paid = paid - direct_paid
    if inherited_paid < 0:
        inherited_paid = Decimal("0")

    remaining = budget - paid
    percentage = _pct(paid, budget)
    status_class, status_label, _ = make_status(percentage)
    name = _name(item)

    has_direct_payments = direct_paid > 0
    has_inherited_payments = inherited_paid > 0

    if has_direct_payments and has_inherited_payments:
        payment_detail_label = "Directo + hijos"
        payment_detail_class = "warning"
        payment_detail_text = "Tiene pagos capturados directamente en este nodo y pagos heredados desde sus hijos."
    elif has_direct_payments:
        payment_detail_label = "Pago directo"
        payment_detail_class = "info"
        payment_detail_text = "El pagado corresponde a movimientos capturados directamente en este nodo."
    elif has_inherited_payments:
        payment_detail_label = "De hijos"
        payment_detail_class = "success"
        payment_detail_text = "El pagado viene acumulado desde nodos hijos, nietos o niveles inferiores."
    else:
        payment_detail_label = "Sin pagos"
        payment_detail_class = "success"
        payment_detail_text = "No hay pagos registrados en este nodo ni en su cadena inferior para los filtros activos."

    if child_count > 0 and budget != own_budget:
        budget_source_label = "Presupuesto por hijos"
        budget_source_text = "Presupuesto efectivo calculado con la suma de sus hijos."
    elif child_count > 0:
        budget_source_label = "Presupuesto propio"
        budget_source_text = "No hay presupuesto en hijos o se está usando el presupuesto propio como respaldo."
    else:
        budget_source_label = "Presupuesto hoja"
        budget_source_text = "Presupuesto capturado directamente en este nodo hoja."

    return {
        "id": _item_id(item),
        "code": code,
        "category_name": code,
        "subcategory_name": name,
        "label": f"{code} - {name}" if name else code,
        "short_label": f"{code} - {name[:34]}" if name else code,
        "level": code.count("."),
        "children_count": child_count,
        "budget": float(budget),
        "own_budget": float(own_budget),
        "budget_source_label": budget_source_label,
        "budget_source_text": budget_source_text,
        "paid": float(paid),
        "direct_paid": float(direct_paid),
        "inherited_paid": float(inherited_paid),
        "direct_payment_count": direct_payment_count,
        "has_direct_payments": has_direct_payments,
        "has_inherited_payments": has_inherited_payments,
        "payment_detail_label": payment_detail_label,
        "payment_detail_class": payment_detail_class,
        "payment_detail_text": payment_detail_text,
        "remaining": float(remaining),
        "percentage": percentage,
        "status_class": status_class,
        "status_label": status_label,
    }


def _ancestor_codes(code: str, by_code: Dict[str, Any]) -> List[str]:
    """
    Devuelve el propio código + sus padres reales/virtuales existentes en el árbol.
    Ejemplo: 13.2.1 -> ['13.2.1', '13.2', '13']
    """
    code = _normalize_code(code)
    if not code:
        return []

    parts = code.split(".")
    ancestors = []

    for i in range(len(parts), 0, -1):
        candidate = ".".join(parts[:i])
        if candidate in by_code:
            ancestors.append(candidate)

    return ancestors


def build_budget_nav(
    selected_code: Optional[str],
    roots: List[str],
    by_code: Dict[str, Any],
    children: Dict[str, List[str]],
    parent_of: Dict[str, Optional[str]],
    effective_budgets: Dict[str, Decimal],
    paid_by_code: Dict[str, Decimal],
) -> Dict[str, Any]:
    path_codes: List[str] = []

    if selected_code:
        current = selected_code
        while current:
            path_codes.append(current)
            current = parent_of.get(current)
        path_codes.reverse()

    nav_codes = children.get(selected_code, []) if selected_code else roots

    def nav_item(code: str) -> Dict[str, Any]:
        item = by_code[code]
        return {
            "id": _item_id(item),
            "code": code,
            "name": _name(item),
            "label": f"{code} - {_name(item)}" if _name(item) else code,
            "budget": float(effective_budgets.get(code, Decimal("0"))),
            "paid": float(paid_by_code.get(code, Decimal("0"))),
            "children_count": len(children.get(code, [])),
            "level": code.count("."),
        }

    return {
        "selected_code": selected_code,
        "path": [nav_item(code) for code in path_codes if code in by_code],
        "children": [nav_item(code) for code in nav_codes if code in by_code],
        "has_children": bool(nav_codes),
    }


def group_small_rows(rows: List[Dict[str, Any]], max_items: int = 14) -> List[Dict[str, Any]]:
    if len(rows) <= max_items:
        return rows

    ordered = sorted(rows, key=lambda row: max(row["paid"], row["budget"]), reverse=True)
    keep = ordered[:max_items]
    rest = ordered[max_items:]

    other_budget = sum(_money(row.get("budget", 0)) for row in rest)
    other_paid = sum(_money(row.get("paid", 0)) for row in rest)
    other_direct_paid = sum(_money(row.get("direct_paid", 0)) for row in rest)
    other_inherited_paid = sum(_money(row.get("inherited_paid", 0)) for row in rest)
    other_direct_count = sum(int(row.get("direct_payment_count", 0) or 0) for row in rest)

    other_remaining = other_budget - other_paid
    other_pct = _pct(other_paid, other_budget)
    status_class, status_label, _ = make_status(other_pct)

    has_direct = other_direct_paid > 0
    has_inherited = other_inherited_paid > 0

    if has_direct and has_inherited:
        payment_detail_label = "Directo + hijos"
        payment_detail_class = "warning"
        payment_detail_text = "Este grupo incluye pagos directos y pagos heredados desde hijos."
    elif has_direct:
        payment_detail_label = "Pago directo"
        payment_detail_class = "info"
        payment_detail_text = "Este grupo concentra pagos capturados directamente en sus nodos."
    elif has_inherited:
        payment_detail_label = "De hijos"
        payment_detail_class = "success"
        payment_detail_text = "Este grupo concentra pagos heredados desde nodos inferiores."
    else:
        payment_detail_label = "Sin pagos"
        payment_detail_class = "success"
        payment_detail_text = "No hay pagos registrados en este grupo."

    keep.append({
        "id": None,
        "code": "OTROS",
        "category_name": "OTROS",
        "subcategory_name": f"{len(rest)} rubros agrupados",
        "label": f"OTROS - {len(rest)} rubros agrupados",
        "short_label": "OTROS",
        "level": 0,
        "children_count": 0,
        "budget": float(other_budget),
        "own_budget": 0.0,
        "budget_source_label": "Agrupado",
        "budget_source_text": "Presupuesto agrupado para facilitar la lectura de la gráfica.",
        "paid": float(other_paid),
        "direct_paid": float(other_direct_paid),
        "inherited_paid": float(other_inherited_paid),
        "direct_payment_count": other_direct_count,
        "has_direct_payments": has_direct,
        "has_inherited_payments": has_inherited,
        "payment_detail_label": payment_detail_label,
        "payment_detail_class": payment_detail_class,
        "payment_detail_text": payment_detail_text,
        "remaining": float(other_remaining),
        "percentage": other_pct,
        "status_class": status_class,
        "status_label": status_label,
    })

    return keep


def build_monthly_chart(entries: Iterable[Any]) -> Dict[str, Any]:
    totals: Dict[int, Decimal] = defaultdict(Decimal)

    for entry in entries:
        d = _entry_date(entry)
        if d:
            totals[d.month] += _get_entry_amount(entry)

    labels = [MONTHS_ES[m] for m in range(1, 13) if m in totals]
    values = [float(totals[m]) for m in range(1, 13) if m in totals]

    return {"labels": labels, "values": values}


def build_category_chart(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    chart_rows = group_small_rows(rows, max_items=12)

    return {
        "labels": [row["label"] for row in chart_rows],
        "codes": [row["code"] for row in chart_rows],
        "values": [row["paid"] for row in chart_rows],
        "direct_paids": [row.get("direct_paid", 0) for row in chart_rows],
        "inherited_paids": [row.get("inherited_paid", 0) for row in chart_rows],
        "direct_payment_counts": [row.get("direct_payment_count", 0) for row in chart_rows],
        "payment_detail_labels": [row.get("payment_detail_label", "Sin pagos") for row in chart_rows],
        "budgets": [row["budget"] for row in chart_rows],
        "remaining": [row["remaining"] for row in chart_rows],
        "percentages": [row["percentage"] for row in chart_rows],
        "total_items": len(rows),
        "displayed_items": len(chart_rows),
    }


def build_supplier_3d_chart(entries: Iterable[Any]) -> Dict[str, Any]:
    totals: Dict[str, Decimal] = defaultdict(Decimal)
    operations: Dict[str, int] = defaultdict(int)

    for entry in entries:
        supplier = _entry_supplier_name(entry)
        totals[supplier] += _get_entry_amount(entry)
        operations[supplier] += 1

    ordered = sorted(totals.keys(), key=lambda s: totals[s], reverse=True)[:25]

    return {
        "suppliers": ordered,
        "totals": [float(totals[s]) for s in ordered],
        "operations": [operations[s] for s in ordered],
        "averages": [float(totals[s] / operations[s]) if operations[s] else 0 for s in ordered],
    }


def build_surface_3d_chart(entries: Iterable[Any], visible_rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    category_codes = [row["code"] for row in visible_rows if row["code"] != "OTROS"][:16]
    month_numbers = list(range(1, 13))
    matrix = [[Decimal("0") for _ in month_numbers] for _ in category_codes]
    direct_matrix = [[Decimal("0") for _ in month_numbers] for _ in category_codes]
    inherited_matrix = [[Decimal("0") for _ in month_numbers] for _ in category_codes]

    for entry in entries:
        d = _entry_date(entry)
        entry_code = get_entry_budget_code(entry)

        if not d or not entry_code:
            continue

        amount = _get_entry_amount(entry)
        month_idx = d.month - 1

        for i, code in enumerate(category_codes):
            if is_descendant_code(code, entry_code):
                matrix[i][month_idx] += amount
                if entry_code == code:
                    direct_matrix[i][month_idx] += amount
                else:
                    inherited_matrix[i][month_idx] += amount
                break

    customdata = []
    for i, _code_value in enumerate(category_codes):
        row = []
        for j, _month in enumerate(month_numbers):
            row.append([
                float(direct_matrix[i][j]),
                float(inherited_matrix[i][j]),
            ])
        customdata.append(row)

    return {
        "months": [MONTHS_ES[m] for m in month_numbers],
        "categories": category_codes,
        "z": [[float(value) for value in row] for row in matrix],
        "direct_z": [[float(value) for value in row] for row in direct_matrix],
        "inherited_z": [[float(value) for value in row] for row in inherited_matrix],
        "customdata": customdata,
    }


def build_dashboard_budget_payload(
    all_items: Iterable[Any],
    filtered_entries: Iterable[Any],
    selected_budget_item_id: Any = None,
    selected_budget_code: Any = None,
) -> Dict[str, Any]:
    """
    Construye toda la información necesaria para el dashboard presupuestal jerárquico.

    all_items:
        Lista completa de BudgetItem activos.

    filtered_entries:
        Entradas ya filtradas por año/mes/proveedor, pero SIN filtrar por rubro.
        El filtro jerárquico de rubro se hace aquí.

    selected_budget_item_id:
        Soporte para el select tradicional por ID.

    selected_budget_code:
        Soporte recomendado para navegación interactiva por código.
        Ejemplo: /dashboard?budget_code=13.2
    """
    all_items = list(all_items or [])
    filtered_entries = list(filtered_entries or [])

    effective_budgets, by_code, children, parent_of = calculate_effective_budgets(all_items)
    roots = sorted([code for code in by_code if parent_of.get(code) is None], key=_sort_code_key)

    # 1) La ruta interactiva debe preferir budget_code.
    selected_code = _normalize_code(selected_budget_code) if selected_budget_code else None

    # 2) Fallback para el select normal de rubro.
    if not selected_code:
        selected_code = find_selected_code(all_items, selected_budget_item_id)

    # 3) Seguridad: si el código no existe en el árbol, regresar a raíces.
    if selected_code and selected_code not in by_code:
        selected_code = None

    active_root_codes = [selected_code] if selected_code else roots

    # Entradas dentro de la rama activa.
    entries_in_scope = []
    for entry in filtered_entries:
        entry_code = get_entry_budget_code(entry)
        if not entry_code:
            continue

        if any(is_descendant_code(root, entry_code) for root in active_root_codes):
            entries_in_scope.append(entry)

    # Pagos acumulados por código: el pago de un nieto suma al nieto, al padre, al abuelo, etc.
    # Además guardamos el pago DIRECTO por código para que en la tabla se note si el movimiento
    # fue capturado exactamente en ese nodo o si viene heredado desde hijos/nietos.
    paid_by_code: Dict[str, Decimal] = defaultdict(Decimal)
    direct_paid_by_code: Dict[str, Decimal] = defaultdict(Decimal)
    direct_count_by_code: Dict[str, int] = defaultdict(int)

    for entry in entries_in_scope:
        amount = _get_entry_amount(entry)
        entry_code = get_entry_budget_code(entry)

        if entry_code in by_code:
            direct_paid_by_code[entry_code] += amount
            direct_count_by_code[entry_code] += 1

        ancestors = _ancestor_codes(entry_code, by_code)

        if ancestors:
            for anc in ancestors:
                paid_by_code[anc] += amount
        else:
            for code in by_code:
                if is_descendant_code(code, entry_code):
                    paid_by_code[code] += amount

    total_budget = sum((effective_budgets.get(code, Decimal("0")) for code in active_root_codes if code), Decimal("0"))
    total_paid = sum((paid_by_code.get(code, Decimal("0")) for code in active_root_codes if code), Decimal("0"))
    total_remaining = total_budget - total_paid
    percentage = _pct(total_paid, total_budget)
    status_class, status_label, status_message = make_status(percentage)

    # ------------------------------------------------------------
    # TABLA DETALLE PRESUPUESTAL
    # ------------------------------------------------------------
    # Antes se mostraban solo hijos directos:
    #   13.2 -> 13.2.1, 13.2.2, 13.2.3...
    # Ahora se muestra el padre seleccionado + todos sus descendientes:
    #   13.2, 13.2.1, 13.2.2, 13.2.3...
    # Así el padre conserva su presupuesto efectivo completo.
    if selected_code:
        detail_codes = get_child_and_descendant_codes(selected_code, by_code)
    else:
        # En vista general muestra todo el árbol, no solo raíces.
        detail_codes = sorted(by_code.keys(), key=_sort_code_key)

    subcategory_breakdown = [
        _row_for_code(
            code=code,
            by_code=by_code,
            effective_budgets=effective_budgets,
            paid=paid_by_code.get(code, Decimal("0")),
            children=children,
            direct_paid_by_code=direct_paid_by_code,
            direct_count_by_code=direct_count_by_code,
        )
        for code in detail_codes
        if code in by_code
    ]
    subcategory_breakdown.sort(key=lambda row: _sort_code_key(row["code"]))

    # ------------------------------------------------------------
    # GRÁFICAS
    # ------------------------------------------------------------
    # Para las gráficas mantenemos una vista más limpia:
    # - si hay seleccionado, muestra hijos directos; si no hay hijos, muestra el seleccionado.
    # - si no hay seleccionado, muestra raíces.
    if selected_code:
        # Para la gráfica "Avance por rubro" incluimos primero el nodo seleccionado
        # y después sus hijos directos. Así se ve claramente si el padre tiene:
        # - pago directo capturado en ese mismo rubro
        # - pago heredado desde hijos/nietos
        direct_children = children.get(selected_code, [])
        chart_visible_codes = [selected_code] + direct_children if direct_children else [selected_code]
    else:
        chart_visible_codes = roots

    chart_rows_base = [
        _row_for_code(
            code=code,
            by_code=by_code,
            effective_budgets=effective_budgets,
            paid=paid_by_code.get(code, Decimal("0")),
            children=children,
            direct_paid_by_code=direct_paid_by_code,
            direct_count_by_code=direct_count_by_code,
        )
        for code in chart_visible_codes
        if code in by_code
    ]
    chart_rows_base.sort(key=lambda row: _sort_code_key(row["code"]))
    chart_rows = group_small_rows(chart_rows_base, max_items=14)

    subcategory_budget_chart = {
        "labels": [row["label"] for row in chart_rows],
        "codes": [row["code"] for row in chart_rows],
        "budgets": [row["budget"] for row in chart_rows],
        "paids": [row["paid"] for row in chart_rows],
        "direct_paids": [row.get("direct_paid", 0) for row in chart_rows],
        "inherited_paids": [row.get("inherited_paid", 0) for row in chart_rows],
        "direct_payment_counts": [row.get("direct_payment_count", 0) for row in chart_rows],
        "payment_detail_labels": [row.get("payment_detail_label", "Sin pagos") for row in chart_rows],
        "remaining": [max(row["remaining"], 0) for row in chart_rows],
        "percentages": [row["percentage"] for row in chart_rows],
        "levels": [row["level"] for row in chart_rows],
        "total_items": len(chart_rows_base),
        "displayed_items": len(chart_rows),
    }

    total_direct_paid = sum((direct_paid_by_code.get(code, Decimal("0")) for code in active_root_codes if code), Decimal("0"))
    total_inherited_paid = total_paid - total_direct_paid
    if total_inherited_paid < 0:
        total_inherited_paid = Decimal("0")

    budget_summary = {
        "total_budget": float(total_budget),
        "total_paid": float(total_paid),
        "total_direct_paid": float(total_direct_paid),
        "total_inherited_paid": float(total_inherited_paid),
        "total_remaining": float(total_remaining),
        "percentage": percentage,
        "status_class": status_class,
        "status_label": status_label,
        "status_message": status_message,
        "selected_code": selected_code,
    }

    budget_nav = build_budget_nav(
        selected_code=selected_code,
        roots=roots,
        by_code=by_code,
        children=children,
        parent_of=parent_of,
        effective_budgets=effective_budgets,
        paid_by_code=paid_by_code,
    )

    monthly_chart = build_monthly_chart(entries_in_scope)
    category_chart = build_category_chart(chart_rows_base)
    supplier_3d_chart = build_supplier_3d_chart(entries_in_scope)
    surface_3d_chart = build_surface_3d_chart(entries_in_scope, chart_rows_base)

    return {
        "budget_summary": budget_summary,
        "subcategory_breakdown": subcategory_breakdown,
        "subcategory_budget_chart": subcategory_budget_chart,
        "budget_nav": budget_nav,
        "budget_path_nav": budget_nav["path"],
        "budget_children_nav": budget_nav["children"],
        "entries_in_scope": entries_in_scope,
        "total_entries": len(entries_in_scope),
        "monthly_chart": monthly_chart,
        "category_chart": category_chart,
        "supplier_3d_chart": supplier_3d_chart,
        "surface_3d_chart": surface_3d_chart,
    }
