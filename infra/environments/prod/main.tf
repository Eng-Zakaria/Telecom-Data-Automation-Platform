# prod: see modules/platform for what gets created. Cost flags below.
module "platform" {
  source      = "../../modules/platform"
  environment = "prod"

  enable_data_factory = true
  enable_databricks   = true
  enable_fabric       = true

  eventhubs_throughput_units     = 2
  eventhubs_max_throughput_units = 10

  pipeline_principal_ids = var.pipeline_principal_ids
  alert_emails           = var.alert_emails
  fabric_admin_members   = var.fabric_admin_members
}
