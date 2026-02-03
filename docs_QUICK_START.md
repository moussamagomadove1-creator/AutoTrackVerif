# 🚀 Guide de Démarrage Rapide - AutoTrack

## Option 1 : Démo Immédiate (0 installation)

La façon la plus rapide de voir le design et l'interface :

```bash
# Ouvrir le fichier demo.html dans votre navigateur
open demo.html  # Mac
start demo.html # Windows
xdg-open demo.html # Linux
```

✅ **Avantages** : Aucune installation, voir le design immédiatement
❌ **Limites** : Pas de backend, données statiques

---

## Option 2 : Installation Complète (Développement)

### Étape 1 : Backend Python

```bash
cd leboncoin-saas/backend

# Créer environnement virtuel
python -m venv venv

# Activer l'environnement
# Sur Windows :
venv\Scripts\activate
# Sur Mac/Linux :
source venv/bin/activate

# Installer les dépendances
pip install -r requirements.txt

# Lancer le serveur backend
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

✅ Le backend est maintenant accessible sur `http://localhost:8000`

### Étape 2 : Frontend React

**Dans un nouveau terminal** :

```bash
cd leboncoin-saas/frontend

# Installer Node.js si nécessaire
# Télécharger depuis https://nodejs.org

# Installer les dépendances
npm install

# Lancer le serveur de développement
npm run dev
```

✅ Le frontend est maintenant accessible sur `http://localhost:3000`

### Étape 3 : Tester l'application

1. Ouvrir `http://localhost:3000` dans votre navigateur
2. Cliquer sur "S'inscrire"
3. Créer un compte test :
   - Nom : Test User
   - Email : test@example.com
   - Mot de passe : test123

4. Explorer les fonctionnalités :
   - Consulter les annonces
   - Tester les filtres
   - Voir les tarifs
   - Accéder au dashboard

---

## Option 3 : Intégration de Votre Scraper

### Remplacer le scraper mock par votre code

Dans `backend/main.py`, remplacer la classe `VehicleScraper` :

```python
# AVANT (Mock actuel)
class VehicleScraper:
    async def scrape_vehicles(self, filters: dict = None):
        # Données de démonstration...
        mock_vehicles = [...]
        return mock_vehicles

# APRÈS (Votre code)
class VehicleScraper:
    def __init__(self):
        from your_scraper_file import StealthLeBonCoinMonitor
        self.monitor = StealthLeBonCoinMonitor(webhook_url=None)
    
    async def scrape_vehicles(self, filters: dict = None):
        # Utiliser votre code existant
        ads = self.monitor.get_recent_ads_stealth(max_ads=50)
        
        # Convertir au format de l'API
        vehicles = []
        for ad in ads:
            vehicles.append({
                "id": ad['ad_id'],
                "title": ad['title'],
                "price": self._parse_price(ad['price']),
                "location": ad['location'],
                "images": ad.get('images', []),
                "url": ad['url'],
                "published_at": datetime.now(),
                "score": calculate_vehicle_score(ad)
            })
        
        return vehicles
    
    def _parse_price(self, price_str: str) -> int:
        """Convertir '14 500 €' en 14500"""
        return int(price_str.replace(' ', '').replace('€', ''))
```

---

## 🔧 Configuration Avancée

### Variables d'environnement

Créer `.env` dans `backend/` :

```bash
SECRET_KEY=votre-clé-secrète-très-longue-et-sécurisée
DATABASE_URL=postgresql://user:pass@localhost/autotrack
STRIPE_SECRET_KEY=sk_test_...
STRIPE_PUBLISHABLE_KEY=pk_test_...
```

Créer `.env` dans `frontend/` :

```bash
VITE_API_URL=http://localhost:8000
VITE_STRIPE_PUBLISHABLE_KEY=pk_test_...
```

### Base de données PostgreSQL (Production)

```bash
# Installer PostgreSQL
# Mac: brew install postgresql
# Windows: https://www.postgresql.org/download/

# Créer la base
createdb autotrack

# Installer SQLAlchemy
pip install sqlalchemy psycopg2-binary alembic

# Dans backend/main.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

DATABASE_URL = "postgresql://user:password@localhost/autotrack"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
```

---

## 🎯 Checklist Mise en Production

### Backend
- [ ] Remplacer le dictionnaire en mémoire par PostgreSQL
- [ ] Configurer les variables d'environnement
- [ ] Activer HTTPS
- [ ] Implémenter rate limiting
- [ ] Utiliser bcrypt pour les mots de passe
- [ ] Configurer Stripe en mode production
- [ ] Mettre en place les logs (Sentry)
- [ ] Configurer le monitoring (Uptime Robot)

### Frontend
- [ ] Configurer les variables d'environnement de production
- [ ] Optimiser les images (lazy loading)
- [ ] Activer le PWA (Progressive Web App)
- [ ] Configurer Google Analytics
- [ ] Tester sur mobile/tablette
- [ ] Optimiser le bundle (code splitting)

### Scraper
- [ ] Tester la stabilité sur 7 jours
- [ ] Implémenter retry logic
- [ ] Ajouter des alertes en cas d'erreur
- [ ] Monitorer le taux de détection
- [ ] Gérer les changements de structure LeBonCoin

### Déploiement
- [ ] Choisir hébergeur backend (Railway, Render, Fly.io)
- [ ] Choisir hébergeur frontend (Vercel, Netlify)
- [ ] Configurer le domaine personnalisé
- [ ] Activer SSL/TLS
- [ ] Configurer les backups automatiques
- [ ] Mettre en place CI/CD (GitHub Actions)

---

## 📱 URLs Importantes

- **Backend Dev** : http://localhost:8000
- **Frontend Dev** : http://localhost:3000
- **API Docs** : http://localhost:8000/docs (Swagger)
- **Démo HTML** : Ouvrir `demo.html`

---

## 🆘 Troubleshooting

### Le backend ne démarre pas

```bash
# Vérifier la version Python
python --version  # Doit être 3.9+

# Réinstaller les dépendances
pip install --upgrade pip
pip install -r requirements.txt --force-reinstall
```

### Le frontend ne démarre pas

```bash
# Vérifier Node.js
node --version  # Doit être 18+

# Nettoyer et réinstaller
rm -rf node_modules package-lock.json
npm install
```

### Erreur CORS

Dans `backend/main.py`, vérifier :

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Ajouter votre domaine
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### Le scraper est bloqué

- Augmenter les délais entre requêtes
- Utiliser un proxy/VPN
- Tester avec des User-Agents différents
- Vérifier que Chrome est installé

---

## 💡 Conseils

1. **Développement** : Commencer par la démo HTML pour valider le design
2. **Backend** : Tester l'API avec Swagger (`/docs`)
3. **Frontend** : Utiliser React DevTools pour débugger
4. **Scraper** : Tester avec un petit volume avant de passer en production
5. **Monitoring** : Surveiller les logs dès le début

---

## 📞 Support

Si vous rencontrez des problèmes :

1. Vérifier les logs du backend et frontend
2. Consulter la documentation complète dans README.md
3. Tester la démo HTML pour isoler le problème
4. Vérifier que tous les services sont démarrés

**Bon développement ! 🚀**
