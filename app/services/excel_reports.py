import win32com.client as win32
import pythoncom
from pathlib import Path
from io import BytesIO
import tempfile
import os


# ===========================================================================
# CONFIGURACIÓN DE RUTAS
# ===========================================================================

def get_templates_dir(app_root_path: str) -> Path:
    return Path(app_root_path) / "static" / "assets" / "plantillas"


# ===========================================================================
# CONVERSIÓN DE COLOR HEX A ENTERO (para win32com)
# ===========================================================================

def hex_to_int(hex_color: str) -> int:
    """Convierte un color hexadecimal '#RRGGBB' a entero (0xBBGGRR para Excel)."""
    hex_color = hex_color.lstrip('#')
    r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
    # Excel espera BGR (Blue, Green, Red)
    return (b << 16) + (g << 8) + r


# Paleta de colores en formato entero
COLORS = {
    'mint': hex_to_int("#7AA997"),
    'petrol': hex_to_int("#496C70"),
    'olive': hex_to_int("#98B57D"),
    'purple': hex_to_int("#6C5E78"),
    'lavender': hex_to_int("#977A9A"),
    'blue': hex_to_int("#1F4E78"),
    'teal': hex_to_int("#31879B"),
    'red': hex_to_int("#BA6262"),
    'coral': hex_to_int("#C77F7F"),
    'bg': hex_to_int("#EEF4F1"),
    'bg2': hex_to_int("#F7FAF8"),
    'white': hex_to_int("#FFFFFF"),
    'text': hex_to_int("#26332E"),
    'muted': hex_to_int("#72827B"),
    'border': hex_to_int("#D9E2E1"),  # de tu theme
}


# ===========================================================================
# FUNCIONES DE ESTILO (usando win32com)
# ===========================================================================

def apply_table_header_style(range_obj, font_name="Aptos Narrow", font_size=11, bold=True, bg_color=COLORS['petrol'],
                             font_color=COLORS['white']):
    """Aplica estilo a una fila de encabezados de tabla."""
    range_obj.Font.Name = font_name
    range_obj.Font.Size = font_size
    range_obj.Font.Bold = bold
    range_obj.Font.Color = font_color
    range_obj.Interior.Color = bg_color
    range_obj.HorizontalAlignment = -4108  # xlCenter
    range_obj.VerticalAlignment = -4108
    # Bordes
    for border_id in [7, 8, 9, 10]:  # izquierdo, derecho, superior, inferior
        border = range_obj.Borders(border_id)
        border.Weight = 2  # xlThin
        border.Color = COLORS['border']


def apply_body_cell_style(cell, font_name="Aptos Narrow", font_size=10, font_color=COLORS['text'], bg_color=None,
                          has_border=True):
    """Aplica estilo a una celda de datos."""
    cell.Font.Name = font_name
    cell.Font.Size = font_size
    cell.Font.Color = font_color
    if bg_color:
        cell.Interior.Color = bg_color
    if has_border:
        for border_id in [7, 8, 9, 10]:
            border = cell.Borders(border_id)
            border.Weight = 2
            border.Color = COLORS['border']
    cell.VerticalAlignment = -4108


def apply_alternating_row_colors(ws, start_row, end_row, start_col, end_col, even_bg=COLORS['white'],
                                 odd_bg=COLORS['bg']):
    """Aplica colores alternados a filas de datos."""
    for row in range(start_row, end_row + 1):
        bg = even_bg if (row - start_row) % 2 == 0 else odd_bg
        for col in range(start_col, end_col + 1):
            ws.Cells(row, col).Interior.Color = bg


def autofit_columns(ws, start_col, end_col, max_width=42):
    """Ajusta el ancho de las columnas automáticamente sin exceder max_width."""
    for col in range(start_col, end_col + 1):
        col_range = ws.Columns(col)
        col_range.AutoFit()
        # Obtener ancho actual (propiedad ColumnWidth)
        current_width = col_range.ColumnWidth
        if current_width > max_width:
            col_range.ColumnWidth = max_width


# ===========================================================================
# DESPROTECCIÓN
# ===========================================================================

def unprotect_and_unlock_objects(ws):
    try:
        if ws.ProtectContents:
            ws.Unprotect("")
    except:
        pass
    try:
        for sh in ws.Shapes:
            try:
                sh.Locked = False
            except:
                pass
    except:
        pass


# ===========================================================================
# FUNCIONES DE ESCRITURA (con diseño mejorado)
# ===========================================================================

def write_provider_data(ws, context):
    ws.Cells(12, 2).Value = f"AÑO: {context.get('selected_year') or 'TODOS'}"
    ws.Cells(12, 4).Value = f"% CUBIERTO: {context.get('covered_percentage', 0)}%"
    ws.Cells(12, 6).Value = f"RUBRO CONTENEDOR: {context.get('related_budget_name', 'N/A')}"

    # Tabla resumen (encabezados fila 13, datos fila 14)
    header_range = ws.Range(ws.Cells(13, 1), ws.Cells(13, 3))
    apply_table_header_style(header_range, bg_color=COLORS['petrol'])

    start_row = 14
    row = start_row
    for item in context["provider_summary"]:
        ws.Cells(row, 1).Value = item["supplier_name"]
        ws.Cells(row, 2).Value = float(item["total"])
        ws.Cells(row, 3).Value = item["records"]
        ws.Cells(row, 2).NumberFormat = "$#,##0.00"
        row += 1
    end_row = row - 1

    if end_row >= start_row:
        for r in range(start_row, end_row + 1):
            for c in range(1, 4):
                apply_body_cell_style(ws.Cells(r, c))
        apply_alternating_row_colors(ws, start_row, end_row, 1, 3)
        autofit_columns(ws, 1, 3)

    # Tabla detalle (encabezados fila 20, datos fila 21)
    detail_header_range = ws.Range(ws.Cells(20, 1), ws.Cells(20, 6))
    apply_table_header_style(detail_header_range, bg_color=COLORS['mint'])

    detail_start = 21
    row = detail_start
    for registro in context["registros"]:
        ws.Cells(row, 1).Value = registro.application_date.strftime("%d/%m/%Y")
        ws.Cells(row, 2).Value = registro.supplier.business_name
        ws.Cells(row,
                 3).Value = f"{registro.budget_item.item_code} - {registro.budget_item.item_name}" if registro.budget_item else "Sin rubro"
        ws.Cells(row, 4).Value = float(registro.amount)
        ws.Cells(row, 5).Value = registro.concept
        ws.Cells(row, 6).Value = registro.operation_folio or "N/A"
        ws.Cells(row, 4).NumberFormat = "$#,##0.00"
        row += 1
    detail_end = row - 1

    if detail_end >= detail_start:
        for r in range(detail_start, detail_end + 1):
            for c in range(1, 7):
                apply_body_cell_style(ws.Cells(r, c))
        apply_alternating_row_colors(ws, detail_start, detail_end, 1, 6, even_bg=COLORS['white'], odd_bg=COLORS['bg2'])
        autofit_columns(ws, 1, 6)


def write_rubro_data(ws, context):
    ws.Cells(12, 2).Value = f"AÑO: {context.get('selected_year') or 'TODOS'}"
    ws.Cells(12, 4).Value = f"% CUBIERTO: {context.get('covered_percentage', 0)}%"
    ws.Cells(12, 6).Value = f"REGISTROS: {context.get('total_records', 0)}"

    # ==========================================================
    # TABLA ÚNICA AGRUPADA POR RUBRO
    # ==========================================================

    headers = [
        "RUBRO",
        "FECHA MOVIMIENTO",
        "PROVEEDOR MOVIMIENTO",
        "PRESUPUESTO POR RUBRO",
        "MONTO REGISTRO",
        "ACUMULADO RUBRO",
        "RESTANTE RUBRO",
        "% DEL RUBRO",
        "FOLIO REGISTRO",
        "CONCEPTO"
    ]

    header_row = 13
    start_row = 14

    for col, header in enumerate(headers, start=1):
        ws.Cells(header_row, col).Value = header

    header_range = ws.Range(ws.Cells(header_row, 1), ws.Cells(header_row, len(headers)))
    apply_table_header_style(header_range, bg_color=COLORS['petrol'])

    # Diccionario de presupuestos por rubro
    presupuesto_por_rubro = {}

    for item in context.get("rubro_summary", []):
        presupuesto_por_rubro[item["item_code"]] = {
            "budget": float(item.get("budget") or 0),
            "item_name": item.get("item_name", "")
        }

    rubros_ya_mostrados = set()
    acumulado_por_rubro = {}

    row = start_row

    registros_ordenados = sorted(
        context.get("registros", []),
        key=lambda r: (
            r.budget_item.item_code if r.budget_item else "ZZZ",
            r.application_date
        )
    )

    for registro in registros_ordenados:
        if registro.budget_item:
            rubro_codigo = registro.budget_item.item_code
            rubro_nombre = registro.budget_item.item_name
            rubro_texto = f"{rubro_codigo} - {rubro_nombre}"
        else:
            rubro_codigo = "SIN_RUBRO"
            rubro_texto = "SIN RUBRO"

        proveedor = registro.supplier.business_name if registro.supplier else "SIN PROVEEDOR"
        monto = float(registro.amount or 0)

        presupuesto_rubro = presupuesto_por_rubro.get(rubro_codigo, {}).get("budget", 0)

        acumulado_anterior = acumulado_por_rubro.get(rubro_codigo, 0)
        acumulado_actual = acumulado_anterior + monto
        acumulado_por_rubro[rubro_codigo] = acumulado_actual

        restante_rubro = presupuesto_rubro - acumulado_actual

        if presupuesto_rubro > 0:
            porcentaje_rubro = acumulado_actual / presupuesto_rubro
        else:
            porcentaje_rubro = 0

        presupuesto_visible = ""

        if rubro_codigo not in rubros_ya_mostrados:
            presupuesto_visible = presupuesto_rubro
            rubros_ya_mostrados.add(rubro_codigo)

        ws.Cells(row, 1).Value = rubro_texto
        ws.Cells(row, 2).Value = registro.application_date.strftime("%d/%m/%Y") if registro.application_date else ""
        ws.Cells(row, 3).Value = proveedor
        ws.Cells(row, 4).Value = presupuesto_visible
        ws.Cells(row, 5).Value = monto
        ws.Cells(row, 6).Value = acumulado_actual
        ws.Cells(row, 7).Value = restante_rubro
        ws.Cells(row, 8).Value = porcentaje_rubro
        ws.Cells(row, 9).Value = registro.operation_folio or "N/A"
        ws.Cells(row, 10).Value = registro.concept or ""

        if presupuesto_visible != "":
            ws.Cells(row, 4).NumberFormat = "$#,##0.00"

        ws.Cells(row, 5).NumberFormat = "$#,##0.00"
        ws.Cells(row, 6).NumberFormat = "$#,##0.00"
        ws.Cells(row, 7).NumberFormat = "$#,##0.00"
        ws.Cells(row, 8).NumberFormat = "0.00%"

        row += 1

    end_row = row - 1

    if end_row >= start_row:
        for r in range(start_row, end_row + 1):
            for c in range(1, len(headers) + 1):
                apply_body_cell_style(ws.Cells(r, c))

        apply_alternating_row_colors(
            ws,
            start_row,
            end_row,
            1,
            len(headers),
            even_bg=COLORS['white'],
            odd_bg=COLORS['bg2']
        )

        autofit_columns(ws, 1, len(headers))

        # Ajustes especiales de ancho para columnas largas
        ws.Columns(1).ColumnWidth = 28   # Rubro
        ws.Columns(3).ColumnWidth = 32   # Proveedor
        ws.Columns(10).ColumnWidth = 45  # Concepto


def write_contadora_data(ws, context):
    ws.Cells(12, 2).Value = f"AÑO: {context.get('selected_year') or 'TODOS'}"
    ws.Cells(12, 4).Value = f"TOTAL GENERAL: ${context.get('grand_total_all', 0):,.2f}"
    ws.Cells(12, 6).Value = f"REGISTROS: {context.get('total_records', 0)}"

    last_col = 15
    header_range = ws.Range(ws.Cells(13, 1), ws.Cells(13, last_col))
    apply_table_header_style(header_range, bg_color=COLORS['petrol'])

    start_row = 14
    row = start_row
    for item in context["summary_rows"]:
        ws.Cells(row, 1).Value = item["item_code"]
        ws.Cells(row, 2).Value = item["item_name"]
        ws.Cells(row, 3).Value = float(item["total_general"])
        for month_idx in range(1, 13):
            ws.Cells(row, 3 + month_idx).Value = float(item["months"][month_idx])
        for col in range(3, last_col + 1):
            ws.Cells(row, col).NumberFormat = "$#,##0.00"
        row += 1
    end_row = row - 1

    if end_row >= start_row:
        for r in range(start_row, end_row + 1):
            for c in range(1, last_col + 1):
                apply_body_cell_style(ws.Cells(r, c))
        apply_alternating_row_colors(ws, start_row, end_row, 1, last_col)
        autofit_columns(ws, 1, last_col)

    # Fila de totales
    total_row = end_row + 1
    ws.Cells(total_row, 1).Value = "TOTAL GENERAL"
    ws.Cells(total_row, 3).Value = float(context["grand_total_all"])
    for month_idx in range(1, 13):
        ws.Cells(total_row, 3 + month_idx).Value = float(context["grand_totals"][month_idx])
    for col in range(3, last_col + 1):
        ws.Cells(total_row, col).NumberFormat = "$#,##0.00"
    # Aplicar estilo a la fila de totales
    total_range = ws.Range(ws.Cells(total_row, 1), ws.Cells(total_row, last_col))
    total_range.Font.Bold = True
    total_range.Interior.Color = COLORS['olive']
    total_range.Font.Color = COLORS['white']


# ===========================================================================
# FUNCIÓN PRINCIPAL DE EXPORTACIÓN (reutilizable)
# ===========================================================================

def export_with_excel(template_path: Path, write_func, context: dict) -> BytesIO:
    pythoncom.CoInitialize()
    excel = None
    temp_file_path = None
    wb = None

    try:
        excel = win32.DispatchEx('Excel.Application')
        excel.Visible = False
        excel.DisplayAlerts = False

        wb = excel.Workbooks.Open(str(template_path))
        ws = wb.ActiveSheet

        unprotect_and_unlock_objects(ws)
        write_func(ws, context)

        with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as tmp:
            temp_file_path = tmp.name

        wb.SaveAs(temp_file_path, FileFormat=51)
        wb.Close(SaveChanges=False)

        with open(temp_file_path, 'rb') as f:
            output = BytesIO(f.read())

        output.seek(0)
        return output

    except Exception as e:
        raise Exception(f"Error al generar reporte con Excel: {str(e)}")

    finally:
        try:
            if wb:
                wb.Close(SaveChanges=False)
        except:
            pass

        try:
            if excel:
                excel.Quit()
        except:
            pass

        if temp_file_path and os.path.exists(temp_file_path):
            os.unlink(temp_file_path)

        pythoncom.CoUninitialize()


# ===========================================================================
# FUNCIONES EXPORTADORAS (punto de entrada)
# ===========================================================================

def export_provider_report(app_root_path: str, context: dict) -> BytesIO:
    template_path = get_templates_dir(app_root_path) / "Resumen_proveedor.xlsx"
    return export_with_excel(template_path, write_provider_data, context)


def export_rubro_report(app_root_path: str, context: dict) -> BytesIO:
    template_path = get_templates_dir(app_root_path) / "Resumen_rubro.xlsx"
    return export_with_excel(template_path, write_rubro_data, context)


def export_contadora_report(app_root_path: str, context: dict) -> BytesIO:
    template_path = get_templates_dir(app_root_path) / "Resumen_mes.xlsx"
    return export_with_excel(template_path, write_contadora_data, context)