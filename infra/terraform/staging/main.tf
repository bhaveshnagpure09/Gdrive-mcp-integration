# Staging environment infrastructure
# Target: AWS ECS Fargate + RDS PostgreSQL (pgvector extension)
# Apply: terraform -chdir=infra/terraform/staging init && terraform apply

terraform {
  required_version = ">= 1.5"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # Remote state — configure S3 bucket and DynamoDB lock table before use
  # backend "s3" {
  #   bucket         = "ib-tfstate-staging"
  #   key            = "staging/terraform.tfstate"
  #   region         = "ap-south-1"
  #   dynamodb_table = "ib-tfstate-lock"
  # }
}

provider "aws" {
  region = var.aws_region
}

# ── VPC & Networking ───────────────────────────────────────────────────────────
# TODO: replace with actual VPC ID once created
# module "vpc" {
#   source  = "terraform-aws-modules/vpc/aws"
#   version = "~> 5.0"
#   name    = "ib-staging-vpc"
#   cidr    = "10.1.0.0/16"
#   azs             = ["${var.aws_region}a", "${var.aws_region}b"]
#   private_subnets = ["10.1.1.0/24", "10.1.2.0/24"]
#   public_subnets  = ["10.1.101.0/24", "10.1.102.0/24"]
#   enable_nat_gateway = true
# }

# ── RDS PostgreSQL with pgvector ───────────────────────────────────────────────
# TODO: uncomment and supply subnet/sg IDs when VPC is ready
# resource "aws_db_instance" "postgres" {
#   identifier        = "ib-staging-postgres"
#   engine            = "postgres"
#   engine_version    = "15.5"
#   instance_class    = "db.t3.medium"
#   allocated_storage = 20
#   db_name           = "ib_job_skill_mapping_staging"
#   username          = var.db_username
#   password          = var.db_password   # use aws_secretsmanager_secret in production
#   publicly_accessible    = false
#   deletion_protection    = true
#   skip_final_snapshot    = false
#   final_snapshot_identifier = "ib-staging-final"
#   # pgvector is installed via RDS parameter group or init SQL script
# }

# ── ECS Cluster & Fargate Service ─────────────────────────────────────────────
# resource "aws_ecs_cluster" "main" {
#   name = "ib-staging-cluster"
# }
#
# resource "aws_ecs_task_definition" "api" {
#   family                   = "ib-staging-api"
#   requires_compatibilities = ["FARGATE"]
#   network_mode             = "awsvpc"
#   cpu                      = "512"
#   memory                   = "1024"
#   execution_role_arn       = aws_iam_role.ecs_exec.arn
#
#   container_definitions = jsonencode([{
#     name  = "api"
#     image = "${var.ecr_repo_url}:${var.image_tag}"
#     portMappings = [{ containerPort = 8000 }]
#     environment = [
#       { name = "DATABASE_URL", value = "postgresql://${var.db_username}:${var.db_password}@${aws_db_instance.postgres.address}:5432/ib_job_skill_mapping_staging" },
#       { name = "PYTHONPATH",   value = "/app/src" },
#       { name = "LOG_LEVEL",    value = "INFO" }
#     ]
#   }])
# }

# ── Outputs ────────────────────────────────────────────────────────────────────
# See outputs.tf
