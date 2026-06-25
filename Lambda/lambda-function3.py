import json
import os
import ssl
import boto3
import urllib.request
from datetime import datetime

# Inisialisasi AWS SDK
dynamodb = boto3.resource('dynamodb')
s3 = boto3.client('s3')
sns = boto3.client('sns')

# Ambil konfigurasi dari Environment Variables Lambda
GROQ_API_KEY = os.environ.get('GROQ_API_KEY')
TABLE_NAME = os.environ.get('TABLE_NAME')
BUCKET_NAME = os.environ.get('BUCKET_NAME')
SNS_TOPIC_ARN = os.environ.get('SNS_TOPIC_ARN')

def lambda_handler(event, context):
    try:
        # 1. Parsing data cerdas (Mendukung Proxy Integration Aktif maupun Non-Aktif)
        body = {}
        if event and 'body' in event:
            if isinstance(event['body'], str):
                body = json.loads(event['body'])
            elif isinstance(event['body'], dict):
                body = event['body']
        elif isinstance(event, dict):
            body = event
            
        # Pastikan variabel ini selalu terdefinisi dengan nilai default jika key tidak ditemukan
        amount = body.get('amount', 0)
        user_id = body.get('user_id', 'unknown')
        transaction_id = body.get('transaction_id', str(int(datetime.utcnow().timestamp())))
        
        # 2. Proses ETL (Hitung Pajak 11% & Total Billing) - Bulatkan ke Integer
        pajak = int(round(amount * 0.11))
        total_billing = amount + pajak
        processed_at = datetime.utcnow().isoformat()
        
        # 3. AI: Deteksi AMAN / FRAUD via Groq API
        status_ai = "AMAN" # Default
        print(f"=== DEBUG API KEY: {GROQ_API_KEY} ===")
        
        if GROQ_API_KEY:
            # Tambahkan User-Agent browser agar tidak diblokir oleh Cloudflare/Groq
            headers = {
                "Authorization": f"Bearer {GROQ_API_KEY.strip()}",
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
            payload = {
                "model": "llama-3.1-8b-instant",
                "messages": [
                    {
                        "role": "system", 
                        "content": "You are a fraud detection AI. Analyze the transaction amount. If the amount is 100,000,000 or above, or if the user_id contains suspicious words like 'hacker', you MUST reply strictly with only one word: 'FRAUD'. Otherwise, reply strictly with 'AMAN'."
                    },
                    {"role": "user", "content": f"User: {user_id}, Amount: {amount}"}
                ],
                "temperature": 0.0
            }
            
            try:
                # Membuat context untuk bypass verifikasi SSL
                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
                
                req = urllib.request.Request(
                    "https://api.groq.com/openai/v1/chat/completions",
                    data=json.dumps(payload).encode('utf-8'),
                    headers=headers,
                    method='POST'
                )
                
                # Tambahkan parameter context=ctx di dalam urlopen
                with urllib.request.urlopen(req, timeout=5, context=ctx) as response:
                    res_json = json.loads(response.read().decode('utf-8'))
                    raw_content = res_json['choices'][0]['message']['content']
                    status_ai = "".join(c for c in raw_content if c.isalnum()).strip().upper()
                    
            except Exception as e:
                print(f"Groq API Error: {str(e)}")
                # Biar tidak bikin crash seluruh fungsi, lempar error-nya ke status_ai
                status_ai = f"ERROR_GROQ: {str(e)}"
        else:
            status_ai = "ERROR_KEY_NOT_FOUND"
        
        # Bungkus data hasil transformasi
        transaction_data = {
            "transaction_id": transaction_id, 
            "user_id": user_id,
            "amount": amount,
            "pajak_11": pajak,
            "total_billing": total_billing,
            "status_ai": status_ai,
            "processed_at": processed_at
        }
        
        # 4. Simpan ke DynamoDB
        table = dynamodb.Table(TABLE_NAME)
        table.put_item(Item=transaction_data)
        
        # 5. Arsip JSON ke S3
        s3_key = f"raw-transactions/{transaction_id}.json"
        s3.put_object(
            Bucket=BUCKET_NAME,
            Key=s3_key,
            Body=json.dumps(transaction_data),
            ContentType='application/json'
        )
        
        # 6. Jika FRAUD -> Publish ke SNS
        if "FRAUD" in status_ai:
            message = f"ALERT: Terdeteksi transaksi FRAUD!\nID: {transaction_id}\nTotal: {total_billing}"
            sns.publish(
                TopicArn=SNS_TOPIC_ARN,
                Message=message,
                Subject="Fraud Incident Alert!"
            )
            
        return {
            "statusCode": 200,
            "body": json.dumps({"message": "Transaction processed successfully", "status": status_ai, "data": transaction_data})
        }
        
    except Exception as e:
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)})
        }
