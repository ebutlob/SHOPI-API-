import random
import threading
import os
from typing import List, Optional
from datetime import datetime
from .models import Site, Proxy
from .config import settings
from data.loaders import load_sites, load_proxies

class PoolManager:
    def __init__(self):
        self.sites: List[Site] = []
        self.proxies: List[Proxy] = []
        self.failed_sites: set = set()
        self.failed_proxies: set = set()
        self.lock = threading.Lock()
        self.last_refresh = datetime.now()
        self._load_pools()
    
    def _load_pools(self):
        """Load sites and proxies from files"""
        self.sites = load_sites()
        self.proxies = load_proxies()
        
        if not self.sites:
            self.sites = [
                Site(
                    store="https://example.myshopify.com",
                    product="/products/test",
                    price="1.99 USD"
                )
            ]
        
        if not self.proxies:
            self.proxies = [
                Proxy(host="proxy.example.com", port=8080, 
                      username="user", password="pass")
            ]
    
    def get_site(self) -> Optional[Site]:
        with self.lock:
            available = [s for s in self.sites 
                        if s.id not in self.failed_sites and s.enabled]
            
            if not available:
                self.failed_sites.clear()
                available = [s for s in self.sites if s.enabled]
            
            if not available:
                return None
            
            weights = [s.weight for s in available]
            return random.choices(available, weights=weights, k=1)[0]
    
    def get_proxy(self) -> Optional[Proxy]:
        with self.lock:
            available = [p for p in self.proxies 
                        if p.id not in self.failed_proxies]
            
            if not available:
                self.failed_proxies.clear()
                available = self.proxies.copy()
            
            if not available:
                return None
            
            return random.choice(available)
    
    def mark_site_failed(self, site_id: int):
        with self.lock:
            self.failed_sites.add(site_id)
    
    def mark_proxy_failed(self, proxy_id: int):
        with self.lock:
            self.failed_proxies.add(proxy_id)
    
    def refresh(self):
        with self.lock:
            self._load_pools()
            self.failed_sites.clear()
            self.failed_proxies.clear()

pool_manager = PoolManager()
