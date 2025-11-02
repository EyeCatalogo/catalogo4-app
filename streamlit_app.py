import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import tempfile
import requests
from io import BytesIO
from datetime import datetime
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4

st.set_page_config(page_title="Catálogo Premium", page_icon="📦")
st.title("📊 Catálogo Premium de Productos desde Google Sheets")

uploaded_file = st.file_uploader("Sube tu archivo de credenciales (.json)", type="json")

# --- Función para cargar los datos ---
def cargar_datos(credenciales):
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        with tempfile.NamedTemporaryFile(delete=False, suffix=".json") as temp:
            temp.write(credenciales.read())
            temp_path = temp.name

        creds = ServiceAccountCredentials.from_json_keyfile_name(temp_path, scope)
        client = gspread.authorize(creds)

        sheet = client.open("Catalogo").sheet1
        data = sheet.get_all_records()

        df = pd.DataFrame(data)

        # --- Corregir columna 'categoria' ---
        if "categoria" in df.columns:
            df["categoria"] = df["categoria"].fillna(df.get("Categoria", "Sin categoría"))
        elif "Categoria" in df.columns:
            df["categoria"] = df["Categoria"].fillna("Sin categoría")
        else:
            df["categoria"] = "Sin categoría"

        return df

    except Exception as e:
        st.error(f"🚫 Error al conectar con Google Sheets: {e}")
        return None

# --- Cargar datos ---
if uploaded_file is not None:
    if st.button("Cargar datos"):
        df = cargar_datos(uploaded_file)
        if df is not None and not df.empty:
            st.success("✅ Datos cargados correctamente.")
            st.dataframe(df)
            st.session_state["df"] = df
        else:
            st.warning("No se encontraron datos o la hoja está vacía.")
else:
    st.info("🔹 Sube tu archivo de credenciales JSON para comenzar.")

# --- Función para agregar número de página ---
def add_page_number(canvas, doc):
    page_num = canvas.getPageNumber()
    text = f"Página {page_num}"
    canvas.setFont("Helvetica", 8)
    canvas.drawRightString(A4[0] - 2*cm, 1*cm, text)

# --- Función para generar PDF premium ---
def generar_catalogo_premium_pdf(df):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    story = []

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="TituloPrincipal", fontSize=24, leading=28, alignment=1, spaceAfter=20))
    styles.add(ParagraphStyle(name="ProductoTitulo", fontSize=12, leading=14, alignment=1, textColor=colors.HexColor("#2E4053")))
    styles.add(ParagraphStyle(name="ProductoTexto", fontSize=10, leading=12, alignment=1))

    # --- Portada ---
    story.append(Spacer(1, 5*cm))
    story.append(Paragraph("📦 Catálogo de Productos Premium", styles["TituloPrincipal"]))
    story.append(Paragraph(f"Fecha: {datetime.today().strftime('%d/%m/%Y')}", styles["ProductoTexto"]))
    story.append(PageBreak())

    # --- Agrupar por categoría ---
    categorias = df['categoria'].unique()
    for cat in categorias:
        cat_data = df[df['categoria'] == cat]
        story.append(Paragraph(f"Categoría: {cat}", ParagraphStyle(name="CategoriaTitulo", fontSize=16, leading=20, textColor=colors.white, backColor=colors.HexColor("#2E86C1"), alignment=0, spaceAfter=12, spaceBefore=12)))
        
        productos_por_fila = 2
        filas_por_pagina = 3
        productos_por_pagina = productos_por_fila * filas_por_pagina

        for i in range(0, len(cat_data), productos_por_pagina):
            page_data = cat_data.iloc[i:i+productos_por_pagina]
            celdas = []
            fila = []

            for _, row in page_data.iterrows():
                nombre = str(row.get("nombre", row.get("Nombre", ""))) or "N/A"
                categoria = str(row.get("categoria", row.get("Categoria", ""))) or "N/A"
                precio = str(row.get("precio", row.get("Precio", ""))) or "N/A"
                stock = str(row.get("stock", row.get("Stock", ""))) or "N/A"
                imagen_url = str(row.get("imagen", row.get("Imagen", ""))) or ""

                # --- Descargar imagen ---
                if imagen_url.lower() in ["", "nan"]:
                    img = Table([[Paragraph("Imagen no disponible", styles["ProductoTexto"])]],
                                colWidths=[5*cm], rowHeights=[5*cm])
                    img.setStyle(TableStyle([
                        ("BACKGROUND", (0,0), (-1,-1), colors.lightgrey),
                        ("ALIGN", (0,0), (-1,-1), "CENTER"),
                        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
                        ("BOX", (0,0), (-1,-1), 0.25, colors.grey),
                    ]))
                else:
                    try:
                        if "drive.google.com" in imagen_url:
                            if "/d/" in imagen_url:
                                file_id = imagen_url.split("/d/")[1].split("/")[0]
                            elif "id=" in imagen_url:
                                file_id = imagen_url.split("id=")[1].split("&")[0]
                            else:
                                file_id = ""
                            if file_id:
                                imagen_url = f"https://drive.google.com/uc?export=view&id={file_id}"
                        response = requests.get(imagen_url, timeout=10)
                        if response.status_code == 200:
                            img_data = BytesIO(response.content)
                            img = Image(img_data, width=5*cm, height=5*cm)
                        else:
                            raise ValueError("No se pudo descargar la imagen")
                    except Exception:
                        img = Table([[Paragraph("Imagen no disponible", styles["ProductoTexto"])]],
                                    colWidths=[5*cm], rowHeights=[5*cm])
                        img.setStyle(TableStyle([
                            ("BACKGROUND", (0,0), (-1,-1), colors.lightgrey),
                            ("ALIGN", (0,0), (-1,-1), "CENTER"),
                            ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
                            ("BOX", (0,0), (-1,-1), 0.25, colors.grey),
                        ]))

                ficha = [
                    img,
                    Paragraph(f"<b>{nombre}</b>", styles["ProductoTitulo"]),
                    Paragraph(f"Categoría: {categoria}", styles["ProductoTexto"]),
                    Paragraph(f"Precio: ${precio}", styles["ProductoTexto"]),
                    Paragraph(f"Stock: {stock}", styles["ProductoTexto"]),
                ]

                ficha_table = Table([[ficha[0]], [ficha[1]], [ficha[2]], [ficha[3]], [ficha[4]]])
                ficha_table.setStyle(TableStyle([
                    ("ALIGN", (0,0), (-1,-1), "CENTER"),
                    ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
                    ("BOX", (0,0), (-1,-1), 0.25, colors.grey),
                    ("TOPPADDING", (0,0), (-1,-1), 5),
                    ("BOTTOMPADDING", (0,0), (-1,-1), 5),
                ]))

                fila.append(ficha_table)
                if len(fila) == productos_por_fila:
                    celdas.append(fila)
                    fila = []

            if fila:
                celdas.append(fila)

            # Validación de celdas vacías
            for fila_idx, fila_val in enumerate(celdas):
                for col_idx, celda in enumerate(fila_val):
                    if celda is None:
                        celdas[fila_idx][col_idx] = Paragraph("N/A", styles["ProductoTexto"])

            tabla = Table(celdas, colWidths=[9*cm]*productos_por_fila)
            tabla.setStyle(TableStyle([
                ("ALIGN", (0,0), (-1,-1), "CENTER"),
                ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
                ("TOPPADDING", (0,0), (-1,-1), 10),
                ("BOTTOMPADDING", (0,0), (-1,-1), 10),
            ]))
            story.append(tabla)
            story.append(Spacer(1, 1*cm))

        story.append(PageBreak())

    doc.build(story, onFirstPage=add_page_number, onLaterPages=add_page_number)
    buffer.seek(0)
    return buffer

# --- Botón para generar PDF premium ---
if "df" in st.session_state:
    df = st.session_state["df"]

    st.subheader("📄 Generar catálogo Premium PDF")
    if st.button("📘 Generar Catálogo Premium PDF"):
        pdf_buffer = generar_catalogo_premium_pdf(df)
        st.success("Catálogo generado correctamente ✅")
        st.download_button(
            label="⬇️ Descargar Catálogo Premium",
            data=pdf_buffer,
            file_name="catalogo_premium.pdf",
            mime="application/pdf"
        )
