from flask import Flask, request, jsonify, render_template_string

app = Flask(__name__)

# Storage sementara di memori untuk demo dashboard
logs_fraud = []

# Template HTML sederhana untuk Dashboard
DASHBOARD_TEMPLATE = """
<!DOCTYPE html>
<html>
<head><title>EC2 Dashboard - Fraud Monitoring</title></head>
<body>
    <h1>Fraud Monitoring Dashboard (Port 8080)</h1>
    <hr>
    <h2>Log Insiden Fraud Terbaru:</h2>
    <ul>
        {% for log in logs %}
            <li style="color: red;"><strong>[FRAUD]</strong> {{ log }}</li>
        {% else %}
            <li style="color: green;">Belum ada insiden fraud terdeteksi.</li>
        {% endfor %}
    </ul>
</body>
</html>
"""

@app.route('/', methods=['GET'])
def index():
    return render_template_string(DASHBOARD_TEMPLATE, logs=logs_fraud)

# Endpoint Webhook untuk menerima data dari AWS SNS
@app.route('/webhook', methods=['POST'])
def sns_webhook():
    data = request.get_json(force=True)

    sns_type = data.get('Type')
    # AWS SNS mengirimkan konfirmasi langganan pertama kali berbentuk 'SubscriptionConfirmation'
    if sns_type == 'SubscriptionConfirmation':
        print(f"Salin URL ini untuk konfirmasi SNS: {data.get('SubscribeURL')}", flush=True)
        return jsonify({"status": "pending_confirmation"}), 200

    if data and 'Message' in data:
        logs_fraud.append(data['Message'])

    return jsonify({"status": "received"}), 200

if __name__ == '__main__':
    # Berjalan di port 8080 sesuai diagram
    app.run(host='0.0.0.0', port=8080)

