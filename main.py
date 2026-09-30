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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)