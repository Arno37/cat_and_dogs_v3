from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
import sys
from pathlib import Path
import os
from apscheduler.schedulers.background import BackgroundScheduler
from src.monitoring.prometheus_metrics import track_feedback
import atexit

# Ajouter le répertoire racine au path
ROOT_DIR = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT_DIR))

from .routes import router

# V3 - Import optionnel Prometheus
ENABLE_PROMETHEUS = os.getenv('ENABLE_PROMETHEUS', 'false').lower() == 'true'

if ENABLE_PROMETHEUS:
    try:
        from src.monitoring.prometheus_metrics import setup_prometheus
        print("✅ Prometheus metrics module loaded")
    except ImportError:
        print("⚠️  Prometheus metrics not available (install requirements/monitoring.txt)")
        ENABLE_PROMETHEUS = False

# 🔄 Scheduler pour mettre à jour métriques feedback chaque minute
scheduler = BackgroundScheduler()

def scheduled_track_feedback():
    """Tâche schedulée toutes les minutes"""
    try:
        track_feedback()
    except Exception as e:
        print(f"⚠️ Scheduled feedback tracking failed: {e}", file=sys.stderr, flush=True)

# ✅ CRÉER app AVANT d'utiliser @app.on_event()
app = FastAPI(
    title="🐱🐶 Cats vs Dogs Classifier",
    description="""
**API complète de Computer Vision avec monitoring intégré pour classifier des images de chats et de chiens**

## 🎯 Fonctionnalités

**🧠 Modèle d'IA**
* Architecture : CNN (Convolutional Neural Network)
* Framework : Keras × TensorFlow
* Classes : Chat 🐱 | Chien 🐶

**🔬 Testez le modèle**
* Uploadez vos propres images
* Obtenez les probabilités de prédiction
* Temps d'inférence en temps réel

**📊 Monitoring & Analytics**
* Enregistrement des prédictions en PostgreSQL
* Collecte de feedback utilisateur (avec consentement RGPD)
* Statistiques d'utilisation et de performance
* 🆕 **V3** : Métriques Prometheus temps réel
* 🆕 **V3** : Dashboards Grafana externes
* 🆕 **V3** : Alerting Discord automatique

## 🔐 Authentification

L'API utilise un **Bearer Token** pour sécuriser les endpoints d'inférence.

Format : `Authorization: Bearer <votre_token>`

## 📈 Endpoints principaux

**Routes Web**
* `/` - Interface web principale
* `/inference` - Page de test du modèle
* `/info` - Informations sur le modèle

**Routes API**
* `POST /api/predict` - Endpoint de prédiction
* `GET /api/statistics` - Statistiques du monitoring
* `GET /api/recent-predictions` - Dernières prédictions
* `POST /api/update-feedback` - Mise à jour du feedback
* `GET /health` - État de santé de l'API
* 🆕 `GET /metrics` - Métriques Prometheus (V3)

## 🛡️ RGPD

Le système respecte le RGPD :
* ✅ Consentement explicite de l'utilisateur
* ✅ Données personnelles stockées uniquement avec accord
* ✅ Métriques anonymes par défaut

## 📚 Documentation

* **Swagger UI** : `/docs` (cette page)
* **ReDoc** : `/redoc` (documentation alternative)
* **OpenAPI JSON** : `/openapi.json`

**Version** : 3.0.0 | **License** : MIT
    """,
    version="3.0.0",  # 🆕 Version mise à jour
    contact={
        "name": "Rémi Julien",
        "url": "https://github.com/remijul/computer-vision-cats-and-dogs-v3",  # 🆕
    },
    license_info={
        "name": "MIT",
        "url": "https://opensource.org/licenses/MIT",
    }
)

# 🆕 V3 - Configuration Prometheus (optionnelle, n'affecte pas V2)
if ENABLE_PROMETHEUS:
    try:
        setup_prometheus(app)
        print("✅ Prometheus metrics enabled at /metrics")
    except Exception as e:
        print(f"⚠️  Could not setup Prometheus: {e}")

# Ajouter les routes
app.include_router(router)

# ✅ EVENT HANDLERS - Maintenant app est défini
@app.on_event("startup")
async def startup_event():
    scheduler.add_job(scheduled_track_feedback, 'interval', minutes=1, id='track_feedback')
    scheduler.start()
    print("✅ Feedback tracking scheduler started", file=sys.stderr, flush=True)

# Arrêter proprement
@app.on_event("shutdown")
async def shutdown_event():
    scheduler.shutdown()
    print("✅ Feedback tracking scheduler stopped", file=sys.stderr, flush=True)

atexit.register(lambda: scheduler.shutdown())

# Optionnel : servir des fichiers statiques
STATIC_DIR = ROOT_DIR / "src" / "web" / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")