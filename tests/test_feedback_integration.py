#!/usr/bin/env python3
"""Test simple pour vérifier que les feedbacks sont enregistrés en DB"""
import httpx
import sys
from pathlib import Path

# Configuration
API_BASE_URL = "http://localhost:8002"  # STUDENT_PORT_API depuis .env
API_TOKEN = "?C@TSD0GS!"
TEST_IMAGE = Path(__file__).parent.parent / "data" / "raw" / "PetImages" / "Cat" / "0.jpg"

def test_health():
    """Test du healthcheck"""
    print("🏥 Test healthcheck...")
    response = httpx.get(f"{API_BASE_URL}/health", timeout=10)
    print(f"   Status: {response.status_code}")
    data = response.json()
    print(f"   Database: {data.get('database')}")
    print(f"   Model loaded: {data.get('model_loaded')}")
    assert response.status_code == 200
    assert data['status'] in ['healthy', 'degraded']
    print("   ✅ Healthcheck OK\n")

def test_prediction():
    """Test de prédiction avec insertion en DB"""
    print("🧠 Test prédiction...")
    
    if not TEST_IMAGE.exists():
        print(f"   ⚠️  Image de test non trouvée: {TEST_IMAGE}")
        print("   Utilisation d'une image factice...")
        # Créer une petite image test
        from PIL import Image
        img = Image.new('RGB', (128, 128), color='red')
        test_file = Path(__file__).parent / "test_cat.jpg"
        img.save(test_file)
        image_path = test_file
    else:
        image_path = TEST_IMAGE
    
    # Envoi de la prédiction
    with open(image_path, 'rb') as f:
        files = {'file': ('test_cat.jpg', f, 'image/jpeg')}
        data = {'rgpd_consent': 'true'}
        headers = {'Authorization': f'Bearer {API_TOKEN}'}
        
        response = httpx.post(
            f"{API_BASE_URL}/api/predict",
            files=files,
            data=data,
            headers=headers,
            timeout=30
        )
    
    print(f"   Status: {response.status_code}")
    if response.status_code == 200:
        result = response.json()
        print(f"   Prédiction: {result.get('prediction')}")
        print(f"   Confiance: {result.get('confidence')}")
        print(f"   Feedback ID: {result.get('feedback_id')}")
        print("   ✅ Prédiction réussie\n")
        return result.get('feedback_id')
    else:
        print(f"   ❌ Erreur: {response.text}")
        return None

def verify_in_database():
    """Vérification directe en base de données"""
    print("🗄️  Vérification en base de données...")
    
    # Import après s'assurer que .env est chargé
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from src.database.db_connector import get_db_session
    from src.database.models import PredictionFeedback
    
    db = get_db_session()
    try:
        # Compter les enregistrements
        count = db.query(PredictionFeedback).count()
        print(f"   Nombre total d'enregistrements: {count}")
        
        # Récupérer le dernier
        if count > 0:
            last = db.query(PredictionFeedback).order_by(
                PredictionFeedback.id.desc()
            ).first()
            print(f"   Dernier enregistrement:")
            print(f"     - ID: {last.id}")
            print(f"     - Résultat: {last.prediction_result}")
            print(f"     - Confiance cat: {last.proba_cat}%")
            print(f"     - Confiance dog: {last.proba_dog}%")
            print(f"     - Temps inférence: {last.inference_time_ms}ms")
            print(f"     - RGPD consent: {last.rgpd_consent}")
            print(f"     - Timestamp: {last.created_at}")
            print("   ✅ Feedback bien enregistré en base !")
        else:
            print("   ⚠️  Aucun enregistrement trouvé")
        
        return count
    finally:
        db.close()

if __name__ == "__main__":
    try:
        # Test 1: Health check
        test_health()
        
        # Test 2: Prédiction
        feedback_id = test_prediction()
        
        # Test 3: Vérification DB
        count = verify_in_database()
        
        print("\n" + "="*60)
        if feedback_id and count > 0:
            print("✅ SUCCÈS: Les feedbacks sont bien enregistrés en base !")
        else:
            print("❌ ÉCHEC: Les feedbacks ne sont pas enregistrés")
            sys.exit(1)
        print("="*60)
        
    except Exception as e:
        print(f"\n❌ Erreur: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
