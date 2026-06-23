import json
import os
import urllib.request
from datetime import datetime
import boto3

# Inisialisasi AWS Clients & Config
DYNAMODB = boto3.resource('dynamodb').Table(os.environ.get('TABLE_NAME'))
S3 = boto3.client('s3')
SNS = boto3.client('sns')

GROQ_API_KEY = os.environ.get('GROQ_API_KEY', '').strip()
BUCKET_NAME = os.environ.get('BUCKET_NAME')
SNS_TOPIC_ARN = os.environ.get('SNS_TOPIC_ARN')

def lambda_handler(event, context):
    try:
        # 1. Ambil Data Input (Langsung parsing sebaris)
        body = json.loads(event['body']) if event and isinstance(event.get('body'), str) else (event.get('body', event) or {})
        
        amount = body.get('amount', 0)
        user_id = body.get('user_id', 'unknown')
        transaction_id = body.get('transaction_id', str(int(datetime.utcnow().timestamp())))
        
        # 2. Proses ETL Cepat
        pajak = int(round(amount * 0.11))
        total_billing = amount + pajak
        processed_at = datetime.utcnow().isoformat()
        
        # 3. Request AI & Langsung Return Status
        status_ai = "AMAN"
        if GROQ_API_KEY:
            payload = {
                "model": "llama-3.1-8b-instant",
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
                    status_ai = "".join(c for c in raw if c.isalnum()).upper().strip()
            except Exception as e:
                print(f"Groq Fail: {e}")

        # 4. Satukan Data Hasil Transformasi
        transaction_data = {
            "transaction_id": transaction_id, "user_id": user_id, "amount": amount,
            "pajak_11": pajak, "total_billing": total_billing, "status_ai": status_ai, "processed_at": processed_at
        }
        
        # 5. Simpan ke DynamoDB & S3 (Tanpa variabel penampung tambahan)
        DYNAMODB.put_item(Item=transaction_data)
        S3.put_object(Bucket=BUCKET_NAME, Key=f"raw-transactions/{transaction_id}.json", Body=json.dumps(transaction_data), ContentType='application/json')
        
        # 6. Kirim Alert Jika Fraud
        if status_ai == "FRAUD":
            SNS.publish(TopicArn=SNS_TOPIC_ARN, Message=json.dumps(transaction_data), Subject="Fraud Incident Alert!")
            
        return {
            "statusCode": 200,
            "body": json.dumps({"message": "Transaction processed successfully", "status": status_ai, "data": transaction_data})
        }
        
    except Exception as e:
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}