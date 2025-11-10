import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import json
import os
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
from fpdf import FPDF
import tempfile
import os
import base64
from datetime import datetime


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

# Intentar importar supabase con manejo de errores
SUPABASE_AVAILABLE = False
supabase_client = None

try:
    from supabase import create_client
    SUPABASE_AVAILABLE = True
    st.success("✅ Supabase disponible")
except ImportError as e:
    st.error(f"❌ Error importando Supabase: {e}")

# Configuración de Supabase


@st.cache_resource
def init_supabase():
    if not SUPABASE_AVAILABLE:
        st.error("❌ Supabase no está disponible")
        return None

    try:
        if "supabase" not in st.secrets:
            st.error("❌ No se encontró la sección 'supabase' en secrets.toml")
            return None

        supabase_url = st.secrets["supabase"]["SUPABASE_URL"]
        supabase_key = st.secrets["supabase"]["SUPABASE_KEY"]

        if not supabase_url or not supabase_key:
            st.error("❌ URL o KEY de Supabase están vacíos")
            return None

        st.success("✅ Credenciales de Supabase cargadas correctamente")

        client = create_client(supabase_url, supabase_key)
        st.success("✅ Cliente Supabase creado")
        return client

    except Exception as e:
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
                    f"✅ Encontrados {len(items)} elementos con selector: {selector}")
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

        return productos

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
        
        # 1. Primero buscar el precio en el atributo aria-label que contiene "Ahora: X soles" o "X soles"
        precio_containers = item.select('span.andes-money-amount')
        for container in precio_containers:
            aria_label = container.get('aria-label', '').lower()
            if 'soles' in aria_label:
                # Extraer solo los números del texto
                import re
                numeros = re.findall(r'[\d.,]+', aria_label)
                if numeros:
                    # Tomar el último número encontrado (por si hay varios)
                    precio_texto = numeros[-1]
                    precio = limpiar_precio(precio_texto)
                    st.write(f"Precio encontrado en aria-label: {aria_label} -> {precio_texto} -> {precio}")
                    if precio > 0:
                        break
        
        # 2. Si no se encontró en aria-label, buscar el precio en la estructura estándar
        if precio <= 0:
            # Buscar el contenedor principal de precios
            precio_container = item.select_one('div.ui-search-price__second-line, div.ui-search-price')
            if precio_container:
                # Extraer la parte entera del precio
                precio_elem = precio_container.select_one('span.andes-money-amount__fraction')
                if precio_elem:
                    precio_texto = precio_elem.get_text(strip=True)
                    
                    # Verificar si hay centavos en un elemento separado
                    centavos_elem = precio_container.select_one('span.andes-money-amount__cents')
                    if centavos_elem:
                        precio_texto += ',' + centavos_elem.get_text(strip=True)
                    
                    precio = limpiar_precio(precio_texto)
                    st.write(f"Precio encontrado en estructura estándar: {precio_texto} -> {precio}")
        
        # 3. Último recurso: buscar cualquier precio en la página
        if precio <= 0:
            precio_elems = item.select('span.andes-money-amount__fraction')
            for precio_elem in precio_elems:
                precio_texto = precio_elem.get_text(strip=True)
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


def buscar_ebay(query):
    """Buscar productos en eBay con selectores actualizados"""
    try:
        url = f"https://www.ebay.com/sch/i.html?_nkw={query.replace(' ', '+')}"

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }

        st.write(f"🔍 Buscando en eBay: {query}")

        response = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.content, 'html.parser')

        productos = []

        # Selectores actualizados para eBay
        items = soup.find_all('li', {'class': 's-item'})[:6]  # Tomar más items

        # Saltar el primero (usualmente anuncio)
        for i, item in enumerate(items[1:5]):
            try:
                # Título
                titulo_elem = item.find('div', {'class': 's-item__title'})
                if not titulo_elem:
                    titulo_elem = item.find('h3', {'class': 's-item__title'})
                titulo = titulo_elem.text.strip() if titulo_elem else "Sin título"

                # Precio
                precio_elem = item.find('span', {'class': 's-item__price'})
                precio_texto = precio_elem.text.strip() if precio_elem else "0"
                precio = limpiar_precio(precio_texto.split(' ')[0])

                # Enlace
                enlace_elem = item.find('a', {'class': 's-item__link'})
                enlace = enlace_elem['href'] if enlace_elem else "#"

                # Imagen
                img_elem = item.find('img', {'class': 's-item__image-img'})
                imagen = img_elem['src'] if img_elem else ""

                if titulo != "Sin título" and precio > 0 and "to" not in precio_texto.lower():
                    productos.append({
                        'titulo': titulo,
                        'precio': precio,
                        'enlace': enlace,
                        'imagen': imagen,
                        'tienda': 'eBay',
                        'fecha_consulta': datetime.now().isoformat(),
                        'query_original': query
                    })
                    st.write(f"✅ eBay producto {i+1} agregado")

            except Exception as e:
                continue

        return productos

    except Exception as e:
        st.error(f"Error en eBay: {str(e)}")
        return []


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
    st.title("🛒 Tracker de Precios")
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
        buscar_ebay = st.button("🌎 Buscar en eBay", use_container_width=True)

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

    if buscar_ebay and query:
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
                    if st.button("🔄 Actualizar", key=f"actualizar_{i}"):
                        with st.spinner("Actualizando precio..."):
                            if actualizar_precio_producto(_supabase, producto):
                                time.sleep(1)
                                st.rerun()

                with col4:
                    if st.button("❌ Eliminar", key=f"eliminar_{i}"):
                        if eliminar_producto(_supabase, producto['id']):
                            st.success("✅ Producto eliminado!")
                            time.sleep(1)
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
                                    pdf.add_page()
                                    
                                    # Colores pastel
                                    colors = {
                                        'background': (240, 248, 255),  # Azul claro
                                        'header': (173, 216, 230),     # Azul pastel
                                        'accent1': (255, 218, 185),    # Durazno pastel
                                        'accent2': (221, 255, 221),    # Verde menta pastel
                                        'text': (51, 51, 51),          # Gris oscuro para texto
                                        'border': (200, 200, 200)      # Gris claro para bordes
                                    }
                                    
                                    # Configuración de la página
                                    pdf.set_auto_page_break(auto=True, margin=15)
                                    
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
                                    
                                    # Fondo de la página
                                    pdf.set_fill_color(*colors['background'])
                                    pdf.rect(0, 0, 297, 210, 'F')  # A4 en horizontal: 297x210mm
                                    
                                    # Encabezado con degradado
                                    pdf.set_font('Arial', 'B', 20)
                                    pdf.set_text_color(*colors['text'])
                                    pdf.set_draw_color(*colors['header'])
                                    pdf.set_fill_color(200, 230, 255)  # Azul pastel más claro
                                    pdf.rect(0, 0, 297, 30, 'F')
                                    pdf.set_xy(0, 5)
                                    pdf.cell(0, 10, 'Reporte de Precios', 0, 1, 'C')
                                    
                                    # Información del producto
                                    pdf.set_font('Arial', 'B', 14)
                                    pdf.set_xy(15, 40)
                                    pdf.cell(0, 10, 'Información del Producto', 0, 1, 'L')
                                    
                                    # Tarjeta de información del producto
                                    pdf.set_draw_color(*colors['border'])
                                    pdf.set_fill_color(255, 255, 255)  # Fondo blanco
                                    rounded_rect(15, 55, 260, 40, 5, colors['border'], False)
                                    pdf.rect(15, 55, 260, 40, 'F')
                                    
                                    pdf.set_font('Arial', '', 12)
                                    pdf.set_xy(20, 60)
                                    pdf.multi_cell(250, 8, producto["titulo"], 0, 'L')
                                    
                                    # Precios en tarjetas pequeñas
                                    box_width = 80
                                    box_height = 30
                                    
                                    # Precio actual
                                    pdf.set_fill_color(*colors['accent1'])
                                    rounded_rect(15, 105, box_width, box_height, 5, colors['accent1'])
                                    pdf.set_xy(15, 110)
                                    pdf.set_font('Arial', 'B', 10)
                                    pdf.cell(box_width, 5, 'Precio Actual', 0, 1, 'C')
                                    pdf.set_font('Arial', 'B', 16)
                                    pdf.set_xy(15, 118)
                                    pdf.cell(box_width, 5, f'${producto["precio_actual"]:,.2f}', 0, 1, 'C')
                                    
                                    # Precio inicial
                                    pdf.set_fill_color(*colors['accent2'])
                                    rounded_rect(105, 105, box_width, box_height, 5, colors['accent2'])
                                    pdf.set_xy(105, 110)
                                    pdf.set_font('Arial', 'B', 10)
                                    pdf.cell(box_width, 5, 'Precio Inicial', 0, 1, 'C')
                                    pdf.set_font('Arial', 'B', 16)
                                    pdf.set_xy(105, 118)
                                    pdf.cell(box_width, 5, f'${producto["precio_inicial"]:,.2f}', 0, 1, 'C')
                                    
                                    # Diferencia
                                    diferencia = producto['precio_actual'] - producto['precio_inicial']
                                    porcentaje = (diferencia / producto['precio_inicial']) * 100 if producto['precio_inicial'] > 0 else 0
                                    
                                    diff_color = (255, 100, 100) if diferencia > 0 else (100, 200, 100)
                                    pdf.set_fill_color(*diff_color)
                                    rounded_rect(195, 105, box_width, box_height, 5, diff_color)
                                    pdf.set_xy(195, 110)
                                    pdf.set_font('Arial', 'B', 10)
                                    pdf.cell(box_width, 5, 'Variación', 0, 1, 'C')
                                    pdf.set_font('Arial', 'B', 14)
                                    pdf.set_xy(195, 118)
                                    if diferencia < 0:
                                        pdf.cell(box_width, 5, f'▼ ${abs(diferencia):,.2f} ({abs(porcentaje):.1f}%)', 0, 1, 'C')
                                    elif diferencia > 0:
                                        pdf.cell(box_width, 5, f'▲ ${diferencia:,.2f} ({porcentaje:.1f}%)', 0, 1, 'C')
                                    else:
                                        pdf.cell(box_width, 5, 'Sin cambios', 0, 1, 'C')
                                    
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
                                    pdf.set_font('Arial', 'B', 14)
                                    pdf.set_xy(15, 20)
                                    pdf.cell(0, 10, 'Historial de Precios', 0, 1, 'L')
                                    
                                    # Encabezado de la tabla
                                    pdf.set_fill_color(200, 230, 255)  # Azul pastel para el encabezado
                                    pdf.set_draw_color(*colors['border'])
                                    pdf.set_font('Arial', 'B', 10)
                                    
                                    # Dibujar celdas del encabezado
                                    pdf.set_xy(15, 35)
                                    pdf.cell(140, 10, 'Fecha y Hora', 1, 0, 'C', 1)
                                    pdf.cell(50, 10, 'Precio ($)', 1, 0, 'C', 1)
                                    pdf.cell(50, 10, 'Cambio', 1, 1, 'C', 1)
                                    
                                    # Filas de la tabla
                                    pdf.set_font('Arial', '', 9)
                                    
                                    # Ordenar por fecha más reciente primero
                                    df_sorted = df_historial.sort_values('fecha_consulta', ascending=False)
                                    
                                    for i, (_, row) in enumerate(df_sorted.iterrows()):
                                        # Alternar colores de fila
                                        if i % 2 == 0:
                                            pdf.set_fill_color(255, 255, 255)  # Blanco
                                        else:
                                            pdf.set_fill_color(245, 245, 245)  # Gris muy claro
                                        
                                        fecha = pd.to_datetime(row['fecha_consulta']).strftime('%d/%m/%Y %H:%M')
                                        precio = row['precio']
                                        
                                        # Calcular cambio respecto al precio anterior
                                        cambio = ""
                                        if i < len(df_sorted) - 1:
                                            precio_anterior = df_sorted.iloc[i + 1]['precio']
                                            dif = precio - precio_anterior
                                            if dif > 0:
                                                cambio = f"▲ +${dif:,.2f}"
                                                pdf.set_text_color(200, 0, 0)  # Rojo para aumento
                                            elif dif < 0:
                                                cambio = f"▼ ${dif:,.2f}"
                                                pdf.set_text_color(0, 150, 0)  # Verde para disminución
                                            else:
                                                cambio = "="
                                                pdf.set_text_color(100, 100, 100)  # Gris para igual
                                        
                                        pdf.set_xy(15, 45 + (i * 7))
                                        pdf.cell(140, 7, str(fecha), 1, 0, 'L', 1)
                                        pdf.cell(50, 7, f"${precio:,.2f}", 1, 0, 'R', 1)
                                        pdf.cell(50, 7, cambio, 1, 1, 'C', 1)
                                        pdf.set_text_color(0, 0, 0)  # Restaurar color negro
                                    
                                    # Pie de página
                                    pdf.set_font('Arial', 'I', 8)
                                    pdf.set_text_color(150, 150, 150)
                                    pdf.set_y(-15)
                                    pdf.cell(0, 10, f'Generado el {datetime.now().strftime("%d/%m/%Y %H:%M")} | Tracker de Precios', 0, 0, 'C')
                                    
                                    # Guardar PDF temporal
                                    pdf_output = os.path.join(tempfile.gettempdir(), f'reporte_{producto["id"]}.pdf')
                                    pdf.output(pdf_output)
                                    
                                    # Crear enlace de descarga
                                    with open(pdf_output, 'rb') as f:
                                        pdf_data = f.read()
                                    
                                    # Crear botón de descarga
                                    st.download_button(
                                        label="⬇️ Descargar Reporte PDF",
                                        data=pdf_data,
                                        file_name=f"reporte_{producto['id']}.pdf",
                                        mime='application/pdf'
                                    )
                                    
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
