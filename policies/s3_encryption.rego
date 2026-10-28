# policy_id: POL-S3-002
package terraform.s3_encryption

# Collect all S3 bucket addresses that have a companion encryption config resource
has_encryption[bucket_addr] {
  enc := input.resource_changes[_]
  enc.type == "aws_s3_bucket_server_side_encryption_configuration"
  # The encryption config's 'bucket' field references the bucket ID.
  # In pre-apply plans, check if any encryption config exists for this bucket
  # by matching the resource name suffix convention.
  bucket := input.resource_changes[_]
  bucket.type == "aws_s3_bucket"
  enc.change.after.bucket == bucket.change.after.id
  bucket_addr := bucket.address
}

# Fallback: match by address naming convention (aws_s3_bucket.foo <-> aws_s3_bucket_server_side_encryption_configuration.foo)
has_encryption_by_name[bucket_addr] {
  enc := input.resource_changes[_]
  enc.type == "aws_s3_bucket_server_side_encryption_configuration"
  bucket := input.resource_changes[_]
  bucket.type == "aws_s3_bucket"
  endswith(enc.address, split(bucket.address, ".")[1])
  bucket_addr := bucket.address
}

deny[msg] {
  resource := input.resource_changes[_]
  resource.type == "aws_s3_bucket"
  not has_encryption[resource.address]
  not has_encryption_by_name[resource.address]
  msg := sprintf("POL-S3-002: S3 bucket %s does not have server-side encryption enabled", [resource.address])
}
