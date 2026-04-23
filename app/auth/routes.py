from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required
from werkzeug.security import check_password_hash

from app.models import User

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        user = User.query.filter_by(email=email).first()

        if not user:
            flash("El usuario no existe.", "danger")
            return redirect(url_for("auth.login"))

        if not check_password_hash(user.password_hash, password):
            flash("Contraseña incorrecta.", "danger")
            return redirect(url_for("auth.login"))

        if not user.is_active:
            flash("El usuario está inactivo.", "warning")
            return redirect(url_for("auth.login"))

        login_user(user)
        return redirect(url_for("main.dashboard"))

    return render_template("login.html")


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login"))