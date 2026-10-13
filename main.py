import os
import hmac
import hashlib
import json
from dotenv import load_dotenv
from flask import Flask, request, jsonify, send_from_directory, redirect, make_response
import requests
import random
import csv
import io
import base64
from datetime import datetime
from fpdf import FPDF

# --- CONFIGURATION ENVIRONNEMENT ---
load_dotenv()

# Clés NowPayments (à configurer dans les Variables d'Environnement de Render)
NOWPAYMENTS_API_KEY = os.getenv("NOWPAYMENTS_API_KEY")
NOWPAYMENTS_IPN_SECRET = os.getenv("NOWPAYMENTS_IPN_SECRET")
NOWPAYMENTS_API_URL = "https://api.nowpayments.io/v1"

app = Flask(__name__, static_folder='.')

# --- STOCKAGE TEMPORAIRE DES ANALYSES + PAIEMENTS ---
last_analyses_store = {} 
payments_store = {}  # Stockage des statuts de paiement

@app.route('/')
def home():
    return send_from_directory('.', 'index.html')

# ==========================================
# LOGIQUE MÉTIER CENTRALE (ANALYSE CLASSIQUE)
# ==========================================
def perform_analysis(transactions_list):
    """Détecte les abonnements récurrents classiques (Netflix, Gym, etc.)."""
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
            "scan_mode": "CLASSIC_BANK_AUDIT",
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

# ==========================================
# LOGIQUE MÉTIER SPÉCIALISÉE (DIGITAL / WALLETS)
# ==========================================
def analyze_digital_platforms(transactions_list):
    """Analyse les pertes liées aux frais cachés sur les plateformes digitales."""
    detected_losses = []
    total_loss = 0
    
    keywords_fees = [
        "FEE", "FEES", "CHARGE", "COMMISSION", "SPREAD", "COST", "PRICE", 
        "FRAIS", "COÛT", "COUT", "CHARGEMENT", "SERVICE", 
        "WITHDRAWAL", "RETRAIT", "TRANSFER", "TRANSFERT", "SEND MONEY",
        "TOP UP", "RECHARGE", "AIRTIME", "CRÉDIT", "CREDIT",
        "NETWORK", "OPERATOR", "GAS", "MINER", "SWAP", "OVERNIGHT",
        "INACTIVITY", "MAINTENANCE", "ADMINISTRATION", "PROCESSING"
    ]
    
    for t in transactions_list:
        label_upper = str(t.get('label', '')).upper()
        amount = float(t.get('amount', 0))
        
        if amount >= 0:
            continue
            
        matched_keyword = None
        for kw in keywords_fees:
            if kw in label_upper:
                matched_keyword = kw
                break
                
        if matched_keyword:
            category = "DIGITAL_FEE_HIDDEN"
            diagnosis = f"Frais caché détecté ({matched_keyword})"
            
            if any(x in label_upper for x in ["WITHDRAWAL", "RETRAIT", "CASH"]):
                category = "CASH_WITHDRAWAL_FEE"
                diagnosis = "Surcoût lors du retrait d'espèces"
            elif any(x in label_upper for x in ["TRANSFER", "TRANSFERT", "SEND"]):
                category = "TRANSFER_COMMISSION"
                diagnosis = "Commission de transfert inter-compte/tiers"
            elif any(x in label_upper for x in ["CRYPTO", "BTC", "ETH", "BINANCE", "KRAKEN", "GAS"]):
                category = "BLOCKCHAIN_GAS_SPREAD"
                diagnosis = "Frais réseau blockchain ou spread exchange"
            elif any(x in label_upper for x in ["INACTIVITY", "MAINTENANCE"]):
                category = "ACCOUNT_DORMANCY_PENALTY"
                diagnosis = "Pénalité de compte inactif/maintenance"

            detected_losses.append({
                "ref_hash": hash(label_upper) % 100000000,
                "platform_label": t.get('label'),
                "cost_incurred": abs(amount),
                "category_code": category,
                "diagnosis": diagnosis
            })
            total_loss += abs(amount)

    commission = round(total_loss * 0.18, 2)
    net_gain = round(total_loss - commission, 2)

    return {
        "analysis_summary": {
            "scan_mode": "PLATFORM_DIGITAL_AUDIT",
            "total_operations_scanned": len(transactions_list),
            "hidden_costs_detected": len(detected_losses),
            "monthly_bleed_estimated": round(total_loss / 3, 2),
            "annual_leak_projected": round(total_loss * 4, 2)
        },
        "financial_action": {
            "service_fee_rate": 0.18,
            "client_recovery_potential_net": net_gain,
            "platform_revenue_gross": commission
        },
        "detected_items_anonymized": detected_losses
    }

# ==========================================
# ROUTE API UPLOAD DE FICHIERS
# ==========================================
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
        
        lines_processed = 0
        skipped_header = False

        for row in reader:
            if not row: continue 
            
            if lines_processed == 0 and not skipped_header:
                first_cell = str(row[0]).upper()
                if any(keyword in first_cell for keyword in ["LIBELLE", "LABEL", "DESCRIPTION", "DATE", "MONTANT", "AMOUNT"]):
                    skipped_header = True
                    continue
                    
            if len(row) >= 2:
                label = str(row[0]).strip()
                raw_amount = str(row[1]).strip()
                
                try:
                    clean_amount = raw_amount.replace(',', '.').replace(' ', '').replace('€', '').replace('$', '')
                    if clean_amount.startswith('(') and clean_amount.endswith(')'):
                        clean_amount = '-' + clean_amount[1:-1]
                    amount = float(clean_amount)
                    
                    if amount != 0 and label:
                        transactions.append({"label": label, "amount": amount})
                except ValueError:
                    continue
                    
            lines_processed += 1

        if not transactions:
             return jsonify({"error": "Format invalide ou aucune donnée chiffrée détectée."}), 400

        mode_param = request.form.get('mode', 'classic_file') 
        
        if mode_param == 'digital_text':
            result_data = analyze_digital_platforms(transactions)
        else:
            result_data = perform_analysis(transactions)
        
        user_id = "guest_" + str(random.randint(100000, 999999))
        last_analyses_store[user_id] = result_data
        
        data_json = json.dumps(result_data)
        encoded_token = base64.urlsafe_b64encode(data_json.encode()).decode()
        
        return jsonify({
            "status": "success",
            "message": f"Audit [{mode_param.upper()}] terminé.",
            "data": result_data,
            "temp_user_id": user_id,
            "report_token": encoded_token
        })

    except Exception as e:
        print(f"Erreur analyse fichier: {str(e)}")
        return jsonify({"error": f"Échec lecture fichier: {str(e)}"}), 500

# ==========================================
# INTÉGRATION NOWPAYMENTS (VERSION SIMPLE + AVANCÉE)
# ==========================================
@app.route('/create-crypto-charge', methods=['POST'])
def create_crypto_charge():
    """Crée une facture de paiement crypto via l'API NowPayments."""
    try:
        data = request.get_json()
        temp_user_id = data.get('temp_user_id', 'unknown')
        report_token = data.get('report_token', '')
        
        # NOUVEAU : Gestion des deux versions de paiement
        payment_type = data.get('payment_type', 'simple') # 'simple' ou 'advanced'
        pay_currency = data.get('pay_currency', 'usdttrc20').lower()
        
        # CORRECTION CRUCIALE : Montant fixé à 19.99€ pour être AU-DESSUS du minimum de TOUTES les cryptos (ex: BTC)
        price_amount = 19.99 
        
        # Liste des cryptos autorisées pour la version avancée (fallback sur USDT TRC20)
        allowed_currencies = ['btc', 'eth', 'usdttrc20', 'usdcter20', 'usdc', 'bnb', 'ltc', 'xrp', 'trx']
        if pay_currency not in allowed_currencies:
            pay_currency = 'usdttrc20'

        print("--- DÉBUT DEBUG NOWPAYMENTS ---")
        print(f"Type de paiement: {payment_type}, Crypto choisie: {pay_currency}, Montant: {price_amount} EUR")
        print(f"API Key présente: {bool(NOWPAYMENTS_API_KEY)}")
        if NOWPAYMENTS_API_KEY:
            print(f"API Key (début): {NOWPAYMENTS_API_KEY[:10]}...")
        else:
            print("ERREUR CRITIQUE: NOWPAYMENTS_API_KEY est vide ou None dans Render !")
            return jsonify({"error": "API Key NowPayments non configurée dans Render"}), 500

        payload = {
            "price_amount": price_amount,
            "price_currency": "eur",
            "pay_currency": pay_currency,
            "ipn_callback_url": f"{request.host_url.rstrip('/')}/webhook",
            "order_id": temp_user_id,
            "order_description": f"Sentinel Finance - Rapport Complet ({pay_currency.upper()})",
            "success_url": f"{request.host_url.rstrip('/')}/?status=paid",
            "cancel_url": f"{request.host_url.rstrip('/')}/",
            "is_fixed_rate": False,
            "is_fee_paid_by_user": True
        }

        headers = {
            "x-api-key": NOWPAYMENTS_API_KEY,
            "Content-Type": "application/json"
        }

        print(f"Envoi de la requête à: {NOWPAYMENTS_API_URL}/payment")
        
        response = requests.post(
            f"{NOWPAYMENTS_API_URL}/payment",
            json=payload,
            headers=headers,
            timeout=10
        )

        print(f"Status Code de la réponse: {response.status_code}")
        print(f"Réponse brute de NowPayments: {response.text}")
        print("--- FIN DEBUG NOWPAYMENTS ---")

        # ✅ CORRECTION : NowPayments retourne 201 (Created) pour les paiements créés avec succès
        if response.status_code not in [200, 201]:
            return jsonify({
                "error": f"Erreur NowPayments ({response.status_code}): {response.text}"
            }), response.status_code

        payment_data = response.json()
        payment_id = str(payment_data.get('payment_id'))
        invoice_url = payment_data.get('invoice_url')

        # 🚨 CORRECTION ULTIME : Si NowPayments renvoie une URL null, on la construit nous-mêmes
        if not invoice_url and payment_id:
            invoice_url = f"https://nowpayments.io/payment/?iid={payment_id}"
            print(f"⚠️ invoice_url manquant. URL de secours générée : {invoice_url}")

        payments_store[payment_id] = {
            'user_id': temp_user_id,
            'report_token': report_token,
            'status': 'waiting',
            'created_at': datetime.now().isoformat(),
            'amount': f'{price_amount} EUR'
        }

        return jsonify({
            "status": "success",
            "payment_id": payment_id,
            "invoice_url": invoice_url,
            "message": "Redirection vers le paiement sécurisé..."
        })

    except requests.exceptions.Timeout:
        return jsonify({"error": "Délai d'attente dépassé"}), 504
    except Exception as e:
        print(f"Erreur complète inattendue: {str(e)}")
        return jsonify({"error": str(e)}), 500

# ==========================================
# WEBHOOK IPN (NOTIFICATION DE PAIEMENT NOWPAYMENTS)
# ==========================================
@app.route('/webhook', methods=['POST'])
def handle_webhook():
    """Reçoit et vérifie les notifications de paiement de NowPayments."""
    try:
        if not NOWPAYMENTS_IPN_SECRET:
            return jsonify({"error": "IPN Secret non configuré"}), 500

        signature = request.headers.get('x-nowpayments-sig', '')
        if not signature:
            return jsonify({"error": "Signature manquante"}), 400

        raw_body = request.get_data()
        expected_signature = hmac.new(
            NOWPAYMENTS_IPN_SECRET.encode('utf-8'),
            raw_body,
            hashlib.sha512
        ).hexdigest()

        if not hmac.compare_digest(signature, expected_signature):
            print("⚠️ Signature webhook invalide")
            return jsonify({"error": "Signature invalide"}), 403

        payment_data = json.loads(raw_body)
        payment_id = str(payment_data.get('payment_id', ''))
        payment_status = payment_data.get('payment_status', '')
        order_id = payment_data.get('order_id', '')

        print(f"Webhook reçu: payment_id={payment_id}, status={payment_status}, order_id={order_id}")

        if payment_id in payments_store:
            payment_info = payments_store[payment_id]

            if payment_status in ['finished', 'confirmed']:
                payment_info['status'] = 'paid'
                payment_info['paid_at'] = datetime.now().isoformat()
                print(f"✅ Paiement confirmé: {payment_id}")
            elif payment_status in ['failed', 'expired', 'refunded']:
                payment_info['status'] = 'failed'
                print(f"❌ Paiement échoué: {payment_id}")
            else:
                payment_info['status'] = payment_status

        return jsonify({"status": "ok"}), 200

    except Exception as e:
        print(f"Webhook error: {str(e)}")
        return jsonify({"error": str(e)}), 500

# ==========================================
# VÉRIFICATION DU STATUT DE PAIEMENT (POLLING)
# ==========================================
@app.route('/check-payment/<payment_id>', methods=['GET'])
def check_payment_status(payment_id):
    """Permet au frontend de vérifier si le paiement a été confirmé."""
    if payment_id not in payments_store:
        return jsonify({"status": "not_found"}), 404
    
    payment_info = payments_store[payment_id]
    
    if payment_info['status'] == 'paid':
        report_token = payment_info.get('report_token', '')
        user_id = payment_info.get('user_id', 'unknown')
        return jsonify({
            "status": "paid",
            "report_url": f"/download-report/{user_id}?token={report_token}&paid=true"
        })
    else:
        return jsonify({
            "status": payment_info['status'],
            "message": "Paiement en attente de confirmation blockchain..."
        })

# ==========================================
# GÉNÉRATEUR DE RAPPORT PDF NATIF
# ==========================================
class PDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 15)
        self.cell(0, 10, 'RAPPORT D\'AUDIT FINANCIER SENTINEL', ln=True, align='C')
        self.ln(5)
        self.set_draw_color(26, 35, 126) 
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.set_text_color(128)
        self.cell(0, 10, f'Sentinel Finance © {datetime.now().year} | Page {self.page_no()}/{{nb}}', align='C')

def generate_pdf_report(uid, analysis_data, is_paid=False):
    pdf = PDF()
    pdf.alias_nb_pages()
    pdf.add_page()
    
    summary = analysis_data['analysis_summary']
    financial_action = analysis_data['financial_action']
    detected_items = analysis_data['detected_items_anonymized']
    
    is_digital = summary.get('scan_mode') == 'PLATFORM_DIGITAL_AUDIT'
    
    pdf.set_font('Arial', '', 10)
    pdf.set_text_color(100)
    pdf.cell(0, 8, f'ID Client : {uid}', ln=True)
    pdf.cell(0, 8, f'Date d\'analyse : {datetime.now().strftime("%d/%m/%Y")}', ln=True)
    pdf.ln(5)

    pdf.set_fill_color(255, 243, 224) 
    pdf.set_text_color(230, 81, 0) 
    pdf.rect(10, pdf.get_y(), 190, 35, style='F')
    pdf.set_xy(15, pdf.get_y() + 5)
    pdf.set_font('Arial', 'B', 12)
    
    if is_digital:
        alert_text = (f"AUDIT DIGITAL COMPLETE\n"
                      f"Frais caches detectes : {summary['hidden_costs_detected']} anomalies.\n"
                      f"Perte mensuelle moyenne : {summary['monthly_bleed_estimated']} EUR\n"
                      f"Gaspillage annuel projete : {summary['annual_leak_projected']} EUR")
    else:
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

    col_widths = [80, 55, 55]
    
    if is_digital:
        headers = ['Plateforme / Operation', 'Cout Cache', 'Impact Annuel']
    else:
        headers = ['Categorie Abonnement', 'Cout Mensuel', 'Impact Annuel']
    
    pdf.set_font('Arial', 'B', 10)
    pdf.set_fill_color(26, 35, 126)
    pdf.set_text_color(255)
    for i, h in enumerate(headers):
        pdf.cell(col_widths[i], 8, h, border=1, fill=True, align='C' if i > 0 else 'L')
    pdf.ln()

    pdf.set_font('Arial', '', 10)
    pdf.set_text_color(0)
    for idx, item in enumerate(detected_items):
        if is_digital:
            cat_name = item.get('platform_label', 'Inconnu')[:30] 
            cost_val = f"-{item['cost_incurred']} EUR"
            yearly_impact = f"~ {round(item['cost_incurred']*12, 2)} EUR"
        else:
            cat_name = item['category_code'].replace('_', ' ').title()
            cost_val = f"-{item['amount_monthly']} EUR"
            yearly_impact = f"~ {round(item['amount_monthly']*12, 2)} EUR"
        
        fill_style = (idx % 2 == 0)
        if fill_style:
            pdf.set_fill_color(245, 245, 245) 
            
        pdf.cell(col_widths[0], 8, cat_name, border=1, fill=fill_style)
        pdf.cell(col_widths[1], 8, cost_val, border=1, fill=fill_style, align='R')
        pdf.cell(col_widths[2], 8, yearly_impact, border=1, fill=fill_style, align='R')
        pdf.ln()

    total_annual = summary['annual_leak_projected'] if is_digital else summary['yearly_loss_projected']
    pdf.set_font('Arial', 'B', 11)
    pdf.set_text_color(211, 47, 47) 
    pdf.cell(sum(col_widths[:-1]), 8, 'TOTAL PERDU PAR AN :', border=1, align='R')
    pdf.cell(col_widths[-1], 8, f'{total_annual} EUR', border=1, align='R')
    pdf.ln(10)

    pdf.set_text_color(0)
    pdf.set_font('Arial', 'B', 14)
    pdf.cell(0, 10, 'Votre Gain Potentiel Reel', ln=True)
    pdf.ln(2)
    pdf.set_font('Arial', '', 11)
    
    gain_net = financial_action['client_recovery_potential_net'] if is_digital else financial_action['client_savings_net_monthly']
    
    action_text = (f"Si vous arretez ces fuites des aujourd'hui, vous recupererez :\n"
                   f"+ {gain_net} EUR nets par mois dans votre poche.")
    pdf.multi_cell(0, 7, action_text)
    pdf.ln(5)

    if not is_paid:
        pdf.set_draw_color(211, 47, 47)
        pdf.set_line_width(1)
        pdf.rect(10, pdf.get_y(), 190, 60, style='D')
        pdf.set_xy(15, pdf.get_y() + 5)
        pdf.set_font('Arial', 'B', 13)
        pdf.set_text_color(211, 47, 47)
        pdf.cell(0, 8, 'CONTENU EXCLUSIF MASQUE', ln=True)
        pdf.set_font('Arial', '', 10)
        pdf.set_text_color(0)
        # MISE À JOUR DU PRIX DANS LE PDF (19.99 EUR)
        locked_content = """
Pour obtenir le plan d'action detaille permettant de recuperer ces gains, veuillez payer 19.99 EUR via crypto-monnaie.

Le rapport COMPLET inclut :
- Les numeros verts exacts pour resilier chaque abonnement.
- Les scripts telephoniques prets a l'emploi.
- La comparaison tarifaire alternative.
- Un suivi automatise pour verifier que les fuites sont bien colmatees.
        """
        pdf.multi_cell(0, 5, locked_content.strip())
    else:
        pdf.set_draw_color(76, 175, 80)
        pdf.set_line_width(1)
        pdf.rect(10, pdf.get_y(), 190, 75, style='D')
        pdf.set_xy(15, pdf.get_y() + 5)
        pdf.set_font('Arial', 'B', 13)
        pdf.set_text_color(76, 175, 80)
        pdf.cell(0, 8, 'RAPPORT COMPLET DEBLOQUE - PLAN D\'ACTION', ln=True)
        pdf.set_font('Arial', '', 10)
        pdf.set_text_color(0)
        
        unlocked_content = "PLAN D'ACTION PERSONNALISE :\n\n1. RESILIATION IMMEDIATE (Scripts prets):\n"
        for idx, item in enumerate(detected_items[:5], 1):
            if is_digital:
                service = item.get('platform_label', 'Service')[:25]
            else:
                service = item['category_code'].replace('_', ' ').title()
            unlocked_content += f"   {idx}. {service} - Contact: support@service.com\n"
        
        unlocked_content += "\n2. ALTERNATIVES ECONOMIQUES :\n   - Comparatif complet des fournisseurs\n   - Liens directs vers les offres moins cheres"
        unlocked_content += "\n\n3. SUIVI AUTOMATISE :\n   - Acces au dashboard Sentinel\n   - Alertes mensuelles sur vos depenses"
        
        pdf.multi_cell(0, 5, unlocked_content)
    
    pdf.ln(5)
    pdf.set_font('Arial', 'I', 9)
    pdf.set_text_color(100)
    pdf.multi_cell(0, 5, "Important : Sentinel Finance est un outil d'audit et de conseil independant. Nous n'avons pas acces a vos comptes bancaires.")

    return bytes(pdf.output()) 

@app.route('/download-report/<uid>', methods=['GET'])
def download_report_pdf(uid):
    """Genere le PDF et force le telechargement."""
    analysis_data = None
    is_paid = False
    
    paid_param = request.args.get('paid', 'false')
    if paid_param == 'true':
        is_paid = True
    
    if uid in last_analyses_store:
        analysis_data = last_analyses_store[uid]
    else:
        token_param = request.args.get('token')
        if token_param:
            try:
                decoded_bytes = base64.urlsafe_b64decode(token_param.encode())
                analysis_data = json.loads(decoded_bytes.decode())
            except Exception as decode_err:
                print(f"Erreur decodage token: {decode_err}")

    if not analysis_data:
        return "<h2>Erreur : Donnees introuvables.</h2><a href='/'>Retour Accueil</a>", 404

    try:
        pdf_binary = generate_pdf_report(uid, analysis_data, is_paid=is_paid)
        response = make_response(pdf_binary)
        filename = f"Apercu_Sentinel_{uid}.pdf"
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
    except Exception as e:
        print(f"Erreur generation PDF: {str(e)}")
        return f"<h2>Crash Serveur PDF: {str(e)}</h2>", 500

@app.route('/final-report/<uid>', methods=['GET'])
def serve_final_report_redirect(uid):
    token = request.args.get('token', '')
    query_string = f"?token={token}" if token else ""
    return redirect(f"/download-report/{uid}{query_string}")

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8000))
    app.run(host='0.0.0.0', port=port, debug=False)