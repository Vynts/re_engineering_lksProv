import json, os, urllib.request, boto3
from datetime import datetime, timezone

# 1. SETUP AWS & CONFIG
DB = boto3.resource('dynamodb').Table(os.getenv('TABLE_NAME', ''))
S3, SNS = boto3.client('s3'), boto3.client('sns')
KEY = os.getenv('GROQ_API_KEY', '').strip()

def lambda_handler(event, context):
    try:
        # 2. PARSING INPUT & DEKLARASI DATA
        body = event.get('body', event)
        body = json.loads(body) if isinstance(body, str) else (body or {})
        
        amt = body.get('amount', 0)
        pajak = int(amt * 0.11)
        tx_id = body.get('transaction_id', str(int(datetime.now(timezone.utc).timestamp())))

        data = {
            "transaction_id": tx_id, "user_id": body.get('user_id', 'unknown'),
            "amount": amt, "pajak_11": pajak, "total_billing": amt + pajak,
            "status_ai": "AMAN", "processed_at": datetime.now(timezone.utc).isoformat()
        }

        # 3. KONEKSI KE AI (GROQ)
        if KEY:
            req = urllib.request.Request(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"},
                data=json.dumps({
                    "model": "llama-3.1-8b-instant",
                    "messages": [
                        {"role": "system", "content": "If amount >= 100000000 or user_id contains 'hacker', reply FRAUD. Otherwise AMAN."},
                        {"role": "user", "content": f"User:{data['user_id']}, Amt:{amt}"}
                    ], "temperature": 0.0
                }).encode(), method='POST'
            )
            try:
                with urllib.request.urlopen(req, timeout=4) as res:
                    raw = json.loads(res.read().decode())['choices'][0]['message']['content']
                    data["status_ai"] = "".join(c for c in raw if c.isalnum()).upper().strip()
            except Exception as e: print(f"AI Fail: {e}")

        # 4. SIMPAN AWS (DynamoDB, S3, SNS)
        if os.getenv('TABLE_NAME'): DB.put_item(Item=data)
        if os.getenv('BUCKET_NAME'): S3.put_object(Bucket=os.getenv('BUCKET_NAME'), Key=f"raw-transactions/{tx_id}.json", Body=json.dumps(data))
        if data["status_ai"] == "FRAUD" and os.getenv('SNS_TOPIC_ARN'): SNS.publish(TopicArn=os.getenv('SNS_TOPIC_ARN'), Message=json.dumps(data))

        return {"statusCode": 200, "body": json.dumps({"status": data["status_ai"], "data": data})}

    except Exception as e:
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}
