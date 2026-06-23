provider "aws" {
  region = "us-west-2"
}

resource "aws_s3_bucket" "transaction_bucket" {
  bucket        = "my-unique-transaction-bucket-name" 
  force_destroy = true                                 
}

resource "aws_s3_object" "folder_raw" {
  bucket       = aws_s3_bucket.transaction_bucket.id
  key          = "raw-transaction/"
  content_type = "application/x-directory"
}

resource "aws_s3_object" "folder_athena" {
  bucket       = aws_s3_bucket.transaction_bucket.id
  key          = "hasil-athena/"
  content_type = "application/x-directory"
}

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
