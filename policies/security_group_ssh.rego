# policy_id: POL-SG-001
package terraform.security_group

deny[msg] {
  resource := input.resource_changes[_]
  resource.type == "aws_security_group"
  rule := resource.change.after.ingress[_]
  rule.from_port <= 22
  rule.to_port >= 22
  cidr := rule.cidr_blocks[_]
  cidr == "0.0.0.0/0"
  msg := sprintf("POL-SG-001: %s allows SSH from 0.0.0.0/0", [resource.address])
}
