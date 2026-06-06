from pathlib import Path
from io import BytesIO
from datetime import date, datetime
from reportlab.pdfgen import canvas
from reportlab.lib.colors import lightgrey, red, blue
from pypdf import PdfReader, PdfWriter

BASE_DIR = Path(__file__).parent
TEMPLATES_DIR = BASE_DIR / "templates"
OUTPUT_DIR = BASE_DIR / "output"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

MESES_ES = {
    1: "Enero",
    2: "Febrero",
    3: "Marzo",
    4: "Abril",
    5: "Mayo",
    6: "Junio",
    7: "Julio",
    8: "Agosto",
    9: "Septiembre",
    10: "Octubre",
    11: "Noviembre",
    12: "Diciembre",
}


# =========================================================
# FUNCIONES DE TEXTO
# =========================================================
def split_text_to_lines(text, canvas_obj, font_name, font_size, max_width, max_lines=2):
    """
    Divide un texto en líneas según el ancho máximo.
    Si excede max_lines, recorta la última con '...'
    """
    words = str(text).split()
    if not words:
        return [""]

    lines = []
    current_line = words[0]

    for word in words[1:]:
        test_line = current_line + " " + word
        test_width = canvas_obj.stringWidth(test_line, font_name, font_size)

        if test_width <= max_width:
            current_line = test_line
        else:
            lines.append(current_line)
            current_line = word

    lines.append(current_line)

    if len(lines) > max_lines:
        lines = lines[:max_lines]

        last = lines[-1]
        while canvas_obj.stringWidth(last + "...", font_name, font_size) > max_width and len(last) > 0:
            last = last[:-1].rstrip()

        lines[-1] = last + "..."

    return lines


def draw_text_in_box(
    c,
    text,
    x,
    y,
    width,
    font_name="Helvetica",
    font_size=9.5,
    max_lines=2,
    line_spacing=11,
    single_line_y_shift=0
):
    """
    Dibuja texto dentro de un área de ancho fijo.
    - Si cabe en una línea, se puede mover verticalmente con single_line_y_shift
    - Si no, usa hasta 2 líneas
    - Si aún excede, corta con '...'
    """
    c.setFont(font_name, font_size)

    lines = split_text_to_lines(
        text=text,
        canvas_obj=c,
        font_name=font_name,
        font_size=font_size,
        max_width=width,
        max_lines=max_lines
    )

    # Si solo hay una línea, aplicamos ajuste vertical
    y_base = y + single_line_y_shift if len(lines) == 1 else y

    for i, line in enumerate(lines):
        c.drawString(x, y_base - (i * line_spacing), line)


def draw_text_in_box_centered(
    c,
    text,
    x_left,
    x_right,
    y_bottom,
    y_top,
    font_name="Helvetica",
    font_size=7.5,
    max_lines=2,
    line_spacing=8
):
    """
    Dibuja texto centrado horizontalmente dentro de un área.
    Si ocupa 2 líneas, ambas quedan centradas.
    También centra verticalmente el bloque dentro del área.
    """
    width = x_right - x_left
    c.setFont(font_name, font_size)

    lines = split_text_to_lines(
        text=text,
        canvas_obj=c,
        font_name=font_name,
        font_size=font_size,
        max_width=width,
        max_lines=max_lines
    )

    y_center = (y_bottom + y_top) / 2
    total_block_height = (len(lines) - 1) * line_spacing
    start_y = y_center + (total_block_height / 2)

    for i, line in enumerate(lines):
        line_width = c.stringWidth(line, font_name, font_size)
        x_line = x_left + (width - line_width) / 2
        y_line = start_y - (i * line_spacing)
        c.drawString(x_line, y_line, line)


def draw_text_centered_single_line(
    c,
    text,
    x_left,
    x_right,
    y,
    font_name="Helvetica",
    font_size=9.5
):
    """
    Dibuja una sola línea centrada horizontalmente dentro de un área.
    """
    c.setFont(font_name, font_size)
    text = str(text)
    text_width = c.stringWidth(text, font_name, font_size)
    area_width = x_right - x_left
    x = x_left + (area_width - text_width) / 2
    c.drawString(x, y, text)


# =========================================================
# FECHA
# =========================================================
def normalizar_fecha(fecha):
    """
    Acepta date, datetime o texto YYYY-MM-DD / DD/MM/YYYY.
    Devuelve (anio, mes_texto, dia_texto)
    """
    if isinstance(fecha, datetime):
        fecha_obj = fecha.date()
    elif isinstance(fecha, date):
        fecha_obj = fecha
    elif isinstance(fecha, str):
        fecha = fecha.strip()
        try:
            fecha_obj = datetime.strptime(fecha, "%Y-%m-%d").date()
        except ValueError:
            fecha_obj = datetime.strptime(fecha, "%d/%m/%Y").date()
    else:
        raise ValueError("Formato de fecha no soportado.")

    anio = str(fecha_obj.year)
    mes = MESES_ES[fecha_obj.month]
    dia = f"{fecha_obj.day:02d}"

    return anio, mes, dia


# =========================================================
# OVERLAY REAL
# =========================================================
def crear_overlay_dc3(
    page_width,
    page_height,
    nombre_completo,
    curp,
    puesto,
    curso,
    capacitador,
    fecha
):
    """
    Crea la capa PDF con datos reales sobre la página 1.
    """
    packet = BytesIO()
    c = canvas.Canvas(packet, pagesize=(page_width, page_height))

    # ---------------- DATOS PRINCIPALES ----------------
    c.setFont("Helvetica", 9.5)

    # Nombre (desde Nombrecompleto)
    c.drawString(30, 615, str(nombre_completo))

    # CURP (desde CURP)
    c.drawString(30, 585, str(curp))

    # Puesto (desde Puesto)
    c.drawString(30, 555, str(puesto))

    # Capacitador en posición normal
    c.drawString(30, 325, str(capacitador))

    # ---------------- CURSO EN ÁREA DE TEXTO ----------------
    CURSO_X = 30
    CURSO_Y = 425
    CURSO_WIDTH = 520

    draw_text_in_box(
        c,
        text=str(curso),
        x=CURSO_X,
        y=CURSO_Y,
        width=CURSO_WIDTH,
        font_name="Helvetica",
        font_size=9.5,
        max_lines=2,
        line_spacing=11,
        single_line_y_shift=-10
    )

    # ---------------- CAPACITADOR EN FIRMA (CENTRADO) ----------------
    # Área:
    # x = 40 a 190
    # y = 220 a 240
    draw_text_in_box_centered(
        c,
        text=str(capacitador),
        x_left=40,
        x_right=190,
        y_bottom=220,
        y_top=240,
        font_name="Helvetica",
        font_size=7.5,
        max_lines=2,
        line_spacing=8
    )

    # ---------------- FECHA 1 Y FECHA 2 (MISMAS) ----------------
    anio, mes, dia = normalizar_fecha(fecha)

    y_fecha = 385
    desplazamiento_segunda_fecha = 165

    # Primera fecha
    draw_text_centered_single_line(
        c, anio,
        x_left=270, x_right=310, y=y_fecha,
        font_name="Helvetica", font_size=9.5
    )
    draw_text_centered_single_line(
        c, mes,
        x_left=320, x_right=380, y=y_fecha,
        font_name="Helvetica", font_size=9.5
    )
    draw_text_centered_single_line(
        c, dia,
        x_left=390, x_right=420, y=y_fecha,
        font_name="Helvetica", font_size=9.5
    )

    # Segunda fecha (mismo valor)
    draw_text_centered_single_line(
        c, anio,
        x_left=270 + desplazamiento_segunda_fecha,
        x_right=310 + desplazamiento_segunda_fecha,
        y=y_fecha,
        font_name="Helvetica",
        font_size=9.5
    )
    draw_text_centered_single_line(
        c, mes,
        x_left=320 + desplazamiento_segunda_fecha,
        x_right=380 + desplazamiento_segunda_fecha,
        y=y_fecha,
        font_name="Helvetica",
        font_size=9.5
    )
    draw_text_centered_single_line(
        c, dia,
        x_left=390 + desplazamiento_segunda_fecha,
        x_right=420 + desplazamiento_segunda_fecha,
        y=y_fecha,
        font_name="Helvetica",
        font_size=9.5
    )

    c.save()
    packet.seek(0)
    return packet


# =========================================================
# OVERLAY GRID
# =========================================================
def crear_overlay_grid(page_width, page_height, step=10):
    """
    Crea una rejilla de coordenadas para ayudarte a ubicar los campos.
    """
    packet = BytesIO()
    c = canvas.Canvas(packet, pagesize=(page_width, page_height))

    # Líneas verticales
    for x in range(0, int(page_width) + 1, step):
        c.setStrokeColor(lightgrey)
        c.setLineWidth(0.2)
        c.line(x, 0, x, page_height)

        if x % 50 == 0:
            c.setFillColor(red)
            c.setFont("Helvetica", 6)
            c.drawString(x + 1, page_height - 10, str(x))
            c.drawString(x + 1, 2, str(x))

    # Líneas horizontales
    for y in range(0, int(page_height) + 1, step):
        c.setStrokeColor(lightgrey)
        c.setLineWidth(0.2)
        c.line(0, y, page_width, y)

        if y % 50 == 0:
            c.setFillColor(blue)
            c.setFont("Helvetica", 6)
            c.drawString(2, y + 1, str(y))
            c.drawString(page_width - 28, y + 1, str(y))

    c.setFillColor(red)
    c.setFont("Helvetica-Bold", 8)
    c.drawString(5, 5, "(0,0)")

    c.save()
    packet.seek(0)
    return packet


# =========================================================
# GENERACIÓN REAL
# =========================================================
def generar_dc3(
    nombre_completo,
    curp,
    puesto,
    curso,
    capacitador,
    fecha,
    nombre_plantilla="DIFARMER_base.pdf",
    output_filename="dc3_generada.pdf"
):
    """
    Genera una constancia DC3 real:
    - usa la plantilla PDF base
    - llena solo la página 1
    - conserva intacta la página 2
    """
    plantilla_path = TEMPLATES_DIR / nombre_plantilla

    if not plantilla_path.exists():
        raise FileNotFoundError(f"No se encontró la plantilla: {plantilla_path}")

    reader = PdfReader(str(plantilla_path))
    writer = PdfWriter()

    if len(reader.pages) < 2:
        raise ValueError("La plantilla debe tener al menos 2 páginas.")

    page1 = reader.pages[0]
    page_width = float(page1.mediabox.width)
    page_height = float(page1.mediabox.height)

    overlay_pdf = PdfReader(
        crear_overlay_dc3(
            page_width=page_width,
            page_height=page_height,
            nombre_completo=nombre_completo,
            curp=curp,
            puesto=puesto,
            curso=curso,
            capacitador=capacitador,
            fecha=fecha
        )
    )
    overlay_page = overlay_pdf.pages[0]

    page1.merge_page(overlay_page)
    writer.add_page(page1)

    # Página 2 intacta
    page2 = reader.pages[1]
    writer.add_page(page2)

    output_path = OUTPUT_DIR / output_filename
    with open(output_path, "wb") as f:
        writer.write(f)

    return output_path


# =========================================================
# GUÍA DE COORDENADAS
# =========================================================
def generar_guia_coordenadas(nombre_plantilla="DIFARMER_base.pdf"):
    """
    Genera un PDF con rejilla de coordenadas sobre la página 1
    y conserva la página 2 intacta.
    """
    plantilla_path = TEMPLATES_DIR / nombre_plantilla

    if not plantilla_path.exists():
        raise FileNotFoundError(f"No se encontró la plantilla: {plantilla_path}")

    reader = PdfReader(str(plantilla_path))
    writer = PdfWriter()

    if len(reader.pages) < 2:
        raise ValueError("La plantilla debe tener al menos 2 páginas.")

    page1 = reader.pages[0]
    page_width = float(page1.mediabox.width)
    page_height = float(page1.mediabox.height)

    overlay_pdf = PdfReader(crear_overlay_grid(page_width, page_height, step=10))
    overlay_page = overlay_pdf.pages[0]

    page1.merge_page(overlay_page)
    writer.add_page(page1)

    # Página 2 intacta
    page2 = reader.pages[1]
    writer.add_page(page2)

    output_path = OUTPUT_DIR / "dc3_guia_coordenadas.pdf"
    with open(output_path, "wb") as f:
        writer.write(f)

    return output_path


# =========================================================
# PRUEBA LOCAL
# =========================================================
if __name__ == "__main__":
    ruta = generar_dc3(
        nombre_completo="BOCANEGRA JAVIER DE DIOS",
        curp="BOCJ900101HSRXXX00",
        puesto="AUXILIAR DE FORMACION Y DESARROLLO",
        curso="BRIGADAS MULTIFUNCIONALES",
        capacitador="ANA PAOLA PADILLA QUINTERO",
        fecha="03/06/2026",
        nombre_plantilla="DIFARMER_base.pdf",
        output_filename="dc3_real_prueba.pdf"
    )
    print(f"PDF real de prueba generado en: {ruta}")

    ruta_guia = generar_guia_coordenadas()
    print(f"Guía de coordenadas generada en: {ruta_guia}")
