'''
from werkzeug.security import generate_password_hash
from app import create_app
from app.extensions import db
from app.models import User

app = create_app()

with app.app_context():
    admin_email = "admin@ledgerflow.local"
    admin_password = "admin123"

    existing_user = User.query.filter_by(email=admin_email).first()

    if existing_user:
        existing_user.username = "admin"
        existing_user.password_hash = generate_password_hash(admin_password)
        existing_user.role = "admin"
        existing_user.is_active = True

        print("Usuario administrador actualizado correctamente.")
    else:
        admin = User(
            username="admin",
            email=admin_email,
            password_hash=generate_password_hash(admin_password),
            role="admin",
            is_active=True
        )

        db.session.add(admin)
        print("Usuario administrador creado correctamente.")

    db.session.commit()

    print("Correo:", admin_email)
    print("Contraseña:", admin_password)

'''
from werkzeug.security import generate_password_hash
from app import create_app
from app.extensions import db
from app.models import User

app = create_app()

with app.app_context():
    existing = User.query.filter_by(username="verde1").first()
    if existing:
        print("El usuario verde1 ya existe")
    else:
        user = User(
            username="verde1",
            email="verde1@ledgerflow.local",
            password_hash=generate_password_hash("123"),
            role="user",
            is_active=True
        )
        db.session.add(user)
        db.session.commit()
        print("Usuario verde1 creado correctamente")