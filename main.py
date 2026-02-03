"""
AutoTrack Backend - FastAPI avec Monitoring Simple qui FONCTIONNE
Basé sur le système du main1.py qui marche réellement
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

# Import Selenium
try:
    import undetected_chromedriver as uc
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False

# ============ LOGGING ============
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger(__name__)

# ============ CONFIGURATION ============
SCRAPE_INTERVAL_SECONDS = 10  # 10 secondes - Monitoring ultra-rapide
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

# ============ SCRAPER SIMPLIFIÉ (COMME MAIN1.PY) ============

class SimpleLeBonCoinScraper:
    """Scraper simple et efficace basé sur main1.py"""
    
    def __init__(self):
        self.base_url = "https://www.leboncoin.fr"
        self.driver = None
        self.seen_ads = set()
        self.running = False
    
    def get_chrome_version(self):
        """Détecte la version de Chrome"""
        try:
            import winreg
            try:
                key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Google\Chrome\BLBeacon")
                version, _ = winreg.QueryValueEx(key, "version")
                major_version = version.split('.')[0]
                return int(major_version)
            except:
                pass
            
            try:
                key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"Software\Google\Chrome\BLBeacon")
                version, _ = winreg.QueryValueEx(key, "version")
                major_version = version.split('.')[0]
                return int(major_version)
            except:
                pass
        except:
            pass
        
        return None
    
    def setup_driver(self):
        """Configure le navigateur"""
        if self.driver:
            return True
        
        logger.info("🚀 Initialisation du navigateur...")
        
        try:
            chrome_version = self.get_chrome_version()
            
            options = uc.ChromeOptions()
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
            options.add_argument('--window-size=1920,1080')
            options.add_argument('--log-level=3')
            options.add_argument('--silent')
            
            if chrome_version:
                self.driver = uc.Chrome(
                    options=options,
                    version_main=chrome_version,
                    use_subprocess=True,
                    suppress_welcome=True
                )
            else:
                self.driver = uc.Chrome(
                    options=options,
                    use_subprocess=True,
                    suppress_welcome=True
                )
            
            try:
                self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            except:
                pass
            
            logger.info("✅ Navigateur OK")
            return True
            
        except Exception as e:
            logger.error(f"❌ Erreur init Chrome: {str(e)}")
            return False
    
    def human_delay(self, min_sec=2, max_sec=4):
        """Délai aléatoire"""
        time.sleep(random.uniform(min_sec, max_sec))
    
    def scroll_like_human(self):
        """Scroll progressif"""
        try:
            for _ in range(3):
                scroll_amount = random.randint(300, 700)
                self.driver.execute_script(f"window.scrollBy(0, {scroll_amount});")
                time.sleep(random.uniform(0.5, 1.2))
        except:
            pass
    
    def extract_images(self, element):
        """Extrait les URLs des images"""
        images = []
        try:
            img_elements = element.find_elements(By.TAG_NAME, 'img')
            for img in img_elements:
                img_url = img.get_attribute('src')
                if img_url and ('thumbs' in img_url or 'images' in img_url or 'img' in img_url):
                    if 'thumbs' in img_url:
                        img_url = img_url.replace('thumbs', 'images')
                    images.append(img_url)
            
            images = list(dict.fromkeys(images))
            valid_images = []
            for img in images:
                if (img.startswith('http') and 
                    not any(x in img.lower() for x in ['logo', 'icon', 'favicon', 'sprite', 'blank'])):
                    valid_images.append(img)
            
            return valid_images[:10]
        except:
            return []
    
    def get_recent_ads(self, max_ads=20):
        """Récupère les annonces récentes - MÉTHODE QUI MARCHE"""
        
        logger.info(f"🔍 Récupération de {max_ads} annonces...")
        
        try:
            # Charger la page
            self.driver.get(SCRAPE_URL)
            self.human_delay(3, 5)
            
            # Cookies
            try:
                cookie_button = WebDriverWait(self.driver, 5).until(
                    EC.element_to_be_clickable((By.ID, "didomi-notice-agree-button"))
                )
                time.sleep(random.uniform(1, 2))
                cookie_button.click()
                self.human_delay(2, 3)
            except:
                pass
            
            # Scroll
            self.scroll_like_human()
            self.human_delay(2, 3)
            
            # Chercher les annonces
            ad_elements = []
            selectors = [
                'a[data-qa-id="aditem_container"]',
                'div[data-qa-id="aditem_container"]',
                '[data-test-id="ad"]',
                'article'
            ]
            
            for selector in selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if len(elements) >= 5:
                        ad_elements = elements
                        logger.info(f"  ✅ {len(elements)} annonces trouvées")
                        break
                except:
                    continue
            
            if not ad_elements:
                logger.warning("  ⚠️ Aucune annonce détectée")
                return []
            
            # Parser les annonces
            ads_found = []
            for idx, element in enumerate(ad_elements[:max_ads]):
                ad_data = self._parse_ad(element, idx)
                if ad_data:
                    ads_found.append(ad_data)
            
            return ads_found
            
        except Exception as e:
            logger.error(f"  ❌ Erreur: {str(e)}")
            return []
    
    def _parse_ad(self, element, idx):
        """Parse une annonce"""
        try:
            full_text = element.text
            if not full_text or len(full_text) < 10:
                return None
            
            # TITRE
            title = "Sans titre"
            try:
                title_elem = element.find_element(By.CSS_SELECTOR, '[data-qa-id="aditem_title"]')
                title = title_elem.text if title_elem.text else title
            except:
                lines = full_text.split('\n')
                for line in lines:
                    if len(line) > 10 and '€' not in line:
                        title = line[:100]
                        break
            
            # PRIX - Amélioration de la détection
            price = 0
            price_text = ""
            try:
                # Essayer plusieurs sélecteurs pour le prix
                price_selectors = [
                    '[data-qa-id="aditem_price"]',
                    'span[class*="price"]',
                    'p[class*="price"]',
                    'div[class*="price"]',
                    '[data-test-id="price"]'
                ]
                
                for selector in price_selectors:
                    try:
                        price_elem = element.find_element(By.CSS_SELECTOR, selector)
                        price_text = price_elem.text
                        if price_text and '€' in price_text:
                            break
                    except:
                        continue
                
                # Si toujours pas de prix, chercher dans le texte complet
                if not price_text or '€' not in price_text:
                    # Chercher un prix dans le texte (éviter les prix mensuels)
                    lines = full_text.split('\n')
                    for line in lines:
                        if '€' in line and not any(word in line.lower() for word in ['mois', '/mois', 'semaine', 'jour']):
                            price_match = re.search(r'(\d[\d\s\.\u202f]*)\s*€', line)
                            if price_match:
                                price_text = price_match.group(1)
                                break
            except:
                pass
            
            # Convertir le prix en nombre
            try:
                clean_price = re.sub(r'[^\d]', '', price_text.replace('\u202f', ''))
                if clean_price:
                    price = int(clean_price)
                    if price > 500000 or price < 100:  # Prix aberrant
                        price = 0
                else:
                    price = 0
            except:
                price = 0
            
            # URL
            url = ""
            try:
                url = element.get_attribute('href')
                if not url:
                    link = element.find_element(By.TAG_NAME, 'a')
                    url = link.get_attribute('href')
            except:
                url = f"https://www.leboncoin.fr/voitures/{idx}"
            
            # ID
            ad_id = ""
            if url:
                match = re.search(r'/(\d+)\.htm', url)
                if match:
                    ad_id = f"lbc_{match.group(1)}"
            
            if not ad_id:
                if url and url.startswith('http'):
                    ad_id = url
                else:
                    import hashlib
                    ad_id = hashlib.md5(f"{title}_{price}".encode()).hexdigest()[:16]
            
            # LOCALISATION - Amélioration de la détection
            location = "Non spécifié"
            try:
                # Essayer plusieurs sélecteurs
                location_selectors = [
                    '[data-qa-id="aditem_location"]',
                    'p[data-qa-id="aditem_location"]',
                    '[data-test-id="location"]',
                    'div[class*="location"]',
                    'span[class*="location"]',
                    'p[class*="location"]'
                ]
                
                location_raw = ""
                for selector in location_selectors:
                    try:
                        loc_elem = element.find_element(By.CSS_SELECTOR, selector)
                        location_raw = loc_elem.text.strip()
                        if location_raw and len(location_raw) > 2:
                            break
                    except:
                        continue
                
                # Si toujours rien, chercher dans le texte
                if not location_raw:
                    lines = full_text.split('\n')
                    # Chercher une ligne qui ressemble à une ville (lettres, espaces, tirets)
                    for line in lines:
                        line = line.strip()
                        # Pattern pour détecter une ville (commence par majuscule, contient des lettres)
                        if re.match(r'^[A-ZÀ-Ü][a-zA-ZÀ-ÿ\s\-]{2,}(?:\s+\(\d+\))?$', line):
                            location_raw = line
                            break
                
                if location_raw:
                    # Nettoyer la localisation
                    remove_patterns = [
                        r'\d+[\s.]?\d*\s*km\b',
                        r'kilom[èe]trage\s*:\s*',
                        r'kilom[èe]trage',
                        r'Aujourd\'hui.*',
                        r'Hier.*',
                        r'\d{2}:\d{2}',
                    ]
                    
                    location_clean = location_raw
                    for pattern in remove_patterns:
                        location_clean = re.sub(pattern, '', location_clean, flags=re.IGNORECASE)
                    
                    location_clean = ' '.join(location_clean.split()).strip()
                    
                    if location_clean and len(location_clean) > 2:
                        if not location_clean.replace(' ', '').replace('-', '').replace('(', '').replace(')', '').isdigit():
                            location = location_clean
            except:
                pass
            
            # IMAGES
            images = self.extract_images(element)
            
            # DÉTECTIONS
            brand = self._detect_brand(title)
            model = self._detect_model(title, brand)
            year = self._detect_year(title)
            mileage = self._detect_mileage(full_text)
            fuel = self._detect_fuel(title + " " + full_text)
            gearbox = self._detect_gearbox(title + " " + full_text)
            is_pro = "pro" in full_text.lower() or "professionnel" in full_text.lower()
            score = self._calculate_score(year, mileage, price, is_pro)
            
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
                "is_pro": is_pro,
                "images": images,
                "url": url,
                "published_at": datetime.now(),
                "score": score
            }
            
        except Exception as e:
            return None
    
    def _detect_brand(self, text):
        brands = ["Renault", "Peugeot", "Citroën", "Toyota", "Volkswagen", "Honda", "Ford",
                  "BMW", "Mercedes", "Audi", "Fiat", "Kia", "Hyundai", "Nissan", "Opel",
                  "Mazda", "Volvo", "Tesla", "Jeep", "Dacia", "Skoda", "SEAT", "Suzuki"]
        text_lower = text.lower()
        for brand in brands:
            if brand.lower() in text_lower:
                return brand
        return None
    
    def _detect_model(self, text, brand):
        if not brand:
            return None
        try:
            pattern = re.compile(re.escape(brand) + r"\s+(.+?)(?:\s*[-–—]|\s+\d{4}|\s+\(|$)", re.IGNORECASE)
            m = pattern.search(text)
            if m:
                return " ".join(m.group(1).strip().split()[:2])
        except:
            pass
        return None
    
    def _detect_year(self, text):
        matches = re.findall(r'\b(19[89]\d|20[0-2]\d)\b', text)
        return int(matches[-1]) if matches else None
    
    def _detect_mileage(self, text):
        patterns = [r'(\d+[\s.]?\d*)\s*km(?![²³])', r'(\d+[\s.]?\d*)\s*kilom[èe]tres?']
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    km = int(match.group(1).replace(' ', '').replace('.', ''))
                    if 0 <= km <= 999999:
                        return km
                except:
                    continue
        return None
    
    def _detect_fuel(self, text):
        text_lower = text.lower()
        if "électrique" in text_lower or "electrique" in text_lower:
            return "electrique"
        if "hybride" in text_lower:
            return "hybride"
        if "diesel" in text_lower:
            return "diesel"
        if "essence" in text_lower:
            return "essence"
        return None
    
    def _detect_gearbox(self, text):
        text_lower = text.lower()
        if "automatique" in text_lower or "auto" in text_lower:
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
            if mileage < 20000:
                score += 20
            elif mileage < 50000:
                score += 15
        if is_pro:
            score -= 5
        return round(min(max(score, 0), 100), 1)
    
    def close(self):
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass
            self.driver = None

# Instance globale
scraper = SimpleLeBonCoinScraper()

# ============ WEBSOCKET MANAGER ============

async def broadcast_new_vehicle(vehicle):
    """Broadcast nouvelle annonce"""
    if not websocket_clients:
        return
    
    message = json.dumps({
        "type": "new_vehicle",
        "vehicle": {
            **vehicle,
            "published_at": vehicle["published_at"].isoformat()
        }
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
    logger.info("✅ API démarrée")
    task = asyncio.create_task(background_monitor())
    yield
    scraper.running = False
    scraper.close()
    logger.info("🛑 API arrêtée")

app = FastAPI(title="AutoTrack API", version="2.1", lifespan=lifespan)

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
    await websocket.accept()
    websocket_clients.append(websocket)
    logger.info(f"🔌 Client connecté ({len(websocket_clients)} total)")
    
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        websocket_clients.remove(websocket)
        logger.info(f"🔌 Client déconnecté ({len(websocket_clients)} restants)")

# ============ MONITORING SIMPLE (COMME MAIN1.PY) ============

async def background_monitor():
    """Monitoring simple et efficace"""
    scraper.running = True
    logger.info(f"⏱️  Monitoring démarré (intervalle: {SCRAPE_INTERVAL_SECONDS}s)")
    
    if not scraper.setup_driver():
        logger.error("Impossible de démarrer le driver")
        return
    
    # Scan initial
    logger.info("🔍 Scan initial...")
    try:
        initial_ads = scraper.get_recent_ads(max_ads=20)
        for ad in initial_ads:
            scraper.seen_ads.add(ad['id'])
            database["vehicles"].insert(0, ad)
        logger.info(f"  ℹ️  {len(initial_ads)} annonces chargées\n")
    except Exception as e:
        logger.error(f"❌ Erreur: {str(e)}")
    
    scan_count = 0
    total_new = 0
    
    logger.info(f"✅ Monitoring actif ! (toutes les {SCRAPE_INTERVAL_SECONDS}s)\n")
    
    while scraper.running:
        scan_count += 1
        current_time = datetime.now().strftime("%H:%M:%S")
        
        logger.info(f"[{current_time}] 🔍 Scan #{scan_count}...")
        
        try:
            ads = scraper.get_recent_ads(max_ads=20)
            new_ads = [ad for ad in ads if ad['id'] not in scraper.seen_ads]
            
            if new_ads:
                logger.info(f"  🆕 {len(new_ads)} nouvelle(s) !")
                total_new += len(new_ads)
                
                for ad in new_ads:
                    scraper.seen_ads.add(ad['id'])
                    database["vehicles"].insert(0, ad)
                    
                    logger.info(f"    📌 {ad['title'][:50]} - {ad['price']}€")
                    
                    # Broadcast WebSocket
                    await broadcast_new_vehicle(ad)
                    
                    # Limiter à 1000
                    if len(database["vehicles"]) > 1000:
                        database["vehicles"] = database["vehicles"][:1000]
            else:
                logger.info(f"  ✓ Aucune nouvelle")
            
            if scan_count % 10 == 0:
                logger.info(f"\n📊 Stats: {total_new} nouvelles | {len(database['vehicles'])} total | {len(scraper.seen_ads)} mémorisées\n")
            
        except Exception as e:
            logger.error(f"❌ Erreur: {str(e)}")
        
        logger.info(f"  ⏳ Prochaine vérif dans {SCRAPE_INTERVAL_SECONDS}s...\n")
        await asyncio.sleep(SCRAPE_INTERVAL_SECONDS)

# ============ ROUTES API ============

@app.get("/")
async def root():
    return {
        "name": "AutoTrack API",
        "version": "2.1",
        "status": "running",
        "vehicles_count": len(database["vehicles"]),
        "websocket_clients": len(websocket_clients)
    }

@app.get("/api/vehicles")
async def get_vehicles(
    limit: int = 50,
    page: int = 1,
    brand: Optional[str] = None,
    model: Optional[str] = None,
    location: Optional[str] = None,
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
    vehicles = database["vehicles"].copy()
    
    # Appliquer tous les filtres
    if brand:
        vehicles = [v for v in vehicles if v.get("brand") and v.get("brand").lower() == brand.lower()]
    if model:
        vehicles = [v for v in vehicles if v.get("model") and model.lower() in v.get("model", "").lower()]
    if location:
        vehicles = [v for v in vehicles if v.get("location") and location.lower() in v.get("location", "").lower()]
    if min_price:
        vehicles = [v for v in vehicles if v.get("price", 0) >= min_price]
    if max_price:
        vehicles = [v for v in vehicles if v.get("price", 0) <= max_price]
    if min_year:
        vehicles = [v for v in vehicles if v.get("year") and v.get("year") >= min_year]
    if max_year:
        vehicles = [v for v in vehicles if v.get("year") and v.get("year") <= max_year]
    if max_mileage:
        vehicles = [v for v in vehicles if v.get("mileage") is not None and v.get("mileage") <= max_mileage]
    if fuel:
        vehicles = [v for v in vehicles if v.get("fuel") and v.get("fuel").lower() == fuel.lower()]
    if gearbox:
        vehicles = [v for v in vehicles if v.get("gearbox") and v.get("gearbox").lower() == gearbox.lower()]
    if min_score:
        vehicles = [v for v in vehicles if v.get("score", 0) >= min_score]
    
    # Tri
    if sort == "price_asc":
        vehicles.sort(key=lambda x: x.get("price", 0))
    elif sort == "price_desc":
        vehicles.sort(key=lambda x: x.get("price", 999999), reverse=True)
    elif sort == "score":
        vehicles.sort(key=lambda x: x.get("score", 0), reverse=True)
    
    total = len(vehicles)
    start = (page - 1) * limit
    end = start + limit
    paginated = vehicles[start:end]
    
    return {
        "total": total,
        "page": page,
        "total_pages": (total + limit - 1) // limit,
        "vehicles": paginated,
        "last_updated": vehicles[0]["published_at"].isoformat() if vehicles else None
    }

@app.get("/api/stats")
async def get_stats():
    vehicles = database["vehicles"]
    return {
        "total_vehicles": len(vehicles),
        "scraper_running": scraper.running,
        "last_updated": vehicles[0]["published_at"].isoformat() if vehicles else None,
        "websocket_clients": len(websocket_clients)
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)