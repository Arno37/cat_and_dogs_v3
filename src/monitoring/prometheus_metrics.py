"""
═══════════════════════════════════════════════════════════════════════════════
🎯 PROMETHEUS METRICS - Export de métriques MLOps
═══════════════════════════════════════════════════════════════════════════════

📚 OBJECTIF PÉDAGOGIQUE
Ce module expose les métriques métier de l'application au format Prometheus.
Il illustre comment instrumenter une application ML pour le monitoring production.

🔑 CONCEPTS CLÉS
- Types de métriques Prometheus : Counter, Gauge, Histogram
- Instrumentation automatique vs manuelle (FastAPI)
- Labels pour dimensions multiples (segmentation des données)
- Buckets pour histogrammes (distribution des valeurs)

🔗 INTÉGRATION
- Appelé par : src/api/main.py (setup au démarrage)
- Consommé par : Prometheus (scrape /metrics toutes les 15s)
- Compatible V2 : s'ajoute au monitoring Plotly existant (complémentaire)

═══════════════════════════════════════════════════════════════════════════════
"""
from prometheus_client import Counter, Histogram, Gauge
from prometheus_fastapi_instrumentator import Instrumentator
import os
import sys  # 🆕 AJOUT

# Conditional import for Discord alerting
alert_high_latency = None
try:
    from src.monitoring.discord_notifier import alert_high_latency as _alert_high_latency
    alert_high_latency = _alert_high_latency
    print("✅ Discord alert_high_latency imported", file=sys.stderr, flush=True)
except ImportError:
    print("⚠️ Discord alerting not available", file=sys.stderr, flush=True)

# ═══════════════════════════════════════════════════════════════════════════
# 📊 MÉTRIQUES CUSTOM - Spécifiques au modèle CV cats/dogs
# ═══════════════════════════════════════════════════════════════════════════

# ─────────────────────────────────────────────────────────────────────────────
# 📏 GAUGE : Valeur pouvant monter ET descendre (snapshot de l'état actuel)
# ─────────────────────────────────────────────────────────────────────────────
database_status = Gauge(
    'cv_database_connected',
    'Database connection status (1=connected, 0=disconnected)'
)
# 💡 USAGE
# - .set(1) : marque comme connecté
# - .set(0) : marque comme déconnecté
#
# 🎯 CAS D'USAGE
# - Monitoring santé infrastructure (alerte si = 0)
# - Corrélation : échecs prédictions ↔ base déconnectée ?
#
# 📈 QUERY PROMQL POUR ALERTE
# - cv_database_connected == 0 : déclenche alerte Discord

# ─────────────────────────────────────────────────────────────────────────────
# 📊 COUNTER : Valeur toujours croissante (compte des événements)
# ─────────────────────────────────────────────────────────────────────────────
predictions_total = Counter(
    'cv_predictions_total',
    'Total number of predictions',
    ['result', 'success']
)
# 💡 LABELS
# - result : 'cat', 'dog', 'error'
# - success : 'true', 'false'
#
# 🎯 USAGE
# predictions_total.labels(result='cat', success='true').inc()
#
# 📈 QUERY PROMQL
# - rate(cv_predictions_total[5m]) : prédictions par seconde
# - sum by (result)(cv_predictions_total) : total par classe

# ─────────────────────────────────────────────────────────────────────────────
# 📊 HISTOGRAM : Distribution des valeurs (latence, confiance, etc.)
# ─────────────────────────────────────────────────────────────────────────────
inference_duration = Histogram(
    'cv_inference_duration_seconds',
    'Inference time in seconds',
    buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
)
# 💡 BUCKETS
# Définissent les intervalles de temps (en secondes)
# [0.1, 0.25, 0.5, 1.0, ...] permet de mesurer :
# - Combien de prédictions < 100ms
# - Combien entre 100ms et 250ms
# - etc.
#
# 🎯 USAGE
# with inference_duration.time():
#     result = model.predict(image)
#
# 📈 QUERY PROMQL
# - histogram_quantile(0.95, cv_inference_duration_seconds) : P95 latence
# - avg(cv_inference_duration_seconds_sum / cv_inference_duration_seconds_count) : moyenne

prediction_confidence = Histogram(
    'cv_prediction_confidence',
    'Model confidence score',
    labelnames=['result'],
    buckets=[0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 0.99, 1.0]
)
# 💡 TRACKING CONFIANCE
# Permet de détecter si le modèle devient moins sûr → drift potentiel
#
# 📈 QUERY PROMQL
# - histogram_quantile(0.5, cv_prediction_confidence) : médiane confiance

# 🆕 FEEDBACK UTILISATEUR
cv_user_feedback_total = Counter(
    'cv_user_feedback_total',
    'Nombre de feedbacks utilisateurs collectés',
    ['feedback_type']  # 'positive' ou 'negative'
)

def track_user_feedback(feedback_type: str):
    """
    Enregistre un feedback utilisateur
    
    Args:
        feedback_type: 'positive' (1) ou 'negative' (0)
    """
    try:
        valid_types = ['positive', 'negative']
        if feedback_type not in valid_types:
            print(f"⚠️  Invalid feedback_type: {feedback_type}. Expected: {valid_types}")
            return
        
        cv_user_feedback_total.labels(feedback_type=feedback_type).inc()
        print(f"✅ Tracked user feedback: {feedback_type}")
    except Exception as e:
        print(f"⚠️  Failed to track feedback: {e}")

cv_last_inference_seconds = Gauge(
    'cv_last_inference_seconds',
    'Inference time (seconds) for the most recent request'
)

# 🆕 AVERAGE INFERENCE TIME
cv_avg_inference_seconds = Gauge(
    'cv_avg_inference_seconds',
    'Average inference time (seconds) for all predictions'
)

# 🆕 INFERENCE TIME IN MS FOR ALERTING
cv_inferencetime_ms = Gauge(
    'cv_inferencetime_ms',
    'Latest inference time in milliseconds (for alerting)'
)

def update_last_inference(duration: float):
    print(f"DEBUG: update_last_inference called with {duration}", file=sys.stderr, flush=True)
    try:
        # Update both metrics
        cv_last_inference_seconds.set(duration)
        cv_inferencetime_ms.set(duration * 1000)  # Convert seconds to milliseconds
        
        print(f"✅ Updated inference metrics: {duration:.3f}s / {duration*1000:.0f}ms")
        
        # Check for high latency alert
        if alert_high_latency and duration * 1000 > 1000:  # 1000ms threshold
            print(f"🚨 High latency detected: {duration*1000:.0f}ms > 1000ms", file=sys.stderr, flush=True)
            alert_high_latency(duration * 1000, threshold=1000)
            
    except Exception as e:
        print(f"⚠️ Failed to update inference metrics: {e}", file=sys.stderr, flush=True)

# 🆕 COUNTER HTTP REQUESTS
from prometheus_client import Counter  # 🆕

# counter des requêtes HTTP (label 'method' pour GET/POST)
cv_http_requests_total = Counter(
    "cv_http_requests_total",
    "Total number of HTTP requests processed by the CV app",
    ["method", "endpoint"]
)

def inc_http_request(method: str, endpoint: str) -> None:
    """
    Incrémente le compteur de requêtes HTTP.
    """
    try:
        cv_http_requests_total.labels(method=method.upper(), endpoint=endpoint).inc()
    except Exception:
        # ne pas planter l'app si Prometheus absent
        pass

# ═══════════════════════════════════════════════════════════════════════════
# 🔧 SETUP - Configuration de l'instrumentation Prometheus
# ═══════════════════════════════════════════════════════════════════════════
def setup_prometheus(app):
    """
    Configure Prometheus pour FastAPI
    Compatible avec l'API existante V2
    
    🎯 INSTRUMENTATION AUTOMATIQUE
    Le Instrumentator ajoute automatiquement :
    - http_request_duration_seconds : latence par endpoint
    - http_requests_total : nombre de requêtes par status code
    - http_requests_in_progress : requêtes concurrentes
    
    💡 ENDPOINT /metrics
    Exposé automatiquement au format Prometheus :
    # HELP cv_predictions_total Total number of predictions
    # TYPE cv_predictions_total counter
    cv_predictions_total{result="cat"} 42.0
    cv_predictions_total{result="dog"} 38.0
    
    Args:
        app: Instance FastAPI
    """
    if os.getenv('ENABLE_PROMETHEUS', 'false').lower() == 'true':
        # 📊 INSTRUMENTATION EN 2 ÉTAPES
        # 1. instrument(app) : ajoute middleware pour métriques auto
        # 2. expose(app, endpoint="/metrics") : crée route GET /metrics
        Instrumentator().instrument(app).expose(app, endpoint="/metrics")
        print("✅ Prometheus metrics enabled at /metrics")
        
        # 💡 FORMAT DE SORTIE /metrics
        # Texte brut (Content-Type: text/plain)
        # Scrapable par Prometheus toutes les 15s (cf. prometheus.yml)
    else:
        print("ℹ️  Prometheus metrics disabled")
        # Utile en dev si on veut alléger le monitoring

# ═══════════════════════════════════════════════════════════════════════════
# 📝 HELPERS - Fonctions de tracking appelées par l'API
# ═══════════════════════════════════════════════════════════════════════════

def update_db_status(is_connected: bool):
    """
    Met à jour le statut de la base de données
    
    🔗 APPELÉ PAR : healthcheck ou retry logic de connexion DB
    
    Args:
        is_connected: True si connexion PostgreSQL active
    
    💡 EXEMPLE D'INTÉGRATION
    try:
        db.execute("SELECT 1")
        update_db_status(True)
    except Exception:
        update_db_status(False)
        # Alerte Grafana se déclenche automatiquement
    """
    database_status.set(1 if is_connected else 0)

def track_prediction(result: str, inference_time_ms: int, confidence: float, success: bool = True):
    """
    Track une prédiction dans Prometheus
    
    🔗 APPELÉ PAR : /api/predict après chaque inférence
    
    Args:
        result: 'cat', 'dog', ou 'error'
        inference_time_ms: Temps d'inférence en millisecondes
        confidence: Score de confiance (0.0 à 1.0)
        success: True si prédiction réussie
    
    💡 EXEMPLE D'INTÉGRATION
    result = model.predict(image)
    track_prediction(
        result='cat',
        inference_time_ms=250,
        confidence=0.95,
        success=True
    )
    """
    # Incrémenter compteur de prédictions
    predictions_total.labels(
        result=result,
        success=str(success).lower()
    ).inc()
    
    # Enregistrer temps d'inférence (conversion ms → secondes)
    inference_duration.observe(inference_time_ms / 1000.0)
    
    # Mettre à jour la moyenne d'inférence
    try:
        print(f"🔍 DEBUG: Calling track_inference_time with {inference_time_ms / 1000.0:.3f}s", file=sys.stderr, flush=True)
        track_inference_time(inference_time_ms / 1000.0)
        print(f"✅ track_inference_time called successfully", file=sys.stderr, flush=True)
    except Exception as e:
        print(f"❌ ERROR calling track_inference_time: {e}", file=sys.stderr, flush=True)
    
    # Enregistrer confiance du modèle
    if result != 'error':
        prediction_confidence.labels(result=result).observe(confidence)


# Variables globales pour le calcul de la moyenne
_inference_sum = 0.0
_inference_count = 0

def track_inference_time(duration: float):
    """Track inference time in histogram and update average."""
    global _inference_sum, _inference_count
    try:
        # Enregistre dans l'histogramme
        inference_duration.observe(duration)
        
        # Met à jour les compteurs pour la moyenne
        _inference_sum += duration
        _inference_count += 1
        
        # Calcule et met à jour la moyenne
        avg = _inference_sum / _inference_count
        cv_avg_inference_seconds.set(avg)
        
        print(f"✅ Tracked inference {duration:.3f}s | Avg: {avg:.3f}s (n={_inference_count})", file=sys.stderr, flush=True)
    except Exception as e:
        print(f"❌ ERROR tracking inference time: {e}", file=sys.stderr, flush=True)

# ═══════════════════════════════════════════════════════════════════════════
# 🎓 CONCEPTS AVANCÉS (pour aller plus loin)
# ═══════════════════════════════════════════════════════════════════════════
#
# 1. MÉTRIQUES SUPPLÉMENTAIRES UTILES
#    - model_version (Gauge avec label 'version') : tracking déploiements
#    - input_image_size (Histogram) : détection images hors distribution
#    - gpu_memory_usage (Gauge) : monitoring ressources (si GPU disponible)
#
# 2. CARDINALITY (nombre de combinaisons de labels)
#    ⚠️ Attention : trop de labels = explosion mémoire Prometheus
#    Exemple à ÉVITER : .labels(user_id=...) avec 1M users
#    Limite raisonnable : <10 valeurs par label
#
# 3. MÉTRIQUES VS LOGS
#    - Métriques : agrégées, numériques, queryable (dashboards, alertes)
#    - Logs : détaillés, textuels, debugging (ex: traceback erreurs)
#    Les deux sont complémentaires (pas l'un OU l'autre)
#
# 4. TESTS DES MÉTRIQUES
#    import pytest
#    def test_track_prediction():
#        before = predictions_total._value.get()
#        track_prediction('cat', 100, 0.95)
#        assert predictions_total._value.get() == before + 1
#
# ═══════════════════════════════════════════════════════════════════════════
# 📚 RESSOURCES PÉDAGOGIQUES
# ═══════════════════════════════════════════════════════════════════════════
#
# - Prometheus best practices: https://prometheus.io/docs/practices/naming/
# - Types de métriques expliqués: https://prometheus.io/docs/concepts/metric_types/
# - PromQL tutorial: https://prometheus.io/docs/prometheus/latest/querying/basics/
# - FastAPI Instrumentator: https://github.com/trallnag/prometheus-fastapi-instrumentator
#
# ═══════════════════════════════════════════════════════════════════════════