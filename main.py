"""
AutoTrack Backend - Version Corrigée COMPLÈTE pour Railway
CORRECTIONS APPLIQUÉES:
- Configuration Chrome anti-détection optimisée
- Attentes intelligentes pour le chargement des pages
- Multiples stratégies de détection des annonces
- Système de diagnostic intégré
- Extraction optimisée des données
- Géolocalisation des villes françaises
- Gestion améliorée des timeouts
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

# Import Selenium
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
    logger.info("✅ Selenium importé avec succès")
else:
    logger.error("❌ Selenium non disponible")

# ============ CONFIGURATION ============
SCRAPE_INTERVAL_SECONDS = 10  # 10 secondes pour laisser le temps au site de charger
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
consecutive_empty_scans = 0
MAX_EMPTY_SCANS_BEFORE_REFRESH = 10

# ============ GÉOLOCALISATION DES VILLES ============

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
    "versailles": (48.8014, 2.1301),
    "saint-jean-de-la-ruelle": (47.9111, 1.8697),
}

def calculate_distance(lat1, lon1, lat2, lon2):
    """Calcule la distance en kilomètres entre deux points GPS"""
    R = 6371
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
    city = city.lower().strip()
    city = re.sub(r'\s*\(\d+\)\s*', '', city)
    city = re.sub(r'[-\s]+', ' ', city)
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
    if normalized in FRENCH_CITIES_COORDS:
        return FRENCH_CITIES_COORDS[normalized]
    for city_key, coords in FRENCH_CITIES_COORDS.items():
        if normalized in city_key or city_key in normalized:
            return coords
    return None

# ============ CONFIGURATION CHROME OPTIMISÉE ============

def init_chrome_driver():
    """
    Initialise le driver Chrome avec configuration anti-détection pour Railway
    """
    if not SELENIUM_AVAILABLE:
        logger.error("❌ Selenium n'est pas disponible")
        return None
    
    try:
        logger.info("🚀 Initialisation du navigateur Chrome...")
        
        chrome_options = Options()
        
        # Options essentielles pour Railway
        chrome_options.add_argument('--headless=new')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--disable-software-rasterizer')
        
        # ANTI-DÉTECTION (CRUCIAL)
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        # User agent réaliste et récent
        user_agent = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'
        chrome_options.add_argument(f'user-agent={user_agent}')
        
        # Langue française
        chrome_options.add_argument('--lang=fr-FR')
        chrome_options.add_experimental_option('prefs', {
            'intl.accept_languages': 'fr-FR,fr',
            'profile.default_content_setting_values.notifications': 2,
        })
        
        # Taille de fenêtre
        chrome_options.add_argument('--window-size=1920,1080')
        
        # Performance et discrétion
        chrome_options.add_argument('--disable-extensions')
        chrome_options.add_argument('--disable-setuid-sandbox')
        chrome_options.add_argument('--disable-notifications')
        chrome_options.add_argument('--disable-popup-blocking')
        chrome_options.add_argument('--disable-features=VizDisplayCompositor')
        chrome_options.add_argument('--log-level=3')
        chrome_options.add_argument('--silent')
        
        # Chercher Chrome sur Railway
        chrome_binary_locations = [
            '/usr/bin/chromium-browser',
            '/usr/bin/chromium',
            '/usr/bin/google-chrome',
            '/usr/bin/google-chrome-stable',
        ]
        
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
        driver.set_page_load_timeout(60)
        
        # Masquer l'automatisation avec CDP
        try:
            driver.execute_cdp_cmd('Network.setUserAgentOverride', {
                "userAgent": user_agent
            })
            driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            driver.execute_script("Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]})")
            driver.execute_script("Object.defineProperty(navigator, 'languages', {get: () => ['fr-FR', 'fr']})")
        except Exception as e:
            logger.warning(f"⚠️ Impossible de masquer l'automatisation: {e}")
        
        logger.info("✅ Navigateur Chrome initialisé avec succès")
        return driver
        
    except Exception as e:
        logger.error(f"❌ Erreur init Chrome: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return None

# ============ SCRAPER AMÉLIORÉ ============

class ImprovedLeBonCoinScraper:
    """Scraper amélioré avec détection intelligente et diagnostic"""
    
    def __init__(self):
        self.base_url = "https://www.leboncoin.fr"
        self.driver = None
        self.seen_ads = set()
        self.running = False
        self.page_loaded = False
        self.cookies_accepted = False
    
    def setup_driver(self):
        """Configure le navigateur"""
        if self.driver:
            return True
        
        logger.info("🚀 Initialisation du navigateur...")
        
        try:
            self.driver = init_chrome_driver()
            if self.driver:
                logger.info("✅ Navigateur OK")
                return True
            else:
                logger.error("❌ Échec initialisation navigateur")
                return False
        except Exception as e:
            logger.error(f"❌ Erreur init Chrome: {str(e)}")
            return False
    
    def human_delay(self, min_sec=2, max_sec=4):
        """Délai aléatoire simulant un humain"""
        time.sleep(random.uniform(min_sec, max_sec))
    
    def scroll_like_human(self):
        """Scroll progressif pour charger le lazy loading"""
        try:
            for i in range(3):
                scroll_amount = random.randint(300, 700)
                self.driver.execute_script(f"window.scrollBy(0, {scroll_amount});")
                time.sleep(random.uniform(0.8, 1.5))
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
        """
        Récupère les annonces récentes avec extraction améliorée et attentes intelligentes
        """
        logger.info(f"🔍 Récupération de {max_ads} annonces...")
        
        try:
            # Chargement initial ou rafraîchissement
            if not self.page_loaded:
                logger.info("  📄 Chargement initial de la page...")
                self.driver.get(SCRAPE_URL)
                
                # Attendre que la page soit complètement chargée
                try:
                    WebDriverWait(self.driver, 30).until(
                        lambda d: d.execute_script("return document.readyState") == "complete"
                    )
                    logger.info("  ✅ Page chargée (readyState complete)")
                    
                    # Attendre spécifiquement les annonces
                    WebDriverWait(self.driver, 20).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, 'a[data-qa-id="aditem_container"], div[data-qa-id="aditem_container"], article'))
                    )
                    logger.info("  ✅ Annonces détectées dans le DOM")
                    
                except Exception as e:
                    logger.warning(f"  ⚠️ Timeout lors de l'attente: {e}")
                    # Sauvegarder une capture d'écran pour debug
                    try:
                        screenshot_path = "/tmp/debug_page.png"
                        self.driver.save_screenshot(screenshot_path)
                        logger.info(f"  📸 Screenshot sauvegardé: {screenshot_path}")
                    except:
                        pass
                
                # Gérer les cookies
                if not self.cookies_accepted:
                    try:
                        cookie_button = WebDriverWait(self.driver, 5).until(
                            EC.element_to_be_clickable((By.ID, "didomi-notice-agree-button"))
                        )
                        cookie_button.click()
                        self.cookies_accepted = True
                        time.sleep(1)
                        logger.info("  ✅ Cookies acceptés")
                    except:
                        self.cookies_accepted = True
                        logger.info("  ℹ️  Pas de popup cookies")
                
                self.page_loaded = True
            else:
                logger.info("  🔄 Rafraîchissement de la page...")
                self.driver.refresh()
                
                # Attendre que les annonces se rechargent
                try:
                    WebDriverWait(self.driver, 15).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, 'a[data-qa-id="aditem_container"], article'))
                    )
                    logger.info("  ✅ Page rafraîchie")
                except:
                    logger.warning("  ⚠️ Timeout rafraîchissement")
            
            # Scroll progressif pour charger le lazy loading
            logger.info("  📜 Scroll pour charger les images...")
            time.sleep(2)
            self.driver.execute_script("window.scrollTo(0, 800);")
            time.sleep(1)
            self.driver.execute_script("window.scrollTo(0, 1600);")
            time.sleep(1.5)
            self.driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(0.5)
            
            # LOG CRUCIAL : Voir un aperçu du HTML
            try:
                page_source = self.driver.page_source
                logger.info(f"  📄 Taille du HTML: {len(page_source)} caractères")
                
                # Sauvegarder le HTML complet pour debug
                html_path = "/tmp/debug_page.html"
                with open(html_path, "w", encoding="utf-8") as f:
                    f.write(page_source)
                logger.info(f"  📄 HTML complet sauvegardé: {html_path}")
                
                # Vérifier si LeBonCoin a bien chargé
                if "leboncoin" not in page_source.lower():
                    logger.error("  ❌ La page ne semble pas être LeBonCoin!")
                
            except Exception as e:
                logger.warning(f"  ⚠️ Impossible de sauvegarder le HTML: {e}")
            
            # Chercher les annonces avec TOUS les sélecteurs possibles
            ad_elements = []
            selectors = [
                'a[data-qa-id="aditem_container"]',
                'div[data-qa-id="aditem_container"]',
                '[data-test-id="ad"]',
                'article',
                'li[class*="styles_adCard"]',
                'div[class*="adCard"]',
                '[class*="AdCard"]',
                'a[href*="/voitures/"]',
            ]
            
            for selector in selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if len(elements) >= 5:
                        ad_elements = elements
                        logger.info(f"  ✅ {len(elements)} annonces trouvées avec: {selector}")
                        break
                    elif len(elements) > 0:
                        logger.info(f"  ⚠️ Seulement {len(elements)} éléments avec: {selector}")
                except Exception as e:
                    logger.warning(f"  ⚠️ Erreur avec sélecteur '{selector}': {e}")
                    continue
            
            if not ad_elements:
                logger.warning("  ⚠️ AUCUNE ANNONCE DÉTECTÉE avec les sélecteurs standards")
                
                # Dernière tentative : chercher TOUS les liens vers /voitures/
                try:
                    all_links = self.driver.find_elements(By.TAG_NAME, 'a')
                    vehicle_links = [link for link in all_links if '/voitures/' in link.get_attribute('href') or '']
                    if vehicle_links:
                        ad_elements = vehicle_links[:max_ads]
                        logger.info(f"  ✅ {len(ad_elements)} liens véhicules trouvés en fallback")
                    else:
                        logger.error("  ❌ Aucun lien véhicule trouvé")
                except Exception as e:
                    logger.error(f"  ❌ Erreur recherche fallback: {e}")
                
                if not ad_elements:
                    return []
            
            # Parser les annonces
            ads_found = []
            for idx, element in enumerate(ad_elements[:max_ads]):
                try:
                    ad_data = self._parse_ad(element, idx)
                    if ad_data:
                        ads_found.append(ad_data)
                        logger.info(f"  ✅ Annonce {idx+1}: {ad_data['title'][:50]}... - {ad_data['price']}€")
                except Exception as e:
                    logger.warning(f"  ⚠️ Erreur parsing annonce {idx}: {e}")
                    continue
            
            logger.info(f"  📊 Total parsé: {len(ads_found)} annonces valides")
            return ads_found
            
        except Exception as e:
            logger.error(f"  ❌ Erreur globale: {str(e)}")
            import traceback
            logger.error(f"  Traceback: {traceback.format_exc()}")
            self.page_loaded = False
            return []
    
    def _extract_title_improved(self, element, full_text):
        """Extraction du titre avec plusieurs stratégies"""
        title = None
        
        # Stratégie 1: Sélecteur standard
        try:
            title_elem = element.find_element(By.CSS_SELECTOR, '[data-qa-id="aditem_title"]')
            if title_elem and title_elem.text and len(title_elem.text) > 5:
                return title_elem.text.strip()
        except:
            pass
        
        # Stratégie 2: Autres sélecteurs
        title_selectors = [
            'p[data-qa-id="aditem_title"]',
            'h2', 'h3',
            '[class*="title"]',
            '[class*="Title"]',
        ]
        
        for selector in title_selectors:
            try:
                elem = element.find_element(By.CSS_SELECTOR, selector)
                if elem and elem.text and len(elem.text) > 5:
                    return elem.text.strip()
            except:
                continue
        
        # Stratégie 3: Extraction depuis le texte
        if full_text:
            lines = [line.strip() for line in full_text.split('\n') if line.strip()]
            for line in lines:
                if any(indicator in line for indicator in ['€', 'km', ':', 'Hier', 'Aujourd\'hui']):
                    continue
                if 10 < len(line) < 150 and re.search(r'[a-zA-Z]{3,}', line):
                    return line[:100]
        
        # Stratégie 4: Marque + modèle
        if full_text:
            brand = self._detect_brand(full_text)
            if brand:
                pattern = re.compile(re.escape(brand) + r"\s+([A-Z][a-zA-Z0-9\s-]+)", re.IGNORECASE)
                match = pattern.search(full_text)
                if match:
                    model_part = match.group(1).strip()
                    model_words = model_part.split()[:3]
                    return f"{brand} {' '.join(model_words)}"
        
        # Stratégie 5: URL
        try:
            url = element.get_attribute('href')
            if url:
                match = re.search(r'/([^/]+)\.htm', url)
                if match:
                    slug = match.group(1)
                    title = slug.replace('-', ' ').replace('_', ' ')
                    title = ' '.join(word.capitalize() for word in title.split())
                    if len(title) > 10:
                        return title[:100]
        except:
            pass
        
        return "Véhicule d'occasion"
    
    def _extract_location_improved(self, element, full_text):
        """Extraction de la ville avec multiples stratégies"""
        location = None
        
        # Stratégie 0: Chercher les paragraphes avec classe contenant "text"
        try:
            location_elems = element.find_elements(By.CSS_SELECTOR, 'p[class*="text"], span[class*="text"]')
            for elem in location_elems:
                text = elem.text.strip()
                if re.search(r'\b\d{5}\b', text):
                    if any(x in text.lower() for x in ['favori', 'favorite', 'retirée']):
                        continue
                    if 5 < len(text) < 80:
                        cleaned = self._clean_location(text)
                        if cleaned and len(cleaned) > 2:
                            return cleaned
        except:
            pass
        
        # Stratégie 1: Sélecteurs standards
        location_selectors = [
            '[data-qa-id="aditem_location"]',
            'p[data-qa-id="aditem_location"]',
            '[data-test-id="location"]',
            'div[class*="location"]',
            'span[class*="location"]',
            'p[class*="location"]',
        ]
        
        for selector in location_selectors:
            try:
                loc_elem = element.find_element(By.CSS_SELECTOR, selector)
                if loc_elem and loc_elem.text:
                    location_raw = loc_elem.text.strip()
                    if any(x in location_raw.lower() for x in ['favori', 'favorite', 'retirée']):
                        continue
                    if len(location_raw) > 2:
                        location = self._clean_location(location_raw)
                        if location and len(location) > 2:
                            return location
            except:
                continue
        
        # Stratégie 2: Patterns dans le texte
        if full_text:
            lines = [line.strip() for line in full_text.split('\n') if line.strip()]
            filtered_lines = [line for line in lines if not any(x in line.lower() for x in ['favori', 'favorite'])]
            
            for line in filtered_lines:
                # Pattern: Ville + code postal
                match = re.search(r'([A-ZÀ-Ü][a-zA-ZÀ-ÿ\s\-\']{2,})\s*\((\d{5})\)', line)
                if match:
                    city = match.group(1).strip()
                    postal = match.group(2)
                    if len(city) > 2:
                        return f"{city} ({postal})"
                
                # Pattern: Ville seule
                if re.match(r'^[A-ZÀ-Ü][a-zA-ZÀ-ÿ\s\-\']{2,40}$', line):
                    if not any(keyword in line.lower() for keyword in 
                              ['hier', 'aujourd', 'pro', 'urgent', 'occasion', 'diesel', 'essence']):
                        if re.search(r'[a-zA-Z]{2,}', line):
                            location = self._clean_location(line)
                            if location and len(location) > 2:
                                return location
        
        # Stratégie 3: Code postal seul
        if full_text:
            postal_match = re.search(r'\b(\d{5})\b', full_text)
            if postal_match:
                postal = postal_match.group(1)
                dept = postal[:2]
                dept_names = {
                    '75': 'Paris', '69': 'Lyon', '13': 'Marseille',
                    '31': 'Toulouse', '33': 'Bordeaux', '59': 'Lille',
                }
                if dept in dept_names:
                    return f"{dept_names[dept]} ({postal})"
                else:
                    return f"Département {dept}"
        
        return "France"
    
    def _clean_location(self, location_raw):
        """Nettoie une localisation extraite"""
        if not location_raw:
            return None
        
        raw_lower = location_raw.lower()
        if any(x in raw_lower for x in ['favori', 'favorite', 'retirée']):
            return None
        if '•' in location_raw:
            return None
        
        # Patterns à supprimer
        remove_patterns = [
            r'\d+[\s.]?\d*\s*km\b',
            r'Aujourd\'hui.*',
            r'Hier.*',
            r'\d{2}:\d{2}',
        ]
        
        location_clean = location_raw
        for pattern in remove_patterns:
            location_clean = re.sub(pattern, '', location_clean, flags=re.IGNORECASE)
        
        location_clean = ' '.join(location_clean.split()).strip()
        
        if location_clean and not location_clean.replace(' ', '').replace('-', '').isdigit():
            if len(location_clean) > 2:
                return location_clean
        
        return None
    
    def _parse_ad(self, element, idx):
        """Parse une annonce complète"""
        try:
            full_text = element.text
            if not full_text or len(full_text) < 10:
                return None
            
            # Titre
            title = self._extract_title_improved(element, full_text)
            
            # Prix
            price = 0
            price_text = ""
            try:
                price_selectors = [
                    '[data-qa-id="aditem_price"]',
                    'span[class*="price"]',
                    'p[class*="price"]',
                ]
                
                for selector in price_selectors:
                    try:
                        price_elem = element.find_element(By.CSS_SELECTOR, selector)
                        price_text = price_elem.text
                        if price_text and '€' in price_text:
                            break
                    except:
                        continue
                
                if not price_text or '€' not in price_text:
                    lines = full_text.split('\n')
                    for line in lines:
                        if '€' in line:
                            price_match = re.search(r'(\d[\d\s\.\u202f,]*)\s*€', line)
                            if price_match:
                                price_text = price_match.group(1)
                                break
            except:
                pass
            
            try:
                clean_price = re.sub(r'[^\d]', '', price_text.replace('\u202f', ''))
                if clean_price:
                    price = int(clean_price)
                    if price > 500000 or price < 100:
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
                import hashlib
                ad_id = hashlib.md5(f"{title}_{price}_{idx}".encode()).hexdigest()[:16]
            
            # Localisation
            location = self._extract_location_improved(element, full_text)
            
            # Images
            images = self.extract_images(element)
            
            # Détections
            brand = self._detect_brand(title + " " + full_text)
            model = self._detect_model(title + " " + full_text, brand)
            year = self._detect_year(title + " " + full_text)
            mileage = self._detect_mileage(full_text)
            fuel = self._detect_fuel(title + " " + full_text)
            gearbox = self._detect_gearbox(title + " " + full_text)
            is_pro = "pro" in full_text.lower()
            score = self._calculate_score(year, mileage, price, is_pro)
            
            # Coordonnées GPS
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
                "images": images,
                "url": url,
                "published_at": datetime.now(),
                "score": score
            }
            
        except Exception as e:
            logger.error(f"Erreur parsing annonce {idx}: {str(e)}")
            return None
    
    def _detect_brand(self, text):
        """Détecte la marque"""
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
        """Détecte le modèle"""
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
        """Détecte l'année"""
        matches = re.findall(r'\b(19[89]\d|20[0-2]\d)\b', text)
        if matches:
            return int(matches[-1])
        return None
    
    def _detect_mileage(self, text):
        """Détecte le kilométrage"""
        patterns = [r'(\d+[\s.]?\d*)\s*km(?![²³])']
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    km_str = match.group(1).replace(' ', '').replace('.', '')
                    km = int(km_str)
                    if 0 <= km <= 999999:
                        return km
                except:
                    continue
        return None
    
    def _detect_fuel(self, text):
        """Détecte le carburant"""
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
        """Détecte la boîte de vitesse"""
        text_lower = text.lower()
        if "automatique" in text_lower:
            return "automatique"
        if "manuelle" in text_lower:
            return "manuelle"
        return None
    
    def _calculate_score(self, year, mileage, price, is_pro):
        """Calcule un score de qualité"""
        score = 50.0
        
        if year:
            if year >= 2022:
                score += 20
            elif year >= 2020:
                score += 15
            elif year >= 2018:
                score += 10
        
        if mileage is not None:
            if mileage < 20000:
                score += 20
            elif mileage < 50000:
                score += 15
            elif mileage < 100000:
                score += 10
        
        if is_pro:
            score -= 5
        
        if 5000 <= price <= 30000:
            score += 5
        
        return round(min(max(score, 0), 100), 1)
    
    def get_diagnostic_info(self):
        """Retourne des infos de diagnostic"""
        if not self.driver:
            return {"error": "Driver non initialisé"}
        
        try:
            current_url = self.driver.current_url
            page_title = self.driver.title
            page_source_length = len(self.driver.page_source)
            
            elements_found = {}
            test_selectors = [
                'a[data-qa-id="aditem_container"]',
                'div[data-qa-id="aditem_container"]',
                'article',
                'a[href*="/voitures/"]',
                'img',
            ]
            
            for selector in test_selectors:
                try:
                    count = len(self.driver.find_elements(By.CSS_SELECTOR, selector))
                    elements_found[selector] = count
                except:
                    elements_found[selector] = "error"
            
            return {
                "current_url": current_url,
                "page_title": page_title,
                "page_source_length": page_source_length,
                "elements_found": elements_found,
                "cookies_accepted": self.cookies_accepted,
                "page_loaded": self.page_loaded,
                "seen_ads_count": len(self.seen_ads),
            }
        except Exception as e:
            return {"error": str(e)}
    
    def close(self):
        """Ferme le navigateur"""
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass
            self.driver = None
            self.page_loaded = False
            self.cookies_accepted = False

# Instance globale
scraper = ImprovedLeBonCoinScraper()

# ============ WEBSOCKET MANAGER ============

async def broadcast_new_vehicle(vehicle):
    """Broadcast nouvelle annonce via WebSocket"""
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
    logger.info("✅ API démarrée")
    task = asyncio.create_task(background_monitor())
    yield
    scraper.running = False
    scraper.close()
    logger.info("🛑 API arrêtée")

app = FastAPI(
    title="AutoTrack API - Version Complète Railway",
    version="3.0",
    description="API de monitoring LeBonCoin avec diagnostic intégré",
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
    """Monitoring en arrière-plan"""
    global consecutive_empty_scans
    
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
        
        if initial_ads:
            consecutive_empty_scans = 0
    except Exception as e:
        logger.error(f"❌ Erreur scan initial: {str(e)}")
    
    scan_count = 0
    total_new = 0
    
    logger.info(f"✅ Monitoring actif !\n")
    
    while scraper.running:
        scan_count += 1
        current_time = datetime.now().strftime("%H:%M:%S")
        
        logger.info(f"[{current_time}] 🔍 Scan #{scan_count}...")
        
        try:
            ads = scraper.get_recent_ads(max_ads=20)
            new_ads = [ad for ad in ads if ad['id'] not in scraper.seen_ads]
            
            if new_ads:
                logger.info(f"  🆕 {len(new_ads)} nouvelle(s) annonce(s) !")
                total_new += len(new_ads)
                consecutive_empty_scans = 0
                
                for ad in new_ads:
                    scraper.seen_ads.add(ad['id'])
                    database["vehicles"].insert(0, ad)
                    logger.info(f"    📌 {ad['title'][:60]}... - {ad['price']}€")
                    await broadcast_new_vehicle(ad)
                    
                    if len(database["vehicles"]) > 1000:
                        database["vehicles"] = database["vehicles"][:1000]
            else:
                consecutive_empty_scans += 1
                logger.info(f"  ✓ Aucune nouvelle annonce ({consecutive_empty_scans}/{MAX_EMPTY_SCANS_BEFORE_REFRESH})")
                
                if consecutive_empty_scans >= MAX_EMPTY_SCANS_BEFORE_REFRESH:
                    logger.warning(f"🔄 Réinitialisation du navigateur...")
                    scraper.close()
                    await asyncio.sleep(5)
                    if scraper.setup_driver():
                        logger.info("✅ Navigateur réinitialisé")
                        consecutive_empty_scans = 0
            
            if scan_count % 5 == 0:
                logger.info(f"\n📊 Stats: {total_new} nouvelles | {len(database['vehicles'])} total\n")
            
        except Exception as e:
            logger.error(f"❌ Erreur scan: {str(e)}")
        
        logger.info(f"  ⏳ Prochaine vérification dans {SCRAPE_INTERVAL_SECONDS}s...\n")
        await asyncio.sleep(SCRAPE_INTERVAL_SECONDS)

# ============ ROUTES API ============

@app.get("/")
async def root():
    """Informations API"""
    return {
        "name": "AutoTrack API - Version Complète",
        "version": "3.0",
        "status": "running",
        "selenium_available": SELENIUM_AVAILABLE,
        "vehicles_count": len(database["vehicles"]),
        "websocket_clients": len(websocket_clients),
        "features": [
            "Configuration Chrome optimisée",
            "Diagnostic intégré",
            "Recherche géolocalisée",
            "WebSocket temps réel"
        ]
    }

@app.get("/api/debug")
async def debug_scraper():
    """Endpoint de diagnostic"""
    return scraper.get_diagnostic_info()

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
    """Récupère les véhicules avec filtres"""
    vehicles = database["vehicles"].copy()
    
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
    
    if sort == "price_asc":
        vehicles.sort(key=lambda x: x.get("price", 0))
    elif sort == "price_desc":
        vehicles.sort(key=lambda x: x.get("price", 999999), reverse=True)
    elif sort == "score":
        vehicles.sort(key=lambda x: x.get("score", 0), reverse=True)
    elif sort == "distance" and location and location_radius_km:
        vehicles.sort(key=lambda x: x.get("distance_km", 999999))
    
    total = len(vehicles)
    start = (page - 1) * limit
    end = start + limit
    paginated = vehicles[start:end]
    
    total_pages = (total + limit - 1) // limit if total > 0 else 0
    
    return {
        "total": total,
        "page": page,
        "total_pages": total_pages,
        "vehicles": paginated,
        "last_updated": vehicles[0]["published_at"].isoformat() if vehicles else None,
        "is_partial": len(paginated) < limit and len(paginated) > 0,
        "has_more": end < total,
        "available_count": len(paginated),
    }

@app.get("/api/stats")
async def get_stats():
    """Statistiques"""
    vehicles = database["vehicles"]
    
    cities_count = {}
    for v in vehicles:
        loc = v.get("location", "Non spécifié")
        cities_count[loc] = cities_count.get(loc, 0) + 1
    
    top_cities = sorted(cities_count.items(), key=lambda x: x[1], reverse=True)[:10]
    
    return {
        "total_vehicles": len(vehicles),
        "scraper_running": scraper.running,
        "selenium_available": SELENIUM_AVAILABLE,
        "last_updated": vehicles[0]["published_at"].isoformat() if vehicles else None,
        "websocket_clients": len(websocket_clients),
        "top_cities": [{"city": city, "count": count} for city, count in top_cities],
    }

@app.get("/api/cities")
async def get_cities():
    """Liste des villes disponibles"""
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
