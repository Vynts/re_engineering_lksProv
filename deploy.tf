provider "aws" {
  region = "ap-southeast-1" # Ubah sesuai region yang kamu inginkan
}

# ==========================================
# 1. KONFIGURASI S3 BUCKET
# ==========================================

resource "aws_s3_bucket" "transaction_bucket" {
  bucket        = "my-unique-transaction-bucket-name" # Pastikan nama bucket ini unik secara global
  force_destroy = true                                 # Mengizinkan bucket dihapus beserta serves didalamnya saat terraform destroy
}

# Membuat Folder "raw-transaction" di S3
resource "aws_s3_object" "folder_raw" {
  bucket       = aws_s3_bucket.transaction_bucket.id
  key          = "raw-transaction/"
  content_type = "application/x-directory"
}

# Membuat Folder "hasil-athena" di S3
resource "aws_s3_object" "folder_athena" {
  bucket       = aws_s3_bucket.transaction_bucket.id
  key          = "hasil-athena/"
  content_type = "application/x-directory"
}

# ==========================================
# 2. KONFIGURASI DYNAMODB TABLE
# ==========================================

resource "aws_dynamodb_table" "transaction_table" {
  name         = "transactions"
  billing_mode = "PAY_PER_REQUEST" # Menggunakan mode On-Demand agar hemat biaya seperlunya
  hash_key     = "transaction_id"

  attribute {
    name = "transaction_id"
    type = "S" # S = String, gunakan "N" jika id berupa Number
  }

  tags = {
    Environment = "Development"
    Project     = "TransactionData"
  }
}