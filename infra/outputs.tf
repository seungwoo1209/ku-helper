output "vpc_id" {
  description = "ID of the VPC"
  value       = aws_vpc.main.id
}

output "public_subnet_id" {
  description = "ID of the public subnet"
  value       = aws_subnet.public.id
}

output "instance_id" {
  description = "ID of the EC2 instance"
  value       = aws_instance.app.id
}

output "instance_public_ip" {
  description = "Public IP of the EC2 instance"
  value       = aws_instance.app.public_ip
}

output "ami_id" {
  description = "AMI used for the EC2 instance"
  value       = data.aws_ami.amazon_linux_2023.id
}

output "key_pair_name" {
  description = "Name of the generated EC2 key pair"
  value       = aws_key_pair.ec2.key_name
}

output "private_key_path" {
  description = "Local path to the generated private key PEM file"
  value       = local_sensitive_file.private_key_pem.filename
}

output "private_key_pem" {
  description = "Generated EC2 private key (PEM)"
  value       = tls_private_key.ec2.private_key_pem
  sensitive   = true
}

output "ssh_command" {
  description = "Convenience SSH command to connect to the instance"
  value       = "ssh -i ${local_sensitive_file.private_key_pem.filename} ec2-user@${aws_instance.app.public_ip}"
}
