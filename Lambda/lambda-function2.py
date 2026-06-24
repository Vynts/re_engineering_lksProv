import json
import os
import urllib.request
from datetime import datetime, timezone
from decimal import Decimal
import boto3

# Inisialisasi AWS Clients & Config
DYNAMODB = boto3.resource('dynamodb')
S3 = boto3.client('s3')
SNS = boto3.client('sns')

GROQ_API_KEY = os.environ.get('GROQ_API_KEY', '').strip()
TABLE_NAME = os.environ.get('TABLE_NAME')
BUCKET_NAME = os.environ.get('BUCKET_NAME')
SNS_TOPIC_ARN = os.environ.get('SNS_TOPIC_ARN')

# Ambil referensi ke tabel DynamoDB secara global
TABLE = DYNAMODB.Table(TABLE_NAME) if TABLE_NAME else None

def lambda_handler(event, context):
    try:
        # 1. Ambil Data Input
        body = json.loads(event['body']) if event and isinstance(event.get('body'), str) else (event.get('body', event) or {})
        
        amount = body.get('amount', 0)
        user_id = body.get('user_id', 'unknown')
        # Mengganti datetime.utcnow() dengan timezone-aware datetime
        current_time = datetime.now(timezone.utc)
        transaction_id = body.get('transaction_id', str(int(current_time.timestamp())))
        
        # 2. Proses ETL Cepat
        pajak = int(round(amount * 0.11))
        total_billing = amount + pajak
        processed_at = current_time.isoformat()
        
        # 3. Request AI & Langsung Return Status
        status_ai = "AMAN"
        if GROQ_API_KEY:
            payload = {
                "model": "llama3-8b-8192",
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
            "transaction_id": transaction_id, 
            "user_id": user_id, 
            "amount": amount,
            "pajak_11": pajak, 
            "total_billing": total_billing, 
            "status_ai": status_ai, 
            "processed_at": processed_at
        }
        
        # Data khusus untuk DynamoDB (konversi angka ke Decimal agar aman dari error float)
        dynamo_data = json.loads(json.dumps(transaction_data), parse_float=Decimal)
        
        # 5. Simpan ke DynamoDB & S3
        if TABLE:
            TABLE.put_item(Item=dynamo_data)  # PERBAIKAN: Menggunakan objek Table
        else:
            print("Warning: TABLE_NAME environment variable is not set.")

        if BUCKET_NAME:
            S3.put_object(
                Bucket=BUCKET_NAME, 
                Key=f"raw-transactions/{transaction_id}.json", 
                Body=json.dumps(transaction_data), 
                ContentType='application/json'
            )
        
        # 6. Kirim Alert Jika Fraud
        if status_ai == "FRAUD" and SNS_TOPIC_ARN:
            SNS.publish(TopicArn=SNS_TOPIC_ARN, Message=json.dumps(transaction_data), Subject="Fraud Incident Alert!")
            
        return {
            "statusCode": 200,
            "body": json.dumps({"message": "Transaction processed successfully", "status": status_ai, "data": transaction_data})
        }
        
    except Exception as e:
        print(f"Handler Error: {str(e)}") # Log error ke CloudWatch agar mudah di-debug
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}