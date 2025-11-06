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
import undetected_chromedriver as uc
import warnings
warnings.filterwarnings('ignore')

# Configuración de la página
st.set_page_config(
    page_title="Tracker de Precios",
    page_icon="🛒",
    layout="wide"
)

# Archivo para guardar los productos trackeados
DATA_FILE = "productos_trackeados.json"

def cargar_productos():
    """Cargar productos guardados desde el archivo JSON"""
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def guardar_productos(productos):
    """Guardar productos en archivo JSON"""
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(productos, f, ensure_ascii=False, indent=2)

def limpiar_precio(precio_texto):
    """Limpiar y convertir el precio a número"""
    if not precio_texto:
        return 0
    
    # Remover símbolos y espacios, mantener solo números y comas
    precio_limpio = re.sub(r'[^\d,]', '', str(precio_texto))
    
    # Si hay coma, asumir que es separador decimal
    if ',' in precio_limpio:
        partes = precio_limpio.split(',')
        if len(partes) == 2:
            # Formato europeo: 1.299,00 -> 1299.00
            precio_limpio = partes[0].replace('.', '') + '.' + partes[1]
        else:
            precio_limpio = precio_limpio.replace(',', '')
    
    try:
        return float(precio_limpio)
    except:
        return 0

def setup_driver():
    """Configurar Selenium WebDriver"""
    try:
        chrome_options = Options()
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        
        driver = webdriver.Chrome(options=chrome_options)
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        return driver
    except Exception as e:
        st.error(f"Error configurando Chrome: {e}")
        return None

def buscar_mercado_libre_selenium(query):
    """Buscar productos en Mercado Libre usando Selenium"""
    driver = None
    try:
        driver = setup_driver()
        if not driver:
            return []
            
        # URL de búsqueda en Mercado Libre Perú
        url = f"https://listado.mercadolibre.com.pe/{query.replace(' ', '-')}"
        st.write(f"🔍 Navegando a: {url}")
        
        driver.get(url)
        
        # Esperar a que cargue la página
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        
        # Tomar screenshot para debugging (opcional)
        # driver.save_screenshot("mercado_libre.png")
        
        # Obtener el HTML después de que cargue JavaScript
        html = driver.page_source
        soup = BeautifulSoup(html, 'html.parser')
        
        # Guardar HTML para análisis
        with open("mercado_libre_debug.html", "w", encoding="utf-8") as f:
            f.write(soup.prettify())
        
        productos = []
        
        # Buscar productos - diferentes patrones de selectores
        patrones_selectores = [
            'li.ui-search-layout__item',
            'div[data-component="search.results"] li',
            'ol.ui-search-layout li',
            'section[data-component="search.results"] li',
            '.ui-search-result',
            '.andes-card'
        ]
        
        items = []
        for patron in patrones_selectores:
            items = soup.select(patron)
            if items:
                st.write(f"✅ Encontrados {len(items)} elementos con patrón: {patron}")
                break
        
        if not items:
            st.warning("❌ No se encontraron productos. Intentando método alternativo...")
            # Buscar cualquier elemento que parezca producto
            items = soup.find_all(['div', 'li'], class_=lambda x: x and any(word in str(x).lower() for word in ['item', 'result', 'product', 'card']))
            st.write(f"Elementos encontrados con método alternativo: {len(items)}")
        
        for i, item in enumerate(items[:5]):  # Procesar primeros 5
            try:
                producto_info = extraer_info_producto(item, i)
                if producto_info:
                    productos.append(producto_info)
                    
            except Exception as e:
                st.write(f"❌ Error procesando item {i}: {str(e)}")
                continue
        
        return productos
        
    except Exception as e:
        st.error(f"🚨 Error en Selenium: {str(e)}")
        return []
    finally:
        if driver:
            driver.quit()

def extraer_info_producto(item, index):
    """Extraer información del producto del elemento HTML"""
    try:
        # Título - múltiples selectores
        titulo = "Sin título"
        titulo_selectors = [
            'h2.ui-search-item__title',
            '.ui-search-item__title',
            'h2',
            '.ui-search-result__title',
            '[class*="title"]',
            '[class*="nombre"]'
        ]
        
        for selector in titulo_selectors:
            titulo_elem = item.select_one(selector)
            if titulo_elem and titulo_elem.get_text(strip=True):
                titulo = titulo_elem.get_text(strip=True)
                break
        
        # Precio - múltiples selectores
        precio = 0
        precio_selectors = [
            'span.andes-money-amount__fraction',
            '.ui-search-price__part .andes-money-amount__fraction',
            '.ui-search-price__fraction',
            '.price-tag-fraction',
            '[class*="price"]',
            '[class*="precio"]',
            '.andes-money-amount'
        ]
        
        for selector in precio_selectors:
            precio_elem = item.select_one(selector)
            if precio_elem:
                precio_texto = precio_elem.get_text(strip=True)
                precio = limpiar_precio(precio_texto)
                if precio > 0:
                    break
        
        # Enlace
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
        
        # Imagen
        imagen = ""
        img_selectors = [
            'img.ui-search-result-image__element',
            'img.ui-search-image__element',
            'img[data-src]',
            'img[src*="http"]'
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
                'fecha_consulta': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'query_original': st.session_state.get('current_query', '')
            }
        else:
            st.write(f"❌ Producto {index+1} descartado - Título: {titulo[:30]}, Precio: {precio}")
            return None
            
    except Exception as e:
        st.write(f"❌ Error extrayendo info producto {index}: {str(e)}")
        return None

def buscar_mercado_libre_api(query):
    """Método alternativo usando requests con headers mejorados"""
    try:
        url = f"https://listado.mercadolibre.com.pe/{query.replace(' ', '-')}"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'es-ES,es;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Cache-Control': 'max-age=0',
        }
        
        st.write(f"🔍 Intentando con requests: {url}")
        
        response = requests.get(url, headers=headers, timeout=15)
        
        if response.status_code != 200:
            st.error(f"Error HTTP: {response.status_code}")
            return []
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Verificar si estamos bloqueados
        if "access denied" in soup.text.lower() or "bot" in soup.text.lower():
            st.error("❌ Acceso bloqueado por Mercado Libre")
            return []
        
        # Buscar productos
        productos = []
        items = soup.select('li.ui-search-layout__item, .ui-search-result, .andes-card')
        
        st.write(f"📦 Elementos encontrados: {len(items)}")
        
        for i, item in enumerate(items[:3]):
            producto_info = extraer_info_producto(item, i)
            if producto_info:
                productos.append(producto_info)
        
        return productos
        
    except Exception as e:
        st.error(f"🚨 Error en API method: {str(e)}")
        return []

def buscar_ebay(query):
    """Buscar productos en eBay"""
    try:
        url = f"https://www.ebay.com/sch/i.html?_nkw={query.replace(' ', '+')}"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        }
        
        response = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        productos = []
        items = soup.find_all('li', class_='s-item')[:4]
        
        for i, item in enumerate(items[1:4]):
            try:
                titulo_elem = item.find('h3', class_='s-item__title')
                titulo = titulo_elem.text.strip() if titulo_elem else "Sin título"
                
                precio_elem = item.find('span', class_='s-item__price')
                precio_texto = precio_elem.text.strip() if precio_elem else "0"
                precio = limpiar_precio(precio_texto.split(' ')[0])
                
                enlace_elem = item.find('a', class_='s-item__link')
                enlace = enlace_elem['href'] if enlace_elem else "#"
                
                img_elem = item.find('img', class_='s-item__image-img')
                imagen = img_elem['src'] if img_elem else ""
                
                if titulo != "Sin título" and precio > 0:
                    productos.append({
                        'titulo': titulo,
                        'precio': precio,
                        'enlace': enlace,
                        'imagen': imagen,
                        'tienda': 'eBay',
                        'fecha_consulta': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        'query_original': query
                    })
                    
            except Exception as e:
                continue
                
        return productos
        
    except Exception as e:
        st.error(f"Error en eBay: {str(e)}")
        return []

def mostrar_producto(producto, key_suffix):
    """Mostrar un producto en una tarjeta"""
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
        st.write(f"**Fecha:** {producto['fecha_consulta']}")
    
    with col3:
        if st.button("📊 Seguir precio", key=f"seguir_{key_suffix}"):
            return True
        if producto['enlace'] != "#":
            st.markdown(f"[🔗 Ver producto]({producto['enlace']})")
    
    return False

def main():
    st.title("🛒 Tracker de Precios de Productos")
    st.markdown("Busca productos en Mercado Libre y eBay y haz seguimiento de sus precios")
    
    # Búsqueda de productos
    st.header("🔍 Buscar Productos")
    
    query = st.text_input("¿Qué producto buscas?", 
                         placeholder="Ej: laptop, zapatillas, teléfono, etc.",
                         key="search_input")
    
    st.session_state.current_query = query
    
    col1, col2 = st.columns(2)
    
    with col1:
        buscar_ml = st.button("🔎 Buscar en Mercado Libre", use_container_width=True)
    
    with col2:
        buscar_ebay = st.button("🌎 Buscar en eBay", use_container_width=True)
    
    # Resultados de búsqueda
    if 'resultados' not in st.session_state:
        st.session_state.resultados = []
    
    # Buscar en Mercado Libre
    if buscar_ml and query:
        with st.spinner("🔍 Buscando en Mercado Libre (esto puede tomar unos segundos)..."):
            # Intentar primero con Selenium
            resultados_ml = buscar_mercado_libre_selenium(query)
            
            # Si Selenium falla, intentar con requests
            if not resultados_ml:
                st.info("🔄 Intentando método alternativo...")
                resultados_ml = buscar_mercado_libre_api(query)
            
            if resultados_ml:
                st.session_state.resultados = resultados_ml
                st.success(f"✅ Encontrados {len(resultados_ml)} productos en Mercado Libre")
            else:
                st.error("""
                ❌ No se pudieron obtener productos de Mercado Libre. Posibles causas:
                - Mercado Libre está bloqueando las peticiones
                - Se necesita Selenium WebDriver
                - La estructura de la página cambió
                
                **Solución:** Instala ChromeDriver o prueba con eBay.
                """)
    
    # Buscar en eBay
    if buscar_ebay and query:
        with st.spinner("🌎 Buscando en eBay..."):
            resultados_ebay = buscar_ebay(query)
            if resultados_ebay:
                st.session_state.resultados = resultados_ebay
                st.success(f"✅ Encontrados {len(resultados_ebay)} productos en eBay")
            else:
                st.error("❌ No se encontraron productos en eBay")
    
    # Mostrar resultados
    if st.session_state.resultados:
        st.header("📦 Resultados de Búsqueda")
        
        productos_trackeados = cargar_productos()
        
        for i, producto in enumerate(st.session_state.resultados):
            st.markdown("---")
            col1, col2 = st.columns([3, 1])
            
            with col1:
                if mostrar_producto(producto, f"resultado_{i}"):
                    # Verificar si el producto ya está siendo seguido
                    ya_existe = any(p['enlace'] == producto['enlace'] for p in productos_trackeados)
                    
                    if not ya_existe:
                        productos_trackeados.append({
                            **producto,
                            'precio_inicial': producto['precio'],
                            'precio_actual': producto['precio'],
                            'fecha_seguimiento': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            'historial_precios': [{
                                'precio': producto['precio'],
                                'fecha': producto['fecha_consulta']
                            }]
                        })
                        guardar_productos(productos_trackeados)
                        st.success("✅ Producto agregado para seguimiento!")
                        st.rerun()
                    else:
                        st.warning("⚠️ Este producto ya está siendo seguido")
    
    # Productos en seguimiento
    st.header("📊 Productos en Seguimiento")
    
    productos_trackeados = cargar_productos()
    
    if not productos_trackeados:
        st.info("ℹ️ No hay productos en seguimiento. Busca productos y haz clic en 'Seguir precio'")
    else:
        st.write(f"**Total de productos en seguimiento:** {len(productos_trackeados)}")
        
        for i, producto in enumerate(productos_trackeados):
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
                                    nuevo['titulo'].lower() in producto['titulo'].lower() or
                                    producto['titulo'].lower() in nuevo['titulo'].lower()):
                                    
                                    precio_anterior = producto['precio_actual']
                                    producto['precio_actual'] = nuevo['precio']
                                    producto['fecha_consulta'] = nuevo['fecha_consulta']
                                    
                                    if abs(precio_anterior - nuevo['precio']) > 0.01:
                                        producto['historial_precios'].append({
                                            'precio': nuevo['precio'],
                                            'fecha': nuevo['fecha_consulta']
                                        })
                                    
                                    guardar_productos(productos_trackeados)
                                    st.success("✅ Precio actualizado!")
                                    time.sleep(1)
                                    st.rerun()
                                    break
            
            with col4:
                if st.button("❌ Eliminar", key=f"eliminar_{i}"):
                    productos_trackeados.pop(i)
                    guardar_productos(productos_trackeados)
                    st.success("✅ Producto eliminado!")
                    time.sleep(1)
                    st.rerun()

if __name__ == "__main__":
    main()