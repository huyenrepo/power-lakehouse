data "aws_region" "current" {}

   locals {
     function_name        = "entsoe-extract"
     entsoe_param_arn     = "arn:aws:ssm:${data.aws_region.current.name}:${data.aws_caller_identity.me.account_id}:parameter${var.entsoe_param_name}"
     databricks_param_arn = "arn:aws:ssm:${data.aws_region.current.name}:${data.aws_caller_identity.me.account_id}:parameter${var.databricks_token_param_name}"
   }

# Zip the build folder
data "archive_file" "lambda" {
  type        = "zip"
  source_dir  = "${path.module}/../../extract/build"
  output_path = "${path.module}/build/entsoe_extract.zip"
}

# --- IAM role the Lambda runs as ---
resource "aws_iam_role" "lambda" {
  name = "${local.function_name}-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

# Write CloudWatch logs
resource "aws_iam_role_policy_attachment" "lambda_logs" {
  role       = aws_iam_role.lambda.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# Least privilege: write only under entsoe/ in the raw bucket, read only the token
resource "aws_iam_role_policy" "lambda_access" {
  name = "${local.function_name}-access"
  role = aws_iam_role.lambda.name
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["s3:PutObject"]
        Resource = "${aws_s3_bucket.raw.arn}/entsoe/*"
      },
      {
        Effect   = "Allow"
        Action   = ["ssm:GetParameter"]
        Resource = local.entsoe_param_arn
      },
      {
     Effect   = "Allow"
     Action   = ["ssm:GetParameter"]
     Resource = [local.entsoe_param_arn, local.databricks_param_arn]
      }
    ]
  })
}

# Log group with retention (otherwise logs are kept forever)
resource "aws_cloudwatch_log_group" "lambda" {
  name              = "/aws/lambda/${local.function_name}"
  retention_in_days = 14
}

# --- The function ---
resource "aws_lambda_function" "extract" {
  function_name    = local.function_name
  role             = aws_iam_role.lambda.arn
  handler          = "entsoe_extract.lambda_handler"
  runtime          = "python3.12"
  architectures    = ["arm64"]
  timeout          = 120
  memory_size      = 256
  filename         = data.archive_file.lambda.output_path
  source_code_hash = data.archive_file.lambda.output_base64sha256

   environment {
     variables = {
       RAW_BUCKET             = aws_s3_bucket.raw.bucket
       ENTSOE_PARAM_NAME      = var.entsoe_param_name
       DATABRICKS_HOST        = var.databricks_host
       DATABRICKS_TOKEN_PARAM = var.databricks_token_param_name
       VOLUME_BASE            = var.volume_base
     }
   }

  depends_on = [aws_cloudwatch_log_group.lambda]
}

output "lambda_function_name" {
  value = aws_lambda_function.extract.function_name
}