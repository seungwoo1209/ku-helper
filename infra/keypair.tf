resource "tls_private_key" "ec2" {
  algorithm = "RSA"
  rsa_bits  = 4096
}

resource "aws_key_pair" "ec2" {
  key_name   = "${var.project}-key"
  public_key = tls_private_key.ec2.public_key_openssh

  tags = {
    Name = "${var.project}-key"
  }
}

resource "local_sensitive_file" "private_key_pem" {
  content         = tls_private_key.ec2.private_key_pem
  filename        = "${path.module}/${var.project}-key.pem"
  file_permission = "0400"
}
