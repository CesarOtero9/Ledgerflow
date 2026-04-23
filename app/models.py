from datetime import datetime
from flask_login import UserMixin
from app.extensions import db, login_manager


class User(db.Model, UserMixin):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.Enum("admin", "user", "viewer"), nullable=False, default="user")
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=True, onupdate=datetime.utcnow)

    entries = db.relationship("Entry", backref="creator", lazy=True)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


class Supplier(db.Model):
    __tablename__ = "suppliers"

    id = db.Column(db.Integer, primary_key=True)
    rfc = db.Column(db.String(13), unique=True, nullable=False)
    business_name = db.Column(db.String(255), nullable=False)
    tax_regime = db.Column(db.String(255), nullable=True)
    tax_regime_code = db.Column(db.String(10), nullable=True)
    fiscal_zip_code = db.Column(db.String(10), nullable=True)
    fiscal_address = db.Column(db.Text, nullable=True)
    fiscal_certificate_path = db.Column(db.String(500), nullable=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=True, onupdate=datetime.utcnow)

    entries = db.relationship("Entry", backref="supplier", lazy=True)
    documents = db.relationship("SupplierDocument", backref="supplier", lazy=True)


class Category(db.Model):
    __tablename__ = "categories"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), unique=True, nullable=False)
    description = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=True, onupdate=datetime.utcnow)

    subcategories = db.relationship("Subcategory", backref="category", lazy=True)
    entries = db.relationship("Entry", backref="category", lazy=True)


class Subcategory(db.Model):
    __tablename__ = "subcategories"

    id = db.Column(db.Integer, primary_key=True)
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=False)
    name = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=True)

    # Presupuesto asignado al subrubro
    budget_amount = db.Column(db.Numeric(15, 2), nullable=False, default=0)

    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=True, onupdate=datetime.utcnow)

    entries = db.relationship("Entry", backref="subcategory", lazy=True)

    __table_args__ = (
        db.UniqueConstraint("category_id", "name", name="uq_subcategory_per_category"),
    )


class Entry(db.Model):
    __tablename__ = "entries"

    id = db.Column(db.Integer, primary_key=True)

    unique_key = db.Column(db.String(50), unique=True, nullable=False)

    application_date = db.Column(db.Date, nullable=False)
    application_month = db.Column(db.String(20), nullable=False)
    application_month_number = db.Column(db.SmallInteger, nullable=False)
    application_year = db.Column(db.SmallInteger, nullable=False)

    supplier_id = db.Column(db.Integer, db.ForeignKey("suppliers.id"), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=False)
    subcategory_id = db.Column(db.Integer, db.ForeignKey("subcategories.id"), nullable=True)

    amount = db.Column(db.Numeric(15, 2), nullable=False)

    operation_folio = db.Column(db.String(120), nullable=True)
    concept = db.Column(db.Text, nullable=False)
    comments = db.Column(db.Text, nullable=True)

    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=True, onupdate=datetime.utcnow)


class SupplierDocument(db.Model):
    __tablename__ = "supplier_documents"

    id = db.Column(db.Integer, primary_key=True)

    supplier_id = db.Column(db.Integer, db.ForeignKey("suppliers.id"), nullable=False)

    document_type = db.Column(
        db.Enum("fiscal_certificate", "other"),
        nullable=False,
        default="fiscal_certificate"
    )

    original_filename = db.Column(db.String(255), nullable=False)
    stored_filename = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(500), nullable=False)
    file_extension = db.Column(db.String(20), nullable=True)
    file_size_kb = db.Column(db.Numeric(12, 2), nullable=True)

    uploaded_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    uploaded_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)