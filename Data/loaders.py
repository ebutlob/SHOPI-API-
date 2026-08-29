import random
import os
from typing import List
from api.models import Site, Proxy, Address
from api.config import settings

def load_sites() -> List[Site]:
    """Load sites from data/sites.txt"""
    sites = []
    try:
        with open(settings.SITES_FILE, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    parts = line.split('|')
                    if len(parts) >= 2:
                        site = Site(
                            store=parts[0].strip(),
                            product=parts[1].strip(),
                            price=parts[2].strip() if len(parts) > 2 else settings.DEFAULT_PRICE,
                            gateway=parts[3].strip() if len(parts) > 3 else settings.DEFAULT_GATEWAY,
                            weight=int(parts[4]) if len(parts) > 4 else 1
                        )
                        site.id = len(sites) + 1
                        sites.append(site)
    except FileNotFoundError:
        os.makedirs(os.path.dirname(settings.SITES_FILE), exist_ok=True)
        with open(settings.SITES_FILE, 'w') as f:
            f.write("# Format: store_url|product_path|price|gateway|weight\n")
            f.write("https://example.myshopify.com|/products/test|1.99 USD|Shopify Payments|1\n")
        
        sites.append(Site(
            store="https://example.myshopify.com",
            product="/products/test",
            price="1.99 USD",
            gateway="Shopify Payments",
            weight=1,
            id=1
        ))
    
    return sites

def load_proxies() -> List[Proxy]:
    """Load proxies from data/proxies.txt"""
    proxies = []
    try:
        with open(settings.PROXIES_FILE, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    parts = line.split(':')
                    if len(parts) == 4:
                        proxy = Proxy(
                            host=parts[0],
                            port=int(parts[1]),
                            username=parts[2],
                            password=parts[3]
                        )
                        proxy.id = len(proxies) + 1
                        proxies.append(proxy)
    except FileNotFoundError:
        os.makedirs(os.path.dirname(settings.PROXIES_FILE), exist_ok=True)
        with open(settings.PROXIES_FILE, 'w') as f:
            f.write("# Format: host:port:username:password\n")
            f.write("proxy.example.com:8080:user:pass\n")
    
    return proxies

def generate_email() -> str:
    """Generate random email"""
    prefix = ''.join(random.choices('abcdefghijklmnopqrstuvwxyz', k=8))
    domain = random.choice(settings.EMAIL_DOMAINS)
    return f"{prefix}{random.randint(10,99)}@{domain}"

def generate_address() -> Address:
    """Generate random US address"""
    first_names = ["John", "James", "Robert", "Michael", "David", "William"]
    last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia"]
    streets = ["Main St", "Oak Ave", "Pine Rd", "Maple Dr", "Cedar Ln", "Elm St"]
    cities = ["New York", "Los Angeles", "Miami", "Austin", "Seattle", "Chicago"]
    states = ["NY", "CA", "FL", "TX", "WA", "IL"]
    
    return Address(
        first_name=random.choice(first_names),
        last_name=random.choice(last_names),
        address1=f"{random.randint(100,9999)} {random.choice(streets)}",
        city=random.choice(cities),
        state=random.choice(states),
        zip=f"{random.randint(10000,99999)}"
    )
