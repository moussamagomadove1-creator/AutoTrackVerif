"""
AutoTrack Backend - Version Railway Optimisée
Configuration Chrome corrigée pour Railway
"""

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, List
from datetime import datetime
import asyncio
import secrets
import os
import re
import random
import time
import logging
from contextlib import asynccontextmanager
import json
import math

# Import Selenium STANDARD - Compatible Railway
SELENIUM_AVAILABLE = False
try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    SELENIUM_AVAILABLE = True
except ImportError as e:
    pass

# ============ LOGGING ============
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger(__name__)

if SELENIUM_AVAILABLE:
    logger.info("✅ Selenium disponible")
else:
    logger.error("❌ Selenium non disponible")

# ============ CONFIGURATION ============
SCRAPE_INTERVAL_SECONDS = int(os.getenv("SCRAPE_INTERVAL", "10"))
SCRAPE_URL = "https://www.leboncoin.fr/voitures/offres"

# Base de données en mémoire
database = {
    "users": {},
    "vehicles": [],
    "subscriptions": {},
    "alerts": {}
}

websocket_clients = []
consecutive_empty_scans = 0
MAX_EMPTY_SCANS_BEFORE_REFRESH = 10

# ============ VILLES FRANCE ============
FRENCH_CITIES_COORDS = {
    "paris": (48.8566, 2.3522),
    "marseille": (43.2965, 5.3698),
    "lyon": (45.7640, 4.8357),
    "toulouse": (43.6047, 1.4442),
    "nice": (43.7102, 7.2620),
    "nantes": (47.2184, -1.5536),
    "bordeaux": (44.8378, -0.5792),
    "lille": (50.6292, 3.0573),
    "strasbourg": (48.5734, 7.7521),
    "montpellier": (43.6108, 3.8767),
}

def calculate_distance(lat1, lon1, lat2, lon2):
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2 + 
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * 
         math.sin(dlon / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return round(R * c, 2)

def normalize_city_name(city: str) -> str:
    if not city:
        return ""
    city = city.lower().strip()
    city = re.sub(r'\s*\(\d+\)\s*', '', city)
    city = re.sub(r'[-\s]+', ' ', city)
    return city.strip()

def get_city_coordinates(city: str) -> Optional[tuple]:
    normalized = normalize_city_name(city)
    if normalized in FRENCH_CITIES_COORDS:
        return FRENCH_CITIES_COORDS[normalized]
    for city_name, coords in FRENCH_CITIES_COORDS.items():
        if normalized in city_name or city_name in normalized:
            return coords
    return None

# ============ CHROME POUR RAILWAY ============
def init_chrome_driver():
    if not SELENIUM_AVAILABLE:
        logger.error("❌ Selenium non disponible")
        return None
    
    try:
        logger.info("🚀 Initialisation Chrome...")
        
        chrome_options = Options()
        
        # Options CRITIQUES pour Railway
        chrome_options.add_argument('--headless=new')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--disable-software-rasterizer')
        chrome_options.add_argument('--disable-extensions')
        chrome_options.add_argument('--disable-setuid-sandbox')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_argument('--log-level=3')
        
        # Chemins possibles pour Chrome sur Railway
        chrome_paths = [
            '/usr/bin/chromium-browser',
            '/usr/bin/chromium',
            '/usr/bin/google-chrome',
            '/usr/bin/google-chrome-stable',
        ]
        
        # Trouver Chrome
        chrome_found = False
        for chrome_path in chrome_paths:
            if os.path.exists(chrome_path):
                chrome_options.binary_location = chrome_path
                chrome_found = True
                logger.info(f"✅ Chrome trouvé: {chrome_path}")
                break
        
        if not chrome_found:
            logger.warning("⚠️ Chrome non trouvé, utilisation par défaut")
        
        # Initialiser
        driver = webdriver.Chrome(options=chrome_options)
        driver.set_page_load_timeout(30)
        
        logger.info("✅ Chrome initialisé")
        return driver
        
    except Exception as e:
        logger.error(f"❌ Erreur Chrome: {e}")
        return None

# ============ SCRAPER ============
class LeboncoinScraper:
    def __init__(self):
        self.driver = None
        self.running = False
        self.last_scraped_ids = set()
        self.page_loaded = False
        self.cookies_accepted = False
    
    def init_driver(self):
        try:
            self.driver = init_chrome_driver()
            if self.driver:
                logger.info("✅ Driver prêt")
                return True
            else:
                logger.error("❌ Échec init driver")
                return False
        except Exception as e:
            logger.error(f"❌ Erreur driver: {e}")
            return False
    
    def close_driver(self):
        if self.driver:
            try:
                self.driver.quit()
                logger.info("🔴 Driver fermé")
            except:
                pass
            finally:
                self.driver = None
    
    def scrape_vehicles(self) -> List[dict]:
        global consecutive_empty_scans
        
        if not self.driver:
            if not self.init_driver():
                return []
        
        try:
            # Charger ou rafraîchir
            if not self.page_loaded:
                logger.info("📄 Chargement initial...")
                self.driver.get(SCRAPE_URL)
                time.sleep(3)
                
                # Accepter cookies
                if not self.cookies_accepted:
                    try:
                        cookie_btn = WebDriverWait(self.driver, 3).until(
                            EC.element_to_be_clickable((By.ID, "didomi-notice-agree-button"))
                        )
                        cookie_btn.click()
                        time.sleep(1)
                    except:
                        pass
                    self.cookies_accepted = True
                
                self.page_loaded = True
            else:
                logger.info("🔄 Rafraîchissement...")
                self.driver.refresh()
                time.sleep(2)
            
            # Attendre annonces
            try:
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "a[data-qa-id='adlink']"))
                )
            except:
                logger.warning("⚠️ Timeout annonces")
            
            # Scroll minimal
            try:
                self.driver.execute_script("window.scrollTo(0, 800);")
                time.sleep(0.5)
            except:
                pass
            
            # Extraire annonces
            vehicles = []
            ads = self.driver.find_elements(By.CSS_SELECTOR, "a[data-qa-id='adlink']")
            logger.info(f"📦 {len(ads)} annonces trouvées")
            
            if len(ads) == 0:
                consecutive_empty_scans += 1
            else:
                consecutive_empty_scans = 0
            
            # Recharger si trop de scans vides
            if consecutive_empty_scans >= MAX_EMPTY_SCANS_BEFORE_REFRESH:
                logger.warning(f"⚠️ {consecutive_empty_scans} scans vides, rechargement...")
                self.page_loaded = False
                consecutive_empty_scans = 0
                return []
            
            for ad in ads[:50]:
                try:
                    ad_id = ad.get_attribute("href").split("/")[-1].split(".htm")[0]
                    
                    if ad_id in self.last_scraped_ids:
                        continue
                    
                    # Titre
                    try:
                        title_elem = ad.find_element(By.CSS_SELECTOR, "[data-qa-id='aditem_title']")
                        title = title_elem.text.strip() if title_elem.text else "Véhicule"
                    except:
                        title = "Véhicule d'occasion"
                    
                    # Prix
                    try:
                        price_elem = ad.find_element(By.CSS_SELECTOR, "[data-qa-id='aditem_price']")
                        price_text = price_elem.text.strip()
                        price = int(re.sub(r'[^\d]', '', price_text))
                    except:
                        price = 0
                    
                    # Localisation
                    try:
                        loc_elem = ad.find_element(By.CSS_SELECTOR, "[data-qa-id='aditem_location']")
                        location = loc_elem.text.strip() if loc_elem.text else "France"
                        # Nettoyer
                        if any(x in location.lower() for x in ['favori', 'specs', 'une', 'pack']):
                            location = "France"
                    except:
                        location = "France"
                    
                    # Coordonnées
                    coordinates = get_city_coordinates(location)
                    
                    # URL
                    url = ad.get_attribute("href")
                    
                    # Image
                    try:
                        img_elem = ad.find_element(By.TAG_NAME, "img")
                        image_url = img_elem.get_attribute("src")
                    except:
                        image_url = None
                    
                    vehicle = {
                        "id": ad_id,
                        "title": title,
                        "price": price,
                        "location": location,
                        "coordinates": coordinates,
                        "url": url,
                        "image_url": image_url,
                        "published_at": datetime.now(),
                        "scraped_at": datetime.now()
                    }
                    
                    vehicles.append(vehicle)
                    self.last_scraped_ids.add(ad_id)
                    
                except Exception as e:
                    continue
            
            logger.info(f"✅ {len(vehicles)} nouvelles annonces")
            return vehicles
            
        except Exception as e:
            logger.error(f"❌ Erreur scraping: {e}")
            return []

scraper = LeboncoinScraper()

# ============ MONITORING ============
async def monitoring_loop():
    logger.info(f"⏱️  Monitoring démarré (intervalle: {SCRAPE_INTERVAL_SECONDS}s)")
    scraper.running = True
    
    while scraper.running:
        try:
            new_vehicles = scraper.scrape_vehicles()
            
            for vehicle in new_vehicles:
                if not any(v["id"] == vehicle["id"] for v in database["vehicles"]):
                    database["vehicles"].insert(0, vehicle)
                    await notify_clients({
                        "type": "new_vehicle",
                        "data": vehicle
                    })
            
            if len(database["vehicles"]) > 1000:
                database["vehicles"] = database["vehicles"][:1000]
            
        except Exception as e:
            logger.error(f"❌ Erreur monitoring: {e}")
        
        await asyncio.sleep(SCRAPE_INTERVAL_SECONDS)

async def notify_clients(message: dict):
    disconnected = []
    for client in websocket_clients:
        try:
            await client.send_json(message)
        except:
            disconnected.append(client)
    for client in disconnected:
        websocket_clients.remove(client)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("✅ API démarrée")
    monitoring_task = asyncio.create_task(monitoring_loop())
    yield
    logger.info("🔴 Arrêt...")
    scraper.running = False
    scraper.close_driver()
    monitoring_task.cancel()

# ============ FASTAPI ============
app = FastAPI(
    title="AutoTrack API",
    description="API monitoring Leboncoin",
    version="3.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    websocket_clients.append(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        websocket_clients.remove(websocket)

@app.get("/")
async def root():
    return {
        "name": "AutoTrack API Railway",
        "version": "3.0",
        "status": "running",
        "selenium_available": SELENIUM_AVAILABLE,
        "vehicles_count": len(database["vehicles"]),
        "websocket_clients": len(websocket_clients)
    }

@app.get("/api/vehicles")
async def get_vehicles(
    limit: int = 50,
    page: int = 1,
    location: Optional[str] = None,
    location_radius_km: Optional[int] = None,
    min_price: Optional[int] = None,
    max_price: Optional[int] = None,
    sort: str = "recent"
):
    vehicles = database["vehicles"].copy()
    
    # Filtres
    if location:
        if location_radius_km and location_radius_km > 0:
            center_coords = get_city_coordinates(location)
            if center_coords:
                filtered = []
                for v in vehicles:
                    if v.get("coordinates"):
                        dist = calculate_distance(
                            center_coords[0], center_coords[1],
                            v["coordinates"][0], v["coordinates"][1]
                        )
                        if dist <= location_radius_km:
                            v_copy = v.copy()
                            v_copy["distance_km"] = dist
                            filtered.append(v_copy)
                vehicles = filtered
            else:
                vehicles = [v for v in vehicles if location.lower() in v.get("location", "").lower()]
        else:
            vehicles = [v for v in vehicles if location.lower() in v.get("location", "").lower()]
    
    if min_price:
        vehicles = [v for v in vehicles if v.get("price", 0) >= min_price]
    if max_price:
        vehicles = [v for v in vehicles if v.get("price", 0) <= max_price]
    
    # Tri
    if sort == "price_asc":
        vehicles.sort(key=lambda x: x.get("price", 0))
    elif sort == "price_desc":
        vehicles.sort(key=lambda x: x.get("price", 999999), reverse=True)
    elif sort == "distance" and location and location_radius_km:
        vehicles.sort(key=lambda x: x.get("distance_km", 999999))
    
    total = len(vehicles)
    start = (page - 1) * limit
    end = start + limit
    paginated = vehicles[start:end]
    
    return {
        "total": total,
        "page": page,
        "total_pages": (total + limit - 1) // limit if total > 0 else 0,
        "vehicles": paginated,
        "last_updated": vehicles[0]["published_at"].isoformat() if vehicles else None
    }

@app.get("/api/stats")
async def get_stats():
    return {
        "total_vehicles": len(database["vehicles"]),
        "scraper_running": scraper.running,
        "selenium_available": SELENIUM_AVAILABLE,
        "websocket_clients": len(websocket_clients)
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
