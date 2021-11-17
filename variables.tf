variable "account_id" {}
variable "asg" {}
variable "region" {}
variable "domain_name" {}
variable "subdomain" {}
variable "auth_user_name" {
  type = string
}
variable "auth_password" {
  type = string
}
variable "rds_scaledown_cluster_arns" {
  description = "This is supposed to work together with the AWS Instance Scheduler. Set the arns of the RDS cluster you want to set a scaling tag for"
  type        = string
  default     = ""
}
variable "rds_scaledown_tag" {
  description = "This is the scaling tag you can set t"
  type        = string
  default     = ""
}