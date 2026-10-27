# Role that EventBridge Scheduler uses to invoke the Lambda
resource "aws_iam_role" "scheduler" {
  name = "${local.function_name}-scheduler-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "scheduler.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "scheduler_invoke" {
  name = "invoke-${local.function_name}"
  role = aws_iam_role.scheduler.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = "lambda:InvokeFunction"
      Resource = aws_lambda_function.extract.arn
    }]
  })
}

resource "aws_scheduler_schedule" "daily" {
  name                         = "${local.function_name}-daily"
  schedule_expression          = "cron(15 14 * * ? *)"   # 14:15 every day
  schedule_expression_timezone = "Europe/Berlin"
  state                        = var.schedule_enabled ? "ENABLED" : "DISABLED"

  flexible_time_window { mode = "OFF" }

  target {
    arn      = aws_lambda_function.extract.arn
    role_arn = aws_iam_role.scheduler.arn
    retry_policy { maximum_retry_attempts = 2 }
  }
}