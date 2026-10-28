# policy_id: POL-EC2-002
package terraform.ec2_imds

# Catch explicit non-required http_tokens
deny[msg] {
  resource := input.resource_changes[_]
  resource.type == "aws_instance"
  metadata := resource.change.after.metadata_options[_]
  metadata.http_tokens != "required"
  msg := sprintf("POL-EC2-002: EC2 instance %s does not enforce IMDSv2 (http_tokens != required)", [resource.address])
}

# Catch missing metadata_options entirely (defaults to IMDSv1)
deny[msg] {
  resource := input.resource_changes[_]
  resource.type == "aws_instance"
  not has_metadata_options(resource)
  msg := sprintf("POL-EC2-002: EC2 instance %s has no metadata_options configured (defaults to IMDSv1)", [resource.address])
}

has_metadata_options(resource) {
  resource.change.after.metadata_options[_]
}
