import streamlit as st
import pandas as pd
import numpy as np
from supabase import create_client
import plotly.express as px
import requests
from datetime import datetime
from fpdf import FPDF
from io import BytesIO
import base64

st.set_page_config("Comparador de Precios", layout="wide")

# --- Conexión a Supabase ---
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- Utilidades ---
def get_products():
    res = supabase.table("products").select("*").execute()
    return pd.DataFrame(res.data) if res.data else pd.DataFrame()

def get_price_history(product_id=None):
    q = supabase.table("price_history").select("*")
    if product_id:
        q = q.eq("product_id", product_id)
    res = q.order("timestamp", desc=True).limit(500).execute()
    df = pd.DataFrame(res.data)
    return df

def generate_pdf(df):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 14)
    pdf.cell(0, 10, "Resumen de Precios", 0, 1, "C")
    pdf.set_font("Arial", "", 10)

    for _, r in df.iterrows():
        product_name = r.get("product_name") or r.get("product_id", "Desconocido")
        pdf.multi_cell(
    190,  # ancho en mm, menor que A4 que es ~210 mm
    8,
    f"{product_name} | {r['site_name']} | ${r['price']} | {r['timestamp']}",
)


    buf = BytesIO()
    pdf.output(buf)
    buf.seek(0)
    return buf

# --- UI ---
st.title("💰 Comparador de Precios — Dashboard")

# Sidebar: seleccionar o escribir producto
products_df = get_products()
product_options = products_df['name'].tolist() if not products_df.empty else []

st.sidebar.subheader("Seleccionar o escribir producto")
selected_from_list = st.sidebar.selectbox("Producto existente", ["-- Ninguno --"] + product_options)
selected_manual = st.sidebar.text_input("O escribe un producto nuevo", "")

# Determinar cuál usar
if selected_manual.strip() != "":
    selected = selected_manual.strip()
elif selected_from_list != "-- Ninguno --":
    selected = selected_from_list
else:
    selected = "-- Todos --"

# Botón para "Check now" que llama webhook de n8n
n8n_url = st.secrets.get("N8N_WEBHOOK_URL", "")
if st.sidebar.button("Check now (n8n webhook)", key="check_now_webhook") and n8n_url:
    payload = {}
    if selected != "-- Todos --":
        prod = products_df[products_df['name'] == selected].iloc[0] if selected in product_options else {}
        payload = {
            "product": selected,
            "product_id": prod.get("id") if prod else None,
            "url": prod.get("example_url") if prod else ""
        }
    else:
        payload = {"action":"check_all"}

    try:
        r = requests.post(n8n_url, json=payload, timeout=30)
        if r.ok:
            st.success("Solicitud enviada a n8n")
        else:
            st.error(f"Webhook error: {r.status_code} {r.text}")
    except Exception as e:
        st.error("Error al llamar webhook: " + str(e))

# Mostrar tabla principal y gráficos
if selected == "-- Todos --":
    ph = get_price_history()
    if ph.empty:
        st.info("No hay historial de precios aún.")
    else:
        prod_map = products_df.set_index("id")["name"].to_dict()
        ph["name"] = ph["product_id"].map(prod_map)
        latest = ph.sort_values("timestamp").groupby("product_id").tail(1)
        latest = latest.sort_values("price")
        st.subheader("Últimos precios (por producto)")
        st.dataframe(latest[["name","site_name","price","timestamp","url"]].rename(columns={"name":"Producto"}), use_container_width=True)
        st.subheader("Evolución (selecciona producto a la izquierda para ver gráfico)")
else:
    prod = products_df[products_df['name'] == selected].iloc[0] if selected in product_options else {}
    st.subheader(f"Historial de precios — {selected}")
    hist = get_price_history(prod.get("id") if prod else None)
    if hist.empty:
        st.warning("No hay datos de historial para este producto.")
    else:
        hist['timestamp'] = pd.to_datetime(hist['timestamp'])
        hist = hist.sort_values('timestamp')
        st.dataframe(hist[['site_name','price','timestamp','url']], use_container_width=True)
        fig = px.line(hist, x='timestamp', y='price', color='site_name', markers=True,
                      labels={'timestamp':'Fecha','price':'Precio ($)','site_name':'Sitio'})
        st.plotly_chart(fig, use_container_width=True)
        if st.button("Generar PDF resumen", key="pdf_button"):
            pdf_buf = generate_pdf(hist.sort_values('timestamp').groupby('site_name').tail(5))
            b64 = base64.b64encode(pdf_buf.read()).decode()
            href = f'<a href="data:application/octet-stream;base64,{b64}" download="reporte_{selected}.pdf">Descargar PDF</a>'
            st.markdown(href, unsafe_allow_html=True)

# Footer
st.markdown("---")
st.write("Conectado a Supabase:", SUPABASE_URL)
