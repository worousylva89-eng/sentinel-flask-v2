import os
from dotenv import load_dotenv
from flask import Flask, request, jsonify, send_file, abort
import requests
import json
import random
from datetime import datetime, timedelta
import stripe
from fpdf import FPDF # Importation de la librairie PDF

# --- CONFIGURATION ENVIRONNEMENT ---
load_dotenv()

SE_LOGIN = os.getenv("SE_LOGIN")
SE_API_KEY = os.getenv("SE_API_KEY")
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")

app = Flask(__name__, static_folder='.')

# Configure Stripe
if STRIPE_SECRET_KEY:
    stripe.api_key = STRIPE_SECRET_KEY

# --- STOCKAGE TEMPORAIRE DES ANALYSES (SIMULATION BASE DE DONNÉES) ---
# Clé = Email User, Valeur = Résultat Analyse
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

# --- GENERATEUR DE DONNEES BANCAIRES FICTIVES DYNAMIQUES ---
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
    
    # Sauvegarde temporaire pour le PDF
    user_id = data.get('user_id', 'guest_' + str(random.randint(1000,9999)))
    last_analyses_store[user_id] = result_data
    
    return jsonify({
        "status": "success",
        "message": "Analyse terminée.",
        "data": result_data,
        "signature": "SECURE_HASH_V2_UNIFIED",
        "temp_user_id": user_id # On renvoie l'ID pour pouvoir récupérer le PDF après
    })

# --- SIMULATEUR BANCAIRE SALT EDGE (MODE DEMO AVANCÉ & DYNAMIQUE) ---
@app.route('/salt-edge/connect', methods=['POST'])
def connect_salt_edge_simulated():
    simulated_transactions = generate_random_bank_transactions(count=8)
    analysis_result = perform_analysis(simulated_transactions)
    
    # Génération d'un ID unique pour lier l'analyse au futur paiement
    temp_id = "sim_" + str(random.randint(100000, 999999))
    last_analyses_store[temp_id] = analysis_result
    
    response_payload = {
        "status": "success",
        "source": "SALT_EDGE_SIMULATION_MODE_DYNAMIC",
        "message": "Connexion sécurisée établie. Données analysées.",
        "data": analysis_result,
        "raw_transactions_count": len(simulated_transactions),
        "security_note": "Demo Mode Active - No real banking data accessed.",
        "temp_user_id": temp_id # Important pour le lien PDF
    }
    
    return jsonify(response_payload)

# --- INTÉGRATION STRIPE CHECKOUT (PAIEMENT RÉEL) ---
@app.route('/create-checkout-session', methods=['POST'])
def create_checkout_session():
    """Crée une session de paiement Stripe pour l'utilisateur."""
    try:
        data = request.get_json()
        customer_email = data.get('email', 'client@example.com')
        temp_user_id = data.get('temp_user_id', 'unknown') # Récupère l'ID envoyé par le front
        
        # Création de la Session Checkout
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'eur',
                    'product_data': {
                        'name': 'Audit Financier Sentinel - Rapport Complet',
                        'description': 'Analyse IA de vos abonnements cachés + Plan d\'action personnalisé.',
                    },
                    'unit_amount': 900, # Prix en centimes -> 9.00 €
                },
                'quantity': 1,
            }],
            mode='payment',
            success_url=f"https://sentinel-flask-v2-2.onrender.com/?status=paid&uid={temp_user_id}", # Ajout de uid dans l'URL
            cancel_url="https://sentinel-flask-v2-2.onrender.com/",
            metadata={'customer_email': customer_email, 'internal_uid': temp_user_id} 
        )
        
        return jsonify({"url": session.url})

    except Exception as e:
        print(f"Stripe Error: {str(e)}")
        return jsonify({"error": str(e)}), 500

# --- GÉNÉRATION DU RAPPORT PDF (LA PIÈCE MAÎTRESSE) ---
@app.route('/generate-report-pdf/<uid>', methods=['GET'])
def generate_report_pdf(uid):
    """Génère et retourne le PDF basé sur l'analyse stockée sous cet UID."""
    
    # 1. Récupérer les données depuis notre stockage mémoire
    analysis_data = last_analyses_store.get(uid)
    
    if not analysis_data:
        return "<h1>Erreur</h1><p>Rapport introuvable ou expiré.</p>", 404

    # 2. Créer le PDF
    pdf = FPDF(unit='mm', format='A4')
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    
    # En-tête Coloré
    pdf.set_fill_color(22, 163, 74) # Vert Sentinel
    pdf.rect(0, 0, 210, 30, 'F')
    pdf.set_y(10)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font('helvetica', 'B', 20)
    pdf.cell(0, 10, 'AGENT SENTINEL', ln=True, align='C')
    pdf.set_font('helvetica', '', 12)
    pdf.cell(0, 10, 'Rapport d\'Audit Financier Personnalisé', ln=True, align='C')
    
    # Corps du document
    pdf.ln(10)
    pdf.set_text_color(50, 50, 50)
    pdf.set_x(15)
    
    # Date
    today_str = datetime.now().strftime("%d/%m/%Y")
    pdf.set_font('helvetica', 'I', 10)
    pdf.cell(0, 10, f'Date de génération : {today_str}', ln=True)
    pdf.ln(5)

    # Résumé Statistique
    summary = analysis_data['analysis_summary']
    action = analysis_data['financial_action']
    
    pdf.set_font('helvetica', 'B', 14)
    pdf.cell(0, 10, 'Synthèse Globale', ln=True)
    pdf.line(15, pdf.get_y(), 195, pdf.get_y()) # Ligne horizontale
    pdf.ln(2)
    
    pdf.set_font('helvetica', '', 12)
    stats_labels = [
        ("Transactions scannées :", summary['total_scanned_lines']),
        ("Abonnements détectés :", summary['subscriptions_detected']),
        ("Perte mensuelle estimée :", f"{summary['monthly_loss_identified']} €"),
        ("Projection annuelle :", f"{summary['yearly_loss_projected']} €")
    ]
    
    for label, value in stats_labels:
        pdf.cell(100, 8, label, border=0)
        pdf.set_font('helvetica', 'B', 12)
        pdf.cell(0, 8, str(value), ln=True, align='R')
        pdf.set_font('helvetica', '', 12)
    
    pdf.ln(5)
    
    # Le Gain Potentiel (Box Verte)
    pdf.set_fill_color(232, 248, 245) # Fond vert clair
    pdf.rect(15, pdf.get_y(), 180, 20, 'F')
    pdf.set_xy(15, pdf.get_y()+5)
    pdf.set_font('helvetica', 'B', 14)
    pdf.set_text_color(39, 174, 96) # Texte vert foncé
    pdf.cell(180, 10, f"VOTRE POTENTIEL NET MENSUEL : +{action['client_savings_net_monthly']} €", align='C')
    pdf.set_text_color(50, 50, 50) # Reset couleur texte
    
    pdf.ln(25)
    
    # Détails des fuites
    pdf.set_font('helvetica', 'B', 14)
    pdf.cell(0, 10, 'Détail des Abonnements Détectés', ln=True)
    pdf.line(15, pdf.get_y(), 195, pdf.get_y())
    pdf.ln(2)
    
    # Table Header
    pdf.set_font('helvetica', 'B', 10)
    pdf.set_fill_color(240, 240, 240)
    pdf.cell(60, 8, 'Catégorie', border=1, fill=True)
    pdf.cell(60, 8, 'Montant / Mois', border=1, fill=True, align='C')
    pdf.cell(60, 8, 'Référence Anonyme', border=1, fill=True, align='C')
    pdf.ln()
    
    pdf.set_font('helvetica', '', 10)
    items = analysis_data['detected_items_anonymized']
    
    if not items:
        pdf.cell(180, 8, 'Aucun abonnement suspect détecté. Félicitations !', border=1)
    else:
        for item in items:
            cat_readable = item['category_code'].replace('_', ' ').title()
            pdf.cell(60, 8, cat_readable, border=1)
            pdf.cell(60, 8, f"{item['amount_monthly']} €", border=1, align='C')
            pdf.cell(60, 8, f"#{item['ref_hash']}", border=1, align='C')
            pdf.ln()
            
    # Pied de page
    pdf.y = 270
    pdf.set_font('helvetica', 'I', 8)
    pdf.set_text_color(150, 150, 150)
    pdf.cell(0, 10, 'Ce rapport est confidentiel et généré automatiquement par Agent Sentinel.', align='C')
    
    # Sortie du PDF
    filename = f"Sentinel_Audit_{uid}.pdf"
    return send_file(
        path_or_fp=__import__('io').BytesIO(pdf.output()),
        mimetype='application/pdf',
        as_attachment=True,
        download_name=filename
    )

@app.route('/salt-edge/callback', methods=['GET'])
def salt_edge_callback():
    return "<h2>✅ Callback Endpoint Active</h2><a href='/'>Retour Accueil</a>"

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8000))
    app.run(host='0.0.0.0', port=port)