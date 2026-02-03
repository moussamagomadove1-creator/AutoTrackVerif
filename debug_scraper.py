"""
Script de diagnostic pour comprendre pourquoi le scraper ne trouve pas d'annonces
"""

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
import time
import random

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]

print("=" * 60)
print("🔍 DIAGNOSTIC SCRAPER LEBONCOIN")
print("=" * 60)

# 1. Initialiser Chrome
print("\n[1/6] Démarrage de Chrome...")
options = uc.ChromeOptions()
options.add_argument("--window-size=1920,1080")
options.add_argument("--disable-blink-features=AutomationControlled")
options.add_argument(f"user-agent={random.choice(USER_AGENTS)}")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
# Mode VISIBLE pour debug
# options.add_argument("--headless=new")

driver = uc.Chrome(options=options, version_main=144, use_subprocess=True)
print("✅ Chrome démarré")

try:
    # 2. Accéder à LeBonCoin
    print("\n[2/6] Accès à LeBonCoin...")
    url = "https://www.leboncoin.fr/voitures/offres"
    driver.get(url)
    time.sleep(5)  # Attendre le chargement
    print(f"✅ Page chargée : {driver.title}")
    
    # 3. Prendre un screenshot
    print("\n[3/6] Capture d'écran...")
    driver.save_screenshot("leboncoin_debug.png")
    print("✅ Screenshot sauvegardé : leboncoin_debug.png")
    
    # 4. Sauvegarder le HTML
    print("\n[4/6] Sauvegarde du HTML...")
    with open("leboncoin_debug.html", "w", encoding="utf-8") as f:
        f.write(driver.page_source)
    print("✅ HTML sauvegardé : leboncoin_debug.html")
    
    # 5. Tester différents sélecteurs
    print("\n[5/6] Test des sélecteurs CSS...")
    
    selectors = [
        "a[data-testid*='ad']",
        "a[href*='/voitures/']",
        "a[href*='.htm']",
        "div[data-testid='ad-list'] a",
        "a[class*='AdCard']",
        "a[class*='ad-card']",
        "article a",
        "li a[href*='/voitures/']",
        "[data-qa-id*='adcard'] a",
    ]
    
    for sel in selectors:
        try:
            elements = driver.find_elements(By.CSS_SELECTOR, sel)
            print(f"  {sel:50} → {len(elements)} éléments")
            
            if elements and len(elements) > 0:
                # Afficher le premier lien trouvé
                first_href = elements[0].get_attribute("href")
                print(f"    └─ Exemple : {first_href[:80]}...")
                
        except Exception as e:
            print(f"  {sel:50} → ERREUR: {e}")
    
    # 6. Chercher tous les liens
    print("\n[6/6] Analyse de tous les liens...")
    all_links = driver.find_elements(By.TAG_NAME, "a")
    print(f"  Total de liens <a> : {len(all_links)}")
    
    voiture_links = []
    for link in all_links:
        href = link.get_attribute("href") or ""
        if "/voitures/" in href and ".htm" in href:
            voiture_links.append(href)
    
    print(f"  Liens vers /voitures/*.htm : {len(voiture_links)}")
    
    if voiture_links:
        print("\n📋 Exemples de liens trouvés :")
        for i, link in enumerate(voiture_links[:5]):
            print(f"  {i+1}. {link}")
    else:
        print("\n❌ AUCUN lien d'annonce trouvé !")
        print("\n💡 Causes possibles :")
        print("  1. La page est vide ou bloquée (vérifier leboncoin_debug.png)")
        print("  2. LeBonCoin affiche un CAPTCHA")
        print("  3. La structure HTML a changé")
        print("  4. Le JavaScript n'a pas fini de charger")
        
        # Vérifier si CAPTCHA
        page_text = driver.page_source.lower()
        if "captcha" in page_text or "recaptcha" in page_text:
            print("\n⚠️ CAPTCHA DÉTECTÉ ! Le bot est repéré.")
        
        if "robot" in page_text or "automated" in page_text:
            print("\n⚠️ Détection de bot ! LeBonCoin bloque le scraper.")

    print("\n" + "=" * 60)
    print("📁 Fichiers générés :")
    print("  - leboncoin_debug.png (capture d'écran)")
    print("  - leboncoin_debug.html (code source)")
    print("=" * 60)
    
    input("\n➡️ Appuyez sur Entrée pour fermer le navigateur...")

except Exception as e:
    print(f"\n❌ ERREUR : {e}")
    import traceback
    traceback.print_exc()

finally:
    print("\n🛑 Fermeture du navigateur...")
    driver.quit()
    print("✅ Terminé !")
