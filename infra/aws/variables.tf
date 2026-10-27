variable "schedule_enabled" {
  description = "Run the extractor daily"
  type        = bool
  default     = false
}

variable "entsoe_param_name" {
  description = "SSM parameter holding the ENTSO-E token"
  type        = string
  default     = "/power-lakehouse/entsoe-api-key"
}