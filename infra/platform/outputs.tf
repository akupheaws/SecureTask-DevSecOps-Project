output "repository_url" {
  value = aws_ecr_repository.app.repository_url
}
output "cluster_name" {
  value = aws_ecs_cluster.main.name
}
output "private_subnets" {
  value = aws_subnet.private[*].id
}
output "app_security_group" {
  value = aws_security_group.app.id
}
output "execution_role_arn" {
  value = aws_iam_role.execution.arn
}
output "task_role_arn" {
  value = aws_iam_role.task.arn
}
output "target_group_arns" {
  value = { for k, v in aws_lb_target_group.app : k => v.arn
  }
}
output "db_host" {
  value = { for k, v in aws_db_instance.main : k => v.address }
}
output "db_secret_arn" {
  value = { for k, v in aws_db_instance.main : k => v.master_user_secret[0].secret_arn }
}
output "log_group" {
  value = aws_cloudwatch_log_group.app.name
}
output "production_url" {
  value = "${var.certificate_arn != "" ? "https" : "http"}://${aws_lb.main.dns_name}"
}
output "staging_url" {
  value = "${var.certificate_arn != "" ? "https" : "http"}://${aws_lb.staging.dns_name}"
}
