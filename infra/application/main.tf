terraform {

  required_version = ">= 1.10.0, < 2.0.0"
  backend "s3" {

  }
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 6.0"
    }
  }

}
provider "aws" {
  region = var.region
}
variable "region" {
  default = "us-east-1"
}
variable "state_bucket" {
  type = string
}
variable "image_digest" {

  type = string
  validation {
    condition     = can(regex("^sha256:[a-f0-9]{64}$", var.image_digest))
    error_message = "Use an immutable SHA256 image digest."
  }

}
variable "name" {
  default = "securetask"
}
variable "environment" {

  type = string
  validation {
    condition     = contains(["staging", "production"], var.environment)
    error_message = "Environment must be staging or production."
  }

}
variable "allow_http_demo" {
  default = false
}
variable "desired_count" {
  default = 1
}
data "terraform_remote_state" "platform" {

  backend = "s3"
  config = { bucket = var.state_bucket, key = "platform/terraform.tfstate", region = var.region
  }

}
locals {
  platform = data.terraform_remote_state.platform.outputs
}
resource "aws_ecs_task_definition" "app" {

  family                   = "${var.name}-${var.environment}"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "256"
  memory                   = "512"
  execution_role_arn       = local.platform.execution_role_arn
  task_role_arn            = local.platform.task_role_arn
  container_definitions = jsonencode([{
    name = "app", image = "${local.platform.repository_url}@${var.image_digest}", essential = true,
    portMappings = [{ containerPort = 3000, protocol = "tcp"
    }],
    environment = [{ name = "DB_HOST", value = local.platform.db_host[var.environment]
      }, { name = "DB_USER", value = "securetask"
      }, { name = "DB_NAME", value = "securetask"
      }, { name = "DB_SSL", value = "true"
      }, { name = "NODE_ENV", value = "production" }, { name = "ALLOW_HTTP_DEMO", value = tostring(var.allow_http_demo)
    }],
    secrets = [{ name = "DB_PASSWORD", valueFrom = "${local.platform.db_secret_arn[var.environment]}:password::"
    }],
    readonlyRootFilesystem = true,
    linuxParameters = { initProcessEnabled = true
    },
    healthCheck = { command = ["CMD-SHELL", "node -e \"fetch('http://127.0.0.1:3000/health/live').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))\""], interval = 30, timeout = 5, retries = 3, startPeriod = 30
    },
    logConfiguration = { logDriver = "awslogs", options = { "awslogs-group" = local.platform.log_group, "awslogs-region" = var.region, "awslogs-stream-prefix" = var.environment
      }
    }

  }])

}
resource "aws_ecs_service" "app" {

  name                               = "${var.name}-${var.environment}"
  cluster                            = local.platform.cluster_name
  task_definition                    = aws_ecs_task_definition.app.arn
  launch_type                        = "FARGATE"
  desired_count                      = var.desired_count
  health_check_grace_period_seconds  = 90
  wait_for_steady_state              = true
  deployment_minimum_healthy_percent = 100
  deployment_maximum_percent         = 200
  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }
  network_configuration {
    subnets          = local.platform.private_subnets
    security_groups  = [local.platform.app_security_group]
    assign_public_ip = false
  }
  load_balancer {
    target_group_arn = local.platform.target_group_arns[var.environment]
    container_name   = "app"
    container_port   = 3000
  }
  lifecycle {
    ignore_changes = [task_definition]
  }

}
output "service_name" {
  value = aws_ecs_service.app.name
}
output "task_definition" {
  value = aws_ecs_task_definition.app.arn
}
