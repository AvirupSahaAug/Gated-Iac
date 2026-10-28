# policy_id: POL-RDS-001
package terraform.rds_encryption

deny[msg] {
  resource := input.resource_changes[_]
  resource.type == "aws_db_instance"
  enc := resource.change.after.storage_encrypted
  enc != true
  msg := sprintf("POL-RDS-001: RDS instance %s has storage encryption disabled", [resource.address])
}
