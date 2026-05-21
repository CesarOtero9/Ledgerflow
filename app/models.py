# app/models.py

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
    business_name = db.Column(db.String(255), nullable=False, index=True)
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


class BudgetItem(db.Model):
    __tablename__ = "budget_items"

    id = db.Column(db.Integer, primary_key=True)
    item_code = db.Column(db.String(50), unique=True, nullable=False)
    item_name = db.Column(db.String(255), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey("budget_items.id"), nullable=True, index=True)
    level = db.Column(db.Integer, nullable=False, default=1, index=True)
    budget_amount = db.Column(db.Numeric(15, 2), nullable=False, default=0)
    is_active = db.Column(db.Boolean, nullable=False, default=True, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=True, onupdate=datetime.utcnow)

    parent = db.relationship(
        "BudgetItem",
        remote_side=[id],
        backref=db.backref("children", lazy=True),
    )

    entries = db.relationship("Entry", backref="budget_item", lazy=True)
    alerts = db.relationship("BudgetAlert", backref="budget_item", lazy=True)

    @property
    def is_root(self):
        return self.parent_id is None

    @property
    def display_name(self):
        return f"{self.item_code} - {self.item_name}"


class Category(db.Model):
    __tablename__ = "categories"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), unique=True, nullable=False)
    description = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=True, onupdate=datetime.utcnow)

    subcategories = db.relationship("Subcategory", backref="category", lazy=True)


class Subcategory(db.Model):
    __tablename__ = "subcategories"

    id = db.Column(db.Integer, primary_key=True)
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=False, index=True)
    name = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=True)
    budget_amount = db.Column(db.Numeric(15, 2), nullable=False, default=0)
    is_active = db.Column(db.Boolean, nullable=False, default=True, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=True, onupdate=datetime.utcnow)


class Entry(db.Model):
    __tablename__ = "entries"

    id = db.Column(db.Integer, primary_key=True)
    unique_key = db.Column(db.String(50), unique=True, nullable=False)
    application_date = db.Column(db.Date, nullable=False, index=True)
    application_month = db.Column(db.String(20), nullable=False)
    application_month_number = db.Column(db.SmallInteger, nullable=False)
    application_year = db.Column(db.SmallInteger, nullable=False, index=True)
    supplier_id = db.Column(db.Integer, db.ForeignKey("suppliers.id"), nullable=False, index=True)
    budget_item_id = db.Column(db.Integer, db.ForeignKey("budget_items.id"), nullable=True, index=True)
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=True, index=True)
    subcategory_id = db.Column(db.Integer, db.ForeignKey("subcategories.id"), nullable=True, index=True)
    amount = db.Column(db.Numeric(15, 2), nullable=False, index=True)
    operation_folio = db.Column(db.String(120), nullable=True)
    concept = db.Column(db.Text, nullable=False)
    comments = db.Column(db.Text, nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=True, onupdate=datetime.utcnow)

    documents = db.relationship(
        "EntryDocument",
        backref="entry",
        lazy=True,
        cascade="all, delete-orphan",
    )


class EntryDocument(db.Model):
    __tablename__ = "entry_documents"

    id = db.Column(db.Integer, primary_key=True)
    entry_id = db.Column(db.Integer, db.ForeignKey("entries.id"), nullable=False, index=True)
    document_type = db.Column(
        db.Enum("payment_request", "payment_receipt", "gmail_comments"),
        nullable=False,
        index=True,
    )
    original_filename = db.Column(db.String(255), nullable=False)
    stored_filename = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(500), nullable=False)
    file_extension = db.Column(db.String(20), nullable=True)
    mime_type = db.Column(db.String(120), nullable=True)
    file_size_kb = db.Column(db.Numeric(12, 2), nullable=True)
    uploaded_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    uploaded_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)


class SupplierDocument(db.Model):
    __tablename__ = "supplier_documents"

    id = db.Column(db.Integer, primary_key=True)
    supplier_id = db.Column(db.Integer, db.ForeignKey("suppliers.id"), nullable=False, index=True)
    document_type = db.Column(
        db.Enum("fiscal_certificate", "other"),
        nullable=False,
        default="fiscal_certificate",
    )
    original_filename = db.Column(db.String(255), nullable=False)
    stored_filename = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(500), nullable=False)
    file_extension = db.Column(db.String(20), nullable=True)
    file_size_kb = db.Column(db.Numeric(12, 2), nullable=True)
    uploaded_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    uploaded_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)


class BudgetAlert(db.Model):
    __tablename__ = "budget_alerts"

    id = db.Column(db.Integer, primary_key=True)
    budget_item_id = db.Column(db.Integer, db.ForeignKey("budget_items.id"), nullable=False, index=True)

    alert_type = db.Column(db.String(50), nullable=False, index=True)
    severity = db.Column(db.String(20), nullable=False, index=True)

    threshold = db.Column(db.Numeric(10, 2), nullable=True)
    current_percentage = db.Column(db.Numeric(10, 2), nullable=True)

    budget_amount = db.Column(db.Numeric(15, 2), nullable=True)
    paid_amount = db.Column(db.Numeric(15, 2), nullable=True)
    remaining_amount = db.Column(db.Numeric(15, 2), nullable=True)

    title = db.Column(db.String(255), nullable=False)
    message = db.Column(db.Text, nullable=False)

    is_active = db.Column(db.Boolean, nullable=False, default=True, index=True)
    is_acknowledged = db.Column(db.Boolean, nullable=False, default=False, index=True)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=True, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_triggered_at = db.Column(db.DateTime, nullable=True)

    acknowledged_at = db.Column(db.DateTime, nullable=True)
    acknowledged_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)

    resolved_at = db.Column(db.DateTime, nullable=True)
    resolved_reason = db.Column(db.String(255), nullable=True)

    acknowledged_user = db.relationship("User", foreign_keys=[acknowledged_by], lazy=True)

    @property
    def status_label(self):
        if self.is_active and not self.is_acknowledged:
            return "No revisada"
        if self.is_active and self.is_acknowledged:
            return "Revisada"
        return "Resuelta"

    @property
    def type_label(self):
        labels = {
            "THRESHOLD": "Umbral presupuestal",
            "DIRECT_PARENT_PAYMENT": "Pago directo en padre",
            "NO_BUDGET_WITH_PAYMENT": "Pago sin presupuesto",
        }
        return labels.get(self.alert_type, self.alert_type)
