import re
from pathlib import Path
from datetime import datetime, timedelta

import pandas as pd
import streamlit as st
from pypdf import PdfReader, PdfWriter

from catalogos import EMPRESAS, CURSOS_POR_AREA, CAPACITADORES_POR_AREA
from pdf_utils import generar_dc3

st.set_page_config(page_title="DC3 Web", layout="wide")

# =========================================================
# RUTAS
# =========================================================
BASE_DIR = Path(__file__).parent
OUTPUT_DIR = BASE_DIR / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# =========================================================
# ESTADO
# =========================================================
if "selected_ids" not in st.session_state:
    st.session_state.selected_ids = set()

if "nombre_search_reset" not in st.session_state:
    st.session_state.nombre_search_reset = 0

if "last_file_signature" not in st.session_state:
    st.session_state.last_file_signature = None

if "pdf_generado" not in st.session_state:
    st.session_state.pdf_generado = False

if "pdf_bytes" not in st.session_state:
    st.session_state.pdf_bytes = None

if "pdf_filename" not in st.session_state:
    st.session_state.pdf_filename = None

st.title("Generador DC3 Web")


# =========================================================
# FUNCIONES
# =========================================================
def generar_fechas_automaticas(cursos, fecha_inicial):
    fechas = []
    fecha_actual = fecha_inicial
    cursos_en_dia = 0

    for _ in cursos:
        while fecha_actual.weekday() == 6:  # domingo
            fecha_actual += timedelta(days=1)

        fechas.append(fecha_actual)
        cursos_en_dia += 1

        if cursos_en_dia == 2:
            fecha_actual += timedelta(days=1)
            cursos_en_dia = 0

    return fechas


def preparar_dataframe(df):
    df = df.copy().reset_index(drop=False).rename(columns={"index": "__rowid"})

    # Nombre visible en pantalla
    if "Nombre" in df.columns:
        df["__display_name"] = df["Nombre"].astype(str).fillna("").str.strip()
    elif "Nombrecompleto" in df.columns:
        df["__display_name"] = df["Nombrecompleto"].astype(str).fillna("").str.strip()
    else:
        df["__display_name"] = ""

    # Nombre real para constancia
    if "Nombrecompleto" not in df.columns and "Nombre" in df.columns:
        df["Nombrecompleto"] = df["Nombre"].astype(str).fillna("").str.strip()

    # ID único por fila
    df["__uid"] = df["__rowid"].astype(str)

    if "Sucursal" not in df.columns:
        df["Sucursal"] = ""

    return df


def safe_filename(texto):
    texto = str(texto).strip()
    texto = re.sub(r"[^\w\s-]", "", texto, flags=re.UNICODE)
    texto = re.sub(r"\s+", "_", texto)
    return texto[:80] if texto else "archivo"


# =========================================================
# SIDEBAR PRINCIPAL (ACCIONES)
# =========================================================
with st.sidebar:
    st.header("Acciones")

    btn_generar = st.button("🚀 Generar PDF", use_container_width=True)

    st.markdown("---")
    st.subheader("Progreso")

    progreso_placeholder = st.empty()
    estado_placeholder = st.empty()
    descarga_placeholder = st.empty()

    progreso_placeholder.progress(0)
    estado_placeholder.info("Esperando validación para generar.")

    # Si ya existe un PDF generado, mostrar botón de descarga
    if st.session_state.pdf_bytes is not None and st.session_state.pdf_filename is not None:
        descarga_placeholder.download_button(
            "⬇ Descargar PDF FINAL",
            data=st.session_state.pdf_bytes,
            file_name=st.session_state.pdf_filename,
            mime="application/pdf",
            use_container_width=True,
            key="download_pdf_sidebar_fijo"
        )


# =========================================================
# CONFIGURACIÓN
# =========================================================
st.markdown("## Configuración de la capacitación")

col1, col2 = st.columns(2)

with col1:
    empresa = st.selectbox("Empresa", list(EMPRESAS.keys()))
    area = st.selectbox("Área de Capacitación", list(CURSOS_POR_AREA.keys()))

with col2:
    cursos_opciones = CURSOS_POR_AREA[area] + ["[OTRO CURSO]"]
    cursos_seleccionados = st.multiselect("Cursos", cursos_opciones)

    cursos_finales = [c for c in cursos_seleccionados if c != "[OTRO CURSO]"]

    if "[OTRO CURSO]" in cursos_seleccionados:
        otro_curso = st.text_input("Escriba el nombre del curso")
        if otro_curso.strip():
            cursos_finales.append(otro_curso.strip())

    capacitadores_opciones = CAPACITADORES_POR_AREA[area] + ["[OTRO CAPACITADOR]"]
    cap_sel = st.selectbox("Capacitador", capacitadores_opciones)

    if cap_sel == "[OTRO CAPACITADOR]":
        capacitador = st.text_input("Nombre del capacitador")
    else:
        capacitador = cap_sel


# =========================================================
# FECHAS
# =========================================================
st.markdown("## Fechas de capacitación")

fecha_inicial = st.date_input("Fecha inicial", datetime.today())

modo_fechas = st.radio(
    "Modo de fechas",
    ["Automático", "Manual"],
    horizontal=True
)

fechas_cursos = []

if cursos_finales:
    if modo_fechas == "Automático":
        fechas_cursos = generar_fechas_automaticas(cursos_finales, fecha_inicial)

        st.markdown("### Fechas asignadas automáticamente")
        for curso, fecha in zip(cursos_finales, fechas_cursos):
            st.write(f"**{curso}** → {fecha.strftime('%d/%m/%Y')}")
    else:
        st.markdown("### Asigna una fecha por curso")
        for i, curso in enumerate(cursos_finales):
            fecha_manual = st.date_input(
                f"Fecha para: {curso}",
                value=fecha_inicial,
                key=f"fecha_manual_{i}"
            )
            fechas_cursos.append(fecha_manual)


# =========================================================
# CARGA DE EMPLEADOS
# =========================================================
st.markdown("## Cargar relación de empleados")

archivo_empleados = st.file_uploader(
    "Sube la relación de empleados (.xlsx)",
    type=["xlsx"]
)

df_empleados = None
df_seleccionados = pd.DataFrame()

if archivo_empleados is not None:
    firma_archivo = f"{archivo_empleados.name}_{archivo_empleados.size}"

    if st.session_state.last_file_signature != firma_archivo:
        st.session_state.selected_ids = set()
        st.session_state.nombre_search_reset += 1
        st.session_state.last_file_signature = firma_archivo
        st.session_state.pdf_bytes = None
        st.session_state.pdf_filename = None
        st.session_state.pdf_generado = False

    try:
        df_raw = pd.read_excel(archivo_empleados)

        # Validar columnas obligatorias reales
        columnas_obligatorias = ["Nombrecompleto", "CURP", "Puesto"]
        faltantes = [c for c in columnas_obligatorias if c not in df_raw.columns]
        if faltantes:
            st.error(f"Faltan columnas obligatorias en el Excel: {', '.join(faltantes)}")
            st.stop()

        df_empleados = preparar_dataframe(df_raw)

        st.success(f"Archivo cargado correctamente. Total de registros: {len(df_empleados)}")

        st.markdown("## Filtros de empleados")

        filtro = st.radio(
            "Filtrar por:",
            ["Sucursal", "Buscar por nombre"],
            horizontal=True
        )

        df_filtrado = df_empleados.iloc[0:0].copy()

        # -------- FILTRO SUCURSAL --------
        if filtro == "Sucursal":
            if "Sucursal" in df_empleados.columns:
                sucursales = sorted(
                    df_empleados["Sucursal"].dropna().astype(str).unique().tolist()
                )

                sucursales_seleccionadas = st.multiselect(
                    "Selecciona una o varias sucursales",
                    sucursales
                )

                if sucursales_seleccionadas:
                    df_filtrado = df_empleados[
                        df_empleados["Sucursal"].astype(str).isin(sucursales_seleccionadas)
                    ].copy()

                    df_filtrado = df_filtrado.sort_values("__display_name")
                    st.success(f"Empleados encontrados en las sucursales seleccionadas: {len(df_filtrado)}")
                else:
                    st.info("Selecciona al menos una sucursal para ver empleados.")
            else:
                st.warning("No se encontró la columna 'Sucursal' en el archivo.")

        # -------- FILTRO NOMBRE --------
        elif filtro == "Buscar por nombre":
            if "__display_name" in df_empleados.columns:
                nombres_disponibles = sorted(
                    df_empleados["__display_name"]
                    .dropna()
                    .astype(str)
                    .unique()
                    .tolist()
                )

                nombre_elegido = st.selectbox(
                    "Buscar y seleccionar nombre",
                    options=[None] + nombres_disponibles,
                    format_func=lambda x: "Empieza a escribir el nombre..." if x is None else x,
                    key=f"nombre_busqueda_select_{st.session_state.nombre_search_reset}"
                )

                if nombre_elegido:
                    df_filtrado = df_empleados[
                        df_empleados["__display_name"].astype(str) == nombre_elegido
                    ].copy()

                    df_filtrado = df_filtrado.sort_values("__display_name")

                    nuevos_ids = set(df_filtrado["__uid"].tolist())
                    antes = len(st.session_state.selected_ids)

                    st.session_state.selected_ids.update(nuevos_ids)
                    st.session_state.nombre_search_reset += 1

                    despues = len(st.session_state.selected_ids)

                    if despues > antes:
                        st.rerun()
                    else:
                        st.success(f"'{nombre_elegido}' ya estaba agregado en participantes seleccionados.")
                else:
                    st.info("Haz clic en el campo y empieza a escribir para buscar.")
            else:
                st.warning("No se encontró columna de nombre para búsqueda.")

        # -------- SELECCIÓN DE PARTICIPANTES --------
        st.markdown("## Selección de participantes")

        if filtro == "Sucursal" and not df_filtrado.empty:
            col_btn1, col_btn2 = st.columns(2)

            if col_btn1.button("Seleccionar Todos"):
                st.session_state.selected_ids.update(df_filtrado["__uid"].tolist())
                st.rerun()

            if col_btn2.button("Deseleccionar Todos"):
                for uid in df_filtrado["__uid"].tolist():
                    st.session_state.selected_ids.discard(uid)
                st.rerun()

            st.write(f"**Seleccionados acumulados:** {len(st.session_state.selected_ids)}")

            for _, row in df_filtrado.iterrows():
                uid = row["__uid"]
                nombre = row["__display_name"]

                marcado = uid in st.session_state.selected_ids

                valor = st.checkbox(
                    nombre,
                    value=marcado,
                    key=f"chk_{uid}"
                )

                if valor:
                    st.session_state.selected_ids.add(uid)
                else:
                    st.session_state.selected_ids.discard(uid)

        elif filtro == "Buscar por nombre":
            st.info("Al seleccionar un nombre en la búsqueda, se agrega automáticamente a participantes seleccionados.")

        # -------- MOSTRAR SELECCIONADOS --------
        st.markdown("## Participantes seleccionados")

        df_seleccionados = df_empleados[
            df_empleados["__uid"].isin(st.session_state.selected_ids)
        ].copy()

        df_seleccionados = df_seleccionados.sort_values("__display_name")

        if not df_seleccionados.empty:
            st.write(f"**Total seleccionados:** {len(df_seleccionados)}")

            for _, row in df_seleccionados.iterrows():
                uid = row["__uid"]
                nombre = row["__display_name"]

                c1, c2 = st.columns([6, 1])
                c1.write(f"✓ {nombre}")

                if c2.button("Eliminar", key=f"rm_{uid}"):
                    st.session_state.selected_ids.discard(uid)
                    st.rerun()
        else:
            st.info("Aún no has seleccionado participantes.")

    except Exception as e:
        st.error(f"No se pudo leer el archivo Excel: {e}")


# =========================================================
# RESUMEN EN SIDEBAR
# =========================================================
with st.sidebar:
    st.markdown("---")
    st.subheader("Resumen de selección")

    st.write(f"**Empresa:** {empresa}")
    st.write(f"**Área:** {area}")
    st.write(f"**Cursos seleccionados:** {len(cursos_finales)}")
    st.write(f"**Capacitador:** {capacitador}")
    st.write(f"**Modo de fechas:** {modo_fechas}")
    st.write(f"**Participantes seleccionados:** {len(st.session_state.selected_ids)}")

    if cursos_finales:
        st.markdown("**Cursos elegidos:**")
        for curso in cursos_finales:
            st.write(f"- {curso}")

    st.markdown("---")
    st.caption("Barra fija de acciones")


# =========================================================
# GENERACIÓN MASIVA + PDF FINAL
# =========================================================
if btn_generar:
    errores = []

    if not cursos_finales:
        errores.append("Debes seleccionar al menos un curso.")

    if not capacitador or not str(capacitador).strip():
        errores.append("Debes indicar un capacitador.")

    if archivo_empleados is None:
        errores.append("Debes cargar la relación de empleados.")

    if archivo_empleados is not None and len(st.session_state.selected_ids) == 0:
        errores.append("Debes seleccionar al menos un participante.")

    if errores:
        progreso_placeholder.progress(0)
        estado_placeholder.error("No se puede generar todavía.")
        descarga_placeholder.info("Completa los datos para habilitar la generación.")

        st.error("No se puede generar todavía. Revisa lo siguiente:")
        for error in errores:
            st.write(f"- {error}")

    else:
        try:
            if df_seleccionados.empty:
                raise ValueError("No se encontraron participantes seleccionados.")

            if not fechas_cursos or len(fechas_cursos) != len(cursos_finales):
                raise ValueError("No se pudieron resolver correctamente las fechas de los cursos.")

            nombre_plantilla = EMPRESAS[empresa]
            fecha_por_curso = dict(zip(cursos_finales, fechas_cursos))

            total_constancias = len(df_seleccionados) * len(cursos_finales)
            contador = 0
            writer_final = PdfWriter()

            estado_placeholder.info("Generando constancias...")

            for _, participante in df_seleccionados.iterrows():
                nombre_completo = participante["Nombrecompleto"]
                curp = participante["CURP"]
                puesto = participante["Puesto"]

                for curso in cursos_finales:
                    fecha_constancia = fecha_por_curso[curso]

                    nombre_archivo = f"{safe_filename(nombre_completo)}__{safe_filename(curso)}.pdf"

                    ruta_pdf = generar_dc3(
                        nombre_completo=nombre_completo,
                        curp=curp,
                        puesto=puesto,
                        curso=curso,
                        capacitador=capacitador,
                        fecha=fecha_constancia,
                        nombre_plantilla=nombre_plantilla,
                        output_filename=nombre_archivo
                    )

                    with open(ruta_pdf, "rb") as f_pdf:
                        reader_temp = PdfReader(f_pdf)
                        for page in reader_temp.pages:
                            writer_final.add_page(page)

                    # Borrar PDF individual después de agregarlo
                    ruta_tmp = Path(ruta_pdf)
                    if ruta_tmp.exists():
                        ruta_tmp.unlink()

                    contador += 1
                    progreso = int((contador / total_constancias) * 100)
                    progreso_placeholder.progress(progreso)
                    estado_placeholder.info(f"Generando {contador} de {total_constancias} constancias...")

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            nombre_final = f"DC3_FINAL_{safe_filename(empresa)}_{timestamp}.pdf"
            ruta_final = OUTPUT_DIR / nombre_final

            with open(ruta_final, "wb") as f_out:
                writer_final.write(f_out)

            with open(ruta_final, "rb") as f:
                st.session_state.pdf_bytes = f.read()

            st.session_state.pdf_filename = nombre_final
            st.session_state.pdf_generado = True

            progreso_placeholder.progress(100)
            estado_placeholder.success("PDF FINAL generado correctamente.")

            descarga_placeholder.download_button(
                "⬇ Descargar PDF FINAL",
                data=st.session_state.pdf_bytes,
                file_name=st.session_state.pdf_filename,
                mime="application/pdf",
                use_container_width=True,
                key="download_pdf_final"
            )

            st.success("✅ Se generó el PDF final con todas las constancias.")
            st.info(
                f"Participantes: {len(df_seleccionados)} | "
                f"Cursos: {len(cursos_finales)} | "
                f"Constancias generadas: {total_constancias}"
            )

        except Exception as e:
            progreso_placeholder.progress(0)
            estado_placeholder.error("Ocurrió un error al generar.")
            st.error(f"Error al generar el PDF final: {e}")