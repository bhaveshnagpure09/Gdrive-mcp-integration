# Staging environment outputs

# output "api_endpoint" {
#   description = "URL of the staging ALB / ECS service"
#   value       = "https://${aws_lb.api.dns_name}"
# }
#
# output "db_endpoint" {
#   description = "RDS endpoint for the staging database"
#   value       = aws_db_instance.postgres.address
#   sensitive   = true
# }
