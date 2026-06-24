CREATE EXTERNAL TABLE IF NOT EXISTS lks_analytics.transactions (
    transaction_id string,
    user_id string,
    amount bigint,
    pajak_11 bigint,
    total_billing bigint,
    status_ai string,
    processed_at string
)
ROW FORMAT SERDE 'org.openx.data.jsonserde.JsonSerDe'
LOCATION 's3://transaction-buckets/raw-transactions/';