import os
from dotenv import load_dotenv

# Charge les variables depuis le fichier .env
load_dotenv()

# Récupère les clés Salt Edge depuis les variables d'environnement
SE_LOGIN = os.getenv("SE_LOGIN")
SE_API_KEY = os.getenv("SE_API_KEY")

from flask import Flask, request, jsonify, send_from_directory
import os

app = Flask(__name__, static_folder='.') # On dit à Flask de chercher les fichiers ici

# Route principale : Affiche index.html
@app.route('/')
def home():
    return send_from_directory('.', 'index.html')

# Route API : Analyse les données
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

# --- INTÉGRATION SALT EDGE SANDBOX ---
import requests # Nécessaire pour appeler l'API Salt Edge

@app.route('/salt-edge/connect', methods=['POST'])
def connect_salt_edge():
    """Initialise une connexion Sandbox avec Salt Edge."""
    
    # Vérifie que les variables d'environnement sont bien chargées
    if not SE_LOGIN or not SE_API_KEY:
        return jsonify({"error": "Missing Salt Edge credentials (.env)"}), 500
        
    data = request.get_json()
    user_email = data.get('email', 'test_user@example.com')
    
    # Étape 1 : Créer un "Connect Session" chez Salt Edge
    payload_session = {
        "country_code": "FR",
        "user_identifier": user_email,
        "permissions": ["balances", "details", "transactions"],
        "redirect_uri": "https://sentinel-flask-v2-2.onrender.com/salt-edge/callback", # URL de retour après login banque
        "finish_redirect_uri": "https://sentinel-flask-v2-2.onrender.com/" # Où renvoyer l'user une fois fini
    }
    
    headers_se = {
        "Login": SE_LOGIN,
        "API-key": SE_API_KEY,
        "Content-Type": "application/json"
    }
    
    try:
        resp_session = requests.post("https://www.saltedge.com/api/v5/connections", json=payload_session, headers=headers_se)
        
        if resp_session.status_code != 200:
             return jsonify({"error": f"Salt Edge Error: {resp_session.text}"}), 500
             
        connection_id = resp_session.json()['data']['id']
        
        # Étape 2 : Obtenir l'URL de redirection vers la page de choix de banque
        redirect_url = f"https://www.saltedge.com/sandbox/connect/{connection_id}"
        
        return jsonify({
            "status": "success",
            "message": "Session créée. Redirigez l'utilisateur vers cette URL.",
            "redirect_url": redirect_url,
            "connection_id": connection_id
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/salt-edge/callback', methods=['GET'])
def salt_edge_callback():
    """Reçu par Salt Edge après que l'utilisateur a choisi sa banque."""
    conn_id = request.args.get('connection_id')
    status = request.args.get('status')
    
    if status == 'connected':
        # Ici, on pourrait récupérer les vraies transactions depuis Salt Edge
        # Pour l'instant (Sandbox), on simule un succès visuel
        return "<h2>✅ Connexion Réussie !</h2><p>Votre compte bancaire fictif est lié à Sentinel.</p><a href='/'>Retour à l'accueil</a>"
    else:
        return "<h2>❌ Échec de connexion.</h2><a href='/'>Réessayer</a>"
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)