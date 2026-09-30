from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route('/')
def home():
    return jsonify({"status": "ok", "message": "Sentinel v2 is alive"})

@app.route('/analyze', methods=['POST'])
def analyze():
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data"}), 400
    
    # Calcul simple pour tester
    total = sum(abs(t['amount']) for t in data.get('transactions', []))
    
    return jsonify({
        "status": "success",
        "total_processed": total,
        "commission_15pct": round(total * 0.15, 2)
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)