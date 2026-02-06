"""
AutoTrack Backend - Version LÉGÈRE (HTTP + BeautifulSoup)
NOUVELLE APPROCHE:
- Pas de Selenium (trop lourd et détecté)
- Requêtes HTTP simples avec httpx
- Parsing HTML avec BeautifulSoup
- Headers réalistes et rotation des User-Agents
- Plus rapide et moins détectable
"""

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, List
from datetime import datetime
import asyncio
import os
import re
import logging
from contextlib import asynccontextmanager
import json
import math
import httpx
import random

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

# ============ CONFIGURATION ============
SCRAPE_INTERVAL_SECONDS = 30  # Augmenté pour éviter les bans
SCRAPE_URL = "https://www.leboncoin.fr/voitures/offres"
MAX_REQUESTS_BEFORE_BREAK = 2  # Seulement 2 requêtes puis pause longue
BREAK_DURATION = 120  # 2 minutes de pause après ban

# Base de données en mémoire
database = {
    "vehicles": [],
}

# WebSocket clients
websocket_clients = []

# User agents rotatifs (plus variés)
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:132.0) Gecko/20100101 Firefox/132.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1 Safari/605.1.15',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36',
    'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:132.0) Gecko/20100101 Firefox/132.0',
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

def calculate_distance(lat1, lon1, lat2, lon2):
    """Calcule la distance en km entre deux points GPS"""
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2 + 
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * 
         math.sin(dlon / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return round(R * c, 2)

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

# ============ SCRAPER HTTP LÉGER ============

class LightHTTPScraper:
    """Scraper léger utilisant httpx + BeautifulSoup"""
    
    def __init__(self):
        self.client = None
        self.seen_ads = set()
        self.running = False
        self.request_count = 0
        self.consecutive_403 = 0
        self.is_banned = False
        self.last_successful_request = None
    
    async def setup(self):
        """Initialise le client HTTP"""
        if not self.client:
            self.client = httpx.AsyncClient(
                timeout=30.0,
                follow_redirects=True,
                limits=httpx.Limits(max_keepalive_connections=5, max_connections=10)
            )
            logger.info("✅ Client HTTP initialisé")
        return True
    
    def _get_headers(self):
        """Génère des headers réalistes avec rotation"""
        user_agent = random.choice(USER_AGENTS)
        
        # Ajouter de la variabilité dans les headers
        headers = {
            'User-Agent': user_agent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Cache-Control': 'max-age=0',
        }
        
        # Ajouter un referer aléatoire parfois
        if random.random() > 0.5:
            headers['Referer'] = 'https://www.google.fr/'
        
        return headers
    
    async def get_recent_ads(self, max_ads=30):
        """Récupère les annonces via HTTP + parsing HTML"""
        if not BS4_AVAILABLE:
            logger.error("❌ BeautifulSoup non disponible")
            return []
        
        # Vérifier si on est banni
        if self.is_banned:
            logger.warning(f"⏸️ En pause (ban détecté) - Attente de {BREAK_DURATION}s...")
            await asyncio.sleep(BREAK_DURATION)
            self.is_banned = False
            self.consecutive_403 = 0
            logger.info("🔄 Reprise après pause")
        
        self.request_count += 1
        logger.info(f"🔍 [HTTP] Récupération de {max_ads} annonces (requête #{self.request_count})...")
        
        # Délai aléatoire avant la requête (simuler humain)
        if self.last_successful_request:
            delay = random.uniform(2, 5)
            logger.info(f"⏱️ Délai anti-détection: {delay:.1f}s...")
            await asyncio.sleep(delay)
        
        try:
            # Requête HTTP avec headers réalistes et rotatifs
            headers = self._get_headers()
            response = await self.client.get(SCRAPE_URL, headers=headers)
            
            if response.status_code == 403:
                self.consecutive_403 += 1
                logger.error(f"❌ Erreur 403 - Bloqué ({self.consecutive_403}/3)")
                
                # Si 3 erreurs 403 consécutives, pause longue
                if self.consecutive_403 >= 3:
                    logger.warning(f"🚫 BAN DÉTECTÉ - Pause de {BREAK_DURATION}s")
                    self.is_banned = True
                
                return []
            
            if response.status_code == 429:
                logger.warning("⚠️ Rate limit - Pause de 60 secondes...")
                await asyncio.sleep(60)
                return []
            
            if response.status_code != 200:
                logger.error(f"❌ Erreur HTTP: {response.status_code}")
                return []
            
            # Succès - réinitialiser le compteur 403
            self.consecutive_403 = 0
            self.last_successful_request = datetime.now()
            
            html_content = response.text
            logger.info(f"✅ Page téléchargée ({len(html_content)} caractères)")
            
            # Parser avec BeautifulSoup
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Chercher les annonces
            ad_elements = []
            
            # Stratégie 1: data-qa-id
            ads = soup.find_all('a', {'data-qa-id': 'aditem_container'})
            if ads and len(ads) >= 5:
                ad_elements = ads
                logger.info(f"✅ {len(ads)} annonces trouvées (data-qa-id)")
            
            # Stratégie 2: articles
            if not ad_elements:
                ads = soup.find_all('article')
                if ads and len(ads) >= 5:
                    ad_elements = ads
                    logger.info(f"✅ {len(ads)} annonces trouvées (article)")
            
            # Stratégie 3: liens vers /voitures/
            if not ad_elements:
                ads = soup.find_all('a', href=re.compile(r'/voitures/\d+\.htm'))
                if ads:
                    ad_elements = ads
                    logger.info(f"✅ {len(ads)} annonces trouvées (liens)")
            
            if not ad_elements:
                logger.warning("⚠️ AUCUNE ANNONCE DÉTECTÉE dans le HTML")
                return []
            
            # Parser les annonces
            ads_found = []
            for idx, element in enumerate(ad_elements[:max_ads]):
                try:
                    ad_data = self._parse_ad(element, idx, soup)
                    if ad_data:
                        ads_found.append(ad_data)
                        if idx < 3:
                            logger.info(f"  ✅ #{idx+1}: {ad_data['title'][:50]} - {ad_data['price']}€ - {ad_data['location']}")
                except Exception as e:
                    if idx < 3:
                        logger.warning(f"  ⚠️ #{idx+1}: {str(e)[:80]}")
                    continue
            
            logger.info(f"📊 Total parsé: {len(ads_found)}/{len(ad_elements[:max_ads])} annonces")
            return ads_found
            
        except httpx.TimeoutException:
            logger.error("❌ Timeout de la requête HTTP")
            return []
        except Exception as e:
            logger.error(f"❌ Erreur HTTP: {str(e)}")
            return []
    
    def _parse_ad(self, element, idx, soup):
        """Parse une annonce depuis BeautifulSoup avec parsing amélioré des prix"""
        try:
            # Titre
            title = "Véhicule d'occasion"
            title_elem = element.find(attrs={'data-qa-id': 'aditem_title'})
            if title_elem:
                title = title_elem.get_text(strip=True)
            else:
                h_elem = element.find(['h2', 'h3', 'p'])
                if h_elem:
                    text = h_elem.get_text(strip=True)
                    if len(text) > 10 and len(text) < 150:
                        title = text
            
            # Prix - PARSING AMÉLIORÉ
            price = 0
            
            # Méthode 1: data-qa-id
            price_elem = element.find(attrs={'data-qa-id': 'aditem_price'})
            if price_elem:
                price_text = price_elem.get_text(strip=True)
                price = self._extract_price(price_text)
            
            # Méthode 2: Chercher dans tout le texte de l'élément
            if price == 0:
                full_text = element.get_text()
                # Chercher pattern "XXXX €" ou "XX XXX €"
                price_patterns = [
                    r'(\d{1,3}(?:\s?\d{3})*)\s*€',  # "12 500 €" ou "12500 €"
                    r'(\d+)\s*€',  # "1500 €"
                ]
                
                for pattern in price_patterns:
                    matches = re.findall(pattern, full_text)
                    if matches:
                        # Prendre le premier prix trouvé
                        price_str = matches[0].replace(' ', '').replace('\u202f', '')
                        try:
                            price = int(price_str)
                            if 100 <= price <= 500000:
                                break
                            else:
                                price = 0
                        except:
                            price = 0
            
            # Méthode 3: Chercher dans les spans avec classe contenant "price"
            if price == 0:
                price_spans = element.find_all(['span', 'p', 'div'], class_=re.compile(r'price', re.I))
                for span in price_spans:
                    price_text = span.get_text(strip=True)
                    price = self._extract_price(price_text)
                    if price > 0:
                        break
            
            # URL
            url = ""
            if element.name == 'a':
                url = element.get('href', '')
            else:
                link = element.find('a')
                if link:
                    url = link.get('href', '')
            
            if url and not url.startswith('http'):
                url = f"https://www.leboncoin.fr{url}"
            
            # ID
            ad_id = f"lbc_http_{idx}"
            if url:
                match = re.search(r'/(\d+)\.htm', url)
                if match:
                    ad_id = f"lbc_{match.group(1)}"
            
            # Localisation
            location = "France"
            loc_elem = element.find(attrs={'data-qa-id': 'aditem_location'})
            if loc_elem:
                location = loc_elem.get_text(strip=True)
            else:
                # Chercher pattern ville (code postal)
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
            
            # Détections depuis le texte
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
            logger.error(f"Erreur parsing annonce {idx}: {str(e)}")
            return None
    
    def _extract_price(self, price_text):
        """Extrait le prix depuis un texte"""
        if not price_text:
            return 0
        
        try:
            # Nettoyer le texte (enlever espaces insécables, espaces normaux, etc.)
            clean_text = price_text.replace('\u202f', '').replace(' ', '').replace('\xa0', '')
            clean_text = clean_text.replace('€', '').replace(',', '').strip()
            
            # Extraire les chiffres
            numbers = re.findall(r'\d+', clean_text)
            if numbers:
                # Joindre tous les chiffres (pour gérer "12 500" → "12500")
                price_str = ''.join(numbers)
                price = int(price_str)
                
                # Validation
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
scraper = LightHTTPScraper()

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
    logger.info("✅ API démarrée - Mode HTTP LÉGER")
    task = asyncio.create_task(background_monitor())
    yield
    scraper.running = False
    await scraper.close()
    logger.info("🛑 API arrêtée")

app = FastAPI(
    title="AutoTrack API - Version Légère",
    version="6.0",
    description="API légère avec HTTP + BeautifulSoup",
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
    logger.info(f"🔌 Client connecté ({len(websocket_clients)} total)")
    
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        websocket_clients.remove(websocket)
        logger.info(f"🔌 Client déconnecté")

# ============ MONITORING ============

async def background_monitor():
    """Monitoring en arrière-plan avec gestion anti-ban"""
    scraper.running = True
    logger.info(f"⏱️  Monitoring démarré (intervalle: {SCRAPE_INTERVAL_SECONDS}s)")
    logger.info(f"🛡️ Protection anti-ban: max {MAX_REQUESTS_BEFORE_BREAK} requêtes puis pause de {BREAK_DURATION}s")
    
    await scraper.setup()
    
    logger.info("🔍 Scan initial...")
    try:
        initial_ads = await scraper.get_recent_ads(max_ads=30)
        for ad in initial_ads:
            scraper.seen_ads.add(ad['id'])
            database["vehicles"].insert(0, ad)
        logger.info(f"✅ {len(initial_ads)} annonces chargées\n")
    except Exception as e:
        logger.error(f"❌ Erreur scan initial: {str(e)}")
    
    scan_count = 0
    total_new = 0
    requests_in_session = 0
    
    logger.info(f"✅ Monitoring actif en mode HTTP!\n")
    
    while scraper.running:
        scan_count += 1
        current_time = datetime.now().strftime("%H:%M:%S")
        
        logger.info(f"[{current_time}] 🔍 Scan #{scan_count}...")
        
        # Pause préventive après X requêtes
        if requests_in_session >= MAX_REQUESTS_BEFORE_BREAK:
            logger.warning(f"⏸️ Pause préventive de {BREAK_DURATION}s après {requests_in_session} requêtes...")
            await asyncio.sleep(BREAK_DURATION)
            requests_in_session = 0
            logger.info("🔄 Reprise du monitoring")
        
        try:
            ads = await scraper.get_recent_ads(max_ads=30)
            requests_in_session += 1
            
            new_ads = [ad for ad in ads if ad['id'] not in scraper.seen_ads]
            
            if new_ads:
                logger.info(f"🆕 {len(new_ads)} nouvelle(s) annonce(s)!")
                total_new += len(new_ads)
                
                for ad in new_ads:
                    scraper.seen_ads.add(ad['id'])
                    database["vehicles"].insert(0, ad)
                    logger.info(f"  📌 {ad['title'][:60]}... - {ad['price']}€")
                    await broadcast_new_vehicle(ad)
                    
                    if len(database["vehicles"]) > 1000:
                        database["vehicles"] = database["vehicles"][:1000]
            else:
                logger.info(f"✓ Aucune nouvelle annonce")
            
            if scan_count % 5 == 0:
                logger.info(f"\n📊 Stats: {total_new} nouvelles | {len(database['vehicles'])} total | Requêtes session: {requests_in_session}/{MAX_REQUESTS_BEFORE_BREAK}\n")
            
        except Exception as e:
            logger.error(f"❌ Erreur scan: {str(e)}")
        
        logger.info(f"⏳ Prochaine vérification dans {SCRAPE_INTERVAL_SECONDS}s...\n")
        await asyncio.sleep(SCRAPE_INTERVAL_SECONDS)

# ============ ROUTES API ============

@app.get("/")
async def root():
    """Informations API"""
    return {
        "name": "AutoTrack API - Version Légère",
        "version": "6.0",
        "status": "running",
        "method": "HTTP + BeautifulSoup",
        "beautifulsoup_available": BS4_AVAILABLE,
        "vehicles_count": len(database["vehicles"]),
        "websocket_clients": len(websocket_clients),
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
        "vehicles": paginated,
    }

@app.get("/api/stats")
async def get_stats():
    """Statistiques"""
    return {
        "total_vehicles": len(database["vehicles"]),
        "scraper_running": scraper.running,
        "method": "HTTP Light",
        "requests_count": scraper.request_count,
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
