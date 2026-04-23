import os
import uuid

from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename

from app.extensions import db
from app.models import Supplier, SupplierDocument
from app.utils.pdf_extractor import PDFExtractor

proveedores_bp = Blueprint("proveedores", __name__, url_prefix="/proveedores")

ALLOWED_EXTENSIONS = {"pdf"}


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def save_constancia_file(file):
    if not file or file.filename == "":
        return None

    if not allowed_file(file.filename):
        return None

    upload_folder = current_app.config["UPLOAD_FOLDER"]
    os.makedirs(upload_folder, exist_ok=True)

    original_filename = secure_filename(file.filename)
    extension = original_filename.rsplit(".", 1)[1].lower()
    stored_filename = f"{uuid.uuid4().hex}.{extension}"
    file_path = os.path.join(upload_folder, stored_filename)

    file.save(file_path)

    return {
        "original_filename": original_filename,
        "stored_filename": stored_filename,
        "file_path": file_path,
        "file_extension": extension,
        "file_size_kb": round(os.path.getsize(file_path) / 1024, 2)
    }


@proveedores_bp.route("/")
@login_required
def index():
    proveedores = Supplier.query.order_by(Supplier.created_at.desc()).all()
    return render_template("proveedores/index.html", proveedores=proveedores)


@proveedores_bp.route("/nuevo", methods=["GET", "POST"])
@login_required
def nuevo():
    extracted_data = None

    if request.method == "POST":
        action = request.form.get("action", "save")

        rfc = request.form.get("rfc", "").strip().upper()
        business_name = request.form.get("business_name", "").strip().upper()
        tax_regime = request.form.get("tax_regime", "").strip().upper()
        tax_regime_code = request.form.get("tax_regime_code", "").strip()
        fiscal_zip_code = request.form.get("fiscal_zip_code", "").strip()
        fiscal_address = request.form.get("fiscal_address", "").strip().upper()

        constancia_file = request.files.get("constancia_pdf")

        if action == "extract":
            if not constancia_file or constancia_file.filename == "":
                flash("Selecciona una constancia fiscal en PDF para extraer los datos.", "warning")
                return render_template(
                    "proveedores/form.html",
                    proveedor=None,
                    modo="nuevo",
                    extracted_data=None
                )

            if not allowed_file(constancia_file.filename):
                flash("Solo se permiten archivos PDF.", "danger")
                return render_template(
                    "proveedores/form.html",
                    proveedor=None,
                    modo="nuevo",
                    extracted_data=None
                )

            saved_file = save_constancia_file(constancia_file)

            if not saved_file:
                flash("No se pudo guardar el archivo PDF.", "danger")
                return render_template(
                    "proveedores/form.html",
                    proveedor=None,
                    modo="nuevo",
                    extracted_data=None
                )

            extractor = PDFExtractor(saved_file["file_path"])
            extracted_data = extractor.extract_data()

            extracted_data["pending_file"] = saved_file

            flash("Datos extraídos correctamente. Revisa la información antes de guardar.", "success")

            return render_template(
                "proveedores/form.html",
                proveedor=None,
                modo="nuevo",
                extracted_data=extracted_data
            )

        if action == "save":
            pending_file_path = request.form.get("pending_file_path", "").strip()
            pending_original_filename = request.form.get("pending_original_filename", "").strip()
            pending_stored_filename = request.form.get("pending_stored_filename", "").strip()
            pending_file_extension = request.form.get("pending_file_extension", "").strip()
            pending_file_size_kb = request.form.get("pending_file_size_kb", "").strip()

            if constancia_file and constancia_file.filename:
                if not allowed_file(constancia_file.filename):
                    flash("Solo se permiten archivos PDF.", "danger")
                    return redirect(url_for("proveedores.nuevo"))

                saved_file = save_constancia_file(constancia_file)

                if saved_file:
                    pending_file_path = saved_file["file_path"]
                    pending_original_filename = saved_file["original_filename"]
                    pending_stored_filename = saved_file["stored_filename"]
                    pending_file_extension = saved_file["file_extension"]
                    pending_file_size_kb = str(saved_file["file_size_kb"])

            if not rfc or not business_name:
                flash("El RFC y la razón social son obligatorios.", "danger")
                return redirect(url_for("proveedores.nuevo"))

            existing_supplier = Supplier.query.filter_by(rfc=rfc).first()

            if existing_supplier:
                flash("Ya existe un proveedor registrado con ese RFC.", "warning")
                return redirect(url_for("proveedores.nuevo"))

            proveedor = Supplier(
                rfc=rfc,
                business_name=business_name,
                tax_regime=tax_regime or None,
                tax_regime_code=tax_regime_code or None,
                fiscal_zip_code=fiscal_zip_code or None,
                fiscal_address=fiscal_address or None,
                fiscal_certificate_path=pending_file_path or None,
                is_active=True
            )

            db.session.add(proveedor)
            db.session.flush()

            if pending_file_path:
                documento = SupplierDocument(
                    supplier_id=proveedor.id,
                    document_type="fiscal_certificate",
                    original_filename=pending_original_filename or "constancia.pdf",
                    stored_filename=pending_stored_filename or os.path.basename(pending_file_path),
                    file_path=pending_file_path,
                    file_extension=pending_file_extension or "pdf",
                    file_size_kb=float(pending_file_size_kb) if pending_file_size_kb else None,
                    uploaded_by=current_user.id
                )

                db.session.add(documento)

            db.session.commit()

            flash("Proveedor registrado correctamente.", "success")
            return redirect(url_for("proveedores.index"))

    return render_template(
        "proveedores/form.html",
        proveedor=None,
        modo="nuevo",
        extracted_data=extracted_data
    )


@proveedores_bp.route("/editar/<int:proveedor_id>", methods=["GET", "POST"])
@login_required
def editar(proveedor_id):
    proveedor = Supplier.query.get_or_404(proveedor_id)
    extracted_data = None

    if request.method == "POST":
        action = request.form.get("action", "save")

        rfc = request.form.get("rfc", "").strip().upper()
        business_name = request.form.get("business_name", "").strip().upper()
        tax_regime = request.form.get("tax_regime", "").strip().upper()
        tax_regime_code = request.form.get("tax_regime_code", "").strip()
        fiscal_zip_code = request.form.get("fiscal_zip_code", "").strip()
        fiscal_address = request.form.get("fiscal_address", "").strip().upper()
        is_active = True if request.form.get("is_active") == "on" else False

        constancia_file = request.files.get("constancia_pdf")

        if action == "extract":
            if not constancia_file or constancia_file.filename == "":
                flash("Selecciona una constancia fiscal en PDF para extraer los datos.", "warning")
                return render_template(
                    "proveedores/form.html",
                    proveedor=proveedor,
                    modo="editar",
                    extracted_data=None
                )

            if not allowed_file(constancia_file.filename):
                flash("Solo se permiten archivos PDF.", "danger")
                return render_template(
                    "proveedores/form.html",
                    proveedor=proveedor,
                    modo="editar",
                    extracted_data=None
                )

            saved_file = save_constancia_file(constancia_file)

            if not saved_file:
                flash("No se pudo guardar el archivo PDF.", "danger")
                return render_template(
                    "proveedores/form.html",
                    proveedor=proveedor,
                    modo="editar",
                    extracted_data=None
                )

            extractor = PDFExtractor(saved_file["file_path"])
            extracted_data = extractor.extract_data()
            extracted_data["pending_file"] = saved_file

            flash("Datos extraídos correctamente. Revisa la información antes de guardar.", "success")

            return render_template(
                "proveedores/form.html",
                proveedor=proveedor,
                modo="editar",
                extracted_data=extracted_data
            )

        if action == "save":
            pending_file_path = request.form.get("pending_file_path", "").strip()
            pending_original_filename = request.form.get("pending_original_filename", "").strip()
            pending_stored_filename = request.form.get("pending_stored_filename", "").strip()
            pending_file_extension = request.form.get("pending_file_extension", "").strip()
            pending_file_size_kb = request.form.get("pending_file_size_kb", "").strip()

            if constancia_file and constancia_file.filename:
                if not allowed_file(constancia_file.filename):
                    flash("Solo se permiten archivos PDF.", "danger")
                    return redirect(url_for("proveedores.editar", proveedor_id=proveedor.id))

                saved_file = save_constancia_file(constancia_file)

                if saved_file:
                    pending_file_path = saved_file["file_path"]
                    pending_original_filename = saved_file["original_filename"]
                    pending_stored_filename = saved_file["stored_filename"]
                    pending_file_extension = saved_file["file_extension"]
                    pending_file_size_kb = str(saved_file["file_size_kb"])

            if not rfc or not business_name:
                flash("El RFC y la razón social son obligatorios.", "danger")
                return redirect(url_for("proveedores.editar", proveedor_id=proveedor.id))

            existing_supplier = Supplier.query.filter(
                Supplier.rfc == rfc,
                Supplier.id != proveedor.id
            ).first()

            if existing_supplier:
                flash("Otro proveedor ya tiene ese RFC.", "warning")
                return redirect(url_for("proveedores.editar", proveedor_id=proveedor.id))

            proveedor.rfc = rfc
            proveedor.business_name = business_name
            proveedor.tax_regime = tax_regime or None
            proveedor.tax_regime_code = tax_regime_code or None
            proveedor.fiscal_zip_code = fiscal_zip_code or None
            proveedor.fiscal_address = fiscal_address or None
            proveedor.is_active = is_active

            if pending_file_path:
                proveedor.fiscal_certificate_path = pending_file_path

                documento = SupplierDocument(
                    supplier_id=proveedor.id,
                    document_type="fiscal_certificate",
                    original_filename=pending_original_filename or "constancia.pdf",
                    stored_filename=pending_stored_filename or os.path.basename(pending_file_path),
                    file_path=pending_file_path,
                    file_extension=pending_file_extension or "pdf",
                    file_size_kb=float(pending_file_size_kb) if pending_file_size_kb else None,
                    uploaded_by=current_user.id
                )

                db.session.add(documento)

            db.session.commit()

            flash("Proveedor actualizado correctamente.", "success")
            return redirect(url_for("proveedores.index"))

    return render_template(
        "proveedores/form.html",
        proveedor=proveedor,
        modo="editar",
        extracted_data=extracted_data
    )


@proveedores_bp.route("/desactivar/<int:proveedor_id>", methods=["POST"])
@login_required
def desactivar(proveedor_id):
    proveedor = Supplier.query.get_or_404(proveedor_id)
    proveedor.is_active = False
    db.session.commit()

    flash("Proveedor desactivado correctamente.", "success")
    return redirect(url_for("proveedores.index"))


@proveedores_bp.route("/activar/<int:proveedor_id>", methods=["POST"])
@login_required
def activar(proveedor_id):
    proveedor = Supplier.query.get_or_404(proveedor_id)
    proveedor.is_active = True
    db.session.commit()

    flash("Proveedor activado correctamente.", "success")
    return redirect(url_for("proveedores.index"))