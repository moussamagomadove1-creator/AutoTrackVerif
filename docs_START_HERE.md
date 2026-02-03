# 🚀 GUIDE DE DÉMARRAGE RAPIDE - VERSION CORRIGÉE

## ⚡ Solution Rapide (2 minutes)

### Étape 1 : Libérer le Port 8000

**Méthode 1 - Script Automatique** (Recommandé)
```bash
# Exécuter en tant qu'administrateur
kill_port_8000.bat
```

**Méthode 2 - Manuelle**
```bash
# Trouver le processus
netstat -ano | findstr :8000

# Noter le PID (dernière colonne), puis :
taskkill /PID <numero> /F
```

### Étape 2 : Utiliser le Fichier Corrigé

**Remplacer votre main.py** :
1. Renommer l'ancien : `main.py` → `main.py.old`
2. Renommer le nouveau : `main_fixed.py` → `main.py`

### Étape 3 : Lancer

```bash
python main.py
```

**✅ Résultat Attendu** :
```
INFO:     Uvicorn running on http://0.0.0.0:8001
06:XX:XX [INFO] 🚀 Chrome (undetected) lancé (version 144)
06:XX:XX [INFO] ✅ Scraper démarré en arrière-plan
```

---

## 🔍 Ce Qui a Été Corrigé

### ✅ Correction 1 : Version Chrome
```python
# Ligne 357-363 (main_fixed.py)
self.driver = uc.Chrome(
    options=options, 
    version_main=144,  # ← FIX ICI
    use_subprocess=True
)
```

**Avant** : ChromeDriver 145 téléchargé automatiquement  
**Après** : ChromeDriver 144 pour correspondre à votre Chrome

### ✅ Correction 2 : Port
```python
# Ligne 1090 (main_fixed.py)
uvicorn.run(app, host="0.0.0.0", port=8001)  # ← FIX ICI
```

**Avant** : Port 8000 (occupé)  
**Après** : Port 8001 (libre)

---

## 📋 Checklist de Démarrage

- [ ] Processus Python en cours tués
- [ ] Port 8000 ou 8001 libre
- [ ] Fichier `main_fixed.py` renommé en `main.py`
- [ ] Chrome installé (version 144 ou 145)
- [ ] Dépendances installées : `pip install -r requirements.txt`

---

## 🌐 Accès aux Services

| Service | URL | Description |
|---------|-----|-------------|
| **API Backend** | http://localhost:8001 | API principale |
| **Swagger Docs** | http://localhost:8001/docs | Documentation interactive |
| **Frontend** | http://localhost:3000 | Interface React (si lancé) |

---

## ⚠️ Dépannage

### Problème : "Chrome version 144"
**Solution** : Le fichier corrigé force déjà version 144. Rien à faire.

### Problème : "Port déjà utilisé"
**Solution** :
```bash
# Exécuter en admin
kill_port_8000.bat
```

### Problème : "Module uc not found"
**Solution** :
```bash
pip install undetected-chromedriver==3.5.5
```

### Problème : Chrome ne démarre pas
**Solution** :
```bash
# Nettoyer le cache UC
# Windows
rd /s /q "%APPDATA%\undetected_chromedriver"

# Puis relancer
python main.py
```

---

## 🎯 Prochaines Étapes

1. ✅ **Tester l'API** : Ouvrir http://localhost:8001/docs
2. ✅ **Voir les véhicules** : GET `/api/vehicles`
3. ✅ **Créer un compte** : POST `/api/auth/register`
4. ✅ **Lancer le frontend** : `cd frontend && npm run dev`

---

## 📱 Configuration Frontend (Optionnel)

Si vous voulez aussi lancer le frontend React :

**Fichier : frontend/.env**
```bash
VITE_API_URL=http://localhost:8001
```

**Commandes** :
```bash
cd frontend
npm install
npm run dev
```

**Accès** : http://localhost:3000

---

## 💡 Astuces

### Voir les Logs en Temps Réel
Le backend affiche automatiquement :
- 🚀 Démarrage du scraper
- 🔄 Cycles de scraping (toutes les 3 min)
- ✅ Nouvelles annonces détectées
- ❌ Erreurs éventuelles

### Tester le Scraping Manuellement
```bash
# Dans un autre terminal
curl http://localhost:8001/api/admin/scrape-now
```

### Vérifier Chrome
```bash
# Windows
"C:\Program Files\Google\Chrome\Application\chrome.exe" --version

# Doit afficher : 144.0.7559.110 ou 145.x.xxxx.xxx
```

---

## 📞 Besoin d'Aide ?

**Erreurs communes** :
1. Port occupé → Utiliser `kill_port_8000.bat`
2. Chrome incompatible → `main_fixed.py` force la bonne version
3. Module manquant → `pip install -r requirements.txt`

**Logs utiles** :
- Les logs montrent chaque étape du scraping
- Chercher `[ERROR]` pour identifier les problèmes
- `[INFO]` montre le fonctionnement normal

---

**Bon développement ! 🚗💨**
