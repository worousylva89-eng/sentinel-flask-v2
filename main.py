import os
from dotenv import load_dotenv
from flask import Flask, request, jsonify, send_from_directory, redirect
import requests
import json
import random
import csv
import io
from datetime import datetime, timedelta
import stripe

# --- CONFIGURATION ENVIRONNEMENT ---
load_dotenv()

# Clés Stripe
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
if STRIPE_SECRET_KEY:
    stripe.api_key = STRIPE_SECRET_KEY

app = Flask(__name__, static_folder='.')

# --- STOCKAGE TEMPORAIRE DES ANALYSES ---
last_analyses_store = {} 

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

# --- ROUTE API UPLOAD DE FICHIERS (CSV / TXT) ---
@app.route('/analyze', methods=['POST'])
def analyze_upload():
    # Vérifie si un fichier a été envoyé via le champ 'file' du form-data
    if 'file' not in request.files:
        return jsonify({"error": "Aucun fichier reçu"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "Nom de fichier vide"}), 400
        
    try:
        content = file.read().decode('utf-8')
        transactions = []
        
        # Analyse basique CSV (Label, Amount) - Adaptable selon format banque
        reader = csv.reader(io.StringIO(content))
        next(reader, None) # Skip header si présent
        
        for row in reader:
            if len(row) >= 2:
                label = row[0].strip()
                try:
                    # Nettoie les montants (remplace virgule par point, retire espaces)
                    amount_str = row[1].replace(',', '.').replace(' ', '').strip()
                    amount = float(amount_str)
                    transactions.append({
                        "label": label,
                        "amount": amount
                    })
                except ValueError:
                    continue
                    
        if not transactions:
             return jsonify({"error": "Format invalide ou données insuffisantes. Assurez-vous que c'est un CSV avec [Libellé, Montant]"}), 400

        result_data = perform_analysis(transactions)
        
        user_id = "guest_" + str(random.randint(1000,9999))
        last_analyses_store[user_id] = result_data
        
        return jsonify({
            "status": "success",
            "message": "Analyse terminée.",
            "data": result_data,
            "signature": "SECURE_HASH_V2_UNIFIED",
            "temp_user_id": user_id 
        })

    except Exception as e:
        print(f"Erreur analyse fichier: {str(e)}")
        return jsonify({"error": f"Échec lecture fichier: {str(e)}"}), 500

# --- INTÉGRATION STRIPE CHECKOUT ---
@app.route('/create-checkout-session', methods=['POST'])
def create_checkout_session():
    try:
        data = request.get_json()
        customer_email = data.get('email', 'client@example.com')
        temp_user_id = data.get('temp_user_id', 'unknown') 
        
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'eur',
                    'product_data': {
                        'name': 'Audit Financier Sentinel - Rapport Complet',
                        'description': 'Analyse IA de vos abonnements cachés + Plan d\'action personnalisé.',
                    },
                    'unit_amount': 900, 
                },
                'quantity': 1,
            }],
            mode='payment',
            success_url=f"https://sentinel-flask-v2-2.onrender.com/?status=paid&uid={temp_user_id}", 
            cancel_url="https://sentinel-flask-v2-2.onrender.com/",
            metadata={'customer_email': customer_email, 'internal_uid': temp_user_id} 
        )
        
        return jsonify({"url": session.url})

    except Exception as e:
        print(f"Stripe Error: {str(e)}")
        return jsonify({"error": str(e)}), 500

# --- NOUVELLE ROUTE RAPIDE : RETOURNE LES DONNÉES BRUTES POUR LE FRONTEND ---
@app.route('/get-report-data/<uid>', methods=['GET'])
def get_report_data(uid):
    """Renvoie simplement les JSON des analyses sans générer de PDF lourd."""
    analysis_data = last_analyses_store.get(uid)
    
    if not analysis_data:
        return jsonify({"error": "Rapport introuvable ou expiré."}), 404
        
    return jsonify({
        "status": "success",
        "data": analysis_data,
        "generated_at": datetime.now().isoformat()
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8000))
    app.run(host='0.0.0.0', port=port)