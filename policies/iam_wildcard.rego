# policy_id: POL-IAM-003
package terraform.iam

# Case 1: Action is a list containing "*"
deny[msg] {
  resource := input.resource_changes[_]
  resource.type == "aws_iam_role_policy"
  policy := json.unmarshal(resource.change.after.policy)
  statement := policy.Statement[_]
  is_array(statement.Action)
  action := statement.Action[_]
  action == "*"
  msg := sprintf("POL-IAM-003: %s grants wildcard Action", [resource.address])
}

# Case 2: Action is a string "*"
deny[msg] {
  resource := input.resource_changes[_]
  resource.type == "aws_iam_role_policy"
  policy := json.unmarshal(resource.change.after.policy)
  statement := policy.Statement[_]
  is_string(statement.Action)
  statement.Action == "*"
  msg := sprintf("POL-IAM-003: %s grants wildcard Action", [resource.address])
}

# Case 3: Resource is a list containing "*"
deny[msg] {
  resource := input.resource_changes[_]
  resource.type == "aws_iam_role_policy"
  policy := json.unmarshal(resource.change.after.policy)
  statement := policy.Statement[_]
  is_array(statement.Resource)
  res := statement.Resource[_]
  res == "*"
  msg := sprintf("POL-IAM-003: %s grants wildcard Resource", [resource.address])
}

# Case 4: Resource is a string "*"
deny[msg] {
  resource := input.resource_changes[_]
  resource.type == "aws_iam_role_policy"
  policy := json.unmarshal(resource.change.after.policy)
  statement := policy.Statement[_]
  is_string(statement.Resource)
  statement.Resource == "*"
  msg := sprintf("POL-IAM-003: %s grants wildcard Resource", [resource.address])
}
