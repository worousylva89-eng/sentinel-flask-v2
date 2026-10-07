import os
from dotenv import load_dotenv
from flask import Flask, request, jsonify, send_from_directory, redirect
import requests
import json
import random
import csv
import io
import base64
from datetime import datetime, timedelta
import stripe

# --- CONFIGURATION ENVIRONNEMENT ---
load_dotenv()

# Clés Stripe
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
if STRIPE_SECRET_KEY:
    stripe.api_key = STRIPE_SECRET_KEY

app = Flask(__name__, static_folder='.')

# --- STOCKAGE TEMPORAIRE DES ANALYSES (Backup local) ---
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
    if 'file' not in request.files:
        return jsonify({"error": "Aucun fichier reçu"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "Nom de fichier vide"}), 400
        
    try:
        content = file.read().decode('utf-8')
        transactions = []
        
        reader = csv.reader(io.StringIO(content))
        next(reader, None) 
        
        for row in reader:
            if len(row) >= 2:
                label = row[0].strip()
                try:
                    amount_str = row[1].replace(',', '.').replace(' ', '').strip()
                    amount = float(amount_str)
                    transactions.append({"label": label, "amount": amount})
                except ValueError:
                    continue
                    
        if not transactions:
             return jsonify({"error": "Format invalide ou données insuffisantes."}), 400

        result_data = perform_analysis(transactions)
        
        # Génération d'un ID unique court
        user_id = "guest_" + str(random.randint(100000,999999))
        
        # Sauvegarde locale (au cas où)
        last_analyses_store[user_id] = result_data
        
        # ENCODAGE BASE64 POUR L'URL (LA CLÉ DU SUCCÈS)
        data_json = json.dumps(result_data)
        encoded_token = base64.urlsafe_b64encode(data_json.encode()).decode()
        
        return jsonify({
            "status": "success",
            "message": "Analyse terminée.",
            "data": result_data,
            "temp_user_id": user_id,
            "report_token": encoded_token
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
        report_token = data.get('report_token', '') 
        
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
            success_url=f"https://sentinel-flask-v2-2.onrender.com/?status=paid&uid={temp_user_id}&token={report_token}", 
            cancel_url="https://sentinel-flask-v2-2.onrender.com/",
            metadata={'customer_email': customer_email, 'internal_uid': temp_user_id}
        )
        
        return jsonify({"url": session.url})

    except Exception as e:
        print(f"Stripe Error: {str(e)}")
        return jsonify({"error": str(e)}), 500

# ==========================================
# GÉNÉRATEUR DE RAPPORT FINAL INSTANTANÉ (VERSION CORRECTE PDF)
# ==========================================
@app.route('/final-report/<uid>', methods=['GET'])
def serve_final_report(uid):
    """Génère le rapport soit depuis la mémoire, soit depuis le token URL."""
    
    analysis_data = None
    
    # 1. Essayer de trouver dans la mémoire vive (rapide)
    if uid in last_analyses_store:
        analysis_data = last_analyses_store[uid]
    else:
        # 2. Sinon, essayer de décoder le token passé dans l'URL (?token=...)
        token_param = request.args.get('token')
        if token_param:
            try:
                decoded_bytes = base64.urlsafe_b64decode(token_param.encode())
                analysis_data = json.loads(decoded_bytes.decode())
            except Exception as decode_err:
                print(f"Erreur décodage token: {decode_err}")

    # Si toujours rien -> Erreur propre
    if not analysis_data:
        return f"""
        <!DOCTYPE html>
        <html lang="fr">
        <head><title>Rapport Indisponible</title></head>
        <body style="font-family:sans-serif; text-align:center; padding:50px;">
            <h2 style="color:#d32f2f;">⚠️ Session Expirée</h2>
            <p>Votre session d'analyse a expiré pendant le traitement du paiement.</p>
            <br>
            <a href="/" style="background:#1a237e; color:white; padding:10px 20px; text-decoration:none; border-radius:5px;">Retourner à l'accueil</a>
        </body>
        </html>
        """, 404
        
    summary = analysis_data['analysis_summary']
    financial_action = analysis_data['financial_action']
    detected_items = analysis_data['detected_items_anonymized']
    
    items_html = ""
    for item in detected_items:
        items_html += f"""
        <tr style="border-bottom:1px solid #eee;">
            <td style="padding:12px; font-weight:bold; color:#d32f2f;">{item['category_code'].replace('_', ' ').title()}</td>
            <td style="padding:12px; text-align:right; font-size:1.1em;">-{item['amount_monthly']} € / mois</td>
            <td style="padding:12px; text-align:right; color:#666;">≈ {round(item['amount_monthly']*12, 2)} € / an</td>
        </tr>
        """
        
    html_content = f"""
    <!DOCTYPE html>
    <html lang="fr">
    <head>
        <meta charset="UTF-8">
        <title>Rapport Audit Sentinel - {uid}</title>
        <style>
            body {{ font-family: 'Segoe UI', sans-serif; background:#f9f9f9; padding:40px; color:#333; }}
            .container {{ max-width:800px; margin:auto; background:white; padding:40px; border-radius:12px; box-shadow:0 4px 20px rgba(0,0,0,0.1); }}
            h1 {{ color:#1a237e; border-bottom:3px solid #ff9800; padding-bottom:15px; }}
            .alert-box {{ background:#fff3e0; border-left:5px solid #ff9800; padding:20px; margin:25px 0; border-radius:4px; }}
            table {{ width:100%; border-collapse:collapse; margin-top:20px; }}
            th {{ background:#1a237e; color:white; padding:15px; text-align:left; }}
            tr:nth-child(even) {{ background:#f5f5f5; }}
            .total-row td {{ font-weight:bold; font-size:1.2em; color:#d32f2f; border-top:2px solid #ddd; }}
            
            /* ✅ FIX CRUCIAL : Lien au lieu de Bouton pour compatibilité Mobile PDF */
            .print-link {{ 
                display:inline-block; 
                background:#2e7d32; 
                color:white; 
                padding:15px 30px; 
                text-decoration:none; 
                border-radius:6px; 
                font-weight:bold; 
                margin-top:30px; 
                cursor:pointer; 
                font-size:1em;
                transition: all 0.2s ease;
            }}
            .print-link:hover {{ background:#1b5e20; transform: translateY(-2px); box-shadow: 0 4px 10px rgba(0,0,0,0.2); }}
            
            @media print {{ .no-print {{ display:none !important; }} body {{ padding:0; }} .container {{ box-shadow:none; }} }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🛡️ RAPPORT D'AUDIT FINANCIER SENTINEL</h1>
            <p><strong>ID Client :</strong> {uid} | <strong>Date :</strong> {datetime.now().strftime('%d/%m/%Y')}</p>
            
            <div class="alert-box">
                <h3 style="margin-top:0; color:#e65100;">⚠️ ALERTE CRITIQUE DÉTECTÉE</h3>
                <p>Nous avons identifié <strong>{summary['subscriptions_detected']}</strong> abonnements récurrents non essentiels sur vos relevés analysés.</p>
                <p>Cela représente une fuite mensuelle estimée à <strong>{summary['monthly_loss_identified']} €</strong>.</p>
                <p>Votre perte annuelle projetée s'élève à : <span style="font-size:1.5em; font-weight:bold; color:red;">{summary['yearly_loss_projected']} €</span></p>
            </div>

            <h2>Détail des Pertes Identifiées</h2>
            <table>
                <thead>
                    <tr>
                        <th>Catégorie</th>
                        <th style="text-align:right;">Coût Mensuel</th>
                        <th style="text-align:right;">Impact Annuel</th>
                    </tr>
                </thead>
                <tbody>
                    {items_html}
                    <tr class="total-row">
                        <td colspan="2" style="text-align:right;">TOTAL PERDU PAR AN :</td>
                        <td style="text-align:right;">{summary['yearly_loss_projected']} €</td>
                    </tr>
                </tbody>
            </table>

            <h2>💰 Plan d'Action & Gain Potentiel</h2>
            <p>En résiliant ces services superflus, vous récupérerez immédiatement :</p>
            <ul style="line-height:1.8; font-size:1.1em;">
                <li><strong>+ {financial_action['client_savings_net_monthly']} €</strong> nets par mois dans votre poche.</li>
                <li>Frais de service Sentinel appliqués ({int(financial_action['service_fee_rate']*100)}%) : {financial_action['platform_revenue_gross']} €/mois.</li>
                <li>Économies brutes réalisées avant frais : {summary['monthly_loss_identified']} €/mois.</li>
            </ul>
            
            <!-- ✅ LE LIEN MAGIQUE QUI FONCTIONNE PARTOUT -->
            <a href="#" onclick="window.print(); return false;" class="print-link no-print">
                🖨️ Imprimer / Sauvegarder en PDF
            </a>
            <br><br>
            <a href="/" class="no-print" style="color:#666; text-decoration:none;">← Retour à l'accueil Sentinel Finance</a>
        </div>
    </body>
    </html>
    """
    return html_content

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8000))
    app.run(host='0.0.0.0', port=port)