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
  billing_mode = "PAY_PER_REQUEST" 
  hash_key     = "transaction_id"

  attribute {
    name = "transaction_id"
    type = "S" 
  }

  tags = {
    Environment = "Development"
    Project     = "TransactionData"
  }
}
