import re
import fitz


class PDFExtractor:
    def __init__(self, pdf_path):
        self.pdf_path = pdf_path
        self.text = ""

    def extract_text(self):
        text = ""

        try:
            doc = fitz.open(self.pdf_path)

            for page in doc:
                text += "\n" + page.get_text("text")

            doc.close()

        except Exception as e:
            print(f"Error al abrir PDF: {e}")
            return ""

        self.text = self.normalize_text(text)
        return self.text

    @staticmethod
    def normalize_text(text):
        text = text.replace("\xa0", " ")
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n+", "\n", text)
        return text.strip()

    def get_value_after_label(self, labels, stop_labels=None):
        """
        Extrae el valor que aparece después de una etiqueta.
        Sirve para campos en la misma línea, por ejemplo:
        RFC: OEVC000731FX5
        Código Postal:03920 Tipo de Vialidad: CALLE
        """

        if isinstance(labels, str):
            labels = [labels]

        if stop_labels is None:
            stop_labels = [
                "RFC:",
                "CURP:",
                "Nombre (s):",
                "Primer Apellido:",
                "Segundo Apellido:",
                "Denominación/Razón Social:",
                "Régimen Capital:",
                "Nombre Comercial:",
                "Fecha inicio de operaciones:",
                "Estatus en el padrón:",
                "Fecha de último cambio de estado:",
                "Código Postal:",
                "C.P.:",
                "Codigo Postal:",
                "Tipo de Vialidad:",
                "Nombre de Vialidad:",
                "Número Exterior:",
                "Número Interior:",
                "Nombre de la Colonia:",
                "Nombre de la Localidad:",
                "Nombre del Municipio o Demarcación Territorial:",
                "Nombre de la Entidad Federativa:",
                "Entre Calle:",
                "Y Calle:",
                "Actividades Económicas:",
                "Regímenes:",
                "Obligaciones:",
            ]

        for label in labels:
            other_labels = [x for x in stop_labels if x.lower() != label.lower()]

            pattern = re.compile(
                rf"{re.escape(label)}\s*(.*?)\s*(?="
                rf"{'|'.join(re.escape(x) for x in other_labels)}|\n|$)",
                re.IGNORECASE | re.DOTALL
            )

            match = pattern.search(self.text)

            if match:
                value = match.group(1).strip()
                value = re.sub(r"\s+", " ", value)

                if value:
                    return value

        return ""

    def get_section_between(self, start_label, end_labels):
        if isinstance(end_labels, str):
            end_labels = [end_labels]

        pattern = re.compile(
            rf"{re.escape(start_label)}\s*(.*?)\s*(?="
            rf"{'|'.join(re.escape(x) for x in end_labels)}|$)",
            re.IGNORECASE | re.DOTALL
        )

        match = pattern.search(self.text)

        if not match:
            return ""

        section = match.group(1).strip()
        section = re.sub(r"[ \t]+", " ", section)
        return section

    def extract_regimen(self):
        """
        Extrae el primer régimen fiscal de la sección Regímenes.
        Funciona para:
        - Régimen de las Personas Físicas con Actividades Empresariales y Profesionales
        - Régimen General de Ley Personas Morales
        """

        section = self.get_section_between(
            "Regímenes:",
            ["Obligaciones:", "Sus datos personales", "Cadena Original Sello:"]
        )

        if not section:
            return ""

        lines = [line.strip() for line in section.split("\n") if line.strip()]

        ignored = {
            "Régimen",
            "Regimen",
            "Fecha Inicio",
            "Fecha Fin",
            "Régimen Fecha Inicio Fecha Fin",
            "Regimen Fecha Inicio Fecha Fin",
        }

        for line in lines:
            clean_line = re.sub(r"\s+", " ", line).strip()

            if clean_line in ignored:
                continue

            if re.search(r"\d{2}/\d{2}/\d{4}", clean_line):
                clean_line = re.sub(r"\s+\d{2}/\d{2}/\d{4}.*$", "", clean_line).strip()

            if clean_line and not clean_line.lower().startswith("fecha"):
                return clean_line.upper()

        return ""

    def extract_actividad_economica(self):
        section = self.get_section_between(
            "Actividades Económicas:",
            ["Regímenes:", "Obligaciones:"]
        )

        if not section:
            return ""

        lines = [line.strip() for line in section.split("\n") if line.strip()]

        for line in lines:
            clean_line = re.sub(r"\s+", " ", line).strip()

            if "Actividad Económica" in clean_line:
                continue

            match = re.search(r"^\d+\s+(.+?)\s+\d{1,3}\s+\d{2}/\d{2}/\d{4}", clean_line)

            if match:
                return match.group(1).strip().upper()

        return ""

    def detect_person_type(self):
        if re.search(r"Denominación/Razón Social:", self.text, re.IGNORECASE):
            return "PERSONA_MORAL"

        if re.search(r"Nombre \(s\):", self.text, re.IGNORECASE):
            return "PERSONA_FISICA"

        return "DESCONOCIDO"

    def build_fiscal_address(self, data):
        parts = []

        tipo_vialidad = data.get("tipo_vialidad", "")
        nombre_vialidad = data.get("nombre_vialidad", "")
        numero_exterior = data.get("numero_exterior", "")
        numero_interior = data.get("numero_interior", "")
        colonia = data.get("colonia", "")
        localidad = data.get("localidad", "")
        municipio = data.get("municipio", "")
        entidad = data.get("entidad_federativa", "")
        codigo_postal = data.get("codigo_postal", "")

        calle = " ".join(x for x in [tipo_vialidad, nombre_vialidad] if x)

        if calle:
            parts.append(calle)

        if numero_exterior:
            parts.append(f"EXT. {numero_exterior}")

        if numero_interior:
            parts.append(f"INT. {numero_interior}")

        if colonia:
            parts.append(f"COL. {colonia}")

        if localidad:
            parts.append(localidad)

        if municipio:
            parts.append(municipio)

        if entidad:
            parts.append(entidad)

        if codigo_postal:
            parts.append(f"C.P. {codigo_postal}")

        return ", ".join(parts).upper()

    def extract_data(self):
        self.extract_text()

        data = {
            "person_type": "",
            "rfc": "",
            "curp": "",
            "business_name": "",
            "first_name": "",
            "first_last_name": "",
            "second_last_name": "",
            "tax_regime": "",
            "capital_regime": "",
            "fiscal_zip_code": "",
            "fiscal_address": "",
            "tipo_vialidad": "",
            "nombre_vialidad": "",
            "numero_exterior": "",
            "numero_interior": "",
            "colonia": "",
            "localidad": "",
            "municipio": "",
            "entidad_federativa": "",
            "entre_calle": "",
            "y_calle": "",
            "actividad_economica": "",
            "estatus_padron": "",
            "fecha_inicio_operaciones": "",
        }

        if not self.text:
            return data

        person_type = self.detect_person_type()
        data["person_type"] = person_type

        data["rfc"] = self.get_value_after_label("RFC:")
        data["curp"] = self.get_value_after_label("CURP:")

        data["fecha_inicio_operaciones"] = self.get_value_after_label("Fecha inicio de operaciones:")
        data["estatus_padron"] = self.get_value_after_label("Estatus en el padrón:")

        data["fiscal_zip_code"] = self.get_value_after_label([
            "Código Postal:",
            "Codigo Postal:",
            "C.P.:"
        ])

        data["tipo_vialidad"] = self.get_value_after_label("Tipo de Vialidad:")
        data["nombre_vialidad"] = self.get_value_after_label("Nombre de Vialidad:")
        data["numero_exterior"] = self.get_value_after_label("Número Exterior:")
        data["numero_interior"] = self.get_value_after_label("Número Interior:")
        data["colonia"] = self.get_value_after_label("Nombre de la Colonia:")
        data["localidad"] = self.get_value_after_label("Nombre de la Localidad:")
        data["municipio"] = self.get_value_after_label("Nombre del Municipio o Demarcación Territorial:")
        data["entidad_federativa"] = self.get_value_after_label("Nombre de la Entidad Federativa:")
        data["entre_calle"] = self.get_value_after_label("Entre Calle:")
        data["y_calle"] = self.get_value_after_label("Y Calle:")

        data["tax_regime"] = self.extract_regimen()
        data["actividad_economica"] = self.extract_actividad_economica()

        if person_type == "PERSONA_FISICA":
            data["first_name"] = self.get_value_after_label("Nombre (s):")
            data["first_last_name"] = self.get_value_after_label("Primer Apellido:")
            data["second_last_name"] = self.get_value_after_label("Segundo Apellido:")

            full_name = " ".join(
                x for x in [
                    data["first_name"],
                    data["first_last_name"],
                    data["second_last_name"]
                ]
                if x
            )

            data["business_name"] = full_name.upper()

        elif person_type == "PERSONA_MORAL":
            data["business_name"] = self.get_value_after_label("Denominación/Razón Social:")
            data["capital_regime"] = self.get_value_after_label("Régimen Capital:")

        else:
            data["business_name"] = self.get_value_after_label([
                "Denominación/Razón Social:",
                "Nombre Comercial:",
                "Nombre, denominación o razón social"
            ])

        data["fiscal_address"] = self.build_fiscal_address(data)

        for key, value in data.items():
            if isinstance(value, str):
                data[key] = re.sub(r"\s+", " ", value).strip().upper()

        return data