terraform {
  required_version = ">= 1.10"
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 5.0" }
    archive = { source = "hashicorp/archive", version = "~> 2.0" } # Provider to zip the build (The package + Python code to run the code in lambda handler without dependencies error)
  }
}

provider "aws" {
  region = "eu-north-1"   # Region for free tier
  default_tags {
    tags = { project = "power-lakehouse", managed_by = "terraform" }
  }
}