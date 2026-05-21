# app/alertas/routes.py

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.models import BudgetAlert, BudgetItem
from app.services.budget_alert_service import (
    ALERT_TYPE_LABELS,
    SEVERITY_LABELS,
    acknowledge_alert,
    acknowledge_all_active,
    get_alert_counts,
    refresh_all_budget_alerts,
)


alertas_bp = Blueprint("alertas", __name__, url_prefix="/alertas")


@alertas_bp.route("/")
@login_required
def index():
    # Recalcula al entrar para que la pestaña refleje el estado real actual.
    # No elimina historial; solo activa/resuelve según pagos y presupuestos vigentes.
    refresh_all_budget_alerts(commit=True)

    status = request.args.get("status", "active").strip().lower()
    severity = request.args.get("severity", "").strip().lower()
    alert_type = request.args.get("type", "").strip().upper()
    q = request.args.get("q", "").strip()

    query = (
        BudgetAlert.query
        .join(BudgetItem, BudgetAlert.budget_item_id == BudgetItem.id)
        .order_by(
            BudgetAlert.is_active.desc(),
            BudgetAlert.is_acknowledged.asc(),
            BudgetAlert.updated_at.desc(),
            BudgetAlert.id.desc(),
        )
    )

    if status == "active":
        query = query.filter(BudgetAlert.is_active.is_(True))
    elif status == "unacknowledged":
        query = query.filter(
            BudgetAlert.is_active.is_(True),
            BudgetAlert.is_acknowledged.is_(False),
        )
    elif status == "acknowledged":
        query = query.filter(
            BudgetAlert.is_active.is_(True),
            BudgetAlert.is_acknowledged.is_(True),
        )
    elif status == "resolved":
        query = query.filter(BudgetAlert.is_active.is_(False))
    elif status == "all":
        pass
    else:
        status = "active"
        query = query.filter(BudgetAlert.is_active.is_(True))

    if severity:
        query = query.filter(BudgetAlert.severity == severity)

    if alert_type:
        query = query.filter(BudgetAlert.alert_type == alert_type)

    if q:
        like = f"%{q}%"
        query = query.filter(
            db.or_(
                BudgetAlert.title.like(like),
                BudgetAlert.message.like(like),
                BudgetItem.item_code.like(like),
                BudgetItem.item_name.like(like),
            )
        )

    alerts = query.all()
    counts = get_alert_counts()

    return render_template(
        "alertas/index.html",
        alerts=alerts,
        counts=counts,
        filters={
            "status": status,
            "severity": severity,
            "type": alert_type,
            "q": q,
        },
        alert_type_labels=ALERT_TYPE_LABELS,
        severity_labels=SEVERITY_LABELS,
    )


@alertas_bp.route("/<int:alert_id>/marcar-revisada", methods=["POST"])
@login_required
def marcar_revisada(alert_id):
    alert = acknowledge_alert(alert_id, current_user.id if current_user.is_authenticated else None)

    if alert:
        flash("Alerta marcada como revisada. Seguirá activa hasta que el presupuesto o los pagos la resuelvan.", "success")
    else:
        flash("No se encontró la alerta.", "warning")

    return redirect(request.referrer or url_for("alertas.index"))


@alertas_bp.route("/marcar-todas-revisadas", methods=["POST"])
@login_required
def marcar_todas_revisadas():
    total = acknowledge_all_active(current_user.id if current_user.is_authenticated else None)
    flash(f"Se marcaron {total} alerta(s) como revisadas.", "success")
    return redirect(url_for("alertas.index"))


@alertas_bp.route("/recalcular", methods=["POST"])
@login_required
def recalcular():
    refresh_all_budget_alerts(commit=True)
    flash("Alertas recalculadas correctamente.", "success")
    return redirect(url_for("alertas.index"))
