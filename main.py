import os
from dotenv import load_dotenv
from flask import Flask, request, jsonify, send_from_directory, redirect, make_response
import requests
import json
import random
import csv
import io
import base64
from datetime import datetime, timedelta
import stripe
from fpdf import FPDF # Importation de la lib PDF

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
        
        user_id = "guest_" + str(random.randint(100000,999999))
        last_analyses_store[user_id] = result_data
        
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
# GÉNÉRATEUR DE RAPPORT PDF NATIF (VERSION FINALE STABLE)
# ==========================================
class PDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 15)
        self.cell(0, 10, 'RAPPORT D\'AUDIT FINANCIER SENTINEL', ln=True, align='C')
        self.ln(5)
        self.set_draw_color(26, 35, 126) # Bleu foncé
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.set_text_color(128)
        self.cell(0, 10, f'Sentinel Finance © {datetime.now().year} | Page {self.page_no()}/{{nb}}', align='C')

def generate_pdf_report(uid, analysis_data):
    pdf = PDF()
    pdf.alias_nb_pages()
    pdf.add_page()
    
    summary = analysis_data['analysis_summary']
    financial_action = analysis_data['financial_action']
    detected_items = analysis_data['detected_items_anonymized']

    # Infos Client & Date
    pdf.set_font('Arial', '', 10)
    pdf.set_text_color(100)
    pdf.cell(0, 8, f'ID Client : {uid}', ln=True)
    pdf.cell(0, 8, f'Date d\'analyse : {datetime.now().strftime("%d/%m/%Y")}', ln=True)
    pdf.ln(5)

    # Alerte Critique Box (Texte pur sans emoji)
    pdf.set_fill_color(255, 243, 224) # Orange clair bg
    pdf.set_text_color(230, 81, 0) # Texte orange foncé
    pdf.rect(10, pdf.get_y(), 190, 35, style='F')
    pdf.set_xy(15, pdf.get_y() + 5)
    pdf.set_font('Arial', 'B', 12)
    
    alert_text = (f"ALERTE CRITIQUE DETECTEE\n"
                  f"Nous avons identifie {summary['subscriptions_detected']} abonnements recurrents non essentiels.\n"
                  f"Perte mensuelle estimee : {summary['monthly_loss_identified']} EUR\n"
                  f"Perte annuelle projettee : {summary['yearly_loss_projected']} EUR")
                  
    pdf.multi_cell(0, 6, alert_text)
    
    pdf.set_xy(10, pdf.get_y() + 10)
    pdf.set_text_color(0)
    pdf.set_font('Arial', 'B', 14)
    pdf.cell(0, 10, 'Detail des Pertes Identifiees', ln=True)
    pdf.ln(2)

    # Tableau HTML-like simulé avec cells
    col_widths = [80, 55, 55]
    headers = ['Categorie', 'Cout Mensuel', 'Impact Annuel']
    
    # Header Row
    pdf.set_font('Arial', 'B', 10)
    pdf.set_fill_color(26, 35, 126)
    pdf.set_text_color(255)
    for i, h in enumerate(headers):
        pdf.cell(col_widths[i], 8, h, border=1, fill=True, align='C' if i > 0 else 'L')
    pdf.ln()

    # Data Rows
    pdf.set_font('Arial', '', 10)
    pdf.set_text_color(0)
    for idx, item in enumerate(detected_items):
        cat_name = item['category_code'].replace('_', ' ').title()
        monthly_cost = f"-{item['amount_monthly']} EUR"
        yearly_impact = f"~ {round(item['amount_monthly']*12, 2)} EUR"
        
        if idx % 2 == 0:
            pdf.set_fill_color(245, 245, 245) # Zebra striping light gray
            fill_style = True
        else:
            fill_style = False
            
        pdf.cell(col_widths[0], 8, cat_name, border=1, fill=fill_style)
        pdf.cell(col_widths[1], 8, monthly_cost, border=1, fill=fill_style, align='R')
        pdf.cell(col_widths[2], 8, yearly_impact, border=1, fill=fill_style, align='R')
        pdf.ln()

    # Total Line
    pdf.set_font('Arial', 'B', 11)
    pdf.set_text_color(211, 47, 47) # Rouge alerte
    pdf.cell(sum(col_widths[:-1]), 8, 'TOTAL PERDU PAR AN :', border=1, align='R')
    pdf.cell(col_widths[-1], 8, f'{summary["yearly_loss_projected"]} EUR', border=1, align='R')
    pdf.ln(10)

    # Plan d'action (Texte pur sans emoji)
    pdf.set_text_color(0)
    pdf.set_font('Arial', 'B', 14)
    pdf.cell(0, 10, 'Plan d\'Action & Gain Potentiel', ln=True)
    pdf.ln(2)
    pdf.set_font('Arial', '', 11)
    
    action_text = (f"En resilient ces services superflus, vous recupererez immediatement :\n"
                   f"+ {financial_action['client_savings_net_monthly']} EUR nets par mois dans votre poche.\n"
                   f"Frais de service Sentinel appliques ({int(financial_action['service_fee_rate']*100)}%) : {financial_action['platform_revenue_gross']} EUR/mois.")
                   
    pdf.multi_cell(0, 7, action_text)

    # ✅ LA CORRECTION CRUCIALE POUR ÉVITER LE CRASH BYTEARRAY
    return bytes(pdf.output()) 


@app.route('/download-report/<uid>', methods=['GET'])
def download_report_pdf(uid):
    """Génère le PDF et force le téléchargement."""
    
    analysis_data = None
    
    # Récupération données (Mémoire ou Token URL)
    if uid in last_analyses_store:
        analysis_data = last_analyses_store[uid]
    else:
        token_param = request.args.get('token')
        if token_param:
            try:
                decoded_bytes = base64.urlsafe_b64decode(token_param.encode())
                analysis_data = json.loads(decoded_bytes.decode())
            except Exception as decode_err:
                print(f"Erreur décodage token: {decode_err}")

    if not analysis_data:
        return "<h2>❌ Erreur : Données introuvables.</h2><a href='/'>Retour Accueil</a>", 404

    try:
        pdf_binary = generate_pdf_report(uid, analysis_data)
        
        response = make_response(pdf_binary)
        filename = f"Rapport_Sentinel_{uid}.pdf"
        
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        return response

    except Exception as e:
        print(f"Erreur génération PDF: {str(e)}")
        return f"<h2>💥 Crash Serveur PDF: {str(e)}</h2>", 500

# Ancienne route conservée juste au cas où, mais on utilise maintenant /download-report
@app.route('/final-report/<uid>', methods=['GET'])
def serve_final_report_redirect(uid):
    # Redirection simple vers la nouvelle route propre
    token = request.args.get('token', '')
    query_string = f"?token={token}" if token else ""
    return redirect(f"/download-report/{uid}{query_string}")

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8000))
    app.run(host='0.0.0.0', port=port)