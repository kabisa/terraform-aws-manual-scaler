module "api_gateway" {
  source = "terraform-aws-modules/apigateway-v2/aws"

  name          = "manual_scaler-api-gw"
  description   = "My awesome HTTP API Gateway"
  protocol_type = "HTTP"

  cors_configuration = {
    allow_headers = ["content-type", "x-amz-date", "authorization", "x-api-key", "x-amz-security-token", "x-amz-user-agent"]
    allow_methods = ["*"]
    allow_origins = ["*"]
  }

  # Routes and integrations
  integrations = {
    "ANY /" = {
      lambda_arn             = module.lambda_function.lambda_function_arn
      payload_format_version = "2.0"
      timeout_milliseconds   = 12000
    }
  }

  tags = {
    Name = "http-apigateway"
  }
  disable_execute_api_endpoint = false
  domain_name                  = "${var.subdomain}.${var.domain_name}"
  domain_name_certificate_arn  = module.acm.acm_certificate_arn

  default_stage_access_log_destination_arn = aws_cloudwatch_log_group.logs.arn
  default_stage_access_log_format          = "$context.identity.sourceIp - - [$context.requestTime] \"$context.httpMethod $context.routeKey $context.protocol\" $context.status $context.responseLength $context.requestId $context.integrationErrorMessage"

}

data "aws_route53_zone" "this" {
  name = var.domain_name
}

resource "aws_cloudwatch_log_group" "logs" {
  name = "manual_scaler-api-gw-logs"
}


module "acm" {
  source  = "terraform-aws-modules/acm/aws"
  version = "~> 3.0"

  domain_name               = "${var.subdomain}.${var.domain_name}"
  zone_id                   = data.aws_route53_zone.this.id
  subject_alternative_names = []
}

resource "aws_route53_record" "manual_scaler" {
  zone_id = data.aws_route53_zone.this.zone_id
  name    = "${var.subdomain}.${var.domain_name}"
  type    = "A"

  alias {
    name                   = module.api_gateway.apigatewayv2_domain_name_configuration[0].target_domain_name
    zone_id                = module.api_gateway.apigatewayv2_domain_name_configuration[0].hosted_zone_id
    evaluate_target_health = false
  }
}

resource "aws_iam_policy" "allow_api_gateway" {
  name   = "manual_scaler_allow_autoscaling"
  policy = <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Action": [
        "autoscaling:UpdateAutoScalingGroup",
        "autoscaling:DescribeAutoScalingGroups",
        "autoscaling:DescribeScheduledActions",
        "autoscaling:PutScheduledUpdateGroupAction"
      ],
      "Resource": "*",
      "Effect": "Allow"
    }
  ]
}
EOF
}

module "lambda_function" {
  source  = "terraform-aws-modules/lambda/aws"
  version = "~> 2.0"

  function_name = "manual_scaler"
  description   = "My awesome lambda function"
  handler       = "main.handler"
  runtime       = "python3.8"

  publish = true
  timeout = 10

  create_package         = false
  local_existing_package = "${path.module}/code/lambda.zip"

  allowed_triggers = {
    AllowExecutionFromAPIGateway = {
      service    = "apigateway"
      source_arn = "${module.api_gateway.apigatewayv2_api_execution_arn}/*/*/*"
    }
  }
  environment_variables = {
    ASG_NAME       = var.asg,
    AUTH_USER_NAME = var.auth_user_name
    AUTH_PASSWORD  = var.auth_password
  }
  trusted_entities = ["apigateway.amazonaws.com"]
}

resource "aws_iam_policy_attachment" "allow_autoscaling_attachment" {
  name       = "allow-autoscaling"
  roles      = [module.lambda_function.lambda_role_name]
  policy_arn = aws_iam_policy.allow_api_gateway.arn
}