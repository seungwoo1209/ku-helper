terraform {
  backend "s3" {
    key     = "ephemeral/terraform.tfstate"
    encrypt = true
  }
}
