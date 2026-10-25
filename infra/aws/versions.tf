terraform {
  required_version = ">= 1.10"
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 5.0" }
  }
}

provider "aws" {
  region = "eu-north-1"   # Region for free tier
  default_tags {
    tags = { project = "power-lakehouse", managed_by = "terraform" }
  }
}