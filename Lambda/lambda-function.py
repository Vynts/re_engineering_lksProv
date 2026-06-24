import json
import os
import urllib.request
from datetime import datetime, timezone
import boto3

# Inisialisasi AWS Clients & Config di luar handler (Reused across invocations)
DYNAMODB = boto3.resource('dynamodb')
S3 = boto3.client('s3')
SNS = boto3.client('sns')

GROQ_API_KEY = os.environ.get('GROQ_API_KEY', '').strip()
TABLE = DYNAMODB.Table(os.environ['TABLE_NAME']) if os.environ.get('TABLE_NAME') else None
BUCKET_NAME = os.environ.get('BUCKET_NAME')
SNS_TOPIC_ARN = os.environ.get('SNS_TOPIC_ARN')

def lambda_handler(event, context):
    try:
        # 1. Ambil Data Input (Lebih bersih)
        body = event.get('body', event)
        if isinstance(body, str):
            body = json.loads(body)
        body = body or {}

        amount = body.get('amount', 0)
        user_id = body.get('user_id', 'unknown')
        current_time = datetime.now(timezone.utc)
        transaction_id = body.get('transaction_id', str(int(current_time.timestamp())))

        # 2. Proses ETL Cepat (Hasilnya murni Integer, aman untuk DynamoDB)
        pajak = int(round(amount * 0.11))
        
        transaction_data = {
            "transaction_id": transaction_id, 
            "user_id": user_id, 
            "amount": amount,
            "pajak_11": pajak, 
            "total_billing": amount + pajak, 
            "status_ai": "AMAN", 
            "processed_at": current_time.isoformat()
        }

        # 3. Request AI (Gunakan Llama 3.1 terbaru agar tidak error 404)
        if GROQ_API_KEY:
            payload = {
                "model": "llama-3.1-8b-instant",  # Diperbarui ke model yang aktif
                "messages": [
                    {"role": "system", "content": "You are a fraud detection AI. If amount >= 100000000 or user_id contains 'hacker', reply strictly with 'FRAUD'. Otherwise, reply 'AMAN'."},
                    {"role": "user", "content": f"User: {user_id}, Amount: {amount}"}
                ],
                "temperature": 0.0
            }
            req = urllib.request.Request(
                "https://api.groq.com/openai/v1/chat/completions",
                data=json.dumps(payload).encode('utf-8'),
                headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
                method='POST'
            )
            try:
                with urllib.request.urlopen(req, timeout=5) as res:
                    res_json = json.loads(res.read().decode('utf-8'))
                    raw = res_json['choices'][0]['message']['content']
                    transaction_data["status_ai"] = "".join(c for c in raw if c.isalnum()).upper().strip()
            except Exception as e:
                print(f"Groq Fail: {e}")

        # 4. Simpan ke DynamoDB & S3 (Tanpa konversi Decimal berulang)
        if TABLE:
            TABLE.put_item(Item=transaction_data)

        if BUCKET_NAME:
            S3.put_object(
                Bucket=BUCKET_NAME, 
                Key=f"raw-transactions/{transaction_id}.json", 
                Body=json.dumps(transaction_data), 
                ContentType='application/json'
            )

        # 5. Kirim Alert Jika Fraud
        if transaction_data["status_ai"] == "FRAUD" and SNS_TOPIC_ARN:
            SNS.publish(TopicArn=SNS_TOPIC_ARN, Message=json.dumps(transaction_data), Subject="Fraud Incident Alert!")

        return {
            "statusCode": 200,
            "body": json.dumps({"message": "Transaction processed successfully", "status": transaction_data["status_ai"], "data": transaction_data})
        }

    except Exception as e:
        print(f"Handler Error: {str(e)}")
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}
