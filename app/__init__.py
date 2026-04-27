from flask import Flask
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

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(proveedores_bp)
    app.register_blueprint(rubros_bp)
    app.register_blueprint(registros_bp)
    app.register_blueprint(consultas_bp)

    return app