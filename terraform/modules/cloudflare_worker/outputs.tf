output "worker_url" {
  description = "Cloudflare Worker URL"
  value       = "https://${cloudflare_workers_script.discord_webhook_handler.name}.${var.cloudflare_account_id}.workers.dev"
}

output "worker_name" {
  description = "Cloudflare Worker name"
  value       = cloudflare_workers_script.discord_webhook_handler.name
}

output "custom_domain_url" {
  description = "Custom domain URL (if configured)"
  value       = var.cloudflare_zone_id != "" ? "https://${var.worker_subdomain}.${var.worker_domain}/discord-webhook" : ""
}