resource "tls_private_key" "ec2" {
  algorithm = "RSA"
  rsa_bits  = 4096
}

resource "aws_key_pair" "ec2" {
  key_name   = "${var.project}-ec2-key"
  public_key = tls_private_key.ec2.public_key_openssh
}

# private key 는 terraform output `ec2_ssh_private_key_pem` (sensitive) 으로만 노출한다.
# 워크플로(spin-up / deploy-*)가 terraform output 으로 직접 받아 사용하므로 별도 동기화
# 대상이 없다. 과거에는 github_actions_secret 으로 푸시했으나 GITHUB_TOKEN 이 repo secrets
# 쓰기 권한을 받지 못해 PAT 가 필요했고, 시크릿 단일 주체 원칙에도 어긋났다.
