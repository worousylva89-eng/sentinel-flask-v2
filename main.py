import os
from dotenv import load_dotenv
from flask import Flask, request, jsonify, send_from_directory
import requests
import json
import random
from datetime import datetime, timedelta

# --- CONFIGURATION ENVIRONNEMENT ---
load_dotenv()

SE_LOGIN = os.getenv("SE_LOGIN")
SE_API_KEY = os.getenv("SE_API_KEY")

app = Flask(__name__, static_folder='.')

@app.route('/')
def home():
    return send_from_directory('.', 'index.html')

# --- LOGIQUE MÉTIER CENTRALE (ANALYSE) ---
def perform_analysis(transactions_list):
    mots_cles = ["NETFLIX", "FITNESS", "GYM", "SPOTIFY", "PREMIUM", "SUBSCRIPTION", "AMAZON PRIME", "APPLE MUSIC", "DISNEY+", "CANAL+"]
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

# --- GENERATEUR DE DONNEES BANCAIRES FICTIVES DYNAMIQUES ---
def generate_random_bank_transactions(count=8):
    """Simule un relevé bancaire réaliste avec variations."""
    base_date = datetime.now() - timedelta(days=random.randint(1, 30))
    
    templates = [
        {"label_template": "NETFLIX PREMIUM SUBSCRIPTION", "min_amt": 17.99, "max_amt": 19.99},
        {"label_template": "SPOTIFY FAMILY PLAN", "min_amt": 14.99, "max_amt": 16.99},
        {"label_template": "BASIC-FIT GYM MEMBERSHIP", "min_amt": 29.99, "max_amt": 34.99},
        {"label_template": "AMAZON PRIME DELIVERY", "min_amt": 5.99, "max_amt": 7.99},
        {"label_template": "CANAL+ SPORT STREAMING", "min_amt": 19.99, "max_amt": 24.99},
        {"label_template": "CARREFOUR MARKET GROCERY", "min_amt": 40.00, "max_amt": 80.00}, # Non-abo
        {"label_template": "EDF ELECTRICITY BILL", "min_amt": 70.00, "max_amt": 100.00}, # Non-abo standard
        {"label_template": "SALARY TRANSFER INCOME", "min_amt": 2000.00, "max_amt": 3000.00} # Positif
    ]
    
    transactions = []
    selected_templates = random.sample(templates, min(count, len(templates)))
    
    for i, tmpl in enumerate(selected_templates):
        date_offset = i * random.randint(1, 5)
        txn_date = (base_date + timedelta(days=date_offset)).strftime("%Y-%m-%d")
        
        # Variation aléatoire +/- 10%
        variation = random.uniform(0.9, 1.1)
        raw_amount = random.uniform(tmpl["min_amt"], tmpl["max_amt"]) * variation
        
        # Arrondir à 2 décimales, négatif sauf salaire
        is_income = "INCOME" in tmpl["label_template"].upper()
        final_amount = round(raw_amount, 2)
        if not is_income:
            final_amount = -final_amount
            
        transactions.append({
            "date": txn_date,
            "label": tmpl["label_template"],
            "amount": final_amount
        })
        
    return transactions

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

# --- SIMULATEUR BANCAIRE SALT EDGE (MODE DEMO AVANCÉ & DYNAMIQUE) ---
@app.route('/salt-edge/connect', methods=['POST'])
def connect_salt_edge_simulated():
    print(f"DEBUG INFO: Initiating Dynamic Salt Edge Simulation Mode...")
    
    # Génère des transactions différentes à CHAQUE appel !
    simulated_transactions = generate_random_bank_transactions(count=8)
    
    analysis_result = perform_analysis(simulated_transactions)
    
    response_payload = {
        "status": "success",
        "source": "SALT_EDGE_SIMULATION_MODE_DYNAMIC",
        "message": "Connexion sécurisée établie. Données analysées.",
        "data": analysis_result,
        "raw_transactions_count": len(simulated_transactions),
        "security_note": "Demo Mode Active - No real banking data accessed."
    }
    
    return jsonify(response_payload)

@app.route('/salt-edge/callback', methods=['GET'])
def salt_edge_callback():
    return "<h2>✅ Callback Endpoint Active</h2><p>Prêt pour intégration production.</p><a href='/'>Retour Accueil</a>"

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8000))
    app.run(host='0.0.0.0', port=port)