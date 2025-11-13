import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import json
import os
import io
from datetime import datetime
import re
import random
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import warnings
import logging
import plotly.express as px
import pandas as pd
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Obtener la URL del webhook de análisis de tendencia
TREND_ANALYSIS_WEBHOOK_URL = os.getenv('TREND_ANALYSIS_WEBHOOK_URL')
import numpy as np
from fpdf import FPDF
import tempfile
import base64
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from email.utils import formataddr
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Configuración SMTP
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")


# Configurar logging para debugging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

warnings.filterwarnings('ignore')

# Configuración de la página
st.set_page_config(
    page_title="Tracker de Precios",
    page_icon="🛒",
    layout="wide"
)

# URL del webhook de n8n
N8N_WEBHOOK_URL = "http://localhost:5678/webhook-test/webhook-test/tu-webhook-secreto"

def enviar_por_correo(email, producto, pdf_bytes):
    """Envía un correo con el PDF adjunto directamente por SMTP"""
    try:
        if not all([SMTP_SERVER, SMTP_PORT, SMTP_USER, SMTP_PASSWORD]):
            st.error("Error de configuración: Faltan credenciales SMTP")
            return False
            
        # Crear mensaje
        msg = MIMEMultipart()
        msg['From'] = formataddr(('Tracker de Precios', SMTP_USER))
        msg['To'] = email
        msg['Subject'] = f"📊 Reporte de precios - {producto.get('titulo', 'Producto')[:50]}"
        
        # Cuerpo del mensaje
        cuerpo = f"""
        <html>
            <body>
                <h2>¡Hola! Aquí tienes el reporte de precios que solicitaste</h2>
                <div style="background-color: #f5f5f5; padding: 20px; border-radius: 10px; margin: 20px 0;">
                    <h3>{producto.get('titulo', 'Producto')}</h3>
                    <p><strong>Precio actual:</strong> ${producto.get('precio_actual', 'No disponible')}</p>
                    <p><strong>Tienda:</strong> {producto.get('tienda', 'No especificada')}</p>
                </div>
                <p>Adjunto encontrarás el reporte detallado en formato PDF.</p>
                <p>¡Gracias por usar nuestro servicio de seguimiento de precios!</p>
                <p>Saludos,<br>El equipo de Tracker de Precios</p>
            </body>
        </html>
        """
        
        # Adjuntar cuerpo HTML
        msg.attach(MIMEText(cuerpo, 'html'))
        
        # Adjuntar PDF
        nombre_archivo = f"reporte_{producto.get('id', '')}_{datetime.now().strftime('%Y%m%d%H%M%S')}.pdf"
        adjunto = MIMEApplication(pdf_bytes, _subtype='pdf')
        adjunto.add_header('Content-Disposition', 'attachment', filename=nombre_archivo)
        msg.attach(adjunto)
        
        # Enviar correo
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)
            
        return True
        
    except smtplib.SMTPAuthenticationError:
        st.error("Error de autenticación: Verifica tu usuario y contraseña de Gmail")
        return False
    except smtplib.SMTPException as e:
        st.error(f"Error al enviar el correo: {str(e)}")
        return False
    except Exception as e:
        st.error(f"Error inesperado: {str(e)}")
        return False

# Estilos globales
st.markdown("""
    <style>
        /* Estilos generales */
        .main {
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            color: #e6e6e6;
        }
        
        /* Estilos para tarjetas */
        .card {
            background: rgba(255, 255, 255, 0.03);
            border-radius: 16px;
            padding: 1.5rem;
            border: 1px solid rgba(255, 255, 255, 0.1);
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            margin-bottom: 1.5rem;
            transition: all 0.3s ease;
        }
        
        .card:hover {
            border-color: rgba(110, 69, 226, 0.4);
            box-shadow: 0 8px 15px rgba(0, 0, 0, 0.2);
            transform: translateY(-2px);
        }
        
        /* Estilos para botones */
        .stButton>button {
            background: linear-gradient(45deg, #6e45e2, #88d3ce);
            border: none;
            color: white;
            padding: 0.5rem 1.5rem;
            text-align: center;
            text-decoration: none;
            display: inline-block;
            font-size: 0.9rem;
            margin: 4px 2px;
            cursor: pointer;
            border-radius: 12px;
            transition: all 0.3s ease;
            box-shadow: 0 2px 5px rgba(0,0,0,0.2);
        }
        
        .stButton>button:hover {
            transform: translateY(-1px);
            box-shadow: 0 4px 8px rgba(0,0,0,0.3);
        }
        
        /* Estilos para inputs */
        .stTextInput>div>div>input {
            background: rgba(17, 24, 39, 0.3) !important;
            border: 1px solid rgba(255, 255, 255, 0.1) !important;
            color: white !important;
            border-radius: 12px !important;
            padding: 0.75rem 1rem !important;
        }
        
        .stTextInput>div>div>input:focus {
            border-color: #6e45e2 !important;
            box-shadow: 0 0 0 2px rgba(110, 69, 226, 0.2) !important;
        }
        
        /* Estilos para pestañas */
        .stTabs [data-baseweb="tab-list"] {
            gap: 8px;
        }
        
        .stTabs [data-baseweb="tab"] {
            background: rgba(255, 255, 255, 0.05);
            border-radius: 12px !important;
            padding: 0.5rem 1.5rem;
            margin: 0 2px;
            transition: all 0.3s ease;
        }
        
        .stTabs [data-baseweb="tab"]:hover {
            background: rgba(110, 69, 226, 0.2);
        }
        
        .stTabs [aria-selected="true"] {
            background: linear-gradient(45deg, #6e45e2, #88d3ce) !important;
            color: white !important;
        }
        
        /* Estilos para la barra lateral */
        [data-testid="stSidebar"] {
            background: linear-gradient(180deg, #1a1a2e 0%, #16213e 100%) !important;
            border-right: 1px solid rgba(255, 255, 255, 0.1);
        }
        
        /* Estilos para títulos */
        h1, h2, h3 {
            color: #f0f0f0;
        }
        
        /* Estilos para tablas */
        .stDataFrame {
            border-radius: 12px;
            overflow: hidden;
        }
        
        /* Estilos para los mensajes de estado */
        .status-message {
            background: rgba(255, 255, 255, 0.05);
            border-radius: 12px;
            padding: 0.5rem 1rem;
            margin: 0.25rem 0;
            display: inline-flex;
            align-items: center;
            gap: 0.5rem;
        }
    </style>
""", unsafe_allow_html=True)

# Intentar importar supabase con manejo de errores
SUPABASE_AVAILABLE = False
supabase_client = None

try:
    from supabase import create_client
    SUPABASE_AVAILABLE = True
except ImportError as e:
    st.error(f"❌ Error importando Supabase: {e}")

# Configuración de Supabase


@st.cache_resource
def init_supabase():
    # Crear un contenedor para los mensajes de estado
    status_container = st.container()
    
    if not SUPABASE_AVAILABLE:
        with status_container:
            st.error("❌ Supabase no está disponible")
        return None

    try:
        if "supabase" not in st.secrets:
            with status_container:
                st.error("❌ No se encontró la sección 'supabase' en secrets.toml")
            return None

        supabase_url = st.secrets["supabase"]["SUPABASE_URL"]
        supabase_key = st.secrets["supabase"]["SUPABASE_KEY"]

        if not supabase_url or not supabase_key:
            with status_container:
                st.error("❌ URL o KEY de Supabase están vacíos")
            return None

        # Mostrar los tres estados juntos
        with status_container:
            col1, col2, col3 = st.columns(3)
            with col1:
                st.success("✅ Supabase disponible")
            with col2:
                st.success("✅ Credenciales válidas")
            
            client = create_client(supabase_url, supabase_key)
            
            with col3:
                st.success("✅ Cliente creado")
            
            # Añadir un poco de espacio después de los mensajes
            st.markdown("<div style='margin-bottom: 1rem;'></div>", unsafe_allow_html=True)
            
        return client

    except Exception as e:
        with status_container:
            st.error(f"❌ Error inicializando Supabase: {str(e)}")
        return None

# Funciones de base de datos (se mantienen igual)


def guardar_producto_supabase(_supabase, producto_info):
    if not _supabase:
        st.error("❌ No hay conexión a Supabase")
        return None

    try:
        response = _supabase.table('productos')\
            .select('*')\
            .eq('enlace', producto_info['enlace'])\
            .execute()

        if response.data and len(response.data) > 0:
            producto_existente = response.data[0]
            nuevo_precio = producto_info['precio']
            precio_anterior = producto_existente['precio_actual']

            _supabase.table('productos')\
                .update({
                    'precio_actual': nuevo_precio,
                    'updated_at': datetime.now().isoformat()
                })\
                .eq('id', producto_existente['id'])\
                .execute()

            if abs(precio_anterior - nuevo_precio) > 0.01:
                _supabase.table('historial_precios')\
                    .insert({
                        'producto_id': producto_existente['id'],
                        'precio': nuevo_precio,
                        'fecha_consulta': datetime.now().isoformat()
                    })\
                    .execute()

            return producto_existente['id']
        else:
            producto_data = {
                'titulo': producto_info['titulo'],
                'precio_actual': producto_info['precio'],
                'precio_inicial': producto_info['precio'],
                'enlace': producto_info['enlace'],
                'imagen': producto_info.get('imagen', ''),
                'tienda': producto_info['tienda'],
                'query_original': producto_info.get('query_original', ''),
                'fecha_seguimiento': datetime.now().isoformat()
            }

            response = _supabase.table('productos')\
                .insert(producto_data)\
                .execute()

            if response.data:
                producto_id = response.data[0]['id']

                _supabase.table('historial_precios')\
                    .insert({
                        'producto_id': producto_id,
                        'precio': producto_info['precio'],
                        'fecha_consulta': datetime.now().isoformat()
                    })\
                    .execute()

                return producto_id

        return None
    except Exception as e:
        st.error(f"Error guardando producto en Supabase: {e}")
        return None


def obtener_productos_seguimiento(_supabase):
    if not _supabase:
        st.error("❌ No hay conexión a Supabase")
        return []

    try:
        response = _supabase.table('productos')\
            .select('*')\
            .order('created_at', desc=True)\
            .execute()
        return response.data if response.data else []
    except Exception as e:
        st.error(f"Error obteniendo productos: {e}")
        return []


def obtener_historial_producto(_supabase, producto_id):
    if not _supabase:
        return []

    try:
        response = _supabase.table('historial_precios')\
            .select('*')\
            .eq('producto_id', producto_id)\
            .order('fecha_consulta')\
            .execute()
        return response.data if response.data else []
    except Exception as e:
        st.error(f"Error obteniendo historial: {e}")
        return []


def eliminar_producto(_supabase, producto_id):
    if not _supabase:
        return False

    try:
        _supabase.table('productos')\
            .delete()\
            .eq('id', producto_id)\
            .execute()
        return True
    except Exception as e:
        st.error(f"Error eliminando producto: {e}")
        return False


def actualizar_precio_producto(_supabase, producto):
    """Actualiza el precio de un producto de manera rápida y confiable"""
    if not _supabase or not isinstance(producto, dict) or 'id' not in producto:
        st.error("❌ Datos de producto inválidos")
        return False

    try:
        # Usar requests para obtener el HTML directamente (más rápido que Selenium)
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        
        st.info(f"🔍 Actualizando precio para: {producto['titulo'][:50]}...")
        
        # Obtener la página del producto
        response = requests.get(producto['enlace'], headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Selectores actualizados para MercadoLibre
        precio_selectors = [
            {'selector': '.price-tag-fraction', 'attribute': 'text'},
            {'selector': '.andes-money-amount__fraction', 'attribute': 'text'},
            {'selector': '.ui-pdp-price__second-line .price-tag-fraction', 'attribute': 'text'},
            {'selector': '.ui-pdp-price__part', 'attribute': 'text'},
            {'selector': '[itemprop="price"]', 'attribute': 'content'}
        ]
        
        # Buscar el precio usando los selectores
        nuevo_precio = None
        for item in precio_selectors:
            element = soup.select_one(item['selector'])
            if element:
                try:
                    if item['attribute'] == 'text':
                        precio_texto = element.get_text(strip=True)
                    else:
                        precio_texto = element.get(item['attribute'], '')
                    
                    nuevo_precio = limpiar_precio(precio_texto)
                    if nuevo_precio and nuevo_precio > 0:
                        break
                except:
                    continue
        
        if not nuevo_precio or nuevo_precio <= 0:
            st.warning("⚠️ No se pudo obtener el precio. Intenta nuevamente.")
            # Guardar el HTML para depuración
            with open(f"debug_price_{producto['id']}.html", "w", encoding="utf-8") as f:
                f.write(soup.prettify())
            return False
        
        # Redondear a 2 decimales
        nuevo_precio = round(float(nuevo_precio), 2)
        precio_anterior = round(float(producto.get('precio_actual', 0)), 2)
        
        # Actualizar en la base de datos
        _supabase.table('productos')\
            .update({
                'precio_actual': nuevo_precio,
                'updated_at': datetime.now().isoformat()
            })\
            .eq('id', producto['id'])\
            .execute()
        
        # Actualizar la hora de actualización del producto
        _supabase.table('productos')\
            .update({
                'updated_at': datetime.now().isoformat()
            })\
            .eq('id', producto['id'])\
            .execute()
        
        # Siempre registrar en el historial, incluso si el precio no cambió
        _supabase.table('historial_precios')\
            .insert({
                'producto_id': producto['id'],
                'precio': nuevo_precio,
                'fecha_consulta': datetime.now().isoformat()
            })\
            .execute()
        
        # Mostrar el resultado
        if abs(nuevo_precio - precio_anterior) < 0.01:
            st.success(f"✅ Precio actual: ${nuevo_precio:,.2f} (registrado en historial)")
        else:
            st.success(f"✅ Precio actualizado: ${precio_anterior:,.2f} → ${nuevo_precio:,.2f}")
        
        return True
        
    except requests.RequestException as e:
        st.error(f"❌ Error de conexión: {str(e)}")
        return False
    except Exception as e:
        st.error(f"❌ Error inesperado: {str(e)}")
        return False
    """Actualiza el precio de un producto específico usando su enlace directo"""
    if not _supabase or not isinstance(producto, dict) or 'id' not in producto:
        st.error("❌ Datos de producto inválidos")
        return False

    try:
        # Si el producto tiene enlace de MercadoLibre
        if 'enlace' in producto and 'mercadolibre' in producto.get('enlace', ''):
            driver = None
            try:
                driver = setup_driver()
                if not driver:
                    st.error("❌ No se pudo inicializar el navegador")
                    return False

                # Navegar directamente a la página del producto
                st.info(f"🔍 Actualizando precio para: {producto['titulo'][:50]}...")
                driver.get(producto['enlace'])
                
                # Esperar a que cargue la página
                time.sleep(3)
                
                # Extraer el precio directamente
                page_source = driver.page_source
                soup = BeautifulSoup(page_source, 'html.parser')
                
                # Intentar diferentes selectores de precio
                precio_selectors = [
                    '.price-tag-fraction',  # Selector principal
                    '.andes-money-amount__fraction',  # Selector alternativo
                    '.price-tag-text-sr-only',  # Para accesibilidad
                    '.ui-pdp-price__second-line'  # Otra variante
                ]
                
                nuevo_precio = None
                for selector in precio_selectors:
                    precio_elem = soup.select_one(selector)
                    if precio_elem:
                        precio_texto = precio_elem.text.strip()
                        nuevo_precio = limpiar_precio(precio_texto)
                        if nuevo_precio and nuevo_precio > 0:
                            break
                
                if not nuevo_precio or nuevo_precio <= 0:
                    st.warning("⚠️ No se pudo obtener el precio. Revisando el HTML...")
                    # Guardar HTML para depuración
                    with open("debug_price_update.html", "w", encoding="utf-8") as f:
                        f.write(soup.prettify())
                    return False
                
                # Verificar si el precio cambió
                precio_anterior = producto.get('precio_actual', 0)
                if abs(nuevo_precio - precio_anterior) < 0.01:
                    st.info("ℹ️ El precio no ha cambiado")
                    return True
                
                # Actualizar en la base de datos
                response = _supabase.table('productos')\
                    .update({
                        'precio_actual': nuevo_precio,
                        'fecha_actualizacion': datetime.now().isoformat()
                    })\
                    .eq('id', producto['id'])\
                    .execute()
                
                if not response.data:
                    st.error("❌ Error al actualizar el producto")
                    return False
                
                # Registrar en el historial
                _supabase.table('historial_precios')\
                    .insert({
                        'producto_id': producto['id'],
                        'precio': nuevo_precio,
                        'fecha_consulta': datetime.now().isoformat()
                    })\
                    .execute()
                
                st.success(f"✅ Precio actualizado: ${precio_anterior:,.2f} → ${nuevo_precio:,.2f}")
                return True
                
            except Exception as e:
                st.error(f"❌ Error al actualizar el precio: {str(e)}")
                return False
            finally:
                if driver:
                    driver.quit()
        else:
            st.warning("⚠️ No se puede actualizar: enlace no compatible")
            return False
            
    except Exception as e:
        st.error(f"❌ Error en actualizar_precio_producto: {str(e)}")
        return False


# Función para analizar la tendencia de precios
def analizar_tendencia(historial):
    """Analiza la tendencia de precios y devuelve una predicción clara"""
    try:
        if not historial or len(historial) < 2:
            return "### 🔍 No hay suficientes datos para predecir la tendencia"
        
        # Convertir a DataFrame
        df = pd.DataFrame(historial)
        
        # Verificar si existe la columna 'fecha' y si no, usar el índice
        if 'fecha' in df.columns:
            try:
                df['fecha'] = pd.to_datetime(df['fecha'])
            except:
                df['fecha'] = pd.to_datetime('today') - pd.to_timedelta(range(len(df)-1, -1, -1), unit='d')
        else:
            df['fecha'] = pd.to_datetime('today') - pd.to_timedelta(range(len(df)-1, -1, -1), unit='d')
            
        # Asegurarse de que hay una columna de precio
        if 'precio' not in df.columns:
            return "### ❌ Error: No se encontraron precios en el historial"
            
        # Ordenar por fecha
        df = df.sort_values('fecha')
        
        # Calcular cambios
        df['cambio'] = df['precio'].diff()
        df['porcentaje_cambio'] = (df['precio'].pct_change()) * 100
        
        # Obtener últimos cambios
        ultimos_cambios = df['cambio'].dropna().tail(5).values
        
        # Calcular tendencia con regresión lineal simple
        X = np.arange(len(df)).reshape(-1, 1)
        y = df['precio'].values
        
        if len(df) > 1:  # Necesitamos al menos 2 puntos para una línea
            from sklearn.linear_model import LinearRegression
            model = LinearRegression()
            model.fit(X, y)
            pendiente = model.coef_[0]
            
            # Predecir siguiente valor
            siguiente_x = len(df)
            prediccion = model.predict([[siguiente_x]])[0]
            precio_actual = df['precio'].iloc[-1]
            
            # Determinar tendencia
            if abs(pendiente) < 0.01:  # Si la pendiente es casi cero
                tendencia = "🟰 SE MANTIENE"
                prediccion_texto = "El precio probablemente se mantendrá estable"
            elif pendiente > 0:
                tendencia = "🔼 SUBE"
                aumento = prediccion - precio_actual
                prediccion_texto = f"El precio podría subir a ${prediccion:,.2f} (${aumento:,.2f} más)"
            else:
                tendencia = "🔻 BAJA"
                disminucion = precio_actual - prediccion
                prediccion_texto = f"El precio podría bajar a ${prediccion:,.2f} (${disminucion:,.2f} menos)"
        else:
            tendencia = "➖ SIN TENDENCIA CLARA"
            prediccion_texto = "Se necesita más historial para predecir"
        
        # Generar análisis
        analisis = f"""
        ### 📊 PREDICCIÓN DE PRECIO
        
        ## {tendencia}
        
        **{prediccion_texto}**
        
        ---
        
        ### 📈 Datos actuales:
        - **Precio actual:** ${df['precio'].iloc[-1]:,.2f}
        - **Precio más bajo:** ${df['precio'].min():,.2f}
        - **Precio más alto:** ${df['precio'].max():,.2f}
        
        ### 📅 Últimos movimientos:
        """
        
        # Mostrar los últimos 3-5 cambios
        for idx, row in df.tail(5).iterrows():
            precio = row.get('precio', 0)
            cambio = row.get('cambio', 0)
            fecha = row.get('fecha', '')
            
            # Formatear fecha
            if hasattr(fecha, 'strftime'):
                fecha_str = fecha.strftime('%d/%m')
            else:
                fecha_str = str(fecha)[:10]
                
            if pd.notna(cambio) and cambio > 0:
                analisis += f"- {fecha_str}: ${precio:,.2f} (+${cambio:.2f} ▲)\n"
            elif pd.notna(cambio) and cambio < 0:
                analisis += f"- {fecha_str}: ${precio:,.2f} ({cambio:,.2f} ▼)\n"
            else:
                analisis += f"- {fecha_str}: ${precio:,.2f} (Mismo precio)\n"
        
        # Añadir recomendación basada en la tendencia
        analisis += "\n💡 **Consejo rápido:** "
        if "SUBE" in tendencia:
            analisis += "Si necesitas este producto, podrías considerar comprarlo pronto antes de que el precio aumente más."
        elif "BAJA" in tendencia:
            analisis += "Si puedes esperar, el precio podría seguir bajando. Podrías conseguir un mejor precio si esperas un poco más."
        else:
            analisis += "El precio parece estable. Si necesitas el producto, es un buen momento para comprar."
        
        return analisis
        
    except Exception as e:
        return f"""
        ### ❌ Error en el análisis
        
        No se pudo completar la predicción de tendencia.
        
        **Detalles:**
        ```
        {str(e)}
        ```
        
        Intenta actualizar los precios y vuelve a intentarlo.
        """
    
    return analisis

# FUNCIONES DE SCRAPING ACTUALIZADAS


def limpiar_precio(precio_texto):
    """Limpiar y convertir el precio a número"""
    if not precio_texto:
        return 0
    
    # Convertir a string por si acaso
    precio_str = str(precio_texto).strip()
    
    # Si el precio está en formato "1.234,56" (punto como separador de miles y coma decimal)
    if ',' in precio_str and '.' in precio_str:
        # Si hay más de una coma, es probable que sea el formato peruano (1,234.56 -> 1234.56)
        if precio_str.find(',') < precio_str.rfind(','):
            # Formato: 1,234.56 -> 1234.56
            precio_limpio = precio_str.replace(',', '')
        else:
            # Formato: 1.234,56 -> 1234.56
            precio_limpio = precio_str.replace('.', '').replace(',', '.')
    # Si solo hay comas, verificar si es el separador decimal
    elif ',' in precio_str:
        # Si hay más de 3 dígitos después de la última coma, probablemente sea el separador de miles
        ultima_coma = precio_str.rfind(',')
        if len(precio_str) - ultima_coma > 3:
            # Es un separador de miles, eliminarlo
            precio_limpio = precio_str.replace(',', '')
        else:
            # Es un separador decimal, cambiar por punto
            precio_limpio = precio_str.replace(',', '.')
    else:
        # No hay comas, usar el valor tal cual
        precio_limpio = precio_str
    
    # Eliminar cualquier caracter que no sea dígito o punto
    precio_limpio = re.sub(r'[^\d.]', '', precio_limpio)
    
    # Asegurarse de que solo haya un punto decimal
    if precio_limpio.count('.') > 1:
        partes = precio_limpio.split('.')
        precio_limpio = ''.join(partes[:-1]) + '.' + partes[-1]
    
    try:
        return float(precio_limpio)
    except (ValueError, TypeError):
        st.write(f"Error al convertir precio: '{precio_texto}' -> '{precio_limpio}'")
        return 0


def setup_driver():
    """Configurar Selenium WebDriver con mejores opciones"""
    try:
        chrome_options = Options()
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument(
            "--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option(
            "excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        chrome_options.add_argument(
            "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--disable-extensions")

        driver = webdriver.Chrome(options=chrome_options)
        driver.execute_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        return driver
    except Exception as e:
        st.error(f"Error configurando Chrome: {e}")
        return None


def buscar_mercado_libre_selenium(query):
    """Buscar productos en Mercado Libre con selectores actualizados"""
    driver = None
    try:
        driver = setup_driver()
        if not driver:
            return []

        # URL corregida para Perú
        url = f"https://listado.mercadolibre.com.pe/{query.replace(' ', '-')}"
        st.write(f"🔍 Navegando a: {url}")

        driver.get(url)

        # Esperar más tiempo y con condiciones específicas
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )

        # Esperar a que carguen los productos
        time.sleep(3)

        # Tomar screenshot para debugging (opcional)
        # driver.save_screenshot("mercado_libre_debug.png")

        html = driver.page_source
        soup = BeautifulSoup(html, 'html.parser')

        # Guardar HTML para análisis (debugging)
        with open("mercado_libre_debug.html", "w", encoding="utf-8") as f:
            f.write(soup.prettify())

        productos = []

        # SELECTORES ACTUALIZADOS para Mercado Libre 2024
        selectores_posibles = [
            'li.ui-search-layout__item',
            'ol.ui-search-layout li',
            'div.ui-search-result',
            'section[data-component="search.results"] li',
            '.andes-card',
            '[data-testid="search-results"] li',
            '.ui-search-result__wrapper'
        ]

        items_encontrados = []
        for selector in selectores_posibles:
            items = soup.select(selector)
            if items:
                st.write(
                    f"✅ Encontrados {len(items)} elementos")
                items_encontrados = items
                break

        if not items_encontrados:
            st.warning(
                "❌ No se encontraron elementos con los selectores comunes")
            # Buscar cualquier elemento que contenga información de producto
            items_encontrados = soup.find_all(['div', 'li'], class_=lambda x: x and any(
                word in str(x).lower() for word in ['item', 'result', 'product', 'card']))
            st.write(
                f"Elementos encontrados con búsqueda amplia: {len(items_encontrados)}")

        for i, item in enumerate(items_encontrados[:5]):  # Procesar primeros 5
            try:
                producto_info = extraer_info_producto_ml(item, i)
                if producto_info:
                    productos.append(producto_info)

            except Exception as e:
                st.write(f"❌ Error procesando item {i}: {str(e)}")
                continue

        # Ordenar productos por precio de menor a mayor
        productos_ordenados = sorted(productos, key=lambda x: x['precio'] if x['precio'] > 0 else float('inf'))
        
        # Mostrar mensaje con el rango de precios
        if productos_ordenados:
            st.success(f"✅ Encontrados {len(productos_ordenados)} productos. Precios desde S/ {productos_ordenados[0]['precio']:,.2f} hasta S/ {productos_ordenados[-1]['precio']:,.2f}")
        
        return productos_ordenados

    except Exception as e:
        st.error(f"🚨 Error en Mercado Libre: {str(e)}")
        return []
    finally:
        if driver:
            driver.quit()


def extraer_info_producto_ml(item, index):
    """Extraer información del producto de Mercado Libre"""
    try:
        # TÍTULO - Múltiples selectores
        titulo = "Sin título"
        titulo_selectors = [
            'h2.ui-search-item__title',
            '.ui-search-item__title',
            'h2',
            '.ui-search-result__title',
            '[class*="title"]',
            'a.ui-search-item__group__element'
        ]

        for selector in titulo_selectors:
            titulo_elem = item.select_one(selector)
            if titulo_elem and titulo_elem.get_text(strip=True):
                titulo = titulo_elem.get_text(strip=True)
                break

        # PRECIO - Extraer el precio correcto
        precio = 0
        
        # 1. Primero buscar el precio en la estructura estándar (más confiable)
        precio_container = item.select_one('div.ui-search-price__second-line')
        if not precio_container:
            precio_container = item.select_one('div.ui-search-price')
            
        if precio_container:
            # Buscar el precio principal (parte entera)
            precio_elem = precio_container.select_one('span.andes-money-amount__fraction')
            
            if precio_elem:
                precio_texto = precio_elem.get_text(strip=True).replace('.', '')
                
                # Buscar céntimos (si existen)
                centavos_elem = precio_container.select_one('span.andes-money-amount__cents')
                if centavos_elem:
                    centavos = centavos_elem.get_text(strip=True)
                    precio_texto += '.' + centavos.zfill(2)  # Asegurar 2 dígitos
                
                precio = limpiar_precio(precio_texto)
                st.write(f"Precio encontrado en estructura estándar: {precio_texto} -> {precio}")
        
        # 2. Si no se encontró, intentar con el atributo aria-label
        if precio <= 0:
            precio_containers = item.select('span.andes-money-amount')
            for container in precio_containers:
                aria_label = container.get('aria-label', '').lower()
                if 'soles' in aria_label:
                    # Extraer todos los números del texto
                    numeros = re.findall(r'[\d.,]+', aria_label)
                    if len(numeros) >= 2:
                        # Si hay múltiples números, asumir que el primero es el precio y el segundo los céntimos
                        precio_texto = f"{numeros[0].replace('.', '')}.{numeros[1].zfill(2)}"
                    elif numeros:
                        # Si solo hay un número, usarlo como está
                        precio_texto = numeros[0].replace('.', '')
                    
                    if precio_texto:
                        precio = limpiar_precio(precio_texto)
                        st.write(f"Precio encontrado en aria-label: {aria_label} -> {precio_texto} -> {precio}")
                        if precio > 0:
                            break
        
        # 3. Último recurso: buscar cualquier precio en la página
        if precio <= 0:
            precio_elems = item.select('span.andes-money-amount__fraction')
            for precio_elem in precio_elems:
                precio_texto = precio_elem.get_text(strip=True).replace('.', '')
                precio = limpiar_precio(precio_texto)
                if precio > 0:
                    st.write(f"Precio encontrado como último recurso: {precio_texto} -> {precio}")
                    break

        # ENLACE
        enlace = "#"
        link_selectors = [
            'a.ui-search-link',
            'a.ui-search-result__content',
            'a[href*="item.mercadolibre"]',
            'a'
        ]

        for selector in link_selectors:
            link_elem = item.select_one(selector)
            if link_elem and link_elem.get('href'):
                enlace = link_elem['href']
                # Limpiar enlace de parámetros de tracking
                if '?promotion_type' in enlace:
                    enlace = enlace.split('?promotion_type')[0]
                break

        # IMAGEN
        imagen = ""
        img_selectors = [
            'img.ui-search-result-image__element',
            'img.ui-search-image__element',
            'img[data-src]',
            'img[src*="http"]',
            'img.slide--visible'
        ]

        for selector in img_selectors:
            img_elem = item.select_one(selector)
            if img_elem:
                imagen = img_elem.get('data-src') or img_elem.get('src') or ""
                if imagen and imagen.startswith('//'):
                    imagen = 'https:' + imagen
                break

        # Solo agregar si tenemos información válida
        if titulo != "Sin título" and precio > 0:
            # Formatear el precio para mostrarlo con 2 decimales
            precio_formateado = f"{precio:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            st.write(f"✅ Producto {index+1}: {titulo[:50]}... - S/ {precio_formateado}")
            return {
                'titulo': titulo,
                'precio': precio,
                'precio_formateado': f"S/ {precio_formateado}",  # Guardar el precio formateado
                'enlace': enlace,
                'imagen': imagen,
                'tienda': 'Mercado Libre',
                'fecha_consulta': datetime.now().isoformat(),
                'query_original': st.session_state.get('current_query', '')
            }
        else:
            st.write(
                f"❌ Producto {index+1} descartado - Título: {titulo[:30]}, Precio: {precio}")
            return None

    except Exception as e:
        st.write(f"❌ Error extrayendo info producto {index}: {str(e)}")
        return None


def buscar_ebay(query, max_productos=5):
    """Buscar productos en eBay con Selenium mejorado"""
    driver = None
    try:
        # Configurar opciones de Chrome
        chrome_options = Options()
        
        # Configuración mejorada para evitar detección
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        # User agent realista
        user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36'
        chrome_options.add_argument(f'user-agent={user_agent}')
        
        # Inicializar el navegador
        driver = webdriver.Chrome(options=chrome_options)
        
        # Modificar las propiedades del navegador para parecer más humano
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        driver.execute_cdp_cmd('Network.setUserAgentOverride', {"userAgent": user_agent})
        
        # Construir URL de búsqueda
        url = f"https://www.ebay.com/sch/i.html?_nkw={query.replace(' ', '+')}&_sop=15"  # Ordenar por precio + envío más bajo
        
        st.write(f"🔍 Navegando directamente a: {url}")
        
        # Navegar directamente a la URL de búsqueda
        driver.get(url)
        time.sleep(3)  # Esperar a que cargue la página
        
        # Hacer scroll para cargar contenido dinámico
        for _ in range(3):
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1)
        
        # Obtener el HTML después de que se cargue el JavaScript
        html = driver.page_source
        soup = BeautifulSoup(html, 'html.parser')
        
        # Guardar HTML para depuración
        with open("ebay_full_page.html", "w", encoding="utf-8") as f:
            f.write(soup.prettify())
        
        # Lista para almacenar productos
        productos = []
        
        # Buscar elementos de productos
        selectores_posibles = [
            'li.s-item', 'div.s-item__wrapper', 'div.s-item__info', 
            'ul.srp-results li', 'div.srp-river-main', 'div.s-item'
        ]
        
        # Buscar el selector que coincida
        items = []
        for selector in selectores_posibles:
            items = soup.select(selector)
            if items and len(items) > 5:  # Verificar que hay suficientes elementos
                st.write(f"🔍 Se encontraron {len(items)} elementos con el selector: {selector}")
                # Guardar el primer elemento para depuración
                with open("first_item.html", "w", encoding="utf-8") as f:
                    f.write(str(items[0]))
                break
        
        if not items or len(items) <= 5:
            st.warning("No se encontraron suficientes elementos de productos.")
            return []
        
        # Procesar los primeros max_productos productos
        for i, item in enumerate(items[:max_productos]):
            try:
                # Extraer título
                titulo = "Sin título"
                titulo_selectors = [
                    '.s-item__title', 'a.s-item__link', 'div.s-item__title a',
                    'h3.s-item__title', '.s-item__title--has-tags', '.s-item__title--has-subtitle',
                    'div[class*="title"]', 'span[class*="title"]', 'h3', 'h2', 'h1', 'a', 'span', 'div'
                ]
                
                for selector in titulo_selectors:
                    title_elem = item.select_one(selector)
                    if title_elem:
                        titulo = title_elem.get_text(strip=True)
                        if titulo and len(titulo) > 5:  # Filtrar títulos muy cortos
                            break
                
                # Limpiar el título
                titulo = titulo.replace('Nuevo', '').replace('nuevo', '').replace('NUEVO', '').strip()
                titulo = re.sub(r'^\s*[\-\*]\s*', '', titulo)  # Eliminar guiones o asteriscos al inicio
                
                # Saltar si es un anuncio o no tiene título
                if any(x in titulo.lower() for x in ["comprar ahora", "sponsored", "patrocinado", "anuncio", "advertisement"]) or titulo == "Sin título":
                    st.write(f"⚠️ Saltando anuncio o sin título: {titulo[:50]}...")
                    continue
                
                # Extraer precio
                precio = 0
                precio_texto = "S/. 0.00"
                precio_selectors = [
                    '.s-item__price', '.s-item__details .s-item__price',
                    '.s-item__detail--primary', '.s-item__detail--price',
                    '.s-item__price .POSITIVE', '.s-item__price .NEGATIVE',
                    '*[class*="price"]', '*[class*="amount"]',
                    ':contains("$")', ':contains("S/")', ':contains("€")',
                    'span', 'div', 'p'
                ]
                
                for selector in precio_selectors:
                    try:
                        price_elem = item.select_one(selector)
                        if price_elem:
                            precio_texto = price_elem.get_text(strip=True)
                            # Buscar patrones de precio (números con símbolos de moneda)
                            if any(c in precio_texto for c in ['$', '€', 'S/', 'USD', 'EUR', 'PEN']) and any(c.isdigit() for c in precio_texto):
                                st.write(f"✅ Precio encontrado con selector '{selector}': {precio_texto}")
                                break
                    except Exception as e:
                        continue
                
                # Si no se encontró precio, intentar con expresiones regulares
                if not precio_texto or precio_texto == "S/. 0.00":
                    all_text = item.get_text(' ', strip=True)
                    # Buscar patrones de precio con regex
                    price_matches = re.findall(r'[\$€S/]\s*\d+[\d,.]*|\d+[\d,.]*\s*[\$€S/]', all_text)
                    if price_matches:
                        precio_texto = price_matches[0]
                        st.write(f"ℹ️ Precio encontrado con regex: {precio_texto}")
                
                # Limpiar y convertir el precio
                # Primero, manejar el caso específico de 'S/.'
                if 'S/.' in precio_texto:
                    precio_limpio = precio_texto.replace('S/.', '').strip()
                else:
                    precio_limpio = re.sub(r'[^\d.,]', '', precio_texto)
                
                # Reemplazar comas por puntos para el separador decimal
                if ',' in precio_limpio and '.' in precio_limpio:
                    # Si hay ambos, asumir que la coma es el separador de miles
                    precio_limpio = precio_limpio.replace(',', '')
                elif ',' in precio_limpio:
                    # Si solo hay coma, reemplazarla por punto
                    precio_limpio = precio_limpio.replace(',', '.')
                
                try:
                    precio = float(precio_limpio) if precio_limpio else 0
                except ValueError:
                    st.write(f"⚠️ No se pudo convertir el precio: {precio_texto}")
                    precio = 0
                
                # Extraer enlace
                enlace = "#"
                link_selectors = ['a.s-item__link', 'a[href*="itm"]', 'a[class*="link"]', 'a']
                for selector in link_selectors:
                    link_elem = item.select_one(selector)
                    if link_elem and 'href' in link_elem.attrs:
                        enlace = link_elem['href']
                        break
                
                # Extraer imagen
                imagen = ""
                img_selectors = ['img.s-item__image-img', 'img[class*="image"]', 'img']
                for selector in img_selectors:
                    img_elem = item.select_one(selector)
                    if img_elem and 'src' in img_elem.attrs:
                        imagen = img_elem['src']
                        break
                
                # Determinar la moneda
                moneda = "S/."  # Por defecto soles peruanos
                if any(c in precio_texto for c in ['$', 'USD']):
                    moneda = "USD"
                elif '€' in precio_texto or 'EUR' in precio_texto.upper():
                    moneda = "€"
                
                # Agregar producto a la lista
                if titulo != "Sin título" and precio > 0:
                    productos.append({
                        'titulo': titulo[:100] + ('...' if len(titulo) > 100 else ''),
                        'precio': precio,
                        'precio_formateado': f"{moneda} {precio:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
                        'enlace': enlace,
                        'imagen': imagen,
                        'tienda': 'eBay',
                        'fecha_consulta': datetime.now().isoformat(),
                        'query_original': query
                    })
                    
                    st.write(f"✅ Producto {len(productos)}: {titulo[:50]}... - {moneda} {precio:,.2f}")
                    
                    # Detener si ya tenemos suficientes productos
                    if len(productos) >= max_productos:
                        break
            
            except Exception as e:
                st.write(f"⚠️ Error procesando producto {i}: {str(e)}")
                continue
        
        # Ordenar por precio
        productos_ordenados = sorted(productos, key=lambda x: x['precio'])
        return productos_ordenados[:max_productos]
        
    except Exception as e:
        st.error(f"❌ Error al buscar en eBay: {str(e)}")
        st.error("Posibles causas:")
        st.error("- eBay está bloqueando las solicitudes automatizadas")
        st.error("- La estructura de la página ha cambiado")
        st.error("- Problemas de conexión a internet")
        return []
        
    finally:
        if driver:
            try:
                driver.quit()
            except:
                pass
            driver.quit()


def mostrar_producto_busqueda(producto, key_suffix, _supabase):
    """Mostrar un producto en una tarjeta de búsqueda"""
    col1, col2, col3 = st.columns([1, 2, 1])

    with col1:
        if producto['imagen']:
            st.image(producto['imagen'], width=100, use_container_width=True)
        else:
            st.write("📷 Sin imagen")

    with col2:
        st.write(f"**{producto['titulo']}**")
        st.write(f"**Precio:** ${producto['precio']:,.2f}")
        st.write(f"**Tienda:** {producto['tienda']}")
        st.write(f"**Fecha:** {datetime.now().strftime('%Y-%m-%d %H:%M')}")

    with col3:
        if st.button("📊 Seguir precio", key=f"seguir_{key_suffix}"):
            if _supabase:
                with st.spinner('Guardando producto...'):
                    try:
                        producto_id = guardar_producto_supabase(
                            _supabase, producto)
                        if producto_id:
                            st.success("✅ Producto agregado para seguimiento!")
                            # Limpiar resultados de búsqueda
                            if 'resultados' in st.session_state:
                                del st.session_state.resultados
                            st.rerun()
                        else:
                            st.error("❌ Error al guardar el producto")
                    except Exception as e:
                        st.error(f"❌ Error: {str(e)}")
            else:
                st.error("❌ No hay conexión a la base de datos")

        if producto['enlace'] != "#":
            st.markdown(f"[🔗 Ver producto]({producto['enlace']})")


def main():
    # Título principal con estilo
    st.markdown("""
    <div style='margin-bottom: 1.5rem;'>
        <h1 style='margin: 0; padding: 0; font-size: 2.5rem; background: linear-gradient(45deg, #6e45e2, #88d3ce); -webkit-background-clip: text; -webkit-text-fill-color: transparent;'>
            🛒 Tracker de Precios
        </h1>
        <p style='margin: 0.5rem 0 0; color: #94a3b8; font-size: 1.1rem;'>Busca productos y haz seguimiento de sus precios</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Sección de notificaciones por correo con nuevo diseño
    with st.container():
        st.markdown("""
        <div class="card" style="padding: 1rem 1.5rem;">
            <div style="display: flex; align-items: center; gap: 1rem;">
                <div style="display: flex; align-items: center; gap: 0.75rem; flex-grow: 1;">
                    <div style="background: rgba(110, 69, 226, 0.15); width: 40px; height: 40px; border-radius: 12px; display: flex; align-items: center; justify-content: center;">
                        <span style="font-size: 1.2rem;">📧</span>
                    </div>
                    <div style="flex-grow: 1;">
        """, unsafe_allow_html=True)
        
        # Campo de correo
        email = st.text_input(
            label="Correo electrónico",
            placeholder="tucorreo@ejemplo.com",
            key="email_notificaciones",
            label_visibility="collapsed"
        )
        
        st.markdown("""
                    </div>
                </div>
                <div style="margin-left: auto; align-self: flex-end;">
        """, unsafe_allow_html=True)
        
        # Botón de guardar
        guardar_correo = st.button(
            "💾 Guardar correo",
            key="btn_guardar_correo",
            help="Guardar dirección de correo para notificaciones"
        )
        
        st.markdown("""
                </div>
            </div>
            <div style="margin-top: 0.5rem; color: #94a3b8; font-size: 0.85rem;">
                Recibe notificaciones cuando los precios bajen
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # Aplicar estilos a los inputs
        st.markdown("""
        <style>
            div[data-testid='stTextInput'] > div > div > input {
                background: rgba(17, 24, 39, 0.3) !important;
                border: 1px solid rgba(255, 255, 255, 0.1) !important;
                color: white !important;
                border-radius: 8px !important;
                padding: 0.5rem 0.75rem !important;
                height: 38px !important;
            }
            button[data-testid='baseButton-secondary'] {
                background: linear-gradient(45deg, #6e45e2, #88d3ce) !important;
                border: none !important;
                border-radius: 8px !important;
                height: 38px !important;
            }
        </style>
        """, unsafe_allow_html=True)
    
    st.markdown("<div style='margin: 1rem 0; height: 1px; background: rgba(255, 255, 255, 0.05);'></div>", unsafe_allow_html=True)
    st.markdown("Busca productos y haz seguimiento de sus precios")

    # Guardar query en session_state
    if 'current_query' not in st.session_state:
        st.session_state.current_query = ""

    # Inicializar Supabase
    _supabase = init_supabase()

    # Búsqueda de productos
    st.header("🔍 Buscar Productos")

    query = st.text_input("¿Qué producto buscas?",
                          placeholder="Ej: laptop, zapatillas, teléfono, etc.",
                          key="search_input",
                          on_change=lambda: setattr(st.session_state, 'current_query', st.session_state.search_input))

    st.session_state.current_query = query

    col1, col2 = st.columns(2)

    with col1:
        buscar_ml = st.button("🔎 Buscar en Mercado Libre",
                              use_container_width=True)

    with col2:
        btn_buscar_ebay = st.button("🌎 Buscar en eBay", use_container_width=True)

    # Resultados de búsqueda
    if 'resultados' not in st.session_state:
        st.session_state.resultados = []

    if buscar_ml and query:
        with st.spinner("🔄 Buscando en Mercado Libre (puede tomar unos segundos)..."):
            resultados_ml = buscar_mercado_libre_selenium(query)
            if resultados_ml:
                st.session_state.resultados = resultados_ml
                st.success(
                    f"✅ Encontrados {len(resultados_ml)} productos en Mercado Libre")
            else:
                st.error("""
                ❌ No se encontraron productos en Mercado Libre. Posibles causas:
                - Mercado Libre bloqueó la solicitud
                - La estructura de la página cambió
                - Intenta con otro término de búsqueda
                """)

    if btn_buscar_ebay and query:
        with st.spinner("🌎 Buscando en eBay..."):
            resultados_ebay = buscar_ebay(query)
            if resultados_ebay:
                st.session_state.resultados = resultados_ebay
                st.success(
                    f"✅ Encontrados {len(resultados_ebay)} productos en eBay")
            else:
                st.error("❌ No se encontraron productos en eBay")

    # Mostrar resultados de búsqueda
    if st.session_state.resultados:
        st.header("📦 Resultados de Búsqueda")

        for i, producto in enumerate(st.session_state.resultados):
            st.markdown("---")
            mostrar_producto_busqueda(producto, f"resultado_{i}", _supabase)

    # Productos en seguimiento
    st.header("📊 Productos en Seguimiento")

    if _supabase:
        productos_seguimiento = obtener_productos_seguimiento(_supabase)

        if not productos_seguimiento:
            st.info(
                "ℹ️ No hay productos en seguimiento. Busca productos y haz clic en 'Seguir precio'")
        else:
            st.write(
                f"**Total de productos en seguimiento:** {len(productos_seguimiento)}")

            for i, producto in enumerate(productos_seguimiento):
                st.markdown("---")
                col1, col2, col3, col4 = st.columns([1, 2, 1, 1])

                with col1:
                    if producto.get('imagen'):
                        st.image(producto['imagen'], width=80)
                    else:
                        st.write("🖼️")

                with col2:
                    st.write(f"**{producto['titulo'][:100]}...**")
                    st.write(
                        f"**Precio actual:** ${producto['precio_actual']:,.2f}")
                    st.write(
                        f"**Precio inicial:** ${producto['precio_inicial']:,.2f}")
                    st.write(f"**Tienda:** {producto['tienda']}")

                    # Calcular diferencia
                    diferencia = producto['precio_actual'] - \
                        producto['precio_inicial']
                    porcentaje = (
                        diferencia / producto['precio_inicial']) * 100 if producto['precio_inicial'] > 0 else 0

                    if diferencia < 0:
                        st.success(
                            f"📉 Bajó: ${abs(diferencia):,.2f} ({abs(porcentaje):.1f}%)")
                    elif diferencia > 0:
                        st.error(
                            f"📈 Subió: ${diferencia:,.2f} ({porcentaje:.1f}%)")
                    else:
                        st.info("➡️ Sin cambios")

                with col3:
                    # Contenedor para los botones de actualización
                    update_container = st.container()
                    
                    # Botón de actualizar
                    if update_container.button("🔄 Actualizar ahora", key=f"actualizar_{i}"):
                        with st.spinner("Actualizando precio..."):
                            if actualizar_precio_producto(_supabase, producto):
                                time.sleep(1)
                                st.rerun()
                    
                    # Botón de análisis de tendencia
                    if update_container.button(
                        "📊 Analizar tendencia",
                        key=f"analizar_{i}",
                        help="Analizar la tendencia de precios del producto y enviar datos al servidor de pronóstico"
                    ):
                        with st.spinner("Analizando tendencia y enviando datos al servidor..."):
                            historial = obtener_historial_producto(_supabase, producto['id'])
                            if len(historial) > 1:
                                # Preparar datos para el webhook
                                datos_webhook = {
                                    'producto_id': producto['id'],
                                    'titulo': producto['titulo'],
                                    'historial_precios': [{
                                        'fecha_consulta': str(h['fecha_consulta']),
                                        'precio': float(h['precio']) if h['precio'] else None,
                                        'disponibilidad': h.get('disponibilidad', '')
                                    } for h in historial],
                                    'fecha_analisis': datetime.now().isoformat()
                                }
                                
                                try:
                                    # Enviar datos al webhook
                                    if TREND_ANALYSIS_WEBHOOK_URL:
                                        response = requests.post(
                                            TREND_ANALYSIS_WEBHOOK_URL,
                                            json=datos_webhook,
                                            headers={'Content-Type': 'application/json'}
                                        )
                                        response.raise_for_status()
                                        
                                        # Mostrar la respuesta del webhook si existe
                                        if response.status_code == 200 and response.content:
                                            try:
                                                # Intentar obtener la respuesta del webhook
                                                respuesta_completa = response.json()
                                                
                                                # Buscar el texto del análisis en la respuesta
                                                if isinstance(respuesta_completa, list) and len(respuesta_completa) > 0:
                                                    # Si es una lista, tomar el primer elemento
                                                    respuesta_completa = respuesta_completa[0]
                                                
                                                # Función para formatear el texto con saltos de línea
                                                def format_response_text(text):
                                                    # Convertir a string si no lo es
                                                    if not isinstance(text, str):
                                                        text = str(text)
                                                    # Reemplazar \n con doble salto de línea para markdown
                                                    text = text.replace('\n', '\n\n')
                                                    # Convertir listas con asteriscos a formato markdown
                                                    text = re.sub(r'\*\s+\*\*(.*?):\*\*', r'* **\1:**', text)
                                                    return text
                                                
                                                if isinstance(respuesta_completa, dict):
                                                    # Buscar en diferentes posibles ubicaciones del texto de análisis
                                                    response_text = None
                                                    
                                                    # Intentar encontrar el texto en diferentes ubicaciones comunes
                                                    if 'output' in respuesta_completa and isinstance(respuesta_completa['output'], str):
                                                        response_text = respuesta_completa['output']
                                                    elif 'json' in respuesta_completa and 'output' in respuesta_completa['json']:
                                                        response_text = respuesta_completa['json']['output']
                                                    elif 'text' in respuesta_completa:
                                                        response_text = respuesta_completa['text']
                                                    
                                                    # Si encontramos el texto, mostrarlo formateado
                                                    if response_text is not None:
                                                        formatted_text = format_response_text(response_text)
                                                        st.markdown(formatted_text, unsafe_allow_html=False)
                                                    else:
                                                        # Si no encontramos el formato esperado, mostrar la respuesta completa
                                                        st.text(str(respuesta_completa))
                                                elif isinstance(respuesta_completa, str):
                                                    # Si la respuesta es directamente un string
                                                    formatted_text = format_response_text(respuesta_completa)
                                                    st.markdown(formatted_text, unsafe_allow_html=False)
                                                else:
                                                    # Si no reconocemos el formato, mostrar la respuesta completa
                                                    st.text(str(respuesta_completa))
                                            except json.JSONDecodeError:
                                                # Si no es JSON, mostrar como texto plano
                                                st.markdown(response.text, unsafe_allow_html=True)
                                        else:
                                            st.success("✅ Datos procesados por el servidor")
                                            
                                    else:
                                        st.warning("⚠️ No se configuró la URL del webhook de análisis de tendencia")
                                        # Si no hay webhook, mostrar análisis local
                                        analisis = analizar_tendencia(historial)
                                        st.markdown(analisis, unsafe_allow_html=True)
                                    
                                except requests.exceptions.RequestException as e:
                                    st.error(f"❌ Error de conexión con el servidor de pronóstico: {str(e)}")
                                    st.info("Mostrando análisis local...")
                                    # Mostrar análisis local si hay error de conexión
                                    analisis = analizar_tendencia(historial)
                                    st.markdown(analisis, unsafe_allow_html=True)
                                except Exception as e:
                                    st.error(f"❌ Error inesperado: {str(e)}")
                                    # Mostrar análisis local en caso de error inesperado
                                    analisis = analizar_tendencia(historial)
                                    st.markdown(analisis, unsafe_allow_html=True)
                            else:
                                st.warning("Se necesita más historial de precios para realizar el análisis")

                with col4:
                    # Usar una clave única para el estado de confirmación
                    confirm_key = f"confirm_delete_{i}"
                    
                    # Si ya se ha confirmado la eliminación
                    if st.session_state.get(confirm_key, False):
                        if st.button(f"⚠️ ¿Eliminar {producto['titulo'][:15]}...?", 
                                  type="primary", 
                                  key=f"confirm_{i}"):
                            if eliminar_producto(_supabase, producto['id']):
                                # Limpiar el estado de confirmación
                                st.session_state[confirm_key] = False
                                st.success("✅ Producto eliminado!")
                                time.sleep(1)
                                st.rerun()
                        
                        # Botón para cancelar
                        if st.button("❌ Cancelar", key=f"cancel_{i}"):
                            st.session_state[confirm_key] = False
                            st.rerun()
                    else:
                        # Mostrar botón de eliminar normal
                        if st.button("🗑️ Eliminar", key=f"delete_{i}"):
                            st.session_state[confirm_key] = True
                            st.rerun()

                # Gráfico de historial de precios
                with st.expander("📈 Ver historial de precios"):
                    historial = obtener_historial_producto(_supabase, producto['id'])
                    
                    if len(historial) > 1:
                        df_historial = pd.DataFrame(historial)
                        
                        # Asegurarnos de que las fechas estén en el formato correcto
                        df_historial['fecha_consulta'] = pd.to_datetime(df_historial['fecha_consulta'])
                        df_historial = df_historial.sort_values('fecha_consulta')

                        # Crear dos columnas: una para el gráfico y otra para estadísticas
                        col1, col2 = st.columns([3, 1])

                        with col1:
                            # Gráfico de líneas con puntos
                            st.markdown("### Evolución del Precio")
                            
                            # Crear el gráfico con scatter
                            fig = px.scatter(
                                df_historial,
                                x='fecha_consulta',
                                y='precio',
                                title=f"Evolución de precios - {producto['titulo'][:50]}...",
                                labels={
                                    'fecha_consulta': 'Fecha y Hora',
                                    'precio': 'Precio ($)'
                                },
                                # Añadir etiquetas a los puntos
                                text=df_historial['precio'].round(2).astype(str) + ' $',
                                # Desactivar la línea de tendencia por defecto
                                trendline=None
                            )
                            
                            # Añadir línea de tendencia como una capa separada
                            fig.add_scatter(
                                x=df_historial['fecha_consulta'],
                                y=df_historial['precio'],
                                mode='lines+markers',
                                name='Precio',
                                line=dict(color='blue', width=2),
                                marker=dict(size=10, color='blue'),
                                showlegend=False
                            )
                            
                            # Asegurar que se muestren todos los puntos
                            fig.update_traces(
                                mode='markers+text',
                                marker=dict(size=10, color='blue'),
                                textposition='top center',
                                textfont=dict(size=10, color='black')
                            )

                            # Mejorar el diseño del gráfico
                            fig.update_layout(
                                xaxis_title="Fecha y Hora",
                                yaxis_title="Precio ($)",
                                hovermode='x unified',
                                showlegend=False,
                                template='plotly_white',
                                height=500,
                                # Asegurar que se muestren todas las etiquetas del eje X
                                xaxis=dict(
                                    showticklabels=True,
                                    tickangle=45,
                                    nticks=min(10, len(df_historial)),  # Máximo 10 marcas para evitar sobrecarga
                                    tickformat='%d/%m %H:%M'  # Formato de fecha más compacto
                                ),
                                # Ajustar márgenes para que quepa el texto
                                margin=dict(l=50, r=50, t=80, b=150)
                            )

                            # Mostrar el gráfico
                            st.plotly_chart(fig, use_container_width=True)
                            
                            # Botón para generar PDF
                            if st.button("📄 Generar Reporte PDF", key=f"pdf_{producto['id']}"):
                                with st.spinner("Generando reporte PDF..."):
                                    # Crear PDF con orientación horizontal para mejor visualización
                                    pdf = FPDF('L', 'mm', 'A4')
                                    
                                    # Usar Arial como fuente predeterminada
                                    use_unicode = False
                                    
                                    # Función para manejar texto con caracteres especiales
                                    def write_text(pdf, text, w=0, h=0, border=0, ln=0, align='', fill=False, link=''):
                                        if not use_unicode:
                                            # Reemplazar caracteres especiales si no se usa fuente Unicode
                                            text = str(text).replace('▲', '↑').replace('▼', '↓')
                                        # Asegurarse de que align sea un valor válido
                                        align = align.upper() if isinstance(align, str) else ''
                                        if align not in ('L', 'C', 'R', 'J'):
                                            align = ''
                                        pdf.cell(w, h, str(text), border, ln, align, fill, link)
                                    
                                    # Función para establecer la fuente
                                    def set_font(pdf, style='', size=12):
                                        pdf.set_font('Arial', style, size)
                                        pdf.font_size = size
                                    
                                    pdf.add_page()
                                    pdf.set_auto_page_break(auto=True, margin=15)
                                    
                                    # Colores pastel
                                    colors = {
                                        'background': (240, 248, 255),  # Azul claro
                                        'header': (173, 216, 230),     # Azul pastel
                                        'accent1': (255, 218, 185),    # Durazno pastel
                                        'accent2': (221, 255, 221),    # Verde menta pastel
                                        'text': (51, 51, 51),          # Gris oscuro para texto
                                        'border': (200, 200, 200)      # Gris claro para bordes
                                    }
                                    
                                    # Función para establecer la fuente con manejo de Unicode
                                    def set_font(pdf, style='', size=12):
                                        if use_unicode:
                                            font = 'DejaVu'
                                        else:
                                            font = 'Arial'
                                        pdf.set_font(font, style, size)
                                    
                                    # Función para escribir texto con manejo de caracteres especiales
                                    def write_text(pdf, text, w=0, h=0, border=0, ln=0, align='', fill=False, link=''):
                                        # Reemplazar caracteres especiales por texto descriptivo
                                        text = str(text)
                                        text = text.replace('▲', '(sube)').replace('↑', '(sube)')
                                        text = text.replace('▼', '(baja)').replace('↓', '(baja)')
                                        
                                        # Asegurarse de que align sea un valor válido
                                        align = str(align).upper() if align and isinstance(align, str) else ''
                                        if align not in ('L', 'C', 'R', 'J'):
                                            align = ''
                                            
                                        # Asegurarse de que ln sea un entero válido (0, 1, 2)
                                        try:
                                            ln = int(ln)
                                            if ln not in (0, 1, 2):
                                                ln = 0
                                        except (ValueError, TypeError):
                                            ln = 0
                                            
                                        # Usar Arial como fuente predeterminada
                                        pdf.set_font('Arial', size=pdf.font_size)
                                        pdf.cell(w=w, h=h, txt=text, border=border, ln=ln, align=align, fill=fill, link=link)
                                    
                                    # Función para dibujar un rectángulo redondeado
                                    def rounded_rect(x, y, w, h, r, color, fill=True):
                                        d = r * 2
                                        pdf.set_fill_color(*color) if fill else pdf.set_draw_color(*color)
                                        # Esquinas redondeadas
                                        pdf.ellipse(x, y, d, d, 'F' if fill else 'D')
                                        pdf.ellipse(x + w - d, y, d, d, 'F' if fill else 'D')
                                        pdf.ellipse(x, y + h - d, d, d, 'F' if fill else 'D')
                                        pdf.ellipse(x + w - d, y + h - d, d, d, 'F' if fill else 'D')
                                        # Rectángulos para los lados
                                        pdf.rect(x + r, y, w - d, h, 'F' if fill else 'D')
                                        pdf.rect(x, y + r, w, h - d, 'F' if fill else 'D')
                                    
                                    # Colores pastel
                                    colors = {
                                        'background': (240, 248, 255),  # Azul claro
                                        'header': (173, 216, 230),     # Azul pastel
                                        'accent1': (255, 218, 185),    # Durazno pastel
                                        'accent2': (221, 255, 221),    # Verde menta pastel
                                        'text': (51, 51, 51),          # Gris oscuro para texto
                                        'border': (200, 200, 200)      # Gris claro para bordes
                                    }
                                    
                                    # Fondo de la página
                                    pdf.set_fill_color(*colors['background'])
                                    pdf.rect(0, 0, 297, 210, 'F')  # A4 en horizontal: 297x210mm
                                    
                                    # Encabezado con degradado
                                    set_font(pdf, 'B', 16)
                                    pdf.set_text_color(*colors['text'])
                                    pdf.set_draw_color(*colors['header'])
                                    pdf.set_fill_color(200, 230, 255)  # Azul pastel más claro
                                    pdf.rect(0, 0, 297, 30, 'F')
                                    pdf.set_xy(0, 10)
                                    write_text(pdf, 'Reporte de Precios', 0, 10, 0, 1, 'C')
                                    
                                    # Información del producto
                                    pdf.set_font('Arial', 'B', 14)
                                    pdf.set_xy(15, 40)
                                    write_text(pdf, 'Información del Producto', 0, 10, 0, 1, 'L')
                                    
                                    # Tarjeta de información del producto
                                    pdf.set_draw_color(*colors['border'])
                                    pdf.set_fill_color(255, 255, 255)  # Fondo blanco
                                    rounded_rect(15, 55, 260, 40, 5, colors['border'], False)
                                    pdf.rect(15, 55, 260, 40, 'F')
                                    
                                    set_font(pdf, '', 12)
                                    pdf.set_xy(20, 60)
                                    write_text(pdf, producto["titulo"], 250, 8, 0, 'L')
                                    
                                    # Precios en tarjetas pequeñas
                                    box_width = 80
                                    box_height = 30
                                    
                                    # Precio actual
                                    pdf.set_fill_color(*colors['accent1'])
                                    rounded_rect(15, 105, box_width, box_height, 5, colors['accent1'])
                                    pdf.set_xy(15, 110)
                                    set_font(pdf, 'B', 10)
                                    write_text(pdf, 'Precio Actual', box_width, 5, 0, 1, 'C')
                                    set_font(pdf, 'B', 16)
                                    pdf.set_xy(15, 118)
                                    write_text(pdf, f'${producto["precio_actual"]:,.2f}', box_width, 5, 0, 1, 'C')
                                    
                                    # Precio inicial
                                    pdf.set_fill_color(*colors['accent2'])
                                    rounded_rect(105, 105, box_width, box_height, 5, colors['accent2'])
                                    pdf.set_xy(105, 110)
                                    set_font(pdf, 'B', 10)
                                    write_text(pdf, 'Precio Inicial', box_width, 5, 0, 1, 'C')
                                    set_font(pdf, 'B', 16)
                                    pdf.set_xy(105, 118)
                                    write_text(pdf, f'${producto["precio_inicial"]:,.2f}', box_width, 5, 0, 1, 'C')
                                    
                                    # Diferencia
                                    diferencia = producto['precio_actual'] - producto['precio_inicial']
                                    porcentaje = (diferencia / producto['precio_inicial']) * 100 if producto['precio_inicial'] > 0 else 0
                                    
                                    diff_color = (255, 100, 100) if diferencia > 0 else (100, 200, 100)
                                    pdf.set_fill_color(*diff_color)
                                    rounded_rect(195, 105, box_width, box_height, 5, diff_color)
                                    pdf.set_xy(195, 110)
                                    set_font(pdf, 'B', 10)
                                    write_text(pdf, 'Variación', box_width, 5, 0, 1, 'C')
                                    set_font(pdf, 'B', 14)
                                    pdf.set_xy(195, 118)
                                    if diferencia < 0:
                                        write_text(pdf, f'▼ ${abs(diferencia):,.2f} ({abs(porcentaje):.1f}%)', box_width, 5, 0, 1, 'C')
                                    elif diferencia > 0:
                                        write_text(pdf, f'▲ ${diferencia:,.2f} ({porcentaje:.1f}%)', box_width, 5, 0, 1, 'C')
                                    else:
                                        write_text(pdf, 'Sin cambios', box_width, 5, 0, 1, 'C')
                                    
                                    # Crear una nueva página para el gráfico
                                    pdf.add_page('L')  # Página en orientación horizontal
                                    
                                    # Configurar el gráfico para ocupar toda la página
                                    fig.update_layout(
                                        height=500,  # Altura mayor para aprovechar el espacio
                                        margin=dict(l=20, r=20, t=40, b=40),  # Márgenes ajustados
                                        showlegend=False,
                                        title=dict(
                                            text='Evolución del Precio',
                                            x=0.5,  # Centrar título
                                            xanchor='center',
                                            font=dict(size=16)
                                        ),
                                        xaxis=dict(
                                            showgrid=True,
                                            gridcolor='lightgray',
                                            tickfont=dict(size=10),
                                            title='Fecha y Hora',
                                            title_font=dict(size=12)
                                        ),
                                        yaxis=dict(
                                            showgrid=True,
                                            gridcolor='lightgray',
                                            tickfont=dict(size=10),
                                            title='Precio ($)',
                                            title_font=dict(size=12)
                                        ),
                                        plot_bgcolor='white',
                                        paper_bgcolor='white'
                                    )
                                    
                                    # Guardar el gráfico como imagen temporal
                                    temp_img = os.path.join(tempfile.gettempdir(), f'grafico_{producto["id"]}.png')
                                    fig.write_image(temp_img, width=1000, height=500, scale=2)
                                    
                                    # Añadir la imagen del gráfico centrada en la página
                                    pdf.image(temp_img, 
                                             x=10,  # Mínimo margen
                                             y=20,  # Empezar más arriba
                                             w=277,  # Ancho casi completo de la página en horizontal (A4 landscape)
                                             h=160,  # Altura proporcional
                                             type='PNG')
                                    
                                    # Tabla de historial
                                    pdf.add_page()
                                    set_font(pdf, 'B', 14)
                                    pdf.set_xy(15, 20)
                                    write_text(pdf, 'Historial de Precios', 0, 10, 0, 1, 'L')
                                    
                                    # Encabezado de la tabla
                                    pdf.set_fill_color(200, 230, 255)  # Azul pastel para el encabezado
                                    pdf.set_draw_color(*colors['border'])
                                    set_font(pdf, 'B', 10)
                                    
                                    # Dibujar celdas del encabezado
                                    pdf.set_xy(15, 35)
                                    pdf.cell(140, 10, 'Fecha y Hora', 1, 0, 'C', 1)
                                    pdf.cell(50, 10, 'Precio ($)', 1, 0, 'C', 1)
                                    pdf.cell(50, 10, 'Cambio', 1, 1, 'C', 1)
                                    
                                    # Filas de la tabla
                                    set_font(pdf, '', 9)
                                    
                                    # Ordenar por fecha más reciente primero
                                    df_sorted = df_historial.sort_values('fecha_consulta', ascending=False)
                                    
                                    for i, (_, row) in enumerate(df_sorted.iterrows()):
                                        # Alternar colores de fila
                                        if i % 2 == 0:
                                            pdf.set_fill_color(255, 255, 255)  # Blanco
                                        else:
                                            pdf.set_fill_color(245, 245, 245)  # Gris muy claro
                                        
                                        # Restaurar color de texto
                                        pdf.set_text_color(0, 0, 0)  # Negro
                                        
                                        fecha = pd.to_datetime(row['fecha_consulta']).strftime('%d/%m/%Y %H:%M')
                                        precio = row['precio']
                                        
                                        # Calcular cambio respecto al precio anterior
                                        cambio = ""
                                        if i < len(df_sorted) - 1:
                                            precio_anterior = df_sorted.iloc[i + 1]['precio']
                                            dif = precio - precio_anterior
                                            if dif > 0:
                                                cambio = f"↑ +${dif:,.2f}"  # Usar flecha ASCII
                                                pdf.set_text_color(200, 0, 0)  # Rojo para aumento
                                            elif dif < 0:
                                                cambio = f"↓ ${dif:,.2f}"  # Usar flecha ASCII
                                                pdf.set_text_color(0, 150, 0)  # Verde para disminución
                                            else:
                                                cambio = "="
                                                pdf.set_text_color(100, 100, 100)  # Gris para igual
                                        
                                        pdf.set_xy(15, 45 + (i * 7))
                                        pdf.cell(140, 7, str(fecha), 1, 0, 'L', 1)
                                        pdf.cell(50, 7, f"${precio:,.2f}", 1, 0, 'R', 1)
                                        write_text(pdf, cambio, 50, 7, 1, 'C', 1)
                                        pdf.set_text_color(0, 0, 0)  # Restaurar color negro
                                    
                                    # Pie de página
                                    set_font(pdf, 'I', 8)
                                    pdf.set_text_color(150, 150, 150)
                                    pdf.set_y(-15)
                                    write_text(pdf, f'Generado el {datetime.now().strftime("%d/%m/%Y %H:%M")} | Tracker de Precios', 0, 10, 0, 0, 'C')
                                    
                                    # Guardar PDF en memoria
                                    pdf_output = io.BytesIO()
                                    pdf.output(pdf_output)
                                    
                                    # Guardar el PDF en la sesión para usarlo después
                                    if 'pdf_data' not in st.session_state:
                                        st.session_state.pdf_data = {}
                                    
                                    st.session_state.pdf_data[producto['id']] = pdf_output.getvalue()
                                    
                                    # Marcar que el PDF está listo
                                    st.session_state[f'pdf_ready_{producto["id"]}'] = True
                                
                                # Mostrar botones si el PDF está listo
                                if st.session_state.get(f'pdf_ready_{producto["id"]}', False):
                                    # Función para enviar PDF al webhook
                                    def enviar_a_webhook(pdf_bytes, producto_id):
                                        webhook_url = "http://localhost:5678/webhook-test/webhook-test/tu-webhook-secreto"
                                        files = {
                                            'file': (f'reporte_{producto_id}.pdf', pdf_bytes, 'application/pdf')
                                        }
                                        try:
                                            response = requests.post(webhook_url, files=files)
                                            response.raise_for_status()
                                            st.success("✅ PDF enviado al webhook exitosamente")
                                            return True
                                        except Exception as e:
                                            st.error(f"❌ Error al enviar al webhook: {str(e)}")
                                            return False
                                    
                                    # Crear columnas para los botones
                                    col1, col2 = st.columns(2)
                                    
                                    # Botón de descarga
                                    with col1:
                                        st.download_button(
                                            label="⬇️ Descargar PDF",
                                            data=st.session_state.pdf_data.get(producto['id']),
                                            file_name=f"reporte_{producto['id']}.pdf",
                                            mime='application/pdf',
                                            key=f"download_{producto['id']}"
                                        )
                                    
                                    # Función para enviar PDF al webhook
                                    def enviar_a_webhook(pdf_bytes, producto_id):
                                        webhook_url = "http://localhost:5678/webhook-test/webhook-test/tu-webhook-secreto"
                                        files = {
                                            'file': (f'reporte_{producto_id}.pdf', pdf_bytes, 'application/pdf')
                                        }
                                        try:
                                            response = requests.post(webhook_url, files=files)
                                            response.raise_for_status()
                                            return True, "✅ PDF enviado al webhook exitosamente"
                                        except Exception as e:
                                            return False, f"❌ Error al enviar al webhook: {str(e)}"
                                    
                                    # Botón para enviar por correo y al webhook
                                    with col2:
                                        if st.button(
                                            "📧 Enviar por correo",
                                            key=f"enviar_correo_{producto['id']}",
                                            help="Enviar el reporte a rquerevalu@unitru.edu.pe y al webhook"
                                        ):
                                            with st.spinner("Enviando correo a rquerevalu@unitru.edu.pe y al webhook..."):
                                                # Enviar al webhook primero
                                                webhook_ok, webhook_msg = enviar_a_webhook(st.session_state.pdf_data[producto['id']], producto['id'])
                                                if not webhook_ok:
                                                    st.warning(f"Atención: {webhook_msg}")
                                                
                                                # Luego enviar por correo
                                                if enviar_por_correo("rquerevalu@unitru.edu.pe", producto, st.session_state.pdf_data[producto['id']]):
                                                    st.success("✅ Correo enviado correctamente a rquerevalu@unitru.edu.pe")
                                                else:
                                                    st.error("❌ Error al enviar el correo")
                                    
                                    # Eliminar archivos temporales
                                    try:
                                        os.remove(temp_img)
                                        os.remove(pdf_output)
                                    except:
                                        pass

                        with col2:
                            # Mostrar estadísticas rápidas
                            st.markdown("### 📊 Estadísticas")
                            precio_inicial = df_historial['precio'].iloc[0]
                            precio_actual = df_historial['precio'].iloc[-1]
                            cambio = precio_actual - precio_inicial
                            porcentaje = (cambio / precio_inicial) * 100 if precio_inicial > 0 else 0

                            st.metric(
                                "Precio Inicial",
                                f"${precio_inicial:,.2f}"
                            )
                            st.metric(
                                "Precio Actual",
                                f"${precio_actual:,.2f}",
                                f"{cambio:+,.2f} ({porcentaje:+.1f}%)"
                            )

                            # Resumen de cambios
                            st.markdown("#### 📈 Resumen")
                            st.write(f"📅 Período: {len(df_historial)} registros")
                            st.write(f"📅 Desde: {df_historial['fecha_consulta'].min().strftime('%d/%m/%Y %H:%M')}")
                            st.write(f"📅 Hasta: {df_historial['fecha_consulta'].max().strftime('%d/%m/%Y %H:%M')}")

                            # Botón para actualizar manualmente
                            if st.button("🔄 Actualizar ahora", key=f"actualizar_grafico_{producto['id']}"):
                                st.rerun()

                        # Mostrar tabla con el historial completo
                        st.markdown("### 📋 Historial Detallado")
                        df_display = df_historial[['fecha_consulta', 'precio']].copy()
                        df_display['fecha_consulta'] = df_display['fecha_consulta'].dt.strftime('%Y-%m-%d %H:%M')
                        df_display['precio'] = df_display['precio'].apply(lambda x: f"${x:,.2f}")
                        st.dataframe(df_display, use_container_width=True)
                    else:
                        st.info("ℹ️ Aún no hay suficiente historial para mostrar gráficos. Se necesitan al menos 2 registros.")


if __name__ == "__main__":
    main()
