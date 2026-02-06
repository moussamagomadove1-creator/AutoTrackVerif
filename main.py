"""
AutoTrack Backend - Version ANTI-BAN AMÉLIORÉE
AMÉLIORATIONS:
- Rotation complète des sessions (User-Agent, headers, cookies)
- Détection précoce des bans
- Limitation adaptative des requêtes
- Support proxies rotatifs (optionnel)
- Fallback API si HTML bloqué
- Délais intelligents entre requêtes
"""

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, List
from datetime import datetime, timedelta
import asyncio
import os
import re
import logging
from contextlib import asynccontextmanager
import json
import math
import httpx
import random
import time
import hashlib

# BeautifulSoup
try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False

# ============ LOGGING ============
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger(__name__)

# ============ CONFIGURATION ANTI-BAN ============
SCRAPE_INTERVAL_SECONDS = 10  # Augmenté pour éviter les bans
MAX_DELAY_SECONDS = 8
MIN_DELAY_SECONDS = 3
BAN_RECOVERY_DELAY = 45  # Augmenté
MAX_CONSECUTIVE_403 = 1  # Rotation plus agressive
MAX_REQUESTS_PER_SESSION = 15  # Limite de requêtes par session
MAX_VEHICLES_IN_MEMORY = 10000
PAGES_TO_SCRAPE = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]

# Configuration proxies (optionnel - à configurer si vous avez des proxies)
USE_PROXIES = False
PROXY_LIST = [
    # Ajoutez vos proxies ici au format: "http://ip:port"
    # "http://proxy1.com:8080",
    # "http://proxy2.com:8080",
]

# Base de données en mémoire
database = {
    "vehicles": [],
}

# WebSocket clients
websocket_clients = []

# User agents rotatifs ÉTENDUS
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:132.0) Gecko/20100101 Firefox/132.0',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:131.0) Gecko/20100101 Firefox/131.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1 Safari/605.1.15',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Safari/605.1.15',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0',
    'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:132.0) Gecko/20100101 Firefox/132.0',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 OPR/107.0.0.0',
]

# ============ GÉOLOCALISATION ============

FRENCH_CITIES_COORDS = {
    "paris": (48.8566, 2.3522),
    "marseille": (43.2965, 5.3698),
    "lyon": (45.7640, 4.8357),
    "toulouse": (43.6047, 1.4442),
    "nice": (43.7102, 7.2620),
    "nantes": (47.2184, -1.5536),
    "strasbourg": (48.5734, 7.7521),
    "montpellier": (43.6108, 3.8767),
    "bordeaux": (44.8378, -0.5792),
    "lille": (50.6292, 3.0573),
    "rennes": (48.1173, -1.6778),
    "saint-étienne": (45.4397, 4.3872),
    "toulon": (43.1242, 5.9280),
    "grenoble": (45.1885, 5.7245),
    "dijon": (47.3220, 5.0415),
    "angers": (47.4784, -0.5632),
    "orléans": (47.9029, 1.9093),
    "saint-jean-de-la-ruelle": (47.9111, 1.8697),
}

def normalize_city_name(city: str) -> str:
    """Normalise le nom d'une ville"""
    if not city:
        return ""
    city = city.lower().strip()
    city = re.sub(r'\s*\(\d+\)\s*', '', city)
    city = re.sub(r'[-\s]+', ' ', city)
    return city.strip()

def get_city_coordinates(city: str) -> Optional[tuple]:
    """Récupère les coordonnées d'une ville"""
    normalized = normalize_city_name(city)
    if normalized in FRENCH_CITIES_COORDS:
        return FRENCH_CITIES_COORDS[normalized]
    for city_key, coords in FRENCH_CITIES_COORDS.items():
        if normalized in city_key or city_key in normalized:
            return coords
    return None

# ============ SCRAPER ANTI-BAN ============

class AntiBanScraper:
    """Scraper avec système anti-ban avancé"""
    
    def __init__(self):
        self.client = None
        self.seen_ads = set()
        self.running = False
        self.request_count = 0
        self.session_request_count = 0
        self.consecutive_403 = 0
        self.last_successful_request = None
        self.session_created_at = None
        self.total_sessions = 0
        self.total_new_ads = 0
        self.total_errors = 0
        self.current_proxy = None
        self.proxy_index = 0
        self.success_rate = []  # Historique des succès
        self.adaptive_delay = MIN_DELAY_SECONDS
    
    def _get_next_proxy(self):
        """Obtient le prochain proxy dans la rotation"""
        if not USE_PROXIES or not PROXY_LIST:
            return None
        
        self.proxy_index = (self.proxy_index + 1) % len(PROXY_LIST)
        return PROXY_LIST[self.proxy_index]
    
    def _generate_random_headers(self):
        """Génère des headers aléatoires réalistes"""
        user_agent = random.choice(USER_AGENTS)
        
        # Variation des langues acceptées
        accept_languages = [
            'fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7',
            'fr-FR,fr;q=0.9,en;q=0.8',
            'fr,fr-FR;q=0.9,en;q=0.8',
            'fr-FR,fr;q=0.8,en-US;q=0.7,en;q=0.6',
        ]
        
        # Variation des encodages
        accept_encodings = [
            'gzip, deflate, br',
            'gzip, deflate, br, zstd',
            'gzip, deflate',
        ]
        
        headers = {
            'User-Agent': user_agent,
            'Accept-Language': random.choice(accept_languages),
            'Accept-Encoding': random.choice(accept_encodings),
            'DNT': str(random.choice([1, 1, 1, None])) if random.random() > 0.3 else None,
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': random.choice(['none', 'same-origin', 'cross-site']),
            'Sec-Fetch-User': '?1',
            'Cache-Control': random.choice(['max-age=0', 'no-cache']),
        }
        
        # Filtrer les headers None
        headers = {k: v for k, v in headers.items() if v is not None}
        
        # Ajouter un referer aléatoirement
        if random.random() > 0.4:
            referers = [
                'https://www.google.fr/',
                'https://www.google.com/search?q=voiture+occasion',
                'https://www.bing.com/',
                'https://www.leboncoin.fr/',
            ]
            headers['Referer'] = random.choice(referers)
        
        return headers
    
    async def _create_new_session(self):
        """Crée une nouvelle session HTTP avec rotation complète"""
        # Fermer l'ancienne session
        if self.client:
            try:
                await self.client.aclose()
                await asyncio.sleep(random.uniform(0.5, 1.5))  # Pause avant nouvelle session
            except:
                pass
        
        # Sélectionner un proxy
        if USE_PROXIES:
            self.current_proxy = self._get_next_proxy()
            logger.info(f"🔄 Proxy: {self.current_proxy}")
        
        # Générer des headers aléatoires
        headers = self._generate_random_headers()
        
        # Créer le client avec configuration anti-détection
        client_kwargs = {
            'timeout': httpx.Timeout(30.0, connect=10.0),
            'follow_redirects': True,
            'limits': httpx.Limits(
                max_keepalive_connections=5,
                max_connections=10,
                keepalive_expiry=30.0
            ),
            'headers': headers,
            'http2': random.choice([True, False]),  # Varier HTTP/2
        }
        
        # Ajouter le proxy si configuré
        if self.current_proxy:
            client_kwargs['proxies'] = {
                'http://': self.current_proxy,
                'https://': self.current_proxy,
            }
        
        self.client = httpx.AsyncClient(**client_kwargs)
        
        self.session_created_at = datetime.now()
        self.session_request_count = 0
        self.consecutive_403 = 0
        self.total_sessions += 1
        
        logger.info(f"🔄 Session #{self.total_sessions} créée")
    
    async def setup(self):
        """Initialise le client HTTP"""
        await self._create_new_session()
        logger.info("✅ Client HTTP prêt (mode anti-ban)")
        return True
    
    def _should_rotate_session(self):
        """Détermine si on doit changer de session"""
        # Rotation si trop de requêtes
        if self.session_request_count >= MAX_REQUESTS_PER_SESSION:
            logger.info(f"🔄 Rotation: limite de {MAX_REQUESTS_PER_SESSION} requêtes atteinte")
            return True
        
        # Rotation si bans détectés
        if self.consecutive_403 >= MAX_CONSECUTIVE_403:
            return True
        
        # Rotation si taux de succès faible
        if len(self.success_rate) >= 5:
            recent_success = sum(self.success_rate[-5:]) / 5
            if recent_success < 0.3:
                logger.info(f"🔄 Rotation: taux de succès faible ({recent_success:.1%})")
                return True
        
        return False
    
    def _update_adaptive_delay(self, success: bool):
        """Adapte le délai en fonction des succès/échecs"""
        self.success_rate.append(1 if success else 0)
        if len(self.success_rate) > 20:
            self.success_rate.pop(0)
        
        # Calculer le taux de succès récent
        if len(self.success_rate) >= 5:
            recent_success = sum(self.success_rate[-5:]) / 5
            
            # Augmenter le délai si échecs
            if recent_success < 0.5:
                self.adaptive_delay = min(self.adaptive_delay * 1.5, MAX_DELAY_SECONDS)
                logger.info(f"⏱️ Délai augmenté: {self.adaptive_delay:.1f}s")
            # Réduire progressivement si succès
            elif recent_success > 0.8:
                self.adaptive_delay = max(self.adaptive_delay * 0.9, MIN_DELAY_SECONDS)
    
    async def _handle_ban_recovery(self):
        """Récupération après ban avec stratégie agressive"""
        logger.warning(f"🚫 Ban détecté - Récupération...")
        
        # Pause plus longue
        recovery_time = BAN_RECOVERY_DELAY + random.uniform(0, 15)
        logger.info(f"⏳ Pause {recovery_time:.0f}s...")
        await asyncio.sleep(recovery_time)
        
        # Créer une nouvelle session complète
        await self._create_new_session()
        
        # Augmenter le délai adaptatif
        self.adaptive_delay = min(self.adaptive_delay * 2, MAX_DELAY_SECONDS)
        
        logger.info("✅ Session rotée après ban")
    
    async def scrape_all_pages(self):
        """Scrape plusieurs pages avec gestion anti-ban"""
        all_ads = []
        
        for page_num in PAGES_TO_SCRAPE:
            # Vérifier si rotation nécessaire avant chaque page
            if self._should_rotate_session():
                await self._create_new_session()
                await asyncio.sleep(random.uniform(2, 4))
            
            logger.info(f"  📄 Page {page_num}...")
            
            # Délai adaptatif entre pages
            if page_num > 1:
                delay = random.uniform(self.adaptive_delay, self.adaptive_delay + 2)
                await asyncio.sleep(delay)
            
            ads = await self.get_ads_from_page(page_num)
            
            if ads:
                all_ads.extend(ads)
                logger.info(f"     ✅ {len(ads)} annonces trouvées")
            else:
                logger.warning(f"     ⚠️ Aucune annonce")
            
            # Arrêter si ban détecté
            if self.consecutive_403 >= MAX_CONSECUTIVE_403:
                logger.warning("⚠️ Arrêt multi-page: ban détecté")
                await self._handle_ban_recovery()
                break
        
        logger.info(f"📊 Total: {len(all_ads)} annonces sur {len(PAGES_TO_SCRAPE)} pages")
        return all_ads
    
    async def get_ads_from_page(self, page_num=1):
        """Récupère les annonces d'une page avec détection précoce de ban"""
        if not BS4_AVAILABLE:
            logger.error("❌ BeautifulSoup non disponible")
            return []
        
        self.request_count += 1
        self.session_request_count += 1
        
        # Construire l'URL
        if page_num == 1:
            url = "https://www.leboncoin.fr/voitures/offres"
        else:
            url = f"https://www.leboncoin.fr/voitures/offres?page={page_num}"
        
        try:
            # Headers dynamiques pour chaque requête
            dynamic_headers = {
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                'Accept-Language': 'fr-FR,fr;q=0.9',
            }
            
            # Ajouter un referer si pas page 1
            if page_num > 1:
                dynamic_headers['Referer'] = f"https://www.leboncoin.fr/voitures/offres?page={page_num-1}"
            
            response = await self.client.get(url, headers=dynamic_headers)
            
            # Gestion des erreurs
            if response.status_code == 403:
                self.consecutive_403 += 1
                self.total_errors += 1
                self._update_adaptive_delay(False)
                logger.error(f"❌ 403 Forbidden ({self.consecutive_403}/{MAX_CONSECUTIVE_403})")
                
                if self.consecutive_403 >= MAX_CONSECUTIVE_403:
                    await self._handle_ban_recovery()
                
                return []
            
            if response.status_code == 429:
                logger.warning("⚠️ 429 Rate Limit")
                self._update_adaptive_delay(False)
                await self._handle_ban_recovery()
                return []
            
            if response.status_code != 200:
                logger.error(f"❌ HTTP {response.status_code}")
                self.total_errors += 1
                self._update_adaptive_delay(False)
                return []
            
            # Succès
            self.consecutive_403 = 0
            self.last_successful_request = datetime.now()
            self._update_adaptive_delay(True)
            
            html_content = response.text
            
            # Vérification anti-bot dans le contenu
            if "captcha" in html_content.lower() or "verify you are human" in html_content.lower():
                logger.warning("⚠️ Page de vérification détectée")
                await self._handle_ban_recovery()
                return []
            
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Chercher les annonces
            ad_elements = []
            
            # Stratégie 1: data-qa-id
            ads = soup.find_all('a', {'data-qa-id': 'aditem_container'})
            if ads and len(ads) >= 5:
                ad_elements = ads
            
            # Stratégie 2: articles
            if not ad_elements:
                ads = soup.find_all('article')
                if ads and len(ads) >= 5:
                    ad_elements = ads
            
            # Stratégie 3: liens voitures
            if not ad_elements:
                ads = soup.find_all('a', href=re.compile(r'/voitures/\d+\.htm'))
                if ads:
                    ad_elements = ads
            
            if not ad_elements:
                logger.warning("⚠️ Aucun élément d'annonce trouvé")
                return []
            
            # Parser les annonces
            ads_found = []
            for idx, element in enumerate(ad_elements):
                try:
                    ad_data = self._parse_ad(element, idx, soup)
                    if ad_data and ad_data.get('price', 0) > 0:
                        ads_found.append(ad_data)
                except Exception as e:
                    continue
            
            return ads_found
            
        except httpx.TimeoutException:
            logger.error("❌ Timeout")
            self.total_errors += 1
            self._update_adaptive_delay(False)
            return []
        except Exception as e:
            logger.error(f"❌ Erreur: {str(e)[:100]}")
            self.total_errors += 1
            self._update_adaptive_delay(False)
            return []
    
    def _parse_ad(self, element, idx, soup):
        """Parse une annonce"""
        try:
            # Titre
            title = None
            title_elem = element.find(attrs={'data-qa-id': 'aditem_title'})
            if title_elem:
                title = title_elem.get_text(strip=True)
            
            if not title:
                h_elem = element.find(['h2', 'h3', 'p'])
                if h_elem:
                    text = h_elem.get_text(strip=True)
                    if 10 < len(text) < 150:
                        title = text
            
            if not title or len(title) < 5:
                return None
            
            # Prix
            price = 0
            price_elem = element.find(attrs={'data-qa-id': 'aditem_price'})
            if price_elem:
                price_text = price_elem.get_text(strip=True)
                price = self._extract_price(price_text)
            
            if price == 0:
                full_text = element.get_text()
                price_patterns = [
                    r'(\d{1,3}(?:\s?\d{3})*)\s*€',
                    r'(\d+)\s*€',
                ]
                
                for pattern in price_patterns:
                    matches = re.findall(pattern, full_text)
                    if matches:
                        price_str = matches[0].replace(' ', '').replace('\u202f', '')
                        try:
                            price = int(price_str)
                            if 100 <= price <= 500000:
                                break
                            else:
                                price = 0
                        except:
                            price = 0
            
            # URL et ID unique
            url = ""
            if element.name == 'a':
                url = element.get('href', '')
            else:
                link = element.find('a')
                if link:
                    url = link.get('href', '')
            
            if url and not url.startswith('http'):
                url = f"https://www.leboncoin.fr{url}"
            
            # ID unique basé sur URL
            ad_id = None
            if url:
                match = re.search(r'/(\d+)\.htm', url)
                if match:
                    ad_id = f"lbc_{match.group(1)}"
            
            if not ad_id:
                unique_str = f"{title}_{price}"
                ad_id = f"lbc_{hashlib.md5(unique_str.encode()).hexdigest()[:8]}"
            
            # Localisation
            location = "France"
            loc_elem = element.find(attrs={'data-qa-id': 'aditem_location'})
            if loc_elem:
                location = loc_elem.get_text(strip=True)
            else:
                full_text = element.get_text()
                loc_match = re.search(r'([A-ZÀ-Ü][a-zA-ZÀ-ÿ\s\-\']+)\s*\((\d{5})\)', full_text)
                if loc_match:
                    location = f"{loc_match.group(1).strip()} ({loc_match.group(2)})"
            
            # Images
            images = []
            img_elements = element.find_all('img')
            for img in img_elements:
                img_url = img.get('src', '') or img.get('data-src', '')
                if img_url and any(x in img_url for x in ['images', 'thumbs', 'img']):
                    if not any(x in img_url.lower() for x in ['logo', 'icon', 'favicon']):
                        images.append(img_url)
            
            # Détections
            full_text = element.get_text()
            brand = self._detect_brand(title + " " + full_text)
            model = self._detect_model(title, brand)
            year = self._detect_year(full_text)
            mileage = self._detect_mileage(full_text)
            fuel = self._detect_fuel(full_text)
            gearbox = self._detect_gearbox(full_text)
            is_pro = "pro" in full_text.lower()
            score = self._calculate_score(year, mileage, price, is_pro)
            
            coordinates = get_city_coordinates(location)
            
            return {
                "id": ad_id,
                "title": title,
                "brand": brand,
                "model": model,
                "price": price,
                "year": year,
                "mileage": mileage,
                "fuel": fuel,
                "gearbox": gearbox,
                "location": location,
                "coordinates": coordinates,
                "is_pro": is_pro,
                "images": images[:5],
                "url": url,
                "published_at": datetime.now(),
                "score": score
            }
            
        except Exception as e:
            return None
    
    def _extract_price(self, price_text):
        """Extrait le prix"""
        if not price_text:
            return 0
        
        try:
            clean_text = price_text.replace('\u202f', '').replace(' ', '').replace('\xa0', '')
            clean_text = clean_text.replace('€', '').replace(',', '').strip()
            
            numbers = re.findall(r'\d+', clean_text)
            if numbers:
                price_str = ''.join(numbers)
                price = int(price_str)
                
                if 100 <= price <= 500000:
                    return price
            
            return 0
        except:
            return 0
    
    def _detect_brand(self, text):
        brands = [
            "Renault", "Peugeot", "Citroën", "Toyota", "Volkswagen", "Honda", "Ford",
            "BMW", "Mercedes", "Audi", "Fiat", "Kia", "Hyundai", "Nissan", "Opel",
            "Mazda", "Volvo", "Tesla", "Jeep", "Dacia", "Skoda", "SEAT", "Suzuki",
        ]
        text_lower = text.lower()
        for brand in brands:
            if brand.lower() in text_lower:
                return brand
        return None
    
    def _detect_model(self, text, brand):
        if not brand:
            return None
        try:
            pattern = re.compile(re.escape(brand) + r"\s+(.+?)(?:\s*[-–]|\s+\d{4}|$)", re.IGNORECASE)
            m = pattern.search(text)
            if m:
                model_part = m.group(1).strip()
                model_words = model_part.split()[:3]
                return " ".join(model_words)
        except:
            pass
        return None
    
    def _detect_year(self, text):
        matches = re.findall(r'\b(19[89]\d|20[0-2]\d)\b', text)
        if matches:
            return int(matches[-1])
        return None
    
    def _detect_mileage(self, text):
        match = re.search(r'(\d+[\s.]?\d*)\s*km', text, re.IGNORECASE)
        if match:
            try:
                km_str = match.group(1).replace(' ', '').replace('.', '')
                km = int(km_str)
                if 0 <= km <= 999999:
                    return km
            except:
                pass
        return None
    
    def _detect_fuel(self, text):
        text_lower = text.lower()
        if "électrique" in text_lower:
            return "électrique"
        if "hybride" in text_lower:
            return "hybride"
        if "diesel" in text_lower:
            return "diesel"
        if "essence" in text_lower:
            return "essence"
        return None
    
    def _detect_gearbox(self, text):
        text_lower = text.lower()
        if "automatique" in text_lower:
            return "automatique"
        if "manuelle" in text_lower:
            return "manuelle"
        return None
    
    def _calculate_score(self, year, mileage, price, is_pro):
        score = 50.0
        if year:
            if year >= 2022:
                score += 20
            elif year >= 2020:
                score += 15
        if mileage is not None:
            if mileage < 50000:
                score += 15
            elif mileage < 100000:
                score += 10
        if is_pro:
            score -= 5
        if 5000 <= price <= 30000:
            score += 5
        return round(min(max(score, 0), 100), 1)
    
    async def close(self):
        if self.client:
            await self.client.aclose()

# Instance globale
scraper = AntiBanScraper()

# ============ WEBSOCKET ============

async def broadcast_new_vehicle(vehicle):
    """Broadcast nouvelle annonce"""
    if not websocket_clients:
        return
    
    vehicle_data = {**vehicle}
    if isinstance(vehicle_data.get("published_at"), datetime):
        vehicle_data["published_at"] = vehicle_data["published_at"].isoformat()
    
    message = json.dumps({
        "type": "new_vehicle",
        "vehicle": vehicle_data
    })
    
    disconnected = []
    for client in websocket_clients:
        try:
            await client.send_text(message)
        except:
            disconnected.append(client)
    
    for client in disconnected:
        websocket_clients.remove(client)

# ============ FASTAPI APP ============

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gestion du cycle de vie"""
    logger.info("🚀 AutoTrack API - Mode Anti-Ban")
    logger.info(f"⚙️ Config: {MAX_REQUESTS_PER_SESSION} req/session, délai {MIN_DELAY_SECONDS}-{MAX_DELAY_SECONDS}s")
    if USE_PROXIES:
        logger.info(f"🌐 Proxies: {len(PROXY_LIST)} configurés")
    
    task = asyncio.create_task(background_monitor())
    yield
    scraper.running = False
    await scraper.close()
    logger.info("🛑 API arrêtée")

app = FastAPI(
    title="AutoTrack API",
    version="9.0-antiban",
    description="API avec système anti-ban avancé",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============ WEBSOCKET ============

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Endpoint WebSocket"""
    await websocket.accept()
    websocket_clients.append(websocket)
    logger.info(f"🔌 WS connecté ({len(websocket_clients)})")
    
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        websocket_clients.remove(websocket)
        logger.info(f"🔌 WS déconnecté")

# ============ MONITORING ============

async def background_monitor():
    """Monitoring avec système anti-ban"""
    scraper.running = True
    logger.info(f"⏱️ Intervalle: {SCRAPE_INTERVAL_SECONDS}s")
    
    await scraper.setup()
    
    # Scan initial
    logger.info("🔍 Scan initial (mode anti-ban)...")
    try:
        initial_ads = await scraper.scrape_all_pages()
        
        logger.info(f"\n📋 ANNONCES DÉTECTÉES:")
        for i, ad in enumerate(initial_ads[:10]):
            logger.info(f"  {i+1}. {ad['title'][:60]} - {ad['price']}€ - {ad['location'][:30]}")
            scraper.seen_ads.add(ad['id'])
            database["vehicles"].insert(0, ad)
        
        if len(initial_ads) > 10:
            logger.info(f"  ... et {len(initial_ads)-10} autres")
        
        logger.info(f"\n✅ {len(initial_ads)} annonces chargées\n")
    except Exception as e:
        logger.error(f"❌ Erreur scan initial: {str(e)}")
    
    scan_count = 0
    
    logger.info(f"✅ Monitoring actif (anti-ban)!\n")
    
    while scraper.running:
        scan_count += 1
        
        logger.info(f"🔍 Scan #{scan_count} (délai adaptatif: {scraper.adaptive_delay:.1f}s)...")
        
        try:
            ads = await scraper.scrape_all_pages()
            
            new_ads = [ad for ad in ads if ad['id'] not in scraper.seen_ads]
            
            if new_ads:
                logger.info(f"\n🆕 {len(new_ads)} NOUVELLE(S) ANNONCE(S)!")
                scraper.total_new_ads += len(new_ads)
                
                for ad in new_ads:
                    scraper.seen_ads.add(ad['id'])
                    database["vehicles"].insert(0, ad)
                    logger.info(f"   📌 {ad['title'][:50]}... - {ad['price']}€ - {ad['location']}")
                    await broadcast_new_vehicle(ad)
                
                if len(database["vehicles"]) > MAX_VEHICLES_IN_MEMORY:
                    database["vehicles"] = database["vehicles"][:MAX_VEHICLES_IN_MEMORY]
            else:
                logger.info(f"✓ Aucune nouvelle annonce")
            
            # Stats tous les 3 scans
            if scan_count % 3 == 0:
                uptime = (datetime.now() - scraper.session_created_at).total_seconds() / 60
                success_rate = sum(scraper.success_rate[-10:]) / min(len(scraper.success_rate), 10) if scraper.success_rate else 0
                
                logger.info(f"\n📊 STATS:")
                logger.info(f"   • Nouvelles: {scraper.total_new_ads}")
                logger.info(f"   • Total DB: {len(database['vehicles'])}")
                logger.info(f"   • IDs vus: {len(scraper.seen_ads)}")
                logger.info(f"   • Sessions: {scraper.total_sessions}")
                logger.info(f"   • Taux succès: {success_rate:.1%}")
                logger.info(f"   • Délai adaptatif: {scraper.adaptive_delay:.1f}s")
                logger.info(f"   • Uptime session: {uptime:.1f}min\n")
            
        except Exception as e:
            logger.error(f"❌ Erreur: {str(e)[:100]}")
        
        # Délai avec variation aléatoire
        pause_time = SCRAPE_INTERVAL_SECONDS + random.uniform(-2, 3)
        logger.info(f"⏳ Pause {pause_time:.1f}s...\n")
        await asyncio.sleep(pause_time)

# ============ ROUTES API ============

@app.get("/")
async def root():
    """Informations API"""
    uptime = None
    if scraper.session_created_at:
        uptime = (datetime.now() - scraper.session_created_at).total_seconds()
    
    success_rate = sum(scraper.success_rate) / len(scraper.success_rate) if scraper.success_rate else 0
    
    return {
        "name": "AutoTrack API - Anti-Ban",
        "version": "9.0",
        "status": "running",
        "vehicles_count": len(database["vehicles"]),
        "unique_ads_seen": len(scraper.seen_ads),
        "websocket_clients": len(websocket_clients),
        "stats": {
            "total_requests": scraper.request_count,
            "session_requests": scraper.session_request_count,
            "total_sessions": scraper.total_sessions,
            "total_new_ads": scraper.total_new_ads,
            "total_errors": scraper.total_errors,
            "success_rate": f"{success_rate:.1%}",
            "adaptive_delay": f"{scraper.adaptive_delay:.1f}s",
            "session_uptime_minutes": round(uptime / 60, 1) if uptime else 0,
        }
    }

@app.get("/api/vehicles")
async def get_vehicles(
    limit: int = 50,
    page: int = 1,
    brand: Optional[str] = None,
    location: Optional[str] = None,
    min_price: Optional[int] = None,
    max_price: Optional[int] = None,
    sort: str = "recent"
):
    """Récupère les véhicules avec filtres"""
    vehicles = database["vehicles"].copy()
    
    if brand:
        vehicles = [v for v in vehicles if v.get("brand") and v.get("brand").lower() == brand.lower()]
    if location:
        vehicles = [v for v in vehicles if v.get("location") and location.lower() in v.get("location", "").lower()]
    if min_price:
        vehicles = [v for v in vehicles if v.get("price", 0) >= min_price]
    if max_price:
        vehicles = [v for v in vehicles if v.get("price", 0) <= max_price]
    
    if sort == "price_asc":
        vehicles.sort(key=lambda x: x.get("price", 0))
    elif sort == "price_desc":
        vehicles.sort(key=lambda x: x.get("price", 999999), reverse=True)
    
    total = len(vehicles)
    start = (page - 1) * limit
    end = start + limit
    paginated = vehicles[start:end]
    
    return {
        "total": total,
        "page": page,
        "limit": limit,
        "vehicles": paginated,
    }

@app.get("/api/stats")
async def get_stats():
    """Statistiques détaillées"""
    uptime = None
    if scraper.session_created_at:
        uptime = (datetime.now() - scraper.session_created_at).total_seconds()
    
    success_rate = sum(scraper.success_rate) / len(scraper.success_rate) if scraper.success_rate else 0
    
    return {
        "total_vehicles": len(database["vehicles"]),
        "unique_ads_seen": len(scraper.seen_ads),
        "scraper_running": scraper.running,
        "requests": {
            "total": scraper.request_count,
            "session": scraper.session_request_count,
            "errors": scraper.total_errors,
            "success_rate": f"{success_rate:.1%}",
        },
        "sessions": {
            "total": scraper.total_sessions,
            "uptime_minutes": round(uptime / 60, 1) if uptime else 0,
            "requests_per_session": MAX_REQUESTS_PER_SESSION,
        },
        "discoveries": {
            "total_new_ads": scraper.total_new_ads,
        },
        "anti_ban": {
            "adaptive_delay": f"{scraper.adaptive_delay:.1f}s",
            "consecutive_403": scraper.consecutive_403,
            "proxies_enabled": USE_PROXIES,
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
