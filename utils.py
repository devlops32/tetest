# utils.py - Утилиты

import aiohttp
from typing import List, Optional
import random
from config import PROXY_FILE, PROXY_ROTATION

class ProxyRotator:
    def __init__(self):
        self.proxies: List[str] = []
        self.current_index = 0
        self.load_proxies()
    
    def load_proxies(self):
        try:
            with open(PROXY_FILE, 'r') as f:
                self.proxies = [line.strip() for line in f if line.strip()]
        except FileNotFoundError:
            self.proxies = []
    
    def get_next_proxy(self) -> Optional[str]:
        if not self.proxies:
            return None
        if PROXY_ROTATION:
            proxy = self.proxies[self.current_index]
            self.current_index = (self.current_index + 1) % len(self.proxies)
            return proxy
        else:
            return self.proxies[0] if self.proxies else None

proxy_rotator = ProxyRotator()

async def get_proxy_session() -> aiohttp.ClientSession:
    proxy = proxy_rotator.get_next_proxy()
    connector = None
    if proxy:
        proxy_url = f"http://{proxy}"
        connector = aiohttp.TCPConnector()
    return aiohttp.ClientSession(connector=connector)

def parse_product_file(file_path: str) -> dict:
    products = {}
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                parts = line.split('|')
                if len(parts) >= 2:
                    name = parts[0].strip()
                    quantities = [q.strip() for q in parts[1:] if q.strip()]
                    products[name] = quantities
    except FileNotFoundError:
        print(f"⚠️ Файл {file_path} не найден!")
    return products

def get_product_quantities(product_name: str) -> List[str]:
    products = parse_product_file('list.txt')
    return products.get(product_name, [])

def format_card_number(card: str) -> str:
    digits = ''.join(filter(str.isdigit, card))
    if len(digits) == 16:
        return ' '.join([digits[i:i+4] for i in range(0, 16, 4)])
    return card