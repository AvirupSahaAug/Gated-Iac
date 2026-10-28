# policy_id: POL-S3-001
package terraform.s3_acl

deny[msg] {
  resource := input.resource_changes[_]
  resource.type == "aws_s3_bucket_acl"
  acl := resource.change.after.acl
  acl == "public-read"
  msg := sprintf("POL-S3-001: %s has public-read ACL", [resource.address])
}

