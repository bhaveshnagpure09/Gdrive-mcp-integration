# Staging environment variables

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "staging"
}

variable "aws_region" {
  description = "AWS region for the staging environment"
  type        = string
  default     = "ap-south-1"
}

variable "db_username" {
  description = "RDS master username"
  type        = string
  sensitive   = true
}

variable "db_password" {
  description = "RDS master password — use a secrets manager in production"
  type        = string
  sensitive   = true
}

variable "ecr_repo_url" {
  description = "ECR repository URL for the API container image"
  type        = string
  default     = ""
}

variable "image_tag" {
  description = "Docker image tag to deploy"
  type        = string
  default     = "latest"
}
