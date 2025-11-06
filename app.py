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

def actualizar_precio_producto(_supabase, producto_id, nuevo_precio):
    if not _supabase:
        return False
        
    try:
        response = _supabase.table('productos')\
            .select('precio_actual')\
            .eq('id', producto_id)\
            .execute()
        
        if response.data:
            precio_anterior = response.data[0]['precio_actual']
            
            _supabase.table('productos')\
                .update({
                    'precio_actual': nuevo_precio,
                    'updated_at': datetime.now().isoformat()
                })\
                .eq('id', producto_id)\
                .execute()
            
            if abs(precio_anterior - nuevo_precio) > 0.01:
                _supabase.table('historial_precios')\
                    .insert({
                        'producto_id': producto_id,
                        'precio': nuevo_precio,
                        'fecha_consulta': datetime.now().isoformat()
                    })\
                    .execute()
            
            return True
        return False
    except Exception as e:
        st.error(f"Error actualizando precio: {e}")
        return False

# FUNCIONES DE SCRAPING ACTUALIZADAS
def limpiar_precio(precio_texto):
    """Limpiar y convertir el precio a número"""
    if not precio_texto:
        return 0
    
    # Remover símbolos y espacios, mantener números, puntos y comas
    precio_limpio = re.sub(r'[^\d,.]', '', str(precio_texto))
    
    # Manejar diferentes formatos de precio
    if ',' in precio_limpio and '.' in precio_limpio:
        # Formato: 1.299,00 -> 1299.00
        partes = precio_limpio.split(',')
        if len(partes) == 2:
            precio_limpio = partes[0].replace('.', '') + '.' + partes[1]
    elif ',' in precio_limpio:
        # Formato: 1,299 -> 1299
        precio_limpio = precio_limpio.replace(',', '')
    
    try:
        return float(precio_limpio)
    except:
        return 0

def setup_driver():
    """Configurar Selenium WebDriver con mejores opciones"""
    try:
        chrome_options = Options()
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--disable-extensions")
        
        driver = webdriver.Chrome(options=chrome_options)
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
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
                st.write(f"✅ Encontrados {len(items)} elementos con selector: {selector}")
                items_encontrados = items
                break
        
        if not items_encontrados:
            st.warning("❌ No se encontraron elementos con los selectores comunes")
            # Buscar cualquier elemento que contenga información de producto
            items_encontrados = soup.find_all(['div', 'li'], class_=lambda x: x and any(word in str(x).lower() for word in ['item', 'result', 'product', 'card']))
            st.write(f"Elementos encontrados con búsqueda amplia: {len(items_encontrados)}")
        
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
        
        # PRECIO - Múltiples selectores
        precio = 0
        precio_selectors = [
            'span.andes-money-amount__fraction',
            '.ui-search-price__part .andes-money-amount__fraction',
            '.ui-search-price__fraction',
            '.price-tag-fraction',
            '[class*="price"]',
            '.andes-money-amount',
            'div.ui-search-price'
        ]
        
        for selector in precio_selectors:
            precio_elem = item.select_one(selector)
            if precio_elem:
                precio_texto = precio_elem.get_text(strip=True)
                precio = limpiar_precio(precio_texto)
                if precio > 0:
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
            st.write(f"✅ Producto {index+1}: {titulo[:50]}... - ${precio}")
            return {
                'titulo': titulo,
                'precio': precio,
                'enlace': enlace,
                'imagen': imagen,
                'tienda': 'Mercado Libre',
                'fecha_consulta': datetime.now().isoformat(),
                'query_original': st.session_state.get('current_query', '')
            }
        else:
            st.write(f"❌ Producto {index+1} descartado - Título: {titulo[:30]}, Precio: {precio}")
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
        
        for i, item in enumerate(items[1:5]):  # Saltar el primero (usualmente anuncio)
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
            st.image(producto['imagen'], width=100, use_column_width=True)
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
                        producto_id = guardar_producto_supabase(_supabase, producto)
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
        buscar_ml = st.button("🔎 Buscar en Mercado Libre", use_container_width=True)
    
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
                st.success(f"✅ Encontrados {len(resultados_ml)} productos en Mercado Libre")
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
                st.success(f"✅ Encontrados {len(resultados_ebay)} productos en eBay")
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
            st.info("ℹ️ No hay productos en seguimiento. Busca productos y haz clic en 'Seguir precio'")
        else:
            st.write(f"**Total de productos en seguimiento:** {len(productos_seguimiento)}")
            
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
                    st.write(f"**Precio actual:** ${producto['precio_actual']:,.2f}")
                    st.write(f"**Precio inicial:** ${producto['precio_inicial']:,.2f}")
                    st.write(f"**Tienda:** {producto['tienda']}")
                    
                    # Calcular diferencia
                    diferencia = producto['precio_actual'] - producto['precio_inicial']
                    porcentaje = (diferencia / producto['precio_inicial']) * 100 if producto['precio_inicial'] > 0 else 0
                    
                    if diferencia < 0:
                        st.success(f"📉 Bajó: ${abs(diferencia):,.2f} ({abs(porcentaje):.1f}%)")
                    elif diferencia > 0:
                        st.error(f"📈 Subió: ${diferencia:,.2f} ({porcentaje:.1f}%)")
                    else:
                        st.info("➡️ Sin cambios")
                
                with col3:
                    if st.button("🔄 Actualizar", key=f"actualizar_{i}"):
                        with st.spinner("Actualizando precio..."):
                            if producto['tienda'] == 'Mercado Libre':
                                nuevos_resultados = buscar_mercado_libre_selenium(producto.get('query_original', producto['titulo'][:30]))
                            else:
                                nuevos_resultados = buscar_ebay(producto.get('query_original', producto['titulo'][:30]))
                            
                            if nuevos_resultados:
                                for nuevo in nuevos_resultados:
                                    if (nuevo['enlace'] == producto['enlace'] or 
                                        nuevo['titulo'].lower() in producto['titulo'].lower()):
                                        
                                        actualizar_precio_producto(_supabase, producto['id'], nuevo['precio'])
                                        st.success("✅ Precio actualizado!")
                                        time.sleep(1)
                                        st.rerun()
                                        break
                
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
                        df_historial['fecha_consulta'] = pd.to_datetime(df_historial['fecha_consulta'])
                        df_historial = df_historial.sort_values('fecha_consulta')
                        
                        st.line_chart(df_historial.set_index('fecha_consulta')['precio'])
                        
                        st.write("**Historial completo:**")
                        df_display = df_historial[['fecha_consulta', 'precio']].copy()
                        df_display['fecha_consulta'] = df_display['fecha_consulta'].dt.strftime('%Y-%m-%d %H:%M')
                        df_display['precio'] = df_display['precio'].apply(lambda x: f"${x:,.2f}")
                        st.dataframe(df_display, use_container_width=True)
                    else:
                        st.info("ℹ️ Aún no hay suficiente historial para mostrar gráficos")

if __name__ == "__main__":
    main()