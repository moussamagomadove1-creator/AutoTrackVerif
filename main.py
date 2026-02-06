"""
AutoTrack Backend - Version Corrigée avec toutes les anomalies résolues
CORRECTIONS APPLIQUÉES:
- Titre toujours présent (extraction améliorée)
- Ville toujours détectée (multiples stratégies)
- Filtre de recherche par ville avec rayon en km
- Géolocalisation des villes françaises
- Extraction optimisée des données
- Fonction init_chrome() personnalisée intégrée
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

# ----------------------- Selenium / Chrome -----------------------
try:
    import undetected_chromedriver as uc
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    SELENIUM_AVAILABLE = True
except ImportError:
    uc = None  # évite l'erreur "name 'uc' is not defined"
    SELENIUM_AVAILABLE = False

def init_chrome():
    """
    Initialise le navigateur Chrome avec undetected_chromedriver.
    Retourne le driver ou None si erreur.
    """
    if not SELENIUM_AVAILABLE or uc is None:
        print("❌ Selenium ou undetected_chromedriver non installé")
        return None

    try:
        options = uc.ChromeOptions()
        options.add_argument("--headless=new")  # Chrome en mode headless
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--window-size=1920,1080")

        driver = uc.Chrome(options=options)
        print("✅ Chrome initialisé avec succès")
        return driver

    except Exception as e:
        print(f"❌ Erreur init Chrome: {e}")
        return None

# ----------------------- Agent log -----------------------
_script_dir = os.path.dirname(os.path.abspath(__file__))
DEBUG_LOG_PATH = os.path.join(os.path.dirname(_script_dir), ".cursor", "debug.log")

def _debug_log(message, data=None, hypothesis_id=None):
    try:
        import json as _j
        _dir = os.path.dirname(DEBUG_LOG_PATH)
        if _dir:
            os.makedirs(_dir, exist_ok=True)
        with open(DEBUG_LOG_PATH, "a", encoding="utf-8") as _f:
            _f.write(_j.dumps({
                "timestamp": __import__("time").time()*1000,
                "location": "main.py",
                "message": message,
                "data": data or {},
                "sessionId": "debug-session",
                "hypothesisId": hypothesis_id or "E"
            }, ensure_ascii=False) + "\n")
    except Exception:
        pass


def _debug_log(message, data=None, hypothesis_id=None):
    try:
        import json as _j
        _dir = os.path.dirname(DEBUG_LOG_PATH)
        if _dir:
            os.makedirs(_dir, exist_ok=True)
        with open(DEBUG_LOG_PATH, "a", encoding="utf-8") as _f:
            _f.write(_j.dumps({
                "timestamp": __import__("time").time() * 1000,
                "location": "main.py",
                "message": message,
                "data": data or {},
                "sessionId": "debug-session",
                "hypothesisId": hypothesis_id or "E"
            }, ensure_ascii=False) + "\n")
    except Exception:
        pass

# ----------------------- Logging -----------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger(__name__)

# ----------------------- Configuration -----------------------
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

# ----------------------- Anti-ban system -----------------------
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
    
    # Recherche partielle (la ville contient le terme recherché)
    for city_key, coords in FRENCH_CITIES_COORDS.items():
        if normalized in city_key or city_key in normalized:
            return coords
    
    return None

# ============ FONCTION INIT CHROME PERSONNALISÉE ============

def init_chrome():
    """
    Initialise Chrome avec undetected_chromedriver
    Version personnalisée simplifiée
    """
    try:
        options = uc.ChromeOptions()
        options.add_argument("--headless=new")        # mode sans interface graphique
        options.add_argument("--no-sandbox")          # pour Docker / serveur
        options.add_argument("--disable-dev-shm-usage")  # empêche certains crashs
        
        # Initialise le driver Chrome
        driver = uc.Chrome(options=options)
        logger.info("✅ Chrome initialisé avec succès")
        return driver
    except Exception as e:
        logger.error(f"❌ Erreur init Chrome: {e}")
        return None

# ============ SCRAPER AMÉLIORÉ ============

class ImprovedLeBonCoinScraper:
    """Scraper amélioré avec extraction optimisée des données"""
    
    def __init__(self):
        self.base_url = "https://www.leboncoin.fr"
        self.driver = None
        self.seen_ads = set()
        self.running = False
        self.page_loaded = False  # Track si la page est déjà chargée
        self.cookies_accepted = False  # Track si les cookies sont acceptés
    
    def setup_driver(self):
        """Configure le navigateur en utilisant init_chrome()"""
        if self.driver:
            return True
        
        logger.info("🚀 Initialisation du navigateur...")
        
        # Utiliser la fonction init_chrome() personnalisée
        self.driver = init_chrome()
        
        if self.driver:
            try:
                self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            except:
                pass
            
            logger.info("✅ Navigateur OK")
            return True
        else:
            logger.error("❌ Échec initialisation Chrome")
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
        """Récupère les annonces récentes avec extraction améliorée et OPTIMISÉE"""
        
        logger.info(f"🔍 Récupération de {max_ads} annonces...")
        
        try:
            # Si c'est la première fois, charger la page complète
            if not self.page_loaded:
                logger.info("  📄 Chargement initial de la page...")
                self.driver.get(SCRAPE_URL)
                
                # Attente intelligente : attendre que les annonces soient chargées
                try:
                    WebDriverWait(self.driver, 10).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, 'a[data-qa-id="aditem_container"]'))
                    )
                    logger.info("  ✅ Page chargée")
                except:
                    logger.warning("  ⚠️ Timeout lors du chargement initial")
                
                # Gérer les cookies une seule fois
                if not self.cookies_accepted:
                    try:
                        cookie_button = WebDriverWait(self.driver, 3).until(
                            EC.element_to_be_clickable((By.ID, "didomi-notice-agree-button"))
                        )
                        cookie_button.click()
                        self.cookies_accepted = True
                        time.sleep(0.5)  # Petit délai pour laisser le popup disparaître
                    except:
                        self.cookies_accepted = True  # Marquer comme fait même si pas trouvé
                
                self.page_loaded = True
            else:
                # Rafraîchir uniquement (beaucoup plus rapide)
                logger.info("  🔄 Rafraîchissement...")
                self.driver.refresh()
                
                # Attente ultra-courte pour les annonces
                try:
                    WebDriverWait(self.driver, 5).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, 'a[data-qa-id="aditem_container"]'))
                    )
                except:
                    pass
            
            # Scroll minimal et rapide (juste pour déclencher le lazy loading)
            try:
                self.driver.execute_script("window.scrollTo(0, 800);")
                time.sleep(0.3)  # Délai minimal pour le lazy loading
            except:
                pass
            
            # Chercher les annonces immédiatement
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
            # En cas d'erreur, réinitialiser l'état pour forcer un rechargement complet
            self.page_loaded = False
            return []
    
    def _extract_title_improved(self, element, full_text):
        """
        CORRECTION MAJEURE: Extraction du titre avec plusieurs stratégies
        Garantit qu'un titre sera toujours trouvé
        """
        title = None
        
        # Stratégie 1: Sélecteur standard
        try:
            title_elem = element.find_element(By.CSS_SELECTOR, '[data-qa-id="aditem_title"]')
            if title_elem and title_elem.text and len(title_elem.text) > 5:
                title = title_elem.text.strip()
                return title
        except:
            pass
        
        # Stratégie 2: Autres sélecteurs de titre
        title_selectors = [
            'p[data-qa-id="aditem_title"]',
            'h2',
            'h3',
            '[class*="title"]',
            '[class*="Title"]',
        ]
        
        for selector in title_selectors:
            try:
                elem = element.find_element(By.CSS_SELECTOR, selector)
                if elem and elem.text and len(elem.text) > 5:
                    title = elem.text.strip()
                    return title
            except:
                continue
        
        # Stratégie 3: Extraction depuis le texte complet
        if full_text:
            lines = [line.strip() for line in full_text.split('\n') if line.strip()]
            
            # Chercher une ligne qui ressemble à un titre (pas de prix, assez longue)
            for line in lines:
                # Ignorer les lignes avec prix, dates, kilomètres
                if any(indicator in line for indicator in ['€', 'km', ':', 'Hier', 'Aujourd\'hui']):
                    continue
                
                # Ligne assez longue pour être un titre
                if 10 < len(line) < 150:
                    # Vérifier qu'elle contient des lettres
                    if re.search(r'[a-zA-Z]{3,}', line):
                        title = line[:100]
                        return title
        
        # Stratégie 4: Extraire la marque + modèle du texte
        if full_text:
            brand = self._detect_brand(full_text)
            if brand:
                # Chercher le modèle après la marque
                pattern = re.compile(re.escape(brand) + r"\s+([A-Z][a-zA-Z0-9\s-]+)", re.IGNORECASE)
                match = pattern.search(full_text)
                if match:
                    model_part = match.group(1).strip()
                    # Prendre les 2-3 premiers mots
                    model_words = model_part.split()[:3]
                    title = f"{brand} {' '.join(model_words)}"
                    return title
        
        # Stratégie 5: Dernier recours - utiliser l'URL ou un texte générique
        try:
            url = element.get_attribute('href')
            if url:
                # Extraire le slug de l'URL
                match = re.search(r'/([^/]+)\.htm', url)
                if match:
                    slug = match.group(1)
                    # Nettoyer et formater le slug
                    title = slug.replace('-', ' ').replace('_', ' ')
                    title = ' '.join(word.capitalize() for word in title.split())
                    if len(title) > 10:
                        return title[:100]
        except:
            pass
        
        # Absolument dernier recours
        return "Véhicule d'occasion"
    
    def _extract_location_improved(self, element, full_text):
        """
        CORRECTION MAJEURE: Extraction de la ville avec multiples stratégies
        Garantit qu'une ville sera toujours trouvée
        ÉVITE SPÉCIFIQUEMENT le texte des boutons favoris
        """
        location = None
        
        # Stratégie 0A: NOUVEAU - Chercher spécifiquement les paragraphes avec classe contenant "text"
        # Le Bon Coin utilise souvent des classes comme "styles_text__*" pour la localisation
        try:
            location_elems = element.find_elements(By.CSS_SELECTOR, 'p[class*="text"], span[class*="text"]')
            for elem in location_elems:
                text = elem.text.strip()
                
                # Vérifier si c'est une localisation valide (contient code postal)
                if re.search(r'\b\d{5}\b', text):
                    # Ignorer les favoris
                    if any(x in text.lower() for x in ['favori', 'favorite', 'retirée', 'retiree']):
                        continue
                    
                    # Vérifier longueur raisonnable
                    if 5 < len(text) < 80:
                        cleaned = self._clean_location(text)
                        if cleaned and len(cleaned) > 2:
                            _debug_log("location_extract_return", {"strategy": "0A", "value": cleaned, "raw_text": text[:80]}, "C")
                            return cleaned
        except:
            pass
        
        # Stratégie 0B: Chercher TOUS les textes et filtrer par pattern "Ville + Code Postal"
        try:
            all_text_elems = element.find_elements(By.CSS_SELECTOR, 'p, span, div')
            
            for elem in all_text_elems:
                try:
                    # Vérifier que l'élément n'est PAS dans un bouton
                    parent = elem.find_element(By.XPATH, '..')
                    parent_tag = parent.tag_name.lower()
                    
                    if parent_tag == 'button':
                        continue
                    
                    if parent.get_attribute('onclick'):
                        continue
                    
                    text = elem.text.strip()
                    
                    # Ignorer favoris
                    if any(x in text.lower() for x in ['favori', 'favorite', 'retirée', 'retiree']):
                        continue
                    
                    # PATTERN SPÉCIFIQUE: "VilleXXX 12345" ou "Ville-sur-Mer 12345 Complément"
                    # Exemples: "Garennes-sur-Eure 27780" ou "Osny 95520 Livitiers - Ennery"
                    if re.search(r'[A-ZÀ-Ü][a-zA-ZÀ-ÿ\s\-\']+\s+\d{5}', text):
                        if len(text) > 5 and len(text) < 100:
                            cleaned = self._clean_location(text)
                            if cleaned and len(cleaned) > 2:
                                _debug_log("location_extract_return", {"strategy": "0B", "value": cleaned, "raw_text": text[:80]}, "C")
                                return cleaned
                    
                    # Vérifier si ça ressemble à une ville (code postal ou format ville)
                    if re.search(r'\d{5}', text) or re.match(r'^[A-ZÀ-Ü][a-zA-ZÀ-ÿ\s\-\']{2,}$', text):
                        if len(text) > 2 and len(text) < 60:
                            cleaned = self._clean_location(text)
                            if cleaned and len(cleaned) > 2:
                                _debug_log("location_extract_return", {"strategy": "0", "value": cleaned, "raw_text": text[:80]}, "C")
                                return cleaned
                except:
                    continue
        except:
            pass
        
        # Stratégie 1: Sélecteurs standards (AVEC FILTRAGE des favoris)
        location_selectors = [
            '[data-qa-id="aditem_location"]',
            'p[data-qa-id="aditem_location"]',
            '[data-test-id="location"]',
            'div[class*="location"]',
            'span[class*="location"]',
            'p[class*="location"]',
            '[class*="Location"]',
        ]
        
        for selector in location_selectors:
            try:
                loc_elem = element.find_element(By.CSS_SELECTOR, selector)
                if loc_elem and loc_elem.text:
                    location_raw = loc_elem.text.strip()
                    
                    # FILTRAGE CRUCIAL: Ignorer le texte des boutons favoris
                    if any(x in location_raw.lower() for x in ['favori', 'favorite', 'retirée', 'retiree', 'ajoutée', 'ajoutee']):
                        continue
                    # Ignorer les sous-titres / specs (bullet • ou mots-clés véhicule)
                    if '•' in location_raw or any(x in location_raw.lower() for x in ['électrique', 'electrique', 'diesel', 'hybride', 'automatique', 'manuelle', 'à la une', 'pack sérénité', 'occasion récente']):
                        continue
                    
                    if len(location_raw) > 2:
                        location = self._clean_location(location_raw)
                        if location and len(location) > 2:
                            # #region agent log
                            _debug_log("location_extract_return", {"strategy": 1, "value": location, "raw": location_raw[:80], "selector": selector}, "A")
                            # #endregion
                            return location
            except:
                continue
        
        # Stratégie 2: Recherche dans le texte complet avec patterns avancés
        if full_text:
            # Filtrer d'abord le texte des favoris
            lines = [line.strip() for line in full_text.split('\n') if line.strip()]
            filtered_lines = [line for line in lines if not any(x in line.lower() for x in ['favori', 'favorite', 'retirée', 'retiree'])]
            
            for line in filtered_lines:
                # Pattern 1: Ville + code postal entre parenthèses
                match = re.search(r'([A-ZÀ-Ü][a-zA-ZÀ-ÿ\s\-\']{2,})\s*\((\d{5})\)', line)
                if match:
                    city = match.group(1).strip()
                    postal = match.group(2)
                    if len(city) > 2 and not any(x in city.lower() for x in ['hier', 'aujourd', 'pro', 'particulier']):
                        return f"{city} ({postal})"
                
                # Pattern 2: Code postal seul (ex: 75001) suivi de texte
                match = re.search(r'\b(\d{5})\b\s*([A-ZÀ-Ü][a-zA-ZÀ-ÿ\s\-\']{2,40})', line)
                if match:
                    postal = match.group(1)
                    city = match.group(2).strip()
                    # Vérifier que ce n'est pas un mot-clé
                    if not any(keyword in city.lower() for keyword in 
                              ['hier', 'aujourd', 'pro', 'particulier', 'urgent', 'occasion']):
                        return f"{city} ({postal})"
                
                # Pattern 3: Ville seule (commence par majuscule, lettres/espaces/tirets)
                if re.match(r'^[A-ZÀ-Ü][a-zA-ZÀ-ÿ\s\-\']{2,40}$', line):
                    # Vérifier que ce n'est pas un mot-clé ou du texte indésirable
                    if not any(keyword in line.lower() for keyword in 
                              ['hier', 'aujourd', 'pro', 'particulier', 'urgent', 'occasion', 
                               'excellent', 'neuf', 'boite', 'diesel', 'essence', 'kilom', 'annonce',
                               'manuelle', 'automatique', 'gris', 'blanc', 'noir', 'bleu', 'rouge',
                               'une', 'à la', 'pack', 'sérénité', 'serenite', 'récente', 'recente']):
                        # Vérifier qu'il y a au moins 2 lettres consécutives
                        if re.search(r'[a-zA-Z]{2,}', line):
                            location = self._clean_location(line)
                            if location and len(location) > 2:
                                # #region agent log
                                _debug_log("location_extract_return", {"strategy": "2_pattern3", "value": location, "line": line[:80]}, "B")
                                # #endregion
                                return location
                
                # Pattern 4: Code postal + ville
                match = re.search(r'(\d{5})\s+([A-ZÀ-Ü][a-zA-ZÀ-ÿ\s\-\']{2,})', line)
                if match:
                    postal = match.group(1)
                    city = match.group(2).strip()
                    if len(city) > 2:
                        return f"{city} ({postal})"
        
        # Stratégie 3: Chercher un code postal seul et déduire la région
        if full_text:
            postal_match = re.search(r'\b(\d{5})\b', full_text)
            if postal_match:
                postal = postal_match.group(1)
                # Déduire le département
                dept = postal[:2]
                dept_names = {
                    '75': 'Paris',
                    '69': 'Lyon',
                    '13': 'Marseille',
                    '31': 'Toulouse',
                    '33': 'Bordeaux',
                    '59': 'Lille',
                    '44': 'Nantes',
                    '34': 'Montpellier',
                    '67': 'Strasbourg',
                    '06': 'Nice',
                }
                
                if dept in dept_names:
                    return f"{dept_names[dept]} ({postal})"
                else:
                    return f"Département {dept}"
        
        # Stratégie 4: Recherche de villes connues dans le texte
        if full_text:
            text_lower = full_text.lower()
            
            # Chercher les villes majeures dans le texte
            major_cities = [
                'paris', 'marseille', 'lyon', 'toulouse', 'nice', 'nantes',
                'strasbourg', 'montpellier', 'bordeaux', 'lille', 'rennes',
                'reims', 'saint-étienne', 'toulon', 'grenoble', 'dijon',
                'angers', 'nîmes', 'clermont-ferrand', 'tours'
            ]
            
            for city in major_cities:
                if city in text_lower:
                    return city.capitalize()
        
        # Dernier recours: France (au moins on a un pays)
        # #region agent log
        _debug_log("location_extract_return", {"strategy": "fallback", "value": "France"}, "E")
        # #endregion
        return "France"
    
    def _clean_location(self, location_raw):
        """Nettoie une localisation extraite"""
        if not location_raw:
            return None
        
        raw_lower = location_raw.lower()
        # FILTRE CRITIQUE: Rejeter immédiatement les textes de favoris
        if any(x in raw_lower for x in ['favori', 'favorite', 'retirée', 'retiree', 'ajoutée', 'ajoutee']):
            return None
        # Rejeter les textes qui ne sont pas des localisations (sous-titres LBC, packs, une)
        if '•' in location_raw:
            return None
        if any(x in raw_lower for x in ['à la une', 'a la une', 'pack sérénité', 'pack serenite', 'occasion récente', 'occasion recente']):
            return None
        # Rejeter les lignes type specs véhicule (année • carburant • boîte)
        if any(x in raw_lower for x in ['électrique', 'electrique', 'diesel', 'hybride', 'essence', 'automatique', 'manuelle', 'rechargeable']):
            return None
        
        # NOUVEAU: Si le texte contient "Ville 12345 Complément", le garder tel quel (format Le Bon Coin)
        # Exemple: "Garennes-sur-Eure 27780" ou "Osny 95520 Livitiers - Ennery"
        if re.search(r'[A-ZÀ-Ü][a-zA-ZÀ-ÿ\s\-\']+\s+\d{5}', location_raw):
            # Nettoyer seulement les parties indésirables, mais garder le format
            location_clean = location_raw.strip()
            
            # Enlever les dates/heures
            location_clean = re.sub(r'Aujourd\'hui.*', '', location_clean, flags=re.IGNORECASE)
            location_clean = re.sub(r'Hier.*', '', location_clean, flags=re.IGNORECASE)
            location_clean = re.sub(r'\d{2}:\d{2}', '', location_clean)
            
            # Retourner directement si ça reste valide
            location_clean = location_clean.strip()
            if len(location_clean) > 5:
                return location_clean
        
        # Patterns à supprimer
        remove_patterns = [
            r'\d+[\s.]?\d*\s*km\b',
            r'kilom[èe]trage\s*:?\s*',
            r'Aujourd\'hui.*',
            r'Hier.*',
            r'\d{2}:\d{2}',
            r'\b(pro|professionnel|particulier)\b',
            r'annonce',
        ]
        
        location_clean = location_raw
        for pattern in remove_patterns:
            location_clean = re.sub(pattern, '', location_clean, flags=re.IGNORECASE)
        
        # Nettoyer les espaces
        location_clean = ' '.join(location_clean.split()).strip()
        
        # Vérifier que ce n'est pas juste des chiffres
        if location_clean and not location_clean.replace(' ', '').replace('-', '').replace('(', '').replace(')', '').isdigit():
            if len(location_clean) > 2:
                # #region agent log
                _debug_log("clean_location_accept", {"raw": location_raw[:80], "cleaned": location_clean}, "D")
                # #endregion
                return location_clean
        
        return None
    
    def _parse_ad(self, element, idx):
        """Parse une annonce avec extraction améliorée"""
        try:
            full_text = element.text
            if not full_text or len(full_text) < 10:
                return None
            
            # ===== TITRE - EXTRACTION AMÉLIORÉE =====
            title = self._extract_title_improved(element, full_text)
            
            # ===== PRIX - EXTRACTION AMÉLIORÉE =====
            price = 0
            price_text = ""
            try:
                # Essayer plusieurs sélecteurs pour le prix
                price_selectors = [
                    '[data-qa-id="aditem_price"]',
                    'span[class*="price"]',
                    'p[class*="price"]',
                    'div[class*="price"]',
                    '[data-test-id="price"]',
                    '[class*="Price"]',
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
                    lines = full_text.split('\n')
                    for line in lines:
                        # Chercher un prix (éviter les prix mensuels et aberrants)
                        if '€' in line and not any(word in line.lower() for word in ['mois', '/mois', 'semaine', 'jour']):
                            # Pattern pour capturer le prix
                            price_match = re.search(r'(\d[\d\s\.\u202f,]*)\s*€', line)
                            if price_match:
                                price_text = price_match.group(1)
                                break
            except:
                pass
            
            # Convertir le prix en nombre
            try:
                clean_price = re.sub(r'[^\d]', '', price_text.replace('\u202f', '').replace(',', ''))
                if clean_price:
                    price = int(clean_price)
                    # Vérifier que le prix est réaliste pour une voiture
                    if price > 500000 or price < 100:
                        price = 0
                else:
                    price = 0
            except:
                price = 0
            
            # ===== URL =====
            url = ""
            try:
                url = element.get_attribute('href')
                if not url:
                    link = element.find_element(By.TAG_NAME, 'a')
                    url = link.get_attribute('href')
            except:
                url = f"https://www.leboncoin.fr/voitures/{idx}"
            
            # ===== ID =====
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
                    ad_id = hashlib.md5(f"{title}_{price}_{idx}".encode()).hexdigest()[:16]
            
            # ===== LOCALISATION - EXTRACTION AMÉLIORÉE =====
            location = self._extract_location_improved(element, full_text)
            # #region agent log
            _debug_log("parse_ad_location", {"title_short": (title or "")[:50], "location": location}, "E")
            # #endregion
            
            # ===== IMAGES =====
            images = self.extract_images(element)
            
            # ===== DÉTECTIONS =====
            brand = self._detect_brand(title + " " + full_text)
            model = self._detect_model(title + " " + full_text, brand)
            year = self._detect_year(title + " " + full_text)
            mileage = self._detect_mileage(full_text)
            fuel = self._detect_fuel(title + " " + full_text)
            gearbox = self._detect_gearbox(title + " " + full_text)
            is_pro = "pro" in full_text.lower() or "professionnel" in full_text.lower()
            score = self._calculate_score(year, mileage, price, is_pro)
            
            # ===== COORDONNÉES GPS =====
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
                "coordinates": coordinates,  # Nouvelles coordonnées GPS
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
        """Détecte la marque du véhicule"""
        brands = [
            "Renault", "Peugeot", "Citroën", "Toyota", "Volkswagen", "Honda", "Ford",
            "BMW", "Mercedes", "Audi", "Fiat", "Kia", "Hyundai", "Nissan", "Opel",
            "Mazda", "Volvo", "Tesla", "Jeep", "Dacia", "Skoda", "SEAT", "Suzuki",
            "Porsche", "Lexus", "Jaguar", "Land Rover", "Mini", "Alfa Romeo", "DS",
            "Mitsubishi", "Subaru", "Infiniti", "Chevrolet", "Dodge", "Chrysler",
            "Cadillac", "Ferrari", "Lamborghini", "Maserati", "Bentley", "Rolls-Royce",
            "Aston Martin", "McLaren", "Bugatti", "Koenigsegg", "Pagani"
        ]
        text_lower = text.lower()
        for brand in brands:
            if brand.lower() in text_lower:
                return brand
        return None
    
    def _detect_model(self, text, brand):
        """Détecte le modèle du véhicule"""
        if not brand:
            return None
        try:
            # Chercher après la marque
            pattern = re.compile(re.escape(brand) + r"\s+(.+?)(?:\s*[-–—]|\s+\d{4}|\s+\(|$)", re.IGNORECASE)
            m = pattern.search(text)
            if m:
                model_part = m.group(1).strip()
                # Prendre les 2-3 premiers mots du modèle
                model_words = model_part.split()[:3]
                return " ".join(model_words)
        except:
            pass
        return None
    
    def _detect_year(self, text):
        """Détecte l'année du véhicule"""
        # Chercher une année entre 1980 et 2025
        matches = re.findall(r'\b(19[89]\d|20[0-2]\d)\b', text)
        if matches:
            # Prendre la dernière année trouvée (souvent la plus pertinente)
            return int(matches[-1])
        return None
    
    def _detect_mileage(self, text):
        """Détecte le kilométrage"""
        patterns = [
            r'(\d+[\s.]?\d*)\s*km(?![²³])',
            r'(\d+[\s.]?\d*)\s*kilom[èe]tres?'
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    km_str = match.group(1).replace(' ', '').replace('.', '')
                    km = int(km_str)
                    # Vérifier que c'est un kilométrage réaliste
                    if 0 <= km <= 999999:
                        return km
                except:
                    continue
        return None
    
    def _detect_fuel(self, text):
        """Détecte le type de carburant"""
        text_lower = text.lower()
        if "électrique" in text_lower or "electrique" in text_lower:
            return "électrique"
        if "hybride" in text_lower:
            return "hybride"
        if "diesel" in text_lower:
            return "diesel"
        if "essence" in text_lower:
            return "essence"
        return None
    
    def _detect_gearbox(self, text):
        """Détecte le type de boîte de vitesse"""
        text_lower = text.lower()
        if "automatique" in text_lower or "auto" in text_lower:
            return "automatique"
        if "manuelle" in text_lower:
            return "manuelle"
        return None
    
    def _calculate_score(self, year, mileage, price, is_pro):
        """Calcule un score de qualité pour l'annonce"""
        score = 50.0
        
        # Bonus/malus basé sur l'année
        if year:
            if year >= 2022:
                score += 20
            elif year >= 2020:
                score += 15
            elif year >= 2018:
                score += 10
            elif year >= 2015:
                score += 5
            else:
                score -= 5
        
        # Bonus/malus basé sur le kilométrage
        if mileage is not None:
            if mileage < 20000:
                score += 20
            elif mileage < 50000:
                score += 15
            elif mileage < 100000:
                score += 10
            elif mileage < 150000:
                score += 5
            else:
                score -= 5
        
        # Malus si vendeur pro
        if is_pro:
            score -= 5
        
        # Bonus si prix raisonnable
        if price > 0:
            if 5000 <= price <= 30000:
                score += 5
        
        return round(min(max(score, 0), 100), 1)
    
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
    
    # Préparer le véhicule pour l'envoi (convertir datetime)
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
    
    # Nettoyer les clients déconnectés
    for client in disconnected:
        websocket_clients.remove(client)

# ============ FASTAPI APP ============

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gestion du cycle de vie de l'application"""
    logger.info("✅ API démarrée")
    task = asyncio.create_task(background_monitor())
    yield
    scraper.running = False
    scraper.close()
    logger.info("🛑 API arrêtée")

app = FastAPI(
    title="AutoTrack API - Version Corrigée",
    version="2.2",
    description="API de monitoring LeBonCoin avec extraction améliorée et recherche géolocalisée",
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
    """Endpoint WebSocket pour les mises à jour en temps réel"""
    await websocket.accept()
    websocket_clients.append(websocket)
    logger.info(f"🔌 Client connecté ({len(websocket_clients)} total)")
    
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        websocket_clients.remove(websocket)
        logger.info(f"🔌 Client déconnecté ({len(websocket_clients)} restants)")

# ============ MONITORING ============

async def background_monitor():
    """Monitoring en arrière-plan avec scraping régulier"""
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
        
        # Réinitialiser le compteur après un scan réussi
        if initial_ads:
            consecutive_empty_scans = 0
    except Exception as e:
        logger.error(f"❌ Erreur scan initial: {str(e)}")
    
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
                logger.info(f"  🆕 {len(new_ads)} nouvelle(s) annonce(s) !")
                total_new += len(new_ads)
                
                # Réinitialiser le compteur de scans vides
                consecutive_empty_scans = 0
                
                for ad in new_ads:
                    scraper.seen_ads.add(ad['id'])
                    database["vehicles"].insert(0, ad)
                    
                    logger.info(f"    📌 {ad['title'][:60]} - {ad['price']}€ - {ad['location']}")
                    
                    # Broadcast via WebSocket
                    await broadcast_new_vehicle(ad)
                    
                    # Limiter la taille de la base de données
                    if len(database["vehicles"]) > 1000:
                        database["vehicles"] = database["vehicles"][:1000]
            else:
                # Incrémenter le compteur de scans vides
                consecutive_empty_scans += 1
                logger.info(f"  ✓ Aucune nouvelle annonce (scans vides: {consecutive_empty_scans}/{MAX_EMPTY_SCANS_BEFORE_REFRESH})")
                
                # Si on atteint le seuil, rouvrir une nouvelle page
                if consecutive_empty_scans >= MAX_EMPTY_SCANS_BEFORE_REFRESH:
                    logger.warning(f"🔄 {MAX_EMPTY_SCANS_BEFORE_REFRESH} scans consécutifs sans annonce détectés!")
                    logger.info("🌐 Ouverture d'une nouvelle page Leboncoin pour contourner le bannissement...")
                    
                    try:
                        # Fermer l'ancien navigateur
                        scraper.close()
                        
                        # Attendre un peu
                        await asyncio.sleep(random.uniform(3, 6))
                        
                        # Réinitialiser et ouvrir une nouvelle session
                        if scraper.setup_driver():
                            logger.info("✅ Navigateur réinitialisé avec succès!")
                            
                            # Vérifier que le driver fonctionne correctement
                            try:
                                current_url = scraper.driver.current_url
                                logger.info(f"   URL actuelle: {current_url}")
                            except Exception as url_err:
                                logger.error(f"   ⚠️ Erreur lors de la vérification de l'URL: {url_err}")
                            
                            consecutive_empty_scans = 0
                            
                            # Faire un scan immédiatement pour tester
                            logger.info("   Test de connexion à Leboncoin...")
                            test_ads = scraper.get_recent_ads(max_ads=20)
                            if test_ads:
                                logger.info(f"  ✅ {len(test_ads)} annonces détectées après réouverture")
                            else:
                                logger.warning("  ⚠️ Aucune annonce trouvée après réouverture, vérifiez la connexion")
                        else:
                            logger.error("❌ Échec de l'ouverture d'une nouvelle page")
                            
                    except Exception as e:
                        logger.error(f"❌ Erreur lors de la réouverture: {str(e)}")
                        import traceback
                        logger.error(f"   Détails: {traceback.format_exc()}")
                        consecutive_empty_scans = 0  # Réinitialiser pour éviter les boucles infinies
            
            # Stats périodiques
            if scan_count % 10 == 0:
                logger.info(f"\n📊 Stats: {total_new} nouvelles | {len(database['vehicles'])} total | {len(scraper.seen_ads)} mémorisées\n")
            
        except Exception as e:
            logger.error(f"❌ Erreur scan: {str(e)}")
            # En cas d'erreur, ne pas incrémenter le compteur pour éviter les faux positifs
        
        logger.info(f"  ⏳ Prochaine vérification dans {SCRAPE_INTERVAL_SECONDS}s...\n")
        await asyncio.sleep(SCRAPE_INTERVAL_SECONDS)

# ============ ROUTES API ============

def _is_invalid_location(loc):
    """True si la chaîne n'est pas une vraie localisation (specs, une, pack, etc.)."""
    if not loc or not isinstance(loc, str):
        return True
    low = loc.lower()
    if "•" in loc:
        return True
    if any(x in low for x in ["à la une", "a la une", "pack sérénité", "pack serenite", "occasion récente", "occasion recente"]):
        return True
    if any(x in low for x in ["électrique", "electrique", "diesel", "hybride", "automatique", "manuelle", "rechargeable"]):
        return True
    return False

@app.get("/")
async def root():
    """Informations sur l'API"""
    return {
        "name": "AutoTrack API - Version Corrigée",
        "version": "2.2",
        "status": "running",
        "vehicles_count": len(database["vehicles"]),
        "websocket_clients": len(websocket_clients),
        "features": [
            "Titre toujours présent",
            "Ville toujours détectée",
            "Recherche géolocalisée (rayon en km)",
            "WebSocket temps réel",
            "Monitoring automatique",
            "init_chrome() personnalisée intégrée"
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
    """
    Récupère les véhicules avec filtres avancés
    
    NOUVEAU: location_radius_km permet de chercher "aux alentours" d'une ville
    Exemple: location=Paris&location_radius_km=50 → cherche dans un rayon de 50km autour de Paris
    """
    vehicles = database["vehicles"].copy()
    
    # Filtre par marque
    if brand:
        vehicles = [v for v in vehicles if v.get("brand") and v.get("brand").lower() == brand.lower()]
    
    # Filtre par modèle
    if model:
        vehicles = [v for v in vehicles if v.get("model") and model.lower() in v.get("model", "").lower()]
    
    # Filtre par localisation avec rayon (NOUVEAU)
    if location:
        if location_radius_km and location_radius_km > 0:
            # Recherche géolocalisée
            center_coords = get_city_coordinates(location)
            
            if center_coords:
                logger.info(f"🗺️ Recherche dans un rayon de {location_radius_km}km autour de {location}")
                
                filtered_vehicles = []
                for v in vehicles:
                    vehicle_coords = v.get("coordinates")
                    
                    if vehicle_coords:
                        distance = calculate_distance(
                            center_coords[0], center_coords[1],
                            vehicle_coords[0], vehicle_coords[1]
                        )
                        
                        if distance <= location_radius_km:
                            # Ajouter la distance calculée au véhicule
                            v_copy = v.copy()
                            v_copy["distance_km"] = distance
                            filtered_vehicles.append(v_copy)
                
                vehicles = filtered_vehicles
                logger.info(f"  ✅ {len(vehicles)} véhicules trouvés dans le rayon")
            else:
                # Pas de coordonnées, fallback sur recherche textuelle
                logger.warning(f"⚠️ Pas de coordonnées pour {location}, recherche textuelle")
                vehicles = [v for v in vehicles if v.get("location") and location.lower() in v.get("location", "").lower()]
        else:
            # Recherche textuelle simple
            vehicles = [v for v in vehicles if v.get("location") and location.lower() in v.get("location", "").lower()]
    
    # Filtre par prix
    if min_price:
        vehicles = [v for v in vehicles if v.get("price", 0) >= min_price]
    if max_price:
        vehicles = [v for v in vehicles if v.get("price", 0) <= max_price]
    
    # Filtre par année
    if min_year:
        vehicles = [v for v in vehicles if v.get("year") and v.get("year") >= min_year]
    if max_year:
        vehicles = [v for v in vehicles if v.get("year") and v.get("year") <= max_year]
    
    # Filtre par kilométrage
    if max_mileage:
        vehicles = [v for v in vehicles if v.get("mileage") is not None and v.get("mileage") <= max_mileage]
    
    # Filtre par carburant
    if fuel:
        vehicles = [v for v in vehicles if v.get("fuel") and v.get("fuel").lower() == fuel.lower()]
    
    # Filtre par boîte de vitesse
    if gearbox:
        vehicles = [v for v in vehicles if v.get("gearbox") and v.get("gearbox").lower() == gearbox.lower()]
    
    # Filtre par score
    if min_score:
        vehicles = [v for v in vehicles if v.get("score", 0) >= min_score]
    
    # Tri
    if sort == "price_asc":
        vehicles.sort(key=lambda x: x.get("price", 0))
    elif sort == "price_desc":
        vehicles.sort(key=lambda x: x.get("price", 999999), reverse=True)
    elif sort == "score":
        vehicles.sort(key=lambda x: x.get("score", 0), reverse=True)
    elif sort == "distance" and location and location_radius_km:
        # Tri par distance si recherche géolocalisée
        vehicles.sort(key=lambda x: x.get("distance_km", 999999))
    
    total = len(vehicles)
    start = (page - 1) * limit
    end = start + limit
    paginated = vehicles[start:end]
    
    # Sanitiser les localisations invalides (specs / une / pack) déjà en base
    paginated = [dict(v, location="France" if _is_invalid_location(v.get("location")) else v.get("location")) for v in paginated]
    
    # ✅ NOUVEAU: Calculs pour éviter l'attente dans le frontend
    total_pages = (total + limit - 1) // limit if total > 0 else 0
    is_partial = len(paginated) < limit and len(paginated) > 0
    has_more = end < total
    available_count = len(paginated)
    
    # #region agent log
    _debug_log("api_vehicles_return", {
        "vehicles_location_sample": [(v.get("title", "")[:40], v.get("location")) for v in paginated[:12]],
        "page": page,
        "total_pages": total_pages,
        "available_count": available_count,
        "is_partial": is_partial,
        "has_more": has_more
    }, "E")
    # #endregion
    
    return {
        "total": total,
        "page": page,
        "total_pages": total_pages,
        "vehicles": paginated,
        "last_updated": vehicles[0]["published_at"].isoformat() if vehicles else None,
        
        # ✅ NOUVEAUX CHAMPS pour éviter le chargement en boucle
        "is_partial": is_partial,
        "has_more": has_more,
        "available_count": available_count,
        "waiting_for_more": False,
        "is_empty": available_count == 0,
        
        "filters_applied": {
            "brand": brand,
            "model": model,
            "location": location,
            "location_radius_km": location_radius_km,
            "min_price": min_price,
            "max_price": max_price,
            "min_year": min_year,
            "max_year": max_year,
            "max_mileage": max_mileage,
            "fuel": fuel,
            "gearbox": gearbox,
            "min_score": min_score
        }
    }

@app.get("/api/stats")
async def get_stats():
    """Statistiques de l'application"""
    vehicles = database["vehicles"]
    
    # Stats par ville
    cities_count = {}
    for v in vehicles:
        loc = v.get("location", "Non spécifié")
        cities_count[loc] = cities_count.get(loc, 0) + 1
    
    top_cities = sorted(cities_count.items(), key=lambda x: x[1], reverse=True)[:10]
    
    return {
        "total_vehicles": len(vehicles),
        "scraper_running": scraper.running,
        "last_updated": vehicles[0]["published_at"].isoformat() if vehicles else None,
        "websocket_clients": len(websocket_clients),
        "top_cities": [{"city": city, "count": count} for city, count in top_cities],
        "vehicles_with_location": sum(1 for v in vehicles if v.get("location") != "Non spécifié"),
        "vehicles_with_coordinates": sum(1 for v in vehicles if v.get("coordinates") is not None)
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
