# policy_id: POL-DDB-001
package terraform.dynamodb_encryption

# Catch explicitly disabled encryption
deny[msg] {
  resource := input.resource_changes[_]
  resource.type == "aws_dynamodb_table"
  sse := resource.change.after.server_side_encryption[_]
  sse.enabled == false
  msg := sprintf("POL-DDB-001: DynamoDB table %s has server-side encryption disabled", [resource.address])
}

# Catch missing encryption block entirely
deny[msg] {
  resource := input.resource_changes[_]
  resource.type == "aws_dynamodb_table"
  not has_sse_block(resource)
  msg := sprintf("POL-DDB-001: DynamoDB table %s has no server-side encryption configuration", [resource.address])
}

has_sse_block(resource) {
  resource.change.after.server_side_encryption[_]
}
