 from flask import Flask, request, jsonify

app = Flask(__name__)

# Route Racine (Test de vie)
@app.route('/', methods=['GET'])
def home():
    return jsonify({"status": "ok", "message": "Sentinel v2 is alive"})

# Route Analyse (Le vrai travail)
@app.route('/analyze', methods=['POST'])
def analyze():
    data = request.get_json()
    
    if not data:
        return jsonify({"error": "No data sent"}), 400
        
    user_id = data.get('user_id', 'Unknown')
    transactions = data.get('transactions', [])
    
    # Logique simplifiée pour le test
    total_spent = sum(abs(t['amount']) for t in transactions if t['amount'] < 0)
    
    return jsonify({
        "status": "success",
        "user": user_id,
        "total_transactions": len(transactions),
        "estimated_loss_monthly": round(total_spent / 12, 2), # Simulation bête
        "commission_15_percent": round((total_spent / 12) * 0.15, 2)
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)