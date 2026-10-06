import os
from dotenv import load_dotenv
from flask import Flask, request, jsonify, send_from_directory, redirect
import requests
import json
import random
from datetime import datetime, timedelta
import stripe

# --- CONFIGURATION ENVIRONNEMENT ---
load_dotenv()

# Clés Stripe
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
if STRIPE_SECRET_KEY:
    stripe.api_key = STRIPE_SECRET_KEY

# Clés Salt Edge (Renommées pour clarté)
SE_LOGIN = os.getenv("SALTEDGE_CLIENT_ID")      
SE_API_KEY = os.getenv("SALTEDGE_SECRET_KEY")   
SE_BASE_URL = "https://api.saltedge.com/api/v4" 

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

# --- GENERATEUR DE DONNEES FICTIVES (Fallback / Test Local) ---
def generate_random_bank_transactions(count=8):
    base_date = datetime.now() - timedelta(days=random.randint(1, 30))
    
    templates = [
        {"label_template": "NETFLIX PREMIUM SUBSCRIPTION", "min_amt": 17.99, "max_amt": 19.99},
        {"label_template": "SPOTIFY FAMILY PLAN", "min_amt": 14.99, "max_amt": 16.99},
        {"label_template": "BASIC-FIT GYM MEMBERSHIP", "min_amt": 29.99, "max_amt": 34.99},
        {"label_template": "AMAZON PRIME DELIVERY", "min_amt": 5.99, "max_amt": 7.99},
        {"label_template": "CANAL+ SPORT STREAMING", "min_amt": 19.99, "max_amt": 24.99},
        {"label_template": "CARREFOUR MARKET GROCERY", "min_amt": 40.00, "max_amt": 80.00}, 
        {"label_template": "EDF ELECTRICITY BILL", "min_amt": 70.00, "max_amt": 100.00}, 
        {"label_template": "SALARY TRANSFER INCOME", "min_amt": 2000.00, "max_amt": 3000.00} 
    ]
    
    transactions = []
    selected_templates = random.sample(templates, min(count, len(templates)))
    
    for i, tmpl in enumerate(selected_templates):
        date_offset = i * random.randint(1, 5)
        txn_date = (base_date + timedelta(days=date_offset)).strftime("%Y-%m-%d")
        
        variation = random.uniform(0.9, 1.1)
        raw_amount = random.uniform(tmpl["min_amt"], tmpl["max_amt"]) * variation
        
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
    
    user_id = data.get('user_id', 'guest_' + str(random.randint(1000,9999)))
    last_analyses_store[user_id] = result_data
    
    return jsonify({
        "status": "success",
        "message": "Analyse terminée.",
        "data": result_data,
        "signature": "SECURE_HASH_V2_UNIFIED",
        "temp_user_id": user_id 
    })

# ==========================================
# INTÉGRATION RÉELLE SALT EDGE (OPEN BANKING)
# ==========================================

def get_salt_edge_token():
    """Récupère le token d'accès OAuth2 auprès de Salt Edge"""
    if not SE_LOGIN or not SE_API_KEY:
        print("⚠️ ERREUR: Variables SALTEDGE_CLIENT_ID ou SECRET_KEY manquantes.")
        return None
        
    try:
        response = requests.post(
            f"{SE_BASE_URL}/oauth/token",
            data={"grant_type": "client_credentials"},
            auth=(SE_LOGIN, SE_API_KEY)
        )
        if response.status_code == 200:
            return response.json().get("access_token")
        else:
            print(f"❌ Échec authentification Salt Edge: {response.text}")
            return None
    except Exception as e:
        print(f"💥 Exception connexion Salt Edge: {str(e)}")
        return None

@app.route('/salt-edge/connect', methods=['POST'])
def connect_real_salt_edge():
    """Initialise une connexion bancaire réelle via Salt Edge"""
    token = get_salt_edge_token()
    if not token:
        # Fallback vers simulation si l'API échoue (utile pour débugger sans bloquer le site)
        print("🔄 Mode Simulation activé car Salt Edge indisponible.")
        simulated_transactions = generate_random_bank_transactions(count=8)
        analysis_result = perform_analysis(simulated_transactions)
        temp_id = "sim_" + str(random.randint(100000, 999999))
        last_analyses_store[temp_id] = analysis_result
        return jsonify({
            "status": "simulation_mode",
            "message": "Salt Edge inaccessible, utilisation de données fictives.",
            "data": analysis_result,
            "temp_user_id": temp_id 
        }), 200

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    # ✅ CORRECTION ICI : Utilisation du bon ID de démonstration Salt Edge
    payload = {
        "provider_connection": {
            "provider_id": "salt-edge-demo-provider", 
            "return_url": request.url_root + "/salt-edge/callback",
            "state": "unique_state_123" 
        }
    }
    
    try:
        resp = requests.post(f"{SE_BASE_URL}/provider_connections", json=payload, headers=headers)
        
        if resp.status_code == 201:
            connection_data = resp.json()["data"]["attributes"]
            redirect_url = connection_data["redirect_uri"]
            
            return jsonify({
                "status": "success",
                "source": "SALT_EDGE_LIVE",
                "message": "Redirection vers la page de login bancaire...",
                "redirect_url": redirect_url
            })
        else:
            error_msg = resp.text
            print(f"Erreur création connexion Salt Edge: {error_msg}")
            return jsonify({"error": "Échec création connexion", "details": error_msg}), 400
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- CALLBACK SALT EDGE (Reçoit les données après login client) ---
@app.route('/salt-edge/callback', methods=['GET'])
def salt_edge_callback():
    """Endpoint appelé par Salt Edge quand le client a validé sa connexion"""
    state = request.args.get('state')
    provider_connection_id = request.args.get('id') 
    
    if not provider_connection_id:
        return "<h2>❌ Erreur: ID manquant</h2><a href='/'>Retour Accueil</a>"
        
    token = get_salt_edge_token()
    if not token:
         return "<h2>❌ Erreur: Impossible de récupérer le token.</h2>"

    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        # 1. Récupérer les comptes liés à cette connexion
        accounts_resp = requests.get(
            f"{SE_BASE_URL}/accounts?filter[provider_connection_id]={provider_connection_id}",
            headers=headers
        )
        
        if accounts_resp.status_code != 200:
             return f"<h2>❌ Erreur récupération comptes: {accounts_resp.text}</h2>"
             
        accounts = accounts_resp.json().get("data", [])
        if not accounts:
            return "<h2>⚠️ Aucun compte trouvé.</h2>"
            
        account_id = accounts[0]["id"]
        
        # 2. Récupérer les transactions de ce compte
        txns_resp = requests.get(
            f"{SE_BASE_URL}/transactions?filter[account_id]={account_id}&limit=50",
            headers=headers
        )
        
        if txns_resp.status_code != 200:
             return f"<h2>❌ Erreur récupération transactions: {txns_resp.text}</h2>"
             
        raw_txns = txns_resp.json().get("data", [])
        
        # Transformer les données Salt Edge au format attendu par notre analyseur
        formatted_txns = []
        for t in raw_txns:
            attrs = t.get("attributes", {})
            formatted_txns.append({
                "date": attrs.get("booked_at", "")[:10],
                "label": attrs.get("description", ""),
                "amount": float(attrs.get("amount", 0))
            })
            
        # 3. Analyser les vraies données !
        analysis_result = perform_analysis(formatted_txns)
        
        # Stocker temporairement avec un ID unique basé sur le callback
        temp_uid = "real_" + str(hash(provider_connection_id))[-6:]
        last_analyses_store[temp_uid] = analysis_result
        
        # Rediriger vers le frontend avec l'UID pour afficher le rapport
        return redirect(f"/?report_ready=true&uid={temp_uid}")
        
    except Exception as e:
        print(f"Erreur critique Callback Salt Edge: {str(e)}")
        return f"<h2>💥 Crash Serveur: {str(e)}</h2>"

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