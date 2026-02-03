# 🚗 AutoTrack - Version Simplifiée (Tous les fichiers ensemble)

> **Référencement automatique des véhicules LeBonCoin en temps réel**

## ✨ Cette Version

✅ **Structure simplifiée** : Tous les fichiers au même niveau, pas de sous-dossiers  
✅ **Facile à utiliser** : Lancez directement `main.py` ou `start_backend.bat`  
✅ **Fix ChromeDriver** : Version 144 forcée pour compatibilité  
✅ **Port 8001** : Évite les conflits de port

---

## 📁 Structure du Projet (SIMPLIFIÉE)

Tous les fichiers sont maintenant au même niveau :

```
autotrack-tout-ensemble/
│
├── main.py                       ⭐ Fichier principal du backend
├── requirements.txt              📦 Dépendances Python
├── .env.example                  🔧 Configuration
├── demo.html                     🎨 Démo visuelle (sans backend)
│
├── start_backend.bat             ⚡ Lanceur automatique Windows
├── kill_port_8000.bat            🔧 Libérer le port (Windows)
├── kill_port_8000.ps1            🔧 Libérer le port (PowerShell)
│
├── debug_scraper.py              🔍 Script de diagnostic
├── backend_debug_page.html       🐛 Page de debug
├── backend_leboncoin_debug.html  🐛 Debug LeBonCoin
│
├── README.md                     📄 README original
├── README_SIMPLE.md              📄 Ce fichier
│
└── docs_*.md                     📚 Documentation (7 fichiers)
```

---

## 🚀 Installation Rapide (3 Étapes)

### 1️⃣ Installer Python

**Télécharger** : https://www.python.org/downloads/  
⚠️ **Cocher "Add Python to PATH"**

**Vérifier** :
```bash
python --version
```

### 2️⃣ Installer les Dépendances

```bash
pip install -r requirements.txt
```

### 3️⃣ Lancer le Backend

**Option A - Script automatique** (Recommandé pour Windows) :
```bash
# Double-cliquer sur :
start_backend.bat
```

**Option B - Manuel** :
```bash
python main.py
```

**✅ Accès** :
- API : http://localhost:8001
- Documentation : http://localhost:8001/docs

---

## 🔧 Différences avec la Version Originale

### ❌ Avant (avec sous-dossiers)
```
autotrack-fixed/
├── backend/
│   ├── main.py
│   ├── requirements.txt
│   └── debug_scraper.py
├── docs/
│   ├── README.md
│   └── ...
└── demo.html
```

### ✅ Maintenant (tout au même niveau)
```
autotrack-tout-ensemble/
├── main.py
├── requirements.txt
├── debug_scraper.py
├── demo.html
├── docs_README.md
└── ...
```

**Avantages** :
- ✅ Pas besoin de naviguer entre dossiers
- ✅ Scripts `.bat` simplifiés
- ✅ Tout visible au même endroit
- ✅ Plus facile pour les débutants

---

## 🔍 Problème "0 annonces trouvées" ?

### Lancer le Diagnostic

```bash
python debug_scraper.py
```

**Ce script va** :
- Ouvrir Chrome en mode visible
- Prendre un screenshot
- Sauvegarder le HTML
- Tester les sélecteurs CSS
- Identifier le problème

**Fichiers générés** :
- `leboncoin_debug.png` - Capture d'écran
- `leboncoin_debug.html` - Code source

**Guide complet** : `docs_TROUBLESHOOTING_SCRAPER.md`

---

## 📚 Documentation

Tous les fichiers de documentation sont préfixés avec `docs_` :

| Fichier | Description |
|---------|-------------|
| `docs_START_HERE.md` | 🚀 Démarrage rapide |
| `docs_INSTALLATION.md` | 📦 Guide d'installation |
| `docs_TROUBLESHOOTING_SCRAPER.md` | 🔍 Résolution "0 annonces" |
| `docs_CORRECTIONS.md` | 🔧 Détails techniques |
| `docs_PROJECT_SUMMARY.md` | 📋 Vue d'ensemble |
| `docs_QUICK_START.md` | ⚡ Guide rapide |
| `docs_README.md` | 📖 Documentation complète |

---

## ⚠️ Dépannage

### Port déjà utilisé
```bash
# Exécuter en admin
kill_port_8000.bat
```

### Chrome ne démarre pas
```bash
# Nettoyer le cache
rd /s /q "%APPDATA%\undetected_chromedriver"
python main.py
```

### Module manquant
```bash
pip install -r requirements.txt --force-reinstall
```

### 0 annonces trouvées
```bash
# Lancer le diagnostic
python debug_scraper.py

# Lire le guide
docs_TROUBLESHOOTING_SCRAPER.md
```

---

## 🎯 Test Rapide

### 1. Tester l'API

```bash
# Ouvrir dans un navigateur
http://localhost:8001/docs
```

### 2. Récupérer les véhicules

```bash
curl http://localhost:8001/api/vehicles
```

### 3. Forcer un scrape

```bash
curl http://localhost:8001/api/admin/scrape-now
```

---

## ✨ Fonctionnalités

### 🔥 Core
- ⚡ Détection temps réel (< 3 min)
- 🎯 Score intelligent (0-100)
- 🔍 Filtres avancés
- 📸 Images HD (10 max)
- 🔔 Alertes personnalisées
- 📊 Historique

### 💎 Abonnements
- **Gratuit** : 10 annonces
- **Premium** : Illimité (19,99€/mois)
- **Pro** : Premium + API (49,99€/mois)

### 🎨 Design
- Interface sombre
- Glassmorphism
- Animations fluides
- Responsive

---

## 💡 Prochaines Étapes

1. ✅ Tester la démo : Ouvrir `demo.html`
2. ✅ Lire `docs_START_HERE.md`
3. ✅ Lancer le backend : `start_backend.bat` ou `python main.py`
4. ✅ Tester l'API : http://localhost:8001/docs
5. ✅ Si 0 annonces : `python debug_scraper.py`

---

**Fait avec ❤️ pour les passionnés d'automobile 🚗💨**

Version : 1.2 Simplifiée (Février 2025)
