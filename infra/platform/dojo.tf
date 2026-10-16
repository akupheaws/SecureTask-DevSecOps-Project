data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"]
  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd-gp3/ubuntu-noble-24.04-amd64-server-*"]
  }
  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }

}
resource "aws_security_group" "dojo" {

  name   = "${var.name}-dojo"
  vpc_id = aws_vpc.main.id
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

}
resource "aws_iam_role" "dojo" {

  name = "${var.name}-dojo"
  assume_role_policy = jsonencode({ Version = "2012-10-17", Statement = [{ Effect = "Allow", Principal = { Service = "ec2.amazonaws.com"
    }, Action = "sts:AssumeRole"
    }]
  })

}
resource "aws_iam_role_policy_attachment" "dojo_ssm" {

  role       = aws_iam_role.dojo.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"

}
resource "aws_iam_instance_profile" "dojo" {
  name = "${var.name}-dojo"
  role = aws_iam_role.dojo.name
}
resource "aws_instance" "dojo" {

  ami                    = data.aws_ami.ubuntu.id
  instance_type          = "t3.large"
  subnet_id              = aws_subnet.private[0].id
  vpc_security_group_ids = [aws_security_group.dojo.id]
  iam_instance_profile   = aws_iam_instance_profile.dojo.name
  user_data = templatefile("${path.module}/dojo-user-data.sh", {
    compose                = base64gzip(file("${path.module}/../../dojo/docker-compose.yml"))
    init_env               = base64gzip(file("${path.module}/../../dojo/init-env.py"))
    provision              = base64gzip(file("${path.module}/../../dojo/provision.py"))
    setup_host             = base64gzip(file("${path.module}/../../dojo/setup-host.py"))
    integration_secret_arn = aws_secretsmanager_secret.dojo_integration.arn
    region                 = var.region
    admin_secret_arn       = aws_secretsmanager_secret.dojo_admin.arn
  })
  user_data_replace_on_change = false
  lifecycle { ignore_changes = [ami, user_data] }
  metadata_options {
    http_tokens   = "required"
    http_endpoint = "enabled"
  }
  root_block_device {
    volume_size = 40
    encrypted   = true
    volume_type = "gp3"
  }
  tags = { Name = "${var.name}-dojo"
  }
  depends_on = [aws_route_table_association.private, aws_nat_gateway.main, aws_iam_role_policy.dojo_integration]

}
output "dojo_instance_id" {
  value = aws_instance.dojo.id
}
resource "aws_secretsmanager_secret" "dojo_integration" {
  name                    = "${var.name}-dojo-integration"
  recovery_window_in_days = 7
}
resource "aws_iam_role_policy" "dojo_integration" {
  role   = aws_iam_role.dojo.id
  policy = jsonencode({ Version = "2012-10-17", Statement = [{ Effect = "Allow", Action = ["secretsmanager:PutSecretValue"], Resource = [aws_secretsmanager_secret.dojo_integration.arn, aws_secretsmanager_secret.dojo_admin.arn] }] })
}
output "dojo_integration_secret_arn" { value = aws_secretsmanager_secret.dojo_integration.arn }

resource "aws_secretsmanager_secret" "dojo_admin" {
  name                    = "${var.name}-dojo-admin"
  recovery_window_in_days = 7
}
output "dojo_admin_secret_arn" { value = aws_secretsmanager_secret.dojo_admin.arn }
