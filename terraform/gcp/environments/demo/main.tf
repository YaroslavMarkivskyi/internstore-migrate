module "networking" {
  source      = "../../modules/networking"
  project_id  = var.project_id
  region      = var.region
  name_prefix = var.name_prefix
}

module "gke" {
  source              = "../../modules/gke"
  project_id          = var.project_id
  region              = var.region
  cluster_name        = "${var.name_prefix}-gke"
  network_id          = module.networking.network_id
  subnetwork_id       = module.networking.subnetwork_id
  pods_range_name     = module.networking.pods_range_name
  services_range_name = module.networking.services_range_name
}

module "artifact_registry" {
  source                   = "../../modules/artifact-registry"
  project_id               = var.project_id
  region                   = var.region
  repository_id            = "internstore"
  gke_node_service_account = module.gke.node_service_account
}

module "memorystore" {
  source        = "../../modules/memorystore"
  project_id    = var.project_id
  region        = var.region
  instance_name = "${var.name_prefix}-redis"
  network_id    = module.networking.network_id

  # Memorystore requires the VPC peering (private services access) to exist
  # first — expressed here, not faked as a module input (see memorystore's
  # variables.tf comment).
  depends_on = [module.networking]
}

module "kafka" {
  source        = "../../modules/kafka"
  project_id    = var.project_id
  region        = var.region
  cluster_id    = "${var.name_prefix}-kafka"
  subnetwork_id = module.networking.subnetwork_id
}

module "storage" {
  source      = "../../modules/storage"
  project_id  = var.project_id
  region      = var.region
  name_prefix = var.name_prefix
  bucket_name = "${var.project_id}-${var.name_prefix}-assets"
}
