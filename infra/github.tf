data "github_repository" "this" {
  full_name = "${var.github_owner}/${var.github_repository}"
}

resource "github_actions_secret" "ec2_ssh_private_key" {
  repository      = data.github_repository.this.name
  secret_name     = var.ec2_ssh_private_key_secret_name
  plaintext_value = tls_private_key.ec2.private_key_pem
}
