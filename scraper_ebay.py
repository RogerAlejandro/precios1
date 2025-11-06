import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime
import time
import random
from fake_useragent import UserAgent

# Configuración
SEARCH_QUERY = "iphone 13"  # Cambia por el producto que necesites
MAX_RESULTS = 3

def get_random_headers():
    ua = UserAgent()
    return {
        'User-Agent': ua.random,
        'Accept-Language': 'en-US,en;q=0.9',
    }

def scrape_ebay(search_query, max_results=3):
    url = f"https://www.ebay.com/sch/i.html?_nkw={search_query.replace(' ', '+')}"
    
    try:
        response = requests.get(url, headers=get_random_headers(), timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        products = []
        for item in soup.select('.s-item__wrapper')[:max_results]:
            try:
                title_elem = item.select_one('.s-item__title')
                price_elem = item.select_one('.s-item__price')
                
                if not all([title_elem, price_elem]):
                    continue
                
                title = title_elem.text.strip()
                price = price_elem.text.replace('MX', '').replace('$', '').strip()
                
                # Intentar obtener enlace
                link_elem = item.select_one('a.s-item__link')
                link = link_elem['href'] if link_elem else 'No disponible'
                
                products.append({
                    'title': title,
                    'price': float(price.replace(',', '')),  # Convertir a número
                    'currency': 'MXN',
                    'source': 'eBay',
                    'url': link,
                    'scraped_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                })
                
            except Exception as e:
                print(f"Error procesando producto: {e}")
                continue
                
        return pd.DataFrame(products)
        
    except Exception as e:
        print(f"Error al hacer scraping de eBay: {e}")
        return pd.DataFrame()

# Ejecutar el scraping
if __name__ == "__main__":
    print(f"🔍 Buscando '{SEARCH_QUERY}' en eBay...")
    df = scrape_ebay(SEARCH_QUERY, MAX_RESULTS)
    
    if not df.empty:
        print("\n📊 Resultados encontrados:")
        print(df[['title', 'price', 'currency']])
        
        # Guardar en CSV
        filename = f"precios_ebay_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        df.to_csv(filename, index=False)
        print(f"\n💾 Resultados guardados en: {filename}")
    else:
        print("No se encontraron resultados o hubo un error.")