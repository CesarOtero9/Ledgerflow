from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from sqlalchemy import or_
from werkzeug.security import check_password_hash

from app.extensions import db
from app.models import User

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    if request.method == "POST":
        login_value = request.form.get("login", "").strip()
        password = request.form.get("password", "").strip()

        if not login_value or not password:
            flash("Ingresa usuario/correo y contraseña.", "danger")
            return redirect(url_for("auth.login"))

        user = User.query.filter(
            or_(
                User.username == login_value,
                User.email == login_value
            )
        ).first()

        if not user or not check_password_hash(user.password_hash, password):
            flash("Credenciales incorrectas.", "danger")
            return redirect(url_for("auth.login"))

        if not user.is_active:
            flash("Tu usuario está inactivo.", "warning")
            return redirect(url_for("auth.login"))

        login_user(user)
        return redirect(url_for("main.dashboard"))

    return render_template("auth/login.html")


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login"))