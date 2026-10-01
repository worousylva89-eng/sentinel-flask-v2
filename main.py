import os
from dotenv import load_dotenv
from flask import Flask, request, jsonify, send_from_directory
import requests
import json

# --- CONFIGURATION ENVIRONNEMENT ---
load_dotenv()

SE_LOGIN = os.getenv("SE_LOGIN")
SE_API_KEY = os.getenv("SE_API_KEY")

app = Flask(__name__, static_folder='.')

# Route principale : Affiche index.html
@app.route('/')
def home():
    return send_from_directory('.', 'index.html')

# --- LOGIQUE MÉTIER (ANALYSE MANUELLE) ---
@app.route('/analyze', methods=['POST'])
def analyze():
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data"}), 400

    transactions = data.get('transactions', [])
    mots_cles = ["NETFLIX", "FITNESS", "GYM", "SPOTIFY", "PREMIUM", "SUBSCRIPTION"]
    detected = []
    total_loss = 0

    for t in transactions:
        label_upper = str(t.get('label', '')).upper()
        amount = float(t.get('amount', 0))

        if any(k in label_upper for k in mots_cles) and amount < 0:
            detected.append({
                "ref_hash": hash(label_upper) % 100000000,
                "amount_monthly": abs(amount),
                "category_code": "REC_SUB_STREAMING" if "NETFLIX" in label_upper or "SPOTIFY" in label_upper else "REC_SUB_OTHER"
            })
            total_loss += abs(amount)

    commission = round(total_loss * 0.15, 2)
    net_gain = round(total_loss - commission, 2)

    response_data = {
        "analysis_summary": {
            "total_scanned_lines": len(transactions),
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

    return jsonify({
        "status": "success",
        "message": "Analyse terminée.",
        "data": response_data,
        "signature": "SECURE_HASH_V2_UNIFIED"
    })

# --- INTÉGRATION SALT EDGE SANDBOX (CORRIGÉE & ROBUSTE) ---

@app.route('/salt-edge/connect', methods=['POST'])
def connect_salt_edge():
    """Initialise une connexion Sandbox avec Salt Edge."""
    
    # 1. Vérification des clés
    if not SE_LOGIN or not SE_API_KEY:
        print(f"DEBUG ERROR: Missing keys. Login={bool(SE_LOGIN)}, Key={bool(SE_API_KEY)}")
        return jsonify({"error": "Missing Salt Edge credentials (.env file issue)"}), 500
        
    data = request.get_json()
    user_email = data.get('email', 'test_user@example.com')
    
    # 2. Préparation de la requête vers le SANDBOX (URL corrigée !)
    url = "https://sandbox.saltedge.com/api/v5/connections"
    
    headers_se = {
        "Login": SE_LOGIN,
        "API-key": SE_API_KEY,
        "Content-Type": "application/json"
    }
    
    payload_session = {
        "country_code": "FR",
        "user_identifier": user_email,
        "permissions": ["balances", "details", "transactions"],
        "redirect_uri": "https://sentinel-flask-v2-2.onrender.com/salt-edge/callback", 
        "finish_redirect_uri": "https://sentinel-flask-v2-2.onrender.com/" 
    }
    
    try:
        print(f"DEBUG INFO: Attempting connection to Salt Edge Sandbox...")
        
        # Timeout ajouté pour éviter les blocages infinis
        resp_session = requests.post(url, json=payload_session, headers=headers_se, timeout=15)
        
        print(f"DEBUG RESPONSE STATUS: {resp_session.status_code}")
        print(f"DEBUG RESPONSE BODY: {resp_session.text[:500]}") # Limite à 500 chars pour lisibilité
        
        if resp_session.status_code != 200:
             error_detail = f"Salt Edge API Error ({resp_session.status_code}): {resp_session.text}"
             return jsonify({"error": error_detail}), 500
             
        result_json = resp_session.json()
        connection_id = result_json['data']['id']
        
        # Construction de l'URL de redirection pour le sandbox
        redirect_url = f"https://sandbox.saltedge.com/connect/{connection_id}"
        
        return jsonify({
            "status": "success",
            "message": "Session créée avec succès !",
            "redirect_url": redirect_url,
            "connection_id": connection_id
        })
        
    except requests.exceptions.Timeout:
        return jsonify({"error": "Timeout: Salt Edge server did not respond in time."}), 504
    except Exception as e:
        print(f"DEBUG EXCEPTION: {str(e)}")
        return jsonify({"error": f"Internal Server Error contacting Salt Edge: {str(e)}"}), 500

@app.route('/salt-edge/callback', methods=['GET'])
def salt_edge_callback():
    """Reçu par Salt Edge après que l'utilisateur a choisi sa banque."""
    conn_id = request.args.get('connection_id')
    status = request.args.get('status')
    
    if status == 'connected':
        return "<h2>✅ Connexion Réussie !</h2><p>Votre compte bancaire fictif est lié à Sentinel.</p><a href='/'>Retour à l'accueil</a>"
    else:
        return "<h2>❌ Échec de connexion.</h2><a href='/'>Réessayer</a>"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)