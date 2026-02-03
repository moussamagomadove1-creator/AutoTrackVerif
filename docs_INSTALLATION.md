# 📦 GUIDE D'INSTALLATION - AutoTrack

## ⚡ Installation Windows (Recommandé)

### Étape 1 : Décompresser le ZIP

```
Clic droit sur autotrack-fixed.zip → Extraire tout...
```

### Étape 2 : Installer Python

**Télécharger** : https://www.python.org/downloads/  
⚠️ **IMPORTANT** : Cocher "Add Python to PATH"

**Vérifier** :
```bash
python --version
# Doit afficher : Python 3.9+ ou supérieur
```

### Étape 3 : Installer les Dépendances

```bash
cd autotrack-fixed\backend
pip install -r requirements.txt
```

**⏳ Patience** : L'installation prend 2-3 minutes.

### Étape 4 : Lancer

**Méthode Automatique** :
```bash
# Double-cliquer sur :
start_backend.bat
```

**Méthode Manuelle** :
```bash
cd backend
python main.py
```

---

## ✅ Vérification

Si tout fonctionne :

```
INFO:     Uvicorn running on http://0.0.0.0:8001
[INFO] 🚀 Chrome (undetected) lancé (version 144)
[INFO] ✅ Scraper démarré en arrière-plan
```

**Accès** :
- 🌐 API : http://localhost:8001
- 📚 Documentation : http://localhost:8001/docs

---

## 🐧 Installation Linux/Mac

```bash
# Décompresser
unzip autotrack-fixed.zip
cd autotrack-fixed/backend

# Créer environnement virtuel
python3 -m venv venv
source venv/bin/activate

# Installer dépendances
pip install -r requirements.txt

# Lancer
python main.py
```

---

## ❌ Problèmes Courants

### Port 8001 déjà utilisé

**Solution Windows** :
```bash
# Exécuter en admin
kill_port_8000.bat
```

**Solution Linux/Mac** :
```bash
lsof -ti:8001 | xargs kill -9
```

### Python non reconnu

**Solution** : Réinstaller Python et cocher "Add to PATH"

### Module manquant

**Solution** :
```bash
pip install -r requirements.txt --force-reinstall
```

### Chrome version mismatch

**Solution** : Déjà corrigé dans main.py !

---

## 🔍 0 Annonces Trouvées ?

Si le backend démarre mais affiche "0 annonces" :

```bash
cd backend
python debug_scraper.py
```

**Lire** : `docs/TROUBLESHOOTING_SCRAPER.md`

---

## 📂 Structure après Installation

```
autotrack-fixed/
├── backend/
│   ├── main.py              ✅ Prêt
│   ├── requirements.txt     ✅ Installé
│   ├── debug_scraper.py     🔍 Pour diagnostic
│   └── .env.example         ⚙️ À configurer (optionnel)
│
├── docs/                    📚 Documentation
├── start_backend.bat        ⚡ Lanceur
└── demo.html               🎨 Démo
```

---

## 🎯 Prochaines Étapes

1. ✅ Lancer le backend
2. ✅ Ouvrir http://localhost:8001/docs
3. ✅ Tester l'API
4. ✅ Lire `docs/START_HERE.md`

**Bon démarrage ! 🚀**
