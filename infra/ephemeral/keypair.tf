resource "tls_private_key" "ec2" {
  algorithm = "RSA"
  rsa_bits  = 4096
}

resource "aws_key_pair" "ec2" {
  key_name   = "${var.project}-ec2-key"
  public_key = tls_private_key.ec2.public_key_openssh
}

# bastion 경유 SSH 터널 / app 배포에 사용. private key 는 GitHub Secret 으로 동기화.
resource "github_actions_secret" "ec2_ssh_private_key" {
  repository      = var.github_repository
  secret_name     = "EC2_SSH_PRIVATE_KEY"
  plaintext_value = tls_private_key.ec2.private_key_pem
}
