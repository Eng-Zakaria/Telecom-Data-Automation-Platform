# dev: see modules/platform for what gets created. Cost flags below.
module "platform" {
  source      = "../../modules/platform"
  environment = "dev"

  enable_data_factory = false
  enable_databricks   = false
  enable_fabric       = false

  eventhubs_throughput_units     = 1
  eventhubs_max_throughput_units = 0

  pipeline_principal_ids = var.pipeline_principal_ids
  alert_emails           = var.alert_emails
  fabric_admin_members   = var.fabric_admin_members
}
