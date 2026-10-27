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

variable "databricks_host" {
  description = "Databricks workspace URL (not secret)"
  type        = string
  default     = "https://dbc-9cb5ee60-cf19.cloud.databricks.com/"  
}

variable "databricks_token_param_name" {
  description = "SSM parameter holding the Databricks token"
  type        = string
  default     = "/power-lakehouse/databricks-token"
}

variable "volume_base" {
  description = "Unity Catalog Volume the Lambda uploads into"
  type        = string
  default     = "/Volumes/workspace/landing/raw"
}