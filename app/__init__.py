# app/__init__.py

from flask import Flask
from flask_login import current_user
from sqlalchemy.exc import SQLAlchemyError

from config import Config
from app.extensions import db, login_manager


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    login_manager.init_app(app)

    from app.auth.routes import auth_bp
    from app.main.routes import main_bp
    from app.proveedores.routes import proveedores_bp
    from app.rubros.routes import rubros_bp
    from app.registros.routes import registros_bp
    from app.consultas.routes import consultas_bp
    from app.alertas.routes import alertas_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(proveedores_bp)
    app.register_blueprint(rubros_bp)
    app.register_blueprint(registros_bp)
    app.register_blueprint(consultas_bp)
    app.register_blueprint(alertas_bp)

    @app.context_processor
    def inject_budget_alerts_count():
        try:
            if current_user.is_authenticated:
                from app.services.budget_alert_service import get_unacknowledged_active_count
                return {"budget_alert_count": get_unacknowledged_active_count()}
        except (SQLAlchemyError, Exception):
            # Mientras no corras la migración, el header no debe tumbar la app.
            try:
                db.session.rollback()
            except Exception:
                pass

        return {"budget_alert_count": 0}

    return app
