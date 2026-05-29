# Copyright 2026 Abdalrahman Shahrour
import logging

from odoo import api, models

_logger = logging.getLogger(__name__)


class IrCron(models.Model):
    _inherit = "ir.cron"

    @api.model
    def _cron_check_customer_status(self):
        """Nightly cron: evaluate all customer statuses and create follow-up activities."""
        config = self.env["customer.status.config"]._get_config()
        if not config:
            _logger.warning(
                "No customer.status.config found. Skipping customer status check."
            )
            return

        if not config.cron_active:
            _logger.info("Customer status cron is disabled. Skipping.")
            return

        all_partners = self.env["res.partner"].sudo().search([("customer", "=", True)])
        if not all_partners:
            return

        batch_size = 100
        total = len(all_partners)
        _logger.info("Starting customer status check for %d customers.", total)

        for i in range(0, total, batch_size):
            batch = all_partners[i : i + batch_size]
            batch._compute_last_booking_date()
            batch._compute_customer_status()
            batch._check_and_create_activity_if_needed()

        _logger.info("Customer status check completed for %d customers.", total)
