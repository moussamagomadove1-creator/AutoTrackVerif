# 🔍 RÉSOLUTION : "0 liens d'annonces trouvés"

## ❌ Le Problème

```
06:21:19 [INFO]   🔍 0 liens d'annonces trouvés sur la page
```

Le scraper fonctionne, mais ne trouve **aucune annonce** sur LeBonCoin.

---

## 🎯 Diagnostic en 3 Étapes

### Étape 1 : Lancer le Script de Diagnostic

```bash
# Copier debug_scraper.py dans votre dossier backend/
cd backend
python debug_scraper.py
```

**Ce script va :**
- ✅ Ouvrir Chrome en mode VISIBLE (pas headless)
- ✅ Prendre un screenshot de ce que Chrome voit
- ✅ Sauvegarder le HTML de la page
- ✅ Tester tous les sélecteurs CSS
- ✅ Lister les liens trouvés

**Fichiers générés :**
- `leboncoin_debug.png` - Capture d'écran
- `leboncoin_debug.html` - Code HTML brut

### Étape 2 : Analyser les Résultats

**Ouvrir `leboncoin_debug.png`** et vérifier :

#### ✅ Scénario A : Vous voyez les annonces
→ La page charge correctement, mais les **sélecteurs CSS sont obsolètes**

**Solution** : Mettre à jour les sélecteurs (voir Étape 3)

#### ❌ Scénario B : Page blanche ou CAPTCHA
→ LeBonCoin **détecte et bloque** le bot

**Solutions possibles** :
1. Utiliser un proxy/VPN
2. Augmenter les délais entre requêtes
3. Désactiver le mode headless
4. Utiliser des proxies résidentiels
5. Passer par une API LeBonCoin officielle (si disponible)

#### ❌ Scénario C : Message "Accès refusé"
→ Votre IP est **bannie temporairement**

**Solution** : Attendre quelques heures ou changer d'IP

---

## 🔧 Étape 3 : Corriger les Sélecteurs CSS

Si le diagnostic montre que la page charge mais que les sélecteurs sont mauvais :

### 3.1 Inspecter le HTML

```bash
# Ouvrir leboncoin_debug.html dans un navigateur
# Appuyer sur F12 (DevTools)
# Chercher un lien d'annonce
```

### 3.2 Trouver le Bon Sélecteur

**Exemple :** Si vous trouvez ce HTML :
```html
<a href="/voitures/2345678.htm" class="styles_adCard__ABC123">
    <div>Renault Clio</div>
</a>
```

**Le sélecteur CSS correct serait :**
```python
"a[href*='/voitures/'][href*='.htm']"
```

### 3.3 Mettre à Jour main.py

**Fichier : `backend/main.py`**  
**Ligne : ~485-492**

```python
# AVANT (sélecteurs obsolètes)
candidates = [
    "a[data-testid*='ad-card']",
    "a[href*='/voitures/'][href*='.htm']",
    # ...
]

# APRÈS (ajouter vos nouveaux sélecteurs EN PREMIER)
candidates = [
    "VOTRE_NOUVEAU_SELECTEUR_ICI",  # ← À remplacer
    "a[data-testid*='ad-card']",
    "a[href*='/voitures/'][href*='.htm']",
    # ...
]
```

---

## 🚀 Solutions Alternatives

### Solution 1 : Mode Non-Headless (Temporaire)

**Modifier `backend/main.py` ligne ~355** :

```python
# AVANT
options.add_argument("--headless=new")

# APRÈS (commenter la ligne)
# options.add_argument("--headless=new")
```

**Avantage** : Chrome visible, moins de détection  
**Inconvénient** : Fenêtre Chrome ouverte en permanence

### Solution 2 : Augmenter les Délais

**Modifier `backend/main.py` ligne ~436-447** :

```python
# AVANT
self._rand_sleep(2.0, 4.0)
# ...
self._scroll_naturally(steps=4)
self._rand_sleep(1.0, 2.0)

# APRÈS (délais plus longs)
self._rand_sleep(5.0, 8.0)  # Attendre plus longtemps
# ...
self._scroll_naturally(steps=6)  # Plus de scroll
self._rand_sleep(3.0, 5.0)  # Plus d'attente
```

### Solution 3 : Proxy Rotatif

```python
# Ajouter dans _get_driver() (ligne ~348)
options.add_argument('--proxy-server=http://votre-proxy:port')
```

### Solution 4 : API Officielle (Recommandé si disponible)

Chercher si LeBonCoin propose une API publique ou partenaire.

---

## 📋 Checklist de Débogage

- [ ] Lancer `debug_scraper.py`
- [ ] Ouvrir `leboncoin_debug.png` pour voir la page
- [ ] Ouvrir `leboncoin_debug.html` dans un navigateur
- [ ] Inspecter le HTML avec F12
- [ ] Identifier le bon sélecteur CSS pour les liens
- [ ] Mettre à jour `main.py` ligne ~485
- [ ] Tester en mode non-headless
- [ ] Augmenter les délais si nécessaire
- [ ] Vérifier que l'IP n'est pas bannie

---

## 💡 Astuces Avancées

### Vérifier si LeBonCoin Charge en JS

LeBonCoin utilise probablement du **rendu côté client** (React/Vue).  
Chrome doit attendre que le JavaScript s'exécute.

**Solution** : Attendre un élément spécifique

```python
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Dans scrape_vehicles(), après driver.get(url)
try:
    # Attendre que les annonces soient chargées
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "a[href*='/voitures/']"))
    )
    print("✅ Annonces chargées !")
except:
    print("❌ Timeout : les annonces n'ont pas chargé")
```

### Contourner la Détection

```python
# Ajouter dans _get_driver()
driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
    "source": """
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined
        })
    """
})
```

---

## 🎯 Résumé Rapide

| Problème | Solution |
|----------|----------|
| Page vide | Augmenter les délais |
| CAPTCHA | Mode non-headless ou proxy |
| Sélecteurs obsolètes | Mettre à jour ligne ~485 |
| JS non chargé | Ajouter WebDriverWait |
| IP bannie | Attendre ou changer d'IP |

---

## 📞 Prochaines Actions

1. **Lancer le diagnostic** :
   ```bash
   python debug_scraper.py
   ```

2. **Regarder les fichiers générés** :
   - `leboncoin_debug.png`
   - `leboncoin_debug.html`

3. **M'envoyer les résultats** si besoin d'aide :
   - Le screenshot
   - Un extrait du HTML
   - Les logs du terminal

**Bon débogage ! 🔍**
