terraform {
  backend "s3" {
    bucket       = "power-lakehouse-tfstate-814294708752"
    key          = "infra/aws/terraform.tfstate"
    region       = "eu-north-1"
    encrypt      = true
    use_lockfile = true
  }
}