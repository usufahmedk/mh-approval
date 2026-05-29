# Copyright 2026 Abdalrahman Shahrour
from odoo import api, fields, models


class CustomerStatusConfig(models.Model):
    _name = "customer.status.config"
    _description = "Customer Status Configuration"

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        default=lambda self: self.env.company,
        required=True,
        ondelete="cascade",
    )
    at_risk_days = fields.Integer(
        string="At Risk Threshold (Days)",
        default=60,
        help="Number of days without a booking before a customer is flagged as At Risk.",
        required=True,
    )
    inactive_days = fields.Integer(
        string="Inactive Threshold (Days)",
        default=90,
        help="Number of days without a booking before a customer is flagged as Inactive.",
        required=True,
    )
    activity_type_id = fields.Many2one(
        "mail.activity.type",
        string="Activity Type",
        default=lambda self: self._default_activity_type(),
        required=True,
        ondelete="restrict",
    )
    activity_days_due = fields.Integer(
        string="Activity Due In (Days)",
        default=7,
        help="Number of days from flagging until the follow-up activity is due.",
        required=True,
    )
    booking_model_id = fields.Many2one(
        "ir.model",
        string="Booking Model",
        default=lambda self: self._default_booking_model(),
        required=True,
        ondelete="restrict",
        domain=[("model", "=", "mh.booking")],
        help="The model used to track customer bookings.",
    )
    cron_active = fields.Boolean(
        string="Auto-check Status",
        default=True,
        help="If enabled, the nightly cron job will automatically check and update customer statuses.",
    )
    notification_user_ids = fields.Many2many(
        "res.users",
        string="Notification Recipients",
        help="Users to notify when customers are flagged. Used as fallback when a customer has no assigned salesperson.",
    )

    _sql_constraints = [
        (
            "at_risk_before_inactive",
            "CHECK(at_risk_days < inactive_days)",
            "At Risk threshold must be less than Inactive threshold.",
        ),
        (
            "positive_at_risk_days",
            "CHECK(at_risk_days > 0)",
            "At Risk threshold must be positive.",
        ),
        (
            "positive_inactive_days",
            "CHECK(inactive_days > 0)",
            "Inactive threshold must be positive.",
        ),
    ]

    @api.model
    def _default_activity_type(self):
        phone_call = self.env.ref("mail.mail_activity_data_call", raise_if_not_found=False)
        return phone_call.id if phone_call else False

    @api.model
    def _default_booking_model(self):
        return self.env["ir.model"].search([("model", "=", "mh.booking")], limit=1).id

    @api.model
    def _get_config(self, company_id=None):
        """Return the config for the given company (or current company)."""
        domain = []
        if company_id:
            domain.append(("company_id", "=", company_id))
        else:
            domain.append(("company_id", "=", self.env.company.id))
        return self.search(domain, limit=1)

    def _get_booking_date_field(self):
        """Return the field name on the booking model that holds the booking date."""
        self.ensure_one()
        model = self.env[self.booking_model_id.model]
        date_fields = ["booking_date_start", "booking_date", "start", "date"]
        for fname in date_fields:
            if fname in model._fields:
                return fname
        return "start"

    def _get_partner_field(self):
        """Return the field name on the booking model that links to the partner."""
        self.ensure_one()
        model = self.env[self.booking_model_id.model]
        partner_fields = ["partner_id", "customer_id", "partner_ids", "customer_ids"]
        for fname in partner_fields:
            if fname in model._fields:
                field = model._fields[fname]
                if fname == "partner_ids":
                    return fname
                return fname
        return "partner_id"