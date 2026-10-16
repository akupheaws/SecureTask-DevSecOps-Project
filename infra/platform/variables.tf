variable "region" {
  default = "us-east-1"
}
variable "name" {
  default = "securetask"
}
variable "github_repository" {

  description = "GitHub owner/repository owning this installation."
  type        = string
  default     = ""

}
variable "certificate_arn" {

  description = "ACM certificate ARN in this region. Required unless allow_http_demo=true."
  type        = string
  default     = ""

}
variable "allow_http_demo" {
  default = false
}
variable "db_multi_az" {
  default = false
}
variable "deletion_protection" {
  default = true
}
