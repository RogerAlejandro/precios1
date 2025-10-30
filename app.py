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
import json

st.set_page_config("Comparador de Precios", layout="wide")

# --- Conexión a Supabase ---
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- Utilidades ---
def get_fakestore_categories():
    """Obtiene las categorías disponibles en FakeStore API"""
    try:
        response = requests.get("https://fakestoreapi.com/products/categories")
        if response.status_code == 200:
            return response.json()
    except Exception:
        pass
    return ["electronics", "jewelery", "men's clothing", "women's clothing"]

def search_fakestore(query):
    """Busca productos en FakeStore API"""
    try:
        # Primero intentamos buscar por categoría
        categories = get_fakestore_categories()
        query_lower = query.lower()
        
        # Verificar si la búsqueda coincide con alguna categoría
        matching_category = next((cat for cat in categories if query_lower in cat.lower()), None)
        
        if matching_category:
            # Si coincide con una categoría, obtener productos de esa categoría
            response = requests.get(f"https://fakestoreapi.com/products/category/{matching_category}")
        else:
            # Si no, buscar en todos los productos
            response = requests.get("https://fakestoreapi.com/products")
            
        if response.status_code == 200:
            products = response.json()
            # Si no es búsqueda por categoría, filtrar por título o descripción
            if not matching_category:
                products = [
                    p for p in products 
                    if (query_lower in p.get('title', '').lower() or 
                        query_lower in p.get('description', '').lower() or
                        query_lower in p.get('category', '').lower())
                ]
            return products
    except Exception as e:
        st.error(f"Error al buscar en FakeStore: {str(e)}")
    return []

def save_to_supabase(products):
    """Guarda los productos en Supabase"""
    if not products:
        return
    
    for product in products:
        try:
            # Verificar si el producto ya existe por nombre
            existing = supabase.table("products")\
                        .select("id")\
                        .eq("name", product['title'])\
                        .execute()
            
            if not existing.data:
                # Insertar nuevo producto
                new_product = {
                    "name": product['title'],
                    "description": product.get('description', ''),
                    "price": float(product['price']),  # Asegurar que sea float
                    "category": product.get('category', ''),
                    "image_url": product.get('image', ''),
                    "created_at": datetime.now().isoformat()
                }
                
                # Insertar en Supabase
                result = supabase.table("products").insert(new_product).execute()
                if hasattr(result, 'error') and result.error:
                    st.error(f"Error al guardar: {result.error}")
                else:
                    st.success(f"¡{product['title']} agregado correctamente!")
                    st.rerun()
            else:
                st.info(f"El producto {product['title']} ya existe en la base de datos")
                
        except Exception as e:
            st.error(f"Error al guardar producto: {str(e)}")
            # Mostrar más detalles del error para depuración
            if hasattr(e, 'message'):
                st.json(e.message)
            elif hasattr(e, 'args') and e.args:
                st.json(e.args[0])

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

# Get products list
products_df = get_products()
product_options = products_df['name'].tolist() if not products_df.empty else []

# Sidebar: Home button
if st.sidebar.button("🏠 Inicio"):
    selected = "-- Todos --"
else:
    st.sidebar.markdown("---")
    st.sidebar.subheader("🔍 Búsqueda en FakeStore")
    st.sidebar.caption("Sugerencias: electronics, jewelery, men's clothing, women's clothing")
    st.sidebar.subheader("Seleccionar o escribir producto")
    selected_from_list = st.sidebar.selectbox(
        "Producto existente", 
        ["-- Ninguno --"] + product_options
    )
    selected_manual = st.sidebar.text_input("O escribe un producto nuevo", "")
    
    # Determinar cuál usar
    fakestore_results = []
    if selected_manual.strip() != "":
        selected = selected_manual.strip()
        # Buscar en FakeStore API cuando se escribe manualmente
        fakestore_results = search_fakestore(selected)
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
if selected_manual.strip() != "" and fakestore_results:
    st.subheader(f"Resultados de búsqueda para: {selected_manual}")
    
    # Mostrar resultados de FakeStore en la sección principal
    st.info(f"💡 Mostrando {len(fakestore_results)} resultados. Prueba con: electronics, jewelery, men's clothing, women's clothing")
    
    # Agrupar por categoría
    products_by_category = {}
    for product in fakestore_results:
        category = product.get('category', 'Otros')
        if category not in products_by_category:
            products_by_category[category] = []
        products_by_category[category].append(product)
    
    # Mostrar por categorías
    for category, products in products_by_category.items():
        st.subheader(f"📁 {category.title()}")
        cols = st.columns(3)  # 3 columnas para mostrar los productos
        
        for idx, product in enumerate(products):
            with cols[idx % 3]:
                # Tarjeta de producto con borde usando columnas
                col1, col2 = st.columns([1, 4])
                
                with col1:
                    # Imagen
                    st.image(
                        product.get('image', ''), 
                        width=100,
                        use_column_width=True
                    )
                
                with col2:
                    # Título con límite de caracteres
                    title = (product['title'][:30] + '...') if len(product['title']) > 30 else product['title']
                    st.subheader(title, help=product['title'])  # Tooltip con título completo
                    
                    # Precio
                    st.markdown(f"**Precio:** ${product['price']}")
                    
                    # Rating si está disponible
                    if 'rating' in product and product['rating']:
                        rating = product['rating']
                        stars = '⭐' * int(rating.get('rate', 0))
                        st.caption(f"{stars} ({rating.get('count', 0)} reseñas)")
                    
                    # Botón de acción
                    if st.button(
                        "➕ Agregar al comparador", 
                        key=f"add_{product['id']}",
                        use_container_width=True
                    ):
                        save_to_supabase([product])
                        st.rerun()
                
                # Línea divisoria
                st.markdown("---")
    
    st.markdown("---")
elif selected == "-- Todos --":
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
    prod_match = products_df[products_df['name'] == selected]
    if not prod_match.empty:
        prod = prod_match.iloc[0].to_dict()
        product_id = prod.get("id")
    else:
        prod = {}
        product_id = None
    st.subheader(f"Historial de precios — {selected}")
    hist = get_price_history(product_id)
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
