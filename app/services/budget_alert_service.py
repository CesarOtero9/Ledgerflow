# app/services/budget_alert_service.py
# Servicio central de alertas presupuestales de LedgerFlow.
# Regla clave:
# - Los pagos capturados en hijos suben a padres.
# - Los pagos capturados en padres NO bajan automáticamente a hijos.
# - Las alertas no se eliminan al verse; se resuelven solo cuando cambia pago/presupuesto y ya no aplica.

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Dict, Iterable, List, Optional, Set, Tuple

from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError

from app.extensions import db
from app.models import BudgetAlert, BudgetItem, Entry


THRESHOLD_ALERT = "THRESHOLD"
DIRECT_PARENT_PAYMENT_ALERT = "DIRECT_PAYMENT_ON_PARENT"
NO_BUDGET_WITH_PAYMENT_ALERT = "NO_BUDGET_WITH_PAYMENT"

DEFAULT_THRESHOLD = Decimal("70.00")
RISK_THRESHOLD = Decimal("85.00")
EXCEEDED_THRESHOLD = Decimal("100.00")

SEVERITY_RANK = {
    "info": 1,
    "warning": 2,
    "danger": 3,
    "critical": 4,
}

ALERT_TYPE_LABELS = {
    THRESHOLD_ALERT: "Umbral presupuestal",
    DIRECT_PARENT_PAYMENT_ALERT: "Pago directo en rubro padre",
    NO_BUDGET_WITH_PAYMENT_ALERT: "Pago sin presupuesto",
}

SEVERITY_LABELS = {
    "info": "Atención",
    "warning": "Riesgo",
    "danger": "Excedido",
    "critical": "Crítico",
}


def _money(value) -> Decimal:
    if value is None:
        return Decimal("0.00")

    if isinstance(value, Decimal):
        return value

    try:
        text = str(value).replace("$", "").replace(",", "").replace("MXN", "").strip()
        return Decimal(text or "0.00")
    except (InvalidOperation, ValueError, TypeError):
        return Decimal("0.00")


def _pct(paid: Decimal, budget: Decimal) -> Decimal:
    if budget <= 0:
        return Decimal("0.00")
    return ((paid / budget) * Decimal("100")).quantize(Decimal("0.01"))


def _float_money(value: Decimal) -> float:
    return float(_money(value))


def _format_money(value: Decimal) -> str:
    return f"${float(_money(value)):,.2f}"


def _format_pct(value: Decimal) -> str:
    return f"{float(_money(value)):,.2f}%"


def _severity_for_percentage(percentage: Decimal) -> Tuple[str, Decimal, str]:
    if percentage >= EXCEEDED_THRESHOLD:
        return "danger", EXCEEDED_THRESHOLD, "Presupuesto excedido"
    if percentage >= RISK_THRESHOLD:
        return "warning", RISK_THRESHOLD, "Cerca del límite"
    if percentage >= DEFAULT_THRESHOLD:
        return "info", DEFAULT_THRESHOLD, "Umbral superado"
    return "info", Decimal("0.00"), "Saludable"


def _children_map(items: Iterable[BudgetItem]) -> Dict[int, List[int]]:
    children_by_parent: Dict[int, List[int]] = defaultdict(list)

    for item in items:
        if item.parent_id:
            children_by_parent[item.parent_id].append(item.id)

    return children_by_parent


def _ancestor_ids(item_id: Optional[int], items_by_id: Dict[int, BudgetItem]) -> List[int]:
    if not item_id or item_id not in items_by_id:
        return []

    ancestors = []
    current = items_by_id.get(item_id)

    while current:
        ancestors.append(current.id)
        if not current.parent_id:
            break
        current = items_by_id.get(current.parent_id)

    return ancestors


def _descendant_ids(item_id: int, children_by_parent: Dict[int, List[int]]) -> List[int]:
    result = []
    stack = list(children_by_parent.get(item_id, []))

    while stack:
        current_id = stack.pop()
        result.append(current_id)
        stack.extend(children_by_parent.get(current_id, []))

    return result


def _effective_budgets(
    items_by_id: Dict[int, BudgetItem],
    children_by_parent: Dict[int, List[int]],
) -> Dict[int, Decimal]:
    memo: Dict[int, Decimal] = {}

    def effective(item_id: int) -> Decimal:
        if item_id in memo:
            return memo[item_id]

        item = items_by_id[item_id]
        own_budget = _money(item.budget_amount)
        children = children_by_parent.get(item_id, [])

        if not children:
            memo[item_id] = own_budget
            return memo[item_id]

        children_total = sum((effective(child_id) for child_id in children), Decimal("0.00"))

        # Misma regla de negocio del dashboard: si hay hijos, el padre hereda la suma efectiva.
        # Si los hijos no tienen presupuesto, se usa el presupuesto propio del padre como fallback.
        memo[item_id] = children_total if children_total > 0 else own_budget
        return memo[item_id]

    for item_id in items_by_id:
        effective(item_id)

    return memo


def _direct_paid_by_item() -> Dict[int, Decimal]:
    rows = (
        db.session.query(
            Entry.budget_item_id,
            func.coalesce(func.sum(Entry.amount), 0),
        )
        .filter(Entry.budget_item_id.isnot(None))
        .group_by(Entry.budget_item_id)
        .all()
    )

    return {int(item_id): _money(total) for item_id, total in rows if item_id}


def _paid_rollup_by_item(
    direct_paid: Dict[int, Decimal],
    items_by_id: Dict[int, BudgetItem],
) -> Dict[int, Decimal]:
    paid_by_item: Dict[int, Decimal] = defaultdict(lambda: Decimal("0.00"))

    for item_id, amount in direct_paid.items():
        for ancestor_id in _ancestor_ids(item_id, items_by_id):
            paid_by_item[ancestor_id] += amount

    return paid_by_item


def _target_scope(
    target_item_ids: Optional[Iterable[int]],
    items_by_id: Dict[int, BudgetItem],
    children_by_parent: Dict[int, List[int]],
) -> Set[int]:
    if not target_item_ids:
        return set(items_by_id.keys())

    scope: Set[int] = set()

    for raw_id in target_item_ids:
        if raw_id is None:
            continue
        try:
            item_id = int(raw_id)
        except (TypeError, ValueError):
            continue

        if item_id not in items_by_id:
            continue

        scope.add(item_id)
        scope.update(_ancestor_ids(item_id, items_by_id))
        scope.update(_descendant_ids(item_id, children_by_parent))

    return scope


def _alert_title_prefix(severity: str, alert_type: str) -> str:
    if alert_type == DIRECT_PARENT_PAYMENT_ALERT:
        return "Pago directo en rubro padre"
    if alert_type == NO_BUDGET_WITH_PAYMENT_ALERT:
        return "Rubro sin presupuesto con pagos"
    return SEVERITY_LABELS.get(severity, "Alerta")


def _upsert_alert(
    *,
    budget_item: BudgetItem,
    alert_type: str,
    severity: str,
    threshold: Optional[Decimal],
    current_percentage: Optional[Decimal],
    budget_amount: Decimal,
    paid_amount: Decimal,
    remaining_amount: Decimal,
    title: str,
    message: str,
) -> BudgetAlert:
    alert = (
        BudgetAlert.query
        .filter_by(
            budget_item_id=budget_item.id,
            alert_type=alert_type,
            is_active=True,
        )
        .first()
    )

    now = datetime.utcnow()
    threshold = threshold if threshold is not None else Decimal("0.00")
    current_percentage = current_percentage if current_percentage is not None else Decimal("0.00")

    if alert is None:
        alert = BudgetAlert(
            budget_item_id=budget_item.id,
            alert_type=alert_type,
            severity=severity,
            threshold=threshold,
            current_percentage=current_percentage,
            budget_amount=budget_amount,
            paid_amount=paid_amount,
            remaining_amount=remaining_amount,
            title=title,
            message=message,
            is_active=True,
            is_acknowledged=False,
            created_at=now,
            updated_at=now,
            last_triggered_at=now,
        )
        db.session.add(alert)
        return alert

    old_rank = SEVERITY_RANK.get(alert.severity or "info", 0)
    new_rank = SEVERITY_RANK.get(severity or "info", 0)
    old_threshold = _money(alert.threshold)

    # Si la alerta escala de nivel, vuelve a aparecer en la campanita.
    if new_rank > old_rank or threshold > old_threshold:
        alert.is_acknowledged = False
        alert.acknowledged_at = None
        alert.acknowledged_by = None

    alert.severity = severity
    alert.threshold = threshold
    alert.current_percentage = current_percentage
    alert.budget_amount = budget_amount
    alert.paid_amount = paid_amount
    alert.remaining_amount = remaining_amount
    alert.title = title
    alert.message = message
    alert.is_active = True
    alert.resolved_at = None
    alert.resolved_reason = None
    alert.updated_at = now
    alert.last_triggered_at = now

    return alert


def _resolve_alert(budget_item_id: int, alert_type: str, reason: str) -> None:
    active_alerts = (
        BudgetAlert.query
        .filter_by(
            budget_item_id=budget_item_id,
            alert_type=alert_type,
            is_active=True,
        )
        .all()
    )

    now = datetime.utcnow()

    for alert in active_alerts:
        alert.is_active = False
        alert.resolved_at = now
        alert.resolved_reason = reason
        alert.updated_at = now


def refresh_budget_alerts(target_item_ids: Optional[Iterable[int]] = None) -> None:
    """Recalcula alertas presupuestales para todos los rubros o para una rama específica."""
    items = BudgetItem.query.all()

    if not items:
        return

    items_by_id = {item.id: item for item in items}
    children_by_parent = _children_map(items)
    effective_budget_by_id = _effective_budgets(items_by_id, children_by_parent)
    direct_paid_by_id = _direct_paid_by_item()
    paid_by_id = _paid_rollup_by_item(direct_paid_by_id, items_by_id)
    target_ids = _target_scope(target_item_ids, items_by_id, children_by_parent)

    for item_id in target_ids:
        item = items_by_id[item_id]

        # Si está inactivo, resolvemos sus alertas activas para evitar ruido.
        if not item.is_active:
            _resolve_alert(item.id, THRESHOLD_ALERT, "El rubro fue desactivado.")
            _resolve_alert(item.id, DIRECT_PARENT_PAYMENT_ALERT, "El rubro fue desactivado.")
            _resolve_alert(item.id, NO_BUDGET_WITH_PAYMENT_ALERT, "El rubro fue desactivado.")
            continue

        budget = _money(effective_budget_by_id.get(item.id, Decimal("0.00")))
        paid = _money(paid_by_id.get(item.id, Decimal("0.00")))
        direct_paid = _money(direct_paid_by_id.get(item.id, Decimal("0.00")))
        remaining = budget - paid
        children_count = len(children_by_parent.get(item.id, []))
        percentage = _pct(paid, budget)

        # 1) Alerta de umbral presupuestal.
        if budget > 0 and percentage >= DEFAULT_THRESHOLD:
            severity, threshold, level_label = _severity_for_percentage(percentage)
            title = f"{level_label}: {item.item_code} - {item.item_name}"
            message = (
                f"El rubro {item.item_code} - {item.item_name} alcanzó "
                f"{_format_pct(percentage)} de su presupuesto efectivo. "
                f"Presupuesto: {_format_money(budget)} | Pagado: {_format_money(paid)} | "
                f"Pendiente: {_format_money(remaining)}."
            )
            _upsert_alert(
                budget_item=item,
                alert_type=THRESHOLD_ALERT,
                severity=severity,
                threshold=threshold,
                current_percentage=percentage,
                budget_amount=budget,
                paid_amount=paid,
                remaining_amount=remaining,
                title=title,
                message=message,
            )
        else:
            _resolve_alert(
                item.id,
                THRESHOLD_ALERT,
                "El rubro bajó del umbral presupuestal configurado.",
            )

        # 2) Pago directo en padre con hijos.
        # No se reparte a hijos; solo alerta que debe revisarse o reclasificarse.
        if children_count > 0 and direct_paid > 0:
            title = f"Pago directo en padre: {item.item_code} - {item.item_name}"
            message = (
                f"El rubro {item.item_code} - {item.item_name} tiene {children_count} hijo(s), "
                f"pero recibió pagos directos por {_format_money(direct_paid)}. "
                "Ese pago afecta al padre, pero no se distribuye automáticamente entre los hijos. "
                "Revisa si debe reclasificarse a un subrubro."
            )
            _upsert_alert(
                budget_item=item,
                alert_type=DIRECT_PARENT_PAYMENT_ALERT,
                severity="warning",
                threshold=None,
                current_percentage=percentage,
                budget_amount=budget,
                paid_amount=paid,
                remaining_amount=remaining,
                title=title,
                message=message,
            )
        else:
            _resolve_alert(
                item.id,
                DIRECT_PARENT_PAYMENT_ALERT,
                "El rubro ya no tiene pagos directos pendientes de clasificación.",
            )

        # 3) Rubro sin presupuesto pero con pagos.
        if budget <= 0 and paid > 0:
            title = f"Rubro sin presupuesto: {item.item_code} - {item.item_name}"
            message = (
                f"El rubro {item.item_code} - {item.item_name} tiene pagos por {_format_money(paid)}, "
                "pero no tiene presupuesto efectivo asignado."
            )
            _upsert_alert(
                budget_item=item,
                alert_type=NO_BUDGET_WITH_PAYMENT_ALERT,
                severity="danger",
                threshold=None,
                current_percentage=Decimal("0.00"),
                budget_amount=budget,
                paid_amount=paid,
                remaining_amount=remaining,
                title=title,
                message=message,
            )
        else:
            _resolve_alert(
                item.id,
                NO_BUDGET_WITH_PAYMENT_ALERT,
                "El rubro ya tiene presupuesto o ya no tiene pagos asociados.",
            )


def refresh_all_budget_alerts(commit: bool = False) -> None:
    refresh_budget_alerts(target_item_ids=None)
    if commit:
        db.session.commit()


def refresh_alerts_for_budget_item_ids(item_ids: Iterable[Optional[int]], commit: bool = False) -> None:
    ids = {item_id for item_id in item_ids if item_id}
    if not ids:
        return

    refresh_budget_alerts(target_item_ids=ids)

    if commit:
        db.session.commit()


def refresh_alerts_after_entry_change(
    old_budget_item_id: Optional[int] = None,
    new_budget_item_id: Optional[int] = None,
    commit: bool = False,
) -> None:
    ids = set()
    if old_budget_item_id:
        ids.add(old_budget_item_id)
    if new_budget_item_id:
        ids.add(new_budget_item_id)

    refresh_alerts_for_budget_item_ids(ids, commit=commit)


def acknowledge_alert(alert_id: int, user_id: Optional[int]) -> Optional[BudgetAlert]:
    alert = BudgetAlert.query.get(alert_id)
    if not alert:
        return None

    alert.is_acknowledged = True
    alert.acknowledged_at = datetime.utcnow()
    alert.acknowledged_by = user_id
    alert.updated_at = datetime.utcnow()
    db.session.commit()
    return alert


def acknowledge_all_active(user_id: Optional[int]) -> int:
    alerts = BudgetAlert.query.filter_by(is_active=True, is_acknowledged=False).all()
    now = datetime.utcnow()

    for alert in alerts:
        alert.is_acknowledged = True
        alert.acknowledged_at = now
        alert.acknowledged_by = user_id
        alert.updated_at = now

    db.session.commit()
    return len(alerts)


def get_unacknowledged_active_count() -> int:
    try:
        return (
            BudgetAlert.query
            .filter_by(is_active=True, is_acknowledged=False)
            .count()
        )
    except SQLAlchemyError:
        # Útil mientras aún no se ha corrido la migración.
        db.session.rollback()
        return 0


def get_alert_counts() -> Dict[str, int]:
    try:
        return {
            "active": BudgetAlert.query.filter_by(is_active=True).count(),
            "unacknowledged": BudgetAlert.query.filter_by(is_active=True, is_acknowledged=False).count(),
            "resolved": BudgetAlert.query.filter_by(is_active=False).count(),
            "critical": BudgetAlert.query.filter_by(is_active=True, severity="critical").count(),
            "danger": BudgetAlert.query.filter_by(is_active=True, severity="danger").count(),
            "warning": BudgetAlert.query.filter_by(is_active=True, severity="warning").count(),
            "info": BudgetAlert.query.filter_by(is_active=True, severity="info").count(),
        }
    except SQLAlchemyError:
        db.session.rollback()
        return {
            "active": 0,
            "unacknowledged": 0,
            "resolved": 0,
            "critical": 0,
            "danger": 0,
            "warning": 0,
            "info": 0,
        }
