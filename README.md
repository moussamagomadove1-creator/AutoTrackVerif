# 🚗 AutoTrack - SaaS LeBonCoin (VERSION CORRIGÉE)

> **Référencement automatique des véhicules LeBonCoin en temps réel**

## 🎉 Cette Version Inclut

✅ **Fix ChromeDriver** : Version 144 forcée pour compatibilité  
✅ **Port 8001** : Évite les conflits de port  
✅ **Script de Diagnostic** : Pour déboguer le scraping  
✅ **Documentation Complète** : 6 guides inclus  
✅ **Scripts de Démarrage** : Lanceur automatique Windows

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
cd backend
pip install -r requirements.txt
```

### 3️⃣ Lancer le Backend

**Option A - Script automatique** (Recommandé) :
```bash
# Double-cliquer sur :
start_backend.bat
```

**Option B - Manuel** :
```bash
cd backend
python main.py
```

**✅ Accès** :
- API : http://localhost:8001
- Documentation : http://localhost:8001/docs

---

## 📁 Structure du Projet

```
autotrack-fixed/
│
├── 📄 README.md                  Ce fichier
├── 📄 demo.html                  Démo visuelle (sans backend)
│
├── ⚡ start_backend.bat          Lanceur automatique Windows
├── 🔧 kill_port_8000.bat        Libérer le port (Windows)
├── 🔧 kill_port_8000.ps1        Libérer le port (PowerShell)
│
├── 📂 backend/
│   ├── main.py                  ✅ Backend corrigé
│   ├── requirements.txt         Dépendances Python
│   ├── .env.example             Configuration
│   └── debug_scraper.py         🔍 Script de diagnostic
│
└── 📂 docs/
    ├── README.md                Documentation complète
    ├── QUICK_START.md           Guide rapide
    ├── PROJECT_SUMMARY.md       Vue d'ensemble
    ├── START_HERE.md            Démarrage
    ├── CORRECTIONS.md           Détails des corrections
    ├── INSTALLATION.md          Guide d'installation
    └── TROUBLESHOOTING_SCRAPER.md  Résolution des problèmes
```

---

## 🔧 Corrections Appliquées

### ✅ Fix #1 : ChromeDriver Version 144
```python
# backend/main.py ligne 357
self.driver = uc.Chrome(
    options=options, 
    version_main=144,  # ← Compatible avec Chrome 144
    use_subprocess=True
)
```

### ✅ Fix #2 : Port 8001
```python
# backend/main.py ligne 1090
uvicorn.run(app, host="0.0.0.0", port=8001)
```

---

## 🔍 Problème "0 annonces trouvées" ?

### Lancer le Diagnostic

```bash
cd backend
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

**Guide complet** : `docs/TROUBLESHOOTING_SCRAPER.md`

---

## 📚 Documentation

| Fichier | Description |
|---------|-------------|
| `docs/START_HERE.md` | 🚀 Démarrage rapide |
| `docs/INSTALLATION.md` | 📦 Guide d'installation |
| `docs/TROUBLESHOOTING_SCRAPER.md` | 🔍 Résolution "0 annonces" |
| `docs/CORRECTIONS.md` | 🔧 Détails techniques |
| `docs/PROJECT_SUMMARY.md` | 📋 Vue d'ensemble |

**Ordre de lecture recommandé** :
1. START_HERE.md
2. INSTALLATION.md
3. TROUBLESHOOTING_SCRAPER.md (si 0 annonces)

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
python backend/debug_scraper.py

# Lire le guide
docs/TROUBLESHOOTING_SCRAPER.md
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

## 🌐 Déploiement Production

### Backend
- **Railway** : https://railway.app
- **Render** : https://render.com
- **Fly.io** : https://fly.io

### Database
- **Supabase** : PostgreSQL gratuit
- **Railway** : PostgreSQL inclus

### Configuration

```bash
# Copier .env.example → .env
cd backend
cp .env.example .env

# Modifier les valeurs
SECRET_KEY=votre-clé-générée
DATABASE_URL=postgresql://...
```

---

## 💡 Prochaines Étapes

1. ✅ Tester la démo : Ouvrir `demo.html`
2. ✅ Lire `docs/START_HERE.md`
3. ✅ Lancer le backend : `start_backend.bat`
4. ✅ Tester l'API : http://localhost:8001/docs
5. ✅ Si 0 annonces : `python backend/debug_scraper.py`

---

## 📞 Support

**En cas de problème** :
1. Consulter `docs/TROUBLESHOOTING_SCRAPER.md`
2. Lancer `debug_scraper.py`
3. Vérifier les logs du terminal
4. Chercher `[ERROR]` dans les logs

---

**Fait avec ❤️ pour les passionnés d'automobile 🚗💨**

Version : 1.2 (Février 2025)
