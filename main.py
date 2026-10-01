import os
from dotenv import load_dotenv
from flask import Flask, request, jsonify, send_from_directory
import requests
import json
import random

# --- CONFIGURATION ENVIRONNEMENT ---
load_dotenv()

SE_LOGIN = os.getenv("SE_LOGIN")
SE_API_KEY = os.getenv("SE_API_KEY")

app = Flask(__name__, static_folder='.')

# Route principale : Affiche index.html
@app.route('/')
def home():
    return send_from_directory('.', 'index.html')

# --- LOGIQUE MÉTIER CENTRALE (ANALYSE) ---
# Extraite pour être réutilisable par la simulation et l'API manuelle
def perform_analysis(transactions_list):
    mots_cles = ["NETFLIX", "FITNESS", "GYM", "SPOTIFY", "PREMIUM", "SUBSCRIPTION", "AMAZON PRIME", "APPLE MUSIC"]
    detected = []
    total_loss = 0

    for t in transactions_list:
        label_upper = str(t.get('label', '')).upper()
        amount = float(t.get('amount', 0))

        if any(k in label_upper for k in mots_cles) and amount < 0:
            category = "REC_SUB_STREAMING"
            if "GYM" in label_upper or "FITNESS" in label_upper:
                category = "REC_SUB_FITNESS"
            elif "AMAZON" in label_upper or "PRIME" in label_upper:
                category = "REC_SUB_ECOMMERCE"
                
            detected.append({
                "ref_hash": hash(label_upper) % 100000000,
                "amount_monthly": abs(amount),
                "category_code": category
            })
            total_loss += abs(amount)

    commission = round(total_loss * 0.15, 2)
    net_gain = round(total_loss - commission, 2)

    return {
        "analysis_summary": {
            "total_scanned_lines": len(transactions_list),
            "subscriptions_detected": len(detected),
            "monthly_loss_identified": round(total_loss, 2),
            "yearly_loss_projected": round(total_loss * 12, 2)
        },
        "financial_action": {
            "service_fee_rate": 0.15,
            "client_savings_net_monthly": net_gain,
            "platform_revenue_gross": commission
        },
        "detected_items_anonymized": detected
    }

# --- ROUTE API MANUELLE (CSV) ---
@app.route('/analyze', methods=['POST'])
def analyze_manual():
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data"}), 400

    transactions = data.get('transactions', [])
    result_data = perform_analysis(transactions)
    
    return jsonify({
        "status": "success",
        "message": "Analyse terminée.",
        "data": result_data,
        "signature": "SECURE_HASH_V2_UNIFIED"
    })

# --- SIMULATEUR BANCAIRE SALT EDGE (MODE DEMO AVANCÉ) ---
# Remplace l'appel réseau externe par une génération de données locales fiables
@app.route('/salt-edge/connect', methods=['POST'])
def connect_salt_edge_simulated():
    """
    Simule une connexion bancaire réussie.
    Génère des transactions fictives réalistes et les analyse immédiatement.
    """
    print(f"DEBUG INFO: Initiating Salt Edge Simulation Mode...")
    
    # 1. Génération de fausses transactions bancaires réalistes
    simulated_transactions = [
        {"date": "2026-09-01", "label": "NETFLIX PREMIUM SUBSCRIPTION", "amount": -17.99},
        {"date": "2026-09-02", "label": "CARREFOUR MARKET GROCERY", "amount": -54.20}, # Non-abo
        {"date": "2026-09-03", "label": "SPOTIFY FAMILY PLAN", "amount": -14.99},
        {"date": "2026-09-05", "label": "BASIC-FIT GYM MEMBERSHIP", "amount": -29.99},
        {"date": "2026-09-08", "label": "EDF ELECTRICITY BILL", "amount": -85.00}, # Non-abo standard detection
        {"date": "2026-09-10", "label": "AMAZON PRIME DELIVERY", "amount": -6.99},
        {"date": "2026-09-12", "label": "CANAL+ SPORT STREAMING", "amount": -19.99},
        {"date": "2026-09-15", "label": "SALARY TRANSFER INCOME", "amount": 2500.00} # Positif ignoré
    ]

    # 2. Exécution de la logique d'analyse réelle sur ces données
    analysis_result = perform_analysis(simulated_transactions)
    
    # 3. Préparation de la réponse JSON pour le Frontend
    # On retourne directement les résultats comme si c'était venu de Salt Edge
    response_payload = {
        "status": "success",
        "source": "SALT_EDGE_SIMULATION_MODE",
        "message": "Connexion sécurisée établie. Données analysées.",
        "data": analysis_result,
        "raw_transactions_count": len(simulated_transactions),
        "security_note": "Demo Mode Active - No real banking data accessed."
    }
    
    return jsonify(response_payload)

@app.route('/salt-edge/callback', methods=['GET'])
def salt_edge_callback():
    """Endpoint conservé pour compatibilité future avec vraie API."""
    return "<h2>✅ Callback Endpoint Active</h2><p>Prêt pour intégration production.</p><a href='/'>Retour Accueil</a>"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)