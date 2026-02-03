# 🚗 AutoTrack - SaaS Référencement Véhicules LeBonCoin

## 📋 Description

**AutoTrack** est un SaaS professionnel qui référence toutes les annonces de véhicules LeBonCoin en temps réel (< 3 minutes après publication). Il offre un système d'abonnement avec essai gratuit et une interface moderne ultra-professionnelle.

## ✨ Fonctionnalités

### 🔥 Core Features
- ⚡ **Détection temps réel** : Nouvelles annonces en moins de 3 minutes
- 🎯 **Score intelligent** : Algorithme de détection des bonnes affaires (0-100)
- 🔍 **Filtres avancés** : Prix, année, kilométrage, carburant, boîte, localisation
- 📸 **Images HD** : Jusqu'à 10 photos par annonce
- 🔔 **Alertes personnalisées** : Email/Push pour critères spécifiques
- 📊 **Historique** : Suivi des variations de prix

### 💎 Système d'abonnement
- **Gratuit** : 10 annonces complètes à l'inscription
- **Preview** : 5 annonces avec infos limitées (sans compte)
- **Premium** : Accès illimité + alertes + export (19,99€/mois)
- **Pro** : Premium + API + Multi-users (49,99€/mois)

### 🎨 Design Premium
- Interface sombre "Automotive Luxury"
- Glassmorphism et animations fluides
- Score visuel par barre de progression
- Typographie moderne (Outfit font)
- Responsive mobile-first

## 🏗️ Architecture

```
leboncoin-saas/
├── backend/                    # FastAPI Backend
│   ├── main.py                # API + Scraper + Auth
│   ├── requirements.txt       # Dépendances Python
│   └── scraper.py            # (Intégrez votre code ici)
│
├── frontend/                  # React Frontend
│   ├── src/
│   │   ├── App.jsx           # Point d'entrée
│   │   ├── components/       # Composants réutilisables
│   │   │   ├── Navbar.jsx
│   │   │   ├── Hero.jsx
│   │   │   ├── VehicleGrid.jsx
│   │   │   └── ...
│   │   ├── pages/            # Pages
│   │   │   ├── Login.jsx
│   │   │   ├── Register.jsx
│   │   │   ├── Dashboard.jsx
│   │   │   └── Pricing.jsx
│   │   ├── hooks/            # Custom hooks
│   │   ├── utils/            # Utilities
│   │   └── styles/           # CSS modules
│   └── package.json
│
├── database/                  # Database schemas
│   └── schema.sql
│
├── demo.html                  # Démo standalone HTML
└── README.md
```

## 🚀 Installation & Déploiement

### Prérequis
- Python 3.9+
- Node.js 18+
- Chrome (pour scraping)

### Backend Setup

```bash
cd backend

# Créer environnement virtuel
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Installer dépendances
pip install -r requirements.txt

# Lancer le serveur
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend Setup

```bash
cd frontend

# Installer dépendances
npm install

# Variables d'environnement
echo "VITE_API_URL=http://localhost:8000" > .env

# Lancer dev server
npm run dev
```

### Démo rapide (sans installation)

Ouvrez simplement `demo.html` dans votre navigateur !

## 🔧 Configuration

### Backend (`backend/main.py`)

```python
# Configuration
SECRET_KEY = "votre-clé-secrète"  # Générer avec secrets.token_urlsafe(32)

# Intégrer votre scraper
from your_scraper import StealthLeBonCoinMonitor

scraper = StealthLeBonCoinMonitor(webhook_url=None)
# Remplacer le mock dans VehicleScraper.scrape_vehicles()
```

### Stripe (Paiements)

1. Créer compte sur [Stripe](https://stripe.com)
2. Récupérer les clés API
3. Configurer :

```python
import stripe
stripe.api_key = "sk_test_..."

# Dans create_subscription()
checkout_session = stripe.checkout.Session.create(...)
```

### Base de données (Production)

Remplacer le dictionnaire en mémoire par PostgreSQL :

```bash
pip install sqlalchemy psycopg2-binary alembic
```

```python
from sqlalchemy import create_engine
engine = create_engine("postgresql://user:pass@localhost/autotrack")
```

## 📡 API Endpoints

### Authentification
- `POST /api/auth/register` - Inscription
- `POST /api/auth/login` - Connexion
- `GET /api/auth/me` - Profil utilisateur

### Véhicules
- `GET /api/vehicles` - Liste des véhicules (avec filtres)
- `GET /api/vehicles/{id}` - Détails d'un véhicule

### Abonnements
- `POST /api/subscriptions` - Créer abonnement
- `GET /api/subscriptions/me` - Mon abonnement

### Alertes
- `POST /api/alerts` - Créer alerte
- `GET /api/alerts` - Mes alertes
- `DELETE /api/alerts/{id}` - Supprimer alerte

### Stats
- `GET /api/stats` - Statistiques publiques

## 🎯 Intégration de votre scraper

Votre code existant (`scraper_discord.py`) doit être intégré dans `backend/main.py` :

```python
class VehicleScraper:
    async def scrape_vehicles(self, filters: dict = None):
        # REMPLACER LE MOCK PAR :
        
        # 1. Initialiser votre StealthLeBonCoinMonitor
        from your_code import StealthLeBonCoinMonitor
        monitor = StealthLeBonCoinMonitor(webhook_url=None)
        
        # 2. Construire l'URL avec filtres
        url = monitor.build_search_url()
        
        # 3. Scraper avec vos techniques anti-détection
        ads = monitor.get_recent_ads_stealth(max_ads=50)
        
        # 4. Formater pour l'API
        vehicles = []
        for ad in ads:
            vehicles.append({
                "id": ad['ad_id'],
                "title": ad['title'],
                "price": int(ad['price'].replace(' ', '').replace('€', '')),
                "location": ad['location'],
                "images": ad.get('images', []),
                "url": ad['url'],
                "published_at": datetime.now(),
                "score": calculate_vehicle_score(ad)
            })
        
        return vehicles
```

## 🎨 Customisation du Design

### Modifier les couleurs (`frontend/src/styles/App.css`)

```css
:root {
  --color-primary: #00d4ff;      /* Cyan électrique */
  --color-accent: #ff6b6b;       /* Rouge accent */
  --color-success: #51cf66;      /* Vert succès */
  
  /* Changer le thème complet */
  --color-bg: #0a0b0f;          /* Fond sombre */
  --color-surface: #13151b;     /* Surface */
}
```

### Modifier la police

```css
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap');

:root {
  --font-sans: 'Inter', sans-serif;
}
```

## 📊 Monitoring & Analytics

### Logs serveur
```python
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Dans le scraper
logger.info(f"✅ {len(vehicles)} annonces scrapées")
```

### Métriques
- Nombre de scans/jour
- Temps moyen de détection
- Taux de succès scraping
- Nombre d'alertes envoyées

## 🔒 Sécurité

- ✅ JWT pour authentification
- ✅ Hashage SHA-256 des mots de passe (utiliser bcrypt en prod)
- ✅ CORS configuré
- ✅ Rate limiting (à implémenter)
- ✅ HTTPS obligatoire en production

## 🚀 Déploiement Production

### Backend (Railway / Render / Fly.io)

```bash
# Dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Frontend (Vercel / Netlify)

```bash
# Build
npm run build

# Deploy sur Vercel
vercel --prod
```

### Base de données

- PostgreSQL sur Supabase (gratuit)
- ou Railway PostgreSQL
- ou Neon (serverless)

## 📈 Évolutions futures

### V2 Features
- [ ] Machine Learning pour prédiction de prix
- [ ] Comparaison multi-sites (AutoScout24, LaC entrale)
- [ ] Application mobile (React Native)
- [ ] Intégration CRM (HubSpot, Salesforce)
- [ ] Webhooks pour professionnels
- [ ] Analyse de marché par marque/modèle
- [ ] Export PDF rapports personnalisés

### Optimisations
- [ ] Redis pour cache
- [ ] Celery pour tâches asynchrones
- [ ] CDN pour images
- [ ] WebSocket pour notifications temps réel
- [ ] ElasticSearch pour recherche avancée

## 🤝 Support

- **Email** : support@autotrack.fr
- **Documentation** : docs.autotrack.fr
- **Status** : status.autotrack.fr

## 📝 Licence

Propriétaire - Tous droits réservés

## 🙏 Crédits

- Scraping : Undetected-ChromeDriver
- Backend : FastAPI
- Frontend : React + Vite
- Design : Inspiré par les SaaS modernes (Linear, Vercel)
- Paiements : Stripe

---

**Fait avec ❤️ pour les passionnés d'automobile**
