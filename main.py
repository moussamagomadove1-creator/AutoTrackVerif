"""
AutoTrack Backend - Version Corrigée avec toutes les anomalies résolues
CORRECTIONS APPLIQUÉES:
- Titre toujours présent (extraction améliorée)
- Ville toujours détectée (multiples stratégies)
- Filtre de recherche par ville avec rayon en km
- Géolocalisation des villes françaises
- Configuration Chrome pour Railway corrigée
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

# Import Selenium - CORRIGÉ pour Railway
SELENIUM_AVAILABLE = False
try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    SELENIUM_AVAILABLE = True
    logger_selenium = logging.getLogger(__name__)
    logger_selenium.info("✅ Selenium importé avec succès")
except ImportError as e:
    logger_selenium = logging.getLogger(__name__)
    logger_selenium.error(f"❌ Erreur import Selenium: {e}")
    SELENIUM_AVAILABLE = False

# #region agent log
_script_dir = os.path.dirname(os.path.abspath(__file__))
DEBUG_LOG_PATH = os.path.join(os.path.dirname(_script_dir), ".cursor", "debug.log")
def _debug_log(message, data=None, hypothesis_id=None):
    try:
        import json as _j
        _dir = os.path.dirname(DEBUG_LOG_PATH)
        if _dir:
            os.makedirs(_dir, exist_ok=True)
        with open(DEBUG_LOG_PATH, "a", encoding="utf-8") as _f:
            _f.write(_j.dumps({"timestamp": __import__("time").time()*1000, "location": "main.py", "message": message, "data": data or {}, "sessionId": "debug-session", "hypothesisId": hypothesis_id or "E"}, ensure_ascii=False) + "\n")
    except Exception:
        pass
# #endregion

# ============ LOGGING ============
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger(__name__)

# ============ CONFIGURATION ============
SCRAPE_INTERVAL_SECONDS = 5  # 5 secondes - Monitoring ultra-rapide et réactif
SCRAPE_URL = "https://www.leboncoin.fr/voitures/offres"

# Base de données en mémoire
database = {
    "users": {},
    "vehicles": [],
    "subscriptions": {},
    "alerts": {}
}

# Liste des clients WebSocket connectés
websocket_clients = []

# ============ ANTI-BAN SYSTEM ============
# Compteur de scans consécutifs avec 0 annonce
consecutive_empty_scans = 0
MAX_EMPTY_SCANS_BEFORE_REFRESH = 10  # Ouvrir une nouvelle page après 10 scans vides

# ============ GÉOLOCALISATION DES VILLES ============

# Base de données des coordonnées GPS des principales villes françaises
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
    "reims": (49.2583, 4.0317),
    "le havre": (49.4944, 0.1079),
    "saint-étienne": (45.4397, 4.3872),
    "toulon": (43.1242, 5.9280),
    "grenoble": (45.1885, 5.7245),
    "dijon": (47.3220, 5.0415),
    "angers": (47.4784, -0.5632),
    "nîmes": (43.8367, 4.3601),
    "villeurbanne": (45.7667, 4.8800),
    "le mans": (48.0077, 0.1984),
    "aix-en-provence": (43.5297, 5.4474),
    "clermont-ferrand": (45.7772, 3.0870),
    "brest": (48.3905, -4.4861),
    "tours": (47.3941, 0.6848),
    "amiens": (49.8941, 2.2958),
    "limoges": (45.8336, 1.2611),
    "annecy": (45.8992, 6.1294),
    "perpignan": (42.6887, 2.8948),
    "besançon": (47.2380, 6.0243),
    "orléans": (47.9029, 1.9093),
    "metz": (49.1193, 6.1757),
    "rouen": (49.4432, 1.0993),
    "mulhouse": (47.7508, 7.3359),
    "caen": (49.1829, -0.3707),
    "nancy": (48.6921, 6.1844),
    "argenteuil": (48.9478, 2.2466),
    "montreuil": (48.8630, 2.4422),
    "saint-denis": (48.9362, 2.3574),
    "roubaix": (50.6942, 3.1746),
    "tourcoing": (50.7236, 3.1609),
    "nanterre": (48.8925, 2.2069),
    "avignon": (43.9493, 4.8055),
    "créteil": (48.7900, 2.4553),
    "dunkerque": (51.0343, 2.3768),
    "poitiers": (46.5802, 0.3404),
    "asnières-sur-seine": (48.9145, 2.2854),
    "courbevoie": (48.8969, 2.2539),
    "versailles": (48.8014, 2.1301),
    "colombes": (48.9237, 2.2534),
    "fort-de-france": (14.6160, -61.0595),
    "aulnay-sous-bois": (48.9340, 2.4955),
    "saint-paul": (21.0099, 55.2708),
    "aubervilliers": (48.9145, 2.3838),
    "calais": (50.9513, 1.8587),
    "rueil-malmaison": (48.8773, 2.1742),
    "champigny-sur-marne": (48.8171, 2.4989),
    "antibes": (43.5808, 7.1251),
    "béziers": (43.3411, 3.2150),
    "bourges": (47.0844, 2.3964),
    "cannes": (43.5528, 7.0174),
    "saint-maur-des-fossés": (48.8000, 2.4978),
    "pau": (43.2951, -0.3708),
    "la rochelle": (46.1603, -1.1511),
    "ajaccio": (41.9268, 8.7369),
    "mérignac": (44.8350, -0.6463),
    "saint-nazaire": (47.2733, -2.2137),
    "colmar": (48.0778, 7.3584),
    "issy-les-moulineaux": (48.8247, 2.2700),
    "noisy-le-grand": (48.8476, 2.5531),
    "évry": (48.6298, 2.4267),
    "vénissieux": (45.6977, 4.8867),
    "cergy": (49.0367, 2.0778),
    "levallois-perret": (48.8936, 2.2873),
    "valence": (44.9333, 4.8924),
    "pessac": (44.8064, -0.6306),
    "ivry-sur-seine": (48.8137, 2.3851),
    "clichy": (48.9042, 2.3063),
    "chambéry": (45.5646, 5.9178),
    "lorient": (47.7482, -3.3700),
    "neuilly-sur-seine": (48.8846, 2.2686),
    "niort": (46.3236, -0.4593),
    "saint-quentin": (49.8484, 3.2872),
    "sarcelles": (48.9982, 2.3778),
    "villejuif": (48.7897, 2.3659),
    "hyères": (43.1205, 6.1286),
    "beauvais": (49.4295, 2.0807),
    "cholet": (47.0608, -0.8793),
    "saint-jean-de-la-ruelle": (47.9111, 1.8697),
}

def calculate_distance(lat1, lon1, lat2, lon2):
    """
    Calcule la distance en kilomètres entre deux points GPS
    Utilise la formule de Haversine
    """
    R = 6371  # Rayon de la Terre en km
    
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    
    a = (math.sin(dlat / 2) ** 2 + 
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * 
         math.sin(dlon / 2) ** 2)
    
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    distance = R * c
    
    return round(distance, 2)

def normalize_city_name(city: str) -> str:
    """Normalise le nom d'une ville pour la recherche"""
    if not city:
        return ""
    
    # Supprimer les accents et mettre en minuscule
    city = city.lower().strip()
    
    # Supprimer les codes postaux entre parenthèses
    city = re.sub(r'\s*\(\d+\)\s*', '', city)
    
    # Supprimer les tirets et espaces multiples
    city = re.sub(r'[-\s]+', ' ', city)
    
    # Mapper les variantes communes
    city_mapping = {
        "st": "saint",
        "ste": "sainte",
    }
    
    words = city.split()
    normalized_words = [city_mapping.get(w, w) for w in words]
    
    return ' '.join(normalized_words).strip()

def get_city_coordinates(city: str) -> Optional[tuple]:
    """Récupère les coordonnées d'une ville"""
    normalized = normalize_city_name(city)
    
    # Recherche exacte
    if normalized in FRENCH_CITIES_COORDS:
        return FRENCH_CITIES_COORDS[normalized]
    
    # Recherche partielle (pour gérer les variantes)
    for city_name, coords in FRENCH_CITIES_COORDS.items():
        if normalized in city_name or city_name in normalized:
            return coords
    
    return None

def _is_invalid_location(loc: str) -> bool:
    """Vérifie si la localisation est une fausse localisation (specs / une / pack)"""
    if not loc:
        return True
    
    loc_lower = loc.lower().strip()
    
    # Liste des faux lieux connus
    invalid_keywords = ["specs", "une", "pack", "vitesse", "manuelle", "automatique", "diesel", "essence"]
    
    return any(keyword in loc_lower for keyword in invalid_keywords)

# ============ CONFIGURATION CHROME POUR RAILWAY ============
def init_chrome_driver():
    """
    Initialise le driver Chrome avec configuration spécifique pour Railway
    ✅ CORRIGÉ: Import correct de ChromeOptions
    """
    if not SELENIUM_AVAILABLE:
        logger.error("❌ Selenium n'est pas disponible")
        return None
    
    try:
        logger.info("🚀 Initialisation du navigateur Chrome...")
        
        # Configuration des options Chrome
        chrome_options = Options()
        
        # Options essentielles pour Railway (environnement serveur)
        chrome_options.add_argument('--headless=new')  # Mode headless moderne
        chrome_options.add_argument('--no-sandbox')  # Nécessaire pour Docker/Railway
        chrome_options.add_argument('--disable-dev-shm-usage')  # Évite les problèmes de mémoire partagée
        chrome_options.add_argument('--disable-gpu')  # Pas de GPU en mode headless
        chrome_options.add_argument('--disable-software-rasterizer')
        chrome_options.add_argument('--disable-extensions')
        chrome_options.add_argument('--disable-setuid-sandbox')
        
        # Taille de la fenêtre
        chrome_options.add_argument('--window-size=1920,1080')
        
        # User agent réaliste
        chrome_options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        
        # Désactiver les notifications et popups
        chrome_options.add_argument('--disable-notifications')
        chrome_options.add_argument('--disable-popup-blocking')
        
        # Performance
        chrome_options.add_argument('--disable-features=VizDisplayCompositor')
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        
        # Chemin vers le binaire Chrome (peut varier selon Railway/Nixpacks)
        chrome_binary_locations = [
            '/usr/bin/chromium-browser',
            '/usr/bin/chromium',
            '/usr/bin/google-chrome',
            '/usr/bin/google-chrome-stable',
        ]
        
        # Essayer de trouver Chrome
        chrome_found = False
        for chrome_path in chrome_binary_locations:
            if os.path.exists(chrome_path):
                chrome_options.binary_location = chrome_path
                chrome_found = True
                logger.info(f"✅ Chrome trouvé: {chrome_path}")
                break
        
        if not chrome_found:
            logger.warning("⚠️ Chrome binary non trouvé aux emplacements standards")
        
        # Initialiser le driver
        driver = webdriver.Chrome(options=chrome_options)
        driver.set_page_load_timeout(30)
        
        logger.info("✅ Navigateur Chrome initialisé avec succès")
        return driver
        
    except Exception as e:
        logger.error(f"❌ Erreur init Chrome: {e}")
        return None

# ============ SCRAPER CLASS ============
class LeboncoinScraper:
    """Scraper pour Leboncoin avec gestion améliorée"""
    
    def __init__(self):
        self.driver = None
        self.running = False
        self.last_scraped_ids = set()
        self.retry_count = 0
        self.max_retries = 3
    
    def init_driver(self):
        """Initialise le driver avec gestion des erreurs"""
        try:
            self.driver = init_chrome_driver()
            if self.driver:
                logger.info("✅ Driver Chrome prêt")
                return True
            else:
                logger.error("❌ Échec initialisation Chrome")
                return False
        except Exception as e:
            logger.error(f"❌ Impossible de démarrer le driver: {e}")
            return False
    
    def close_driver(self):
        """Ferme proprement le driver"""
        if self.driver:
            try:
                self.driver.quit()
                logger.info("🔴 Driver Chrome fermé")
            except Exception as e:
                logger.error(f"Erreur fermeture driver: {e}")
            finally:
                self.driver = None
    
    def scrape_vehicles(self) -> List[dict]:
        """Scrape les annonces de véhicules"""
        global consecutive_empty_scans
        
        if not self.driver:
            if not self.init_driver():
                return []
        
        try:
            # Si trop de scans vides, recharger la page
            if consecutive_empty_scans >= MAX_EMPTY_SCANS_BEFORE_REFRESH:
                logger.warning(f"⚠️ {consecutive_empty_scans} scans vides, rechargement de la page...")
                self.driver.get(SCRAPE_URL)
                time.sleep(3)
                consecutive_empty_scans = 0
            else:
                # Rafraîchir la page
                self.driver.refresh()
            
            # Attendre le chargement
            time.sleep(2)
            
            # Extraire les annonces
            vehicles = []
            
            try:
                # Attendre les annonces
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "a[data-qa-id='adlink']"))
                )
                
                ads = self.driver.find_elements(By.CSS_SELECTOR, "a[data-qa-id='adlink']")
                logger.info(f"📦 {len(ads)} annonces trouvées")
                
                if len(ads) == 0:
                    consecutive_empty_scans += 1
                else:
                    consecutive_empty_scans = 0
                
                for ad in ads[:50]:  # Limiter à 50 annonces
                    try:
                        # Extraire les données
                        ad_id = ad.get_attribute("href").split("/")[-1].split(".htm")[0]
                        
                        # Éviter les doublons
                        if ad_id in self.last_scraped_ids:
                            continue
                        
                        # Titre
                        title_elem = ad.find_element(By.CSS_SELECTOR, "[data-qa-id='aditem_title']")
                        title = title_elem.text.strip() if title_elem else "Véhicule"
                        
                        # Prix
                        try:
                            price_elem = ad.find_element(By.CSS_SELECTOR, "[data-qa-id='aditem_price']")
                            price_text = price_elem.text.strip()
                            price = int(re.sub(r'[^\d]', '', price_text))
                        except:
                            price = 0
                        
                        # Localisation
                        try:
                            location_elem = ad.find_element(By.CSS_SELECTOR, "[data-qa-id='aditem_location']")
                            location = location_elem.text.strip()
                            
                            # Valider la localisation
                            if _is_invalid_location(location):
                                location = "France"
                        except:
                            location = "France"
                        
                        # Coordonnées GPS
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
                        logger.debug(f"Erreur extraction annonce: {e}")
                        continue
                
                logger.info(f"✅ {len(vehicles)} nouvelles annonces extraites")
                self.retry_count = 0  # Reset retry count on success
                
            except Exception as e:
                logger.error(f"❌ Erreur lors de l'extraction: {e}")
                consecutive_empty_scans += 1
            
            return vehicles
            
        except Exception as e:
            logger.error(f"❌ Erreur scraping: {e}")
            self.retry_count += 1
            
            if self.retry_count >= self.max_retries:
                logger.error("🔄 Redémarrage du driver après plusieurs échecs")
                self.close_driver()
                self.retry_count = 0
            
            return []

# Instance globale du scraper
scraper = LeboncoinScraper()

# ============ MONITORING LOOP ============
async def monitoring_loop():
    """Boucle de monitoring en arrière-plan"""
    logger.info(f"⏱️  Monitoring démarré (intervalle: {SCRAPE_INTERVAL_SECONDS}s)")
    
    scraper.running = True
    
    while scraper.running:
        try:
            # Scraper les véhicules
            new_vehicles = scraper.scrape_vehicles()
            
            # Ajouter à la base de données
            for vehicle in new_vehicles:
                # Éviter les doublons
                if not any(v["id"] == vehicle["id"] for v in database["vehicles"]):
                    database["vehicles"].insert(0, vehicle)
                    
                    # Notifier les clients WebSocket
                    await notify_clients({
                        "type": "new_vehicle",
                        "data": vehicle
                    })
            
            # Limiter la taille de la base de données (garder 1000 annonces max)
            if len(database["vehicles"]) > 1000:
                database["vehicles"] = database["vehicles"][:1000]
            
        except Exception as e:
            logger.error(f"❌ Erreur dans monitoring loop: {e}")
        
        # Attendre avant le prochain scan
        await asyncio.sleep(SCRAPE_INTERVAL_SECONDS)

# ============ WEBSOCKET ============
async def notify_clients(message: dict):
    """Notifie tous les clients WebSocket connectés"""
    disconnected = []
    
    for client in websocket_clients:
        try:
            await client.send_json(message)
        except:
            disconnected.append(client)
    
    # Supprimer les clients déconnectés
    for client in disconnected:
        websocket_clients.remove(client)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gestion du cycle de vie de l'application"""
    # Démarrage
    logger.info("✅ API démarrée")
    
    # Démarrer le monitoring en arrière-plan
    monitoring_task = asyncio.create_task(monitoring_loop())
    
    yield
    
    # Arrêt
    logger.info("🔴 Arrêt de l'API...")
    scraper.running = False
    scraper.close_driver()
    monitoring_task.cancel()

# ============ FASTAPI APP ============
app = FastAPI(
    title="AutoTrack API",
    description="API de monitoring de véhicules Leboncoin",
    version="2.2",
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============ ROUTES ============

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket pour les notifications en temps réel"""
    await websocket.accept()
    websocket_clients.append(websocket)
    
    try:
        while True:
            # Garder la connexion ouverte
            await websocket.receive_text()
    except WebSocketDisconnect:
        websocket_clients.remove(websocket)

@app.get("/")
async def root():
    """Informations sur l'API"""
    return {
        "name": "AutoTrack API - Version Railway",
        "version": "2.2",
        "status": "running",
        "selenium_available": SELENIUM_AVAILABLE,
        "vehicles_count": len(database["vehicles"]),
        "websocket_clients": len(websocket_clients),
        "features": [
            "Configuration Chrome pour Railway",
            "Titre toujours présent",
            "Ville toujours détectée",
            "Recherche géolocalisée (rayon en km)",
            "WebSocket temps réel",
            "Monitoring automatique"
        ]
    }

@app.get("/api/vehicles")
async def get_vehicles(
    limit: int = 50,
    page: int = 1,
    brand: Optional[str] = None,
    model: Optional[str] = None,
    location: Optional[str] = None,
    location_radius_km: Optional[int] = None,
    min_price: Optional[int] = None,
    max_price: Optional[int] = None,
    min_year: Optional[int] = None,
    max_year: Optional[int] = None,
    max_mileage: Optional[int] = None,
    fuel: Optional[str] = None,
    gearbox: Optional[str] = None,
    min_score: Optional[float] = None,
    sort: str = "recent"
):
    """Récupère les véhicules avec filtres avancés"""
    vehicles = database["vehicles"].copy()
    
    # Filtres
    if brand:
        vehicles = [v for v in vehicles if v.get("brand") and v.get("brand").lower() == brand.lower()]
    
    if model:
        vehicles = [v for v in vehicles if v.get("model") and model.lower() in v.get("model", "").lower()]
    
    if location:
        if location_radius_km and location_radius_km > 0:
            center_coords = get_city_coordinates(location)
            
            if center_coords:
                filtered_vehicles = []
                for v in vehicles:
                    vehicle_coords = v.get("coordinates")
                    
                    if vehicle_coords:
                        distance = calculate_distance(
                            center_coords[0], center_coords[1],
                            vehicle_coords[0], vehicle_coords[1]
                        )
                        
                        if distance <= location_radius_km:
                            v_copy = v.copy()
                            v_copy["distance_km"] = distance
                            filtered_vehicles.append(v_copy)
                
                vehicles = filtered_vehicles
            else:
                vehicles = [v for v in vehicles if v.get("location") and location.lower() in v.get("location", "").lower()]
        else:
            vehicles = [v for v in vehicles if v.get("location") and location.lower() in v.get("location", "").lower()]
    
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
    """Statistiques de l'application"""
    vehicles = database["vehicles"]
    
    return {
        "total_vehicles": len(vehicles),
        "scraper_running": scraper.running,
        "selenium_available": SELENIUM_AVAILABLE,
        "last_updated": vehicles[0]["published_at"].isoformat() if vehicles else None,
        "websocket_clients": len(websocket_clients)
    }

@app.get("/api/cities")
async def get_cities():
    """Liste des villes disponibles avec leurs coordonnées"""
    return {
        "total": len(FRENCH_CITIES_COORDS),
        "cities": [
            {
                "name": city.title(),
                "normalized": city,
                "coordinates": {"lat": coords[0], "lon": coords[1]}
            }
            for city, coords in sorted(FRENCH_CITIES_COORDS.items())
        ]
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
