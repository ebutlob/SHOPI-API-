import os
import re
import json
import time
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin
from typing import List, Dict, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

class SiteAutoDiscover:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive"
        })
        self.discovered = {}
        self.lock = threading.Lock()
        self.cache_file = "data/discovered_cache.json"
        self._load_cache()
    
    def _load_cache(self):
        """Load cached discoveries"""
        try:
            os.makedirs("data", exist_ok=True)
            with open(self.cache_file, 'r') as f:
                self.discovered = json.load(f)
        except:
            self.discovered = {}
    
    def _save_cache(self):
        """Save discoveries to cache"""
        try:
            os.makedirs("data", exist_ok=True)
            with open(self.cache_file, 'w') as f:
                json.dump(self.discovered, f, indent=2)
        except:
            pass
    
    def normalize_url(self, url: str) -> str:
        """Normalize URL to proper format"""
        url = url.strip()
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        url = url.rstrip('/')
        return url
    
    def is_shopify_store(self, url: str) -> bool:
        """Check if URL is a Shopify store"""
        shopify_patterns = [
            r'\.myshopify\.com',
            r'/products/',
            r'/collections/',
            r'/cart/',
            r'/checkout/'
        ]
        for pattern in shopify_patterns:
            if re.search(pattern, url, re.IGNORECASE):
                return True
        return False
    
    def discover_product(self, url: str) -> Optional[Dict]:
        """Discover a product on a site"""
        # Check cache first
        if url in self.discovered:
            cached = self.discovered[url]
            # Cache valid for 7 days
            if time.time() - cached.get('timestamp', 0) < 604800:
                return cached
        
        try:
            # Normalize URL
            url = self.normalize_url(url)
            
            # Try to find product
            product = self._find_cheapest_product(url)
            
            if product:
                result = {
                    'url': url,
                    'product_path': product.get('path', '/products/test'),
                    'price': product.get('price', '2.95 USD'),
                    'product_name': product.get('name', 'Unknown Product'),
                    'product_url': product.get('full_url', ''),
                    'timestamp': time.time(),
                    'status': 'success'
                }
                
                with self.lock:
                    self.discovered[url] = result
                    self._save_cache()
                
                return result
            
            return None
            
        except Exception as e:
            return {
                'url': url,
                'status': 'error',
                'error': str(e),
                'timestamp': time.time()
            }
    
    def _find_cheapest_product(self, base_url: str) -> Optional[Dict]:
        """Find cheapest product on a site"""
        # Try different product discovery methods
        methods = [
            self._find_from_collections,
            self._find_from_products,
            self._find_from_homepage,
            self._find_from_sitemap,
            self._find_from_cart,
            self._find_from_shopify_api
        ]
        
        for method in methods:
            try:
                result = method(base_url)
                if result:
                    return result
            except:
                continue
        
        return None
    
    def _find_from_collections(self, base_url: str) -> Optional[Dict]:
        """Find product from collections"""
        collection_urls = [
            '/collections/all',
            '/collections/best-sellers',
            '/collections/new-arrivals',
            '/collections/featured',
            '/collections/sale'
        ]
        
        for collection in collection_urls:
            try:
                url = urljoin(base_url, collection)
                response = self.session.get(url, timeout=10)
                if response.status_code != 200:
                    continue
                
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Find product links
                product_links = []
                for link in soup.find_all('a', href=True):
                    href = link['href']
                    if '/products/' in href:
                        product_links.append(href)
                
                if product_links:
                    # Get first product
                    product_url = urljoin(base_url, product_links[0])
                    product_info = self._get_product_info(product_url)
                    if product_info:
                        return {
                            'path': urlparse(product_url).path,
                            'full_url': product_url,
                            'price': product_info.get('price', '2.95 USD'),
                            'name': product_info.get('name', 'Product')
                        }
            except:
                continue
        
        return None
    
    def _find_from_products(self, base_url: str) -> Optional[Dict]:
        """Find product from direct products page"""
        try:
            response = self.session.get(base_url + '/products', timeout=10)
            if response.status_code != 200:
                return None
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            for link in soup.find_all('a', href=True):
                href = link['href']
                if '/products/' in href and href != '/products/':
                    product_url = urljoin(base_url, href)
                    product_info = self._get_product_info(product_url)
                    if product_info:
                        return {
                            'path': urlparse(product_url).path,
                            'full_url': product_url,
                            'price': product_info.get('price', '2.95 USD'),
                            'name': product_info.get('name', 'Product')
                        }
        except:
            pass
        
        return None
    
    def _find_from_homepage(self, base_url: str) -> Optional[Dict]:
        """Find product from homepage"""
        try:
            response = self.session.get(base_url, timeout=10)
            if response.status_code != 200:
                return None
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Look for product links
            for link in soup.find_all('a', href=True):
                href = link['href']
                if '/products/' in href:
                    product_url = urljoin(base_url, href)
                    product_info = self._get_product_info(product_url)
                    if product_info:
                        return {
                            'path': urlparse(product_url).path,
                            'full_url': product_url,
                            'price': product_info.get('price', '2.95 USD'),
                            'name': product_info.get('name', 'Product')
                        }
            
            # Look for product JSON
            for script in soup.find_all('script'):
                if script.string and 'products' in script.string.lower():
                    try:
                        matches = re.findall(r'\/products\/[a-zA-Z0-9\-_]+', script.string)
                        if matches:
                            product_url = urljoin(base_url, matches[0])
                            product_info = self._get_product_info(product_url)
                            if product_info:
                                return {
                                    'path': urlparse(product_url).path,
                                    'full_url': product_url,
                                    'price': product_info.get('price', '2.95 USD'),
                                    'name': product_info.get('name', 'Product')
                                }
                    except:
                        pass
        except:
            pass
        
        return None
    
    def _find_from_sitemap(self, base_url: str) -> Optional[Dict]:
        """Find product from sitemap"""
        sitemap_urls = [
            '/sitemap.xml',
            '/sitemap_products_1.xml',
            '/sitemap_products.xml',
            '/sitemap.xml.gz'
        ]
        
        for sitemap in sitemap_urls:
            try:
                url = urljoin(base_url, sitemap)
                response = self.session.get(url, timeout=10)
                if response.status_code != 200:
                    continue
                
                if 'sitemapindex' in response.text.lower():
                    soup = BeautifulSoup(response.text, 'xml')
                    for loc in soup.find_all('loc'):
                        sub_url = loc.text
                        if '/products/' in sub_url:
                            product_info = self._get_product_info(sub_url)
                            if product_info:
                                return {
                                    'path': urlparse(sub_url).path,
                                    'full_url': sub_url,
                                    'price': product_info.get('price', '2.95 USD'),
                                    'name': product_info.get('name', 'Product')
                                }
                elif 'urlset' in response.text.lower():
                    soup = BeautifulSoup(response.text, 'xml')
                    for loc in soup.find_all('loc'):
                        loc_url = loc.text
                        if '/products/' in loc_url:
                            product_info = self._get_product_info(loc_url)
                            if product_info:
                                return {
                                    'path': urlparse(loc_url).path,
                                    'full_url': loc_url,
                                    'price': product_info.get('price', '2.95 USD'),
                                    'name': product_info.get('name', 'Product')
                                }
            except:
                continue
        
        return None
    
    def _find_from_cart(self, base_url: str) -> Optional[Dict]:
        """Find product from cart recommend"""
        try:
            response = self.session.get(base_url + '/cart', timeout=10)
            if response.status_code != 200:
                return None
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            for link in soup.find_all('a', href=True):
                href = link['href']
                if '/products/' in href:
                    product_url = urljoin(base_url, href)
                    product_info = self._get_product_info(product_url)
                    if product_info:
                        return {
                            'path': urlparse(product_url).path,
                            'full_url': product_url,
                            'price': product_info.get('price', '2.95 USD'),
                            'name': product_info.get('name', 'Product')
                        }
        except:
            pass
        
        return None
    
    def _find_from_shopify_api(self, base_url: str) -> Optional[Dict]:
        """Find product using Shopify API endpoints"""
        try:
            # Try Shopify's products.json
            api_url = urljoin(base_url, '/products.json')
            response = self.session.get(api_url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get('products'):
                    product = data['products'][0]
                    handle = product.get('handle')
                    if handle:
                        product_url = urljoin(base_url, f'/products/{handle}')
                        return {
                            'path': f'/products/{handle}',
                            'full_url': product_url,
                            'price': f"{product.get('variants', [{}])[0].get('price', '2.95')} USD",
                            'name': product.get('title', 'Product')
                        }
            
            # Try collections.json
            api_url = urljoin(base_url, '/collections.json')
            response = self.session.get(api_url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get('collections'):
                    collection = data['collections'][0]
                    handle = collection.get('handle')
                    if handle:
                        product_url = urljoin(base_url, f'/collections/{handle}/products')
                        response = self.session.get(product_url, timeout=10)
                        if response.status_code == 200:
                            soup = BeautifulSoup(response.text, 'html.parser')
                            for link in soup.find_all('a', href=True):
                                if '/products/' in link['href']:
                                    product_url = urljoin(base_url, link['href'])
                                    product_info = self._get_product_info(product_url)
                                    if product_info:
                                        return {
                                            'path': urlparse(product_url).path,
                                            'full_url': product_url,
                                            'price': product_info.get('price', '2.95 USD'),
                                            'name': product_info.get('name', 'Product')
                                        }
        except:
            pass
        
        return None
    
    def _get_product_info(self, url: str) -> Optional[Dict]:
        """Get product information from product page"""
        try:
            response = self.session.get(url, timeout=10)
            if response.status_code != 200:
                return None
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Get product name
            name = None
            name_selectors = [
                '.product-title', '.product-name', '.product__title',
                'h1[itemprop="name"]', 'h1.product-single__title',
                '.product-item__title', '.product-block__title',
                'h1[class*="product"]', '.product h1'
            ]
            
            for selector in name_selectors:
                elem = soup.select_one(selector)
                if elem:
                    name = elem.text.strip()
                    break
            
            if not name:
                title = soup.find('title')
                if title:
                    name = title.text.split('|')[0].split('–')[0].strip()
            
            # Get price
            price = None
            price_selectors = [
                '.price', '.product-price', '.product__price',
                '.price__current', '[data-price]', '.product-single__price',
                '.product-item__price', '.product-block__price',
                '.current-price', '.product-price__current'
            ]
            
            for selector in price_selectors:
                elem = soup.select_one(selector)
                if elem:
                    price = elem.text.strip()
                    break
            
            # Try JSON-LD
            if not price:
                for script in soup.find_all('script', type='application/ld+json'):
                    try:
                        data = json.loads(script.string)
                        if isinstance(data, dict) and data.get('@type') == 'Product':
                            offers = data.get('offers', {})
                            if offers:
                                price = offers.get('price', '')
                                break
                    except:
                        pass
            
            if not price:
                # Try meta tags
                meta_price = soup.find('meta', {'property': 'product:price:amount'})
                if meta_price:
                    price = meta_price.get('content', '')
            
            if not price:
                return None
            
            # Clean price
            price = re.sub(r'[^\d.,]', '', price)
            if '.' in price:
                price = price.split('.')[0] + '.' + price.split('.')[1][:2]
            
            return {
                'name': name or 'Product',
                'price': f"{price} USD" if price else '2.95 USD'
            }
            
        except:
            return None
    
    def process_site_list(self, urls: List[str]) -> Dict:
        """Process a list of sites and discover products"""
        results = {
            'total': len(urls),
            'success': 0,
            'failed': 0,
            'sites': []
        }
        
        # Filter and normalize URLs
        processed = []
        for url in urls:
            url = url.strip()
            if url and not url.startswith('#'):
                url = self.normalize_url(url)
                if url not in processed:
                    processed.append(url)
        
        # Process with thread pool
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = {executor.submit(self.discover_product, url): url for url in processed}
            
            for future in as_completed(futures):
                url = futures[future]
                try:
                    result = future.result(timeout=30)
                    if result and result.get('status') != 'error':
                        results['success'] += 1
                        results['sites'].append({
                            'url': url,
                            'product_path': result.get('product_path', '/products/test'),
                            'price': result.get('price', '2.95 USD'),
                            'product_name': result.get('product_name', 'Product'),
                            'status': 'success'
                        })
                    else:
                        results['failed'] += 1
                        results['sites'].append({
                            'url': url,
                            'status': 'failed',
                            'error': result.get('error', 'Unknown error') if result else 'No result'
                        })
                except Exception as e:
                    results['failed'] += 1
                    results['sites'].append({
                        'url': url,
                        'status': 'failed',
                        'error': str(e)
                    })
        
        return results
    
    def generate_sites_file(self, results: Dict, output_file: str = "data/sites_auto.txt") -> str:
        """Generate formatted sites.txt from results"""
        lines = [
   
