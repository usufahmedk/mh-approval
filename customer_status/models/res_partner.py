# Copyright 2026 Abdalrahman Shahrour
import logging
from datetime import timedelta

from odoo import api, fields, models

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

        partner_model = self.env["res.partner"].sudo()
        all_partners = partner_model.search([("customer", "=", True)])

        if not all_partners:
            return

        batch_size = 100
        total = len(all_partners)
        _logger.info(
            "Starting customer status check for %d customers.", total
        )

        for i in range(0, total, batch_size):
            batch = all_partners[i : i + batch_size]
            batch._compute_last_booking_date()
            batch._compute_customer_status()

            batch._check_and_create_activity_if_needed()

        _logger.info("Customer status check completed for %d customers.", total)


class ResPartner(models.Model):
    _inherit = "res.partner"

    customer_status = fields.Selection(
        [
            ("active", "Active"),
            ("at_risk", "At Risk"),
            ("inactive", "Inactive"),
        ],
        string="Customer Status",
        compute="_compute_customer_status",
        store=False,
        index=True,
        default="active",
    )
    last_booking_date = fields.Datetime(
        string="Last Booking Date",
        compute="_compute_last_booking_date",
        store=False,
        index=True,
    )
    last_status_change = fields.Date(
        string="Last Status Change",
        copy=False,
        index=True,
        readonly=True,
    )

    def _compute_last_booking_date(self):
        config_model = self.env["customer.status.config"]

        config = config_model._get_config()
        if not config or not config.booking_model_id:
            for partner in self:
                partner.last_booking_date = False
            return

        partners_by_company = {}
        for partner in self:
            company_id = partner.company_id.id if partner.company_id else False
            partners_by_company.setdefault(company_id, []).append(partner.id)

        for company_id, pids in partners_by_company.items():
            cfg = config_model._get_config(company_id=company_id)
            if not cfg:
                self.browse(pids).last_booking_date = False
                continue
            self.browse(pids)._compute_last_booking_dates_sql(
                cfg.booking_model_id.model,
                cfg._get_booking_date_field(),
                cfg._get_partner_field(),
            )

    def _compute_last_booking_dates_sql(self, model_name, date_field, partner_field):
        partner_ids = self.ids
        if not partner_ids:
            return

        try:
            table = self.env[model_name].sudo()._table
        except KeyError:
            self.last_booking_date = False
            return

        model_obj = self.env[model_name].sudo()
        partner_field_clean = partner_field.rstrip("ids")
        is_many2many = partner_field.endswith("_ids")

        if is_many2many:
            field_info = model_obj._fields.get(partner_field)
            if field_info and field_info.type == "many2many":
                rel = field_info.relation
                col1 = field_info.column1
                col2 = field_info.column2
                self.env.cr.execute(
                    f"""
                    SELECT r.{col2}, MAX(t.{date_field})
                    FROM {table} t
                    JOIN {rel} r ON r.{col1} = t.id
                    WHERE r.{col2} IN %s
                    GROUP BY r.{col2}
                    """,
                    [tuple(partner_ids)],
                )
            else:
                self.last_booking_date = False
                return
        else:
            self.env.cr.execute(
                f"""
                SELECT t.{partner_field}, MAX(t.{date_field})
                FROM {table} t
                WHERE t.{partner_field} IN %s
                GROUP BY t.{partner_field}
                """,
                [tuple(partner_ids)],
            )

        date_map = dict(self.env.cr.fetchall())
        for partner in self:
            dt = date_map.get(partner.id)
            partner.last_booking_date = (
                fields.Datetime.to_datetime(dt) if dt else False
            )

    @api.depends("last_booking_date")
    def _compute_customer_status(self):
        today = fields.Date.context_today(self)
        for partner in self:
            config = partner._get_status_config()
            last_booking = partner.last_booking_date

            if not last_booking or not config:
                partner.customer_status = "active"
                continue

            dt = fields.Date.context_today(self, last_booking)
            delta = today - dt
            days = delta.days

            if config.inactive_days and days >= config.inactive_days:
                partner.customer_status = "inactive"
            elif config.at_risk_days and days >= config.at_risk_days:
                partner.customer_status = "at_risk"
            else:
                partner.customer_status = "active"

    def _get_status_config(self):
        config_model = self.env["customer.status.config"]
        company_id = self.company_id.id if self.company_id else False
        config = config_model._get_config(company_id=company_id)
        if config:
            return config
        return config_model._get_config(company_id=False)

    def _create_status_activity(self, new_status):
        config = self._get_status_config()
        if not config:
            return

        activity_type = config.activity_type_id
        if not activity_type:
            activity_type = self.env.ref("mail.mail_activity_data_call", raise_if_not_found=False)
        if not activity_type:
            return

        due_date = fields.Date.context_today(self) + timedelta(days=config.activity_days_due or 7)
        assigned_user = self.user_id
        if not assigned_user and config.notification_user_ids:
            assigned_user = config.notification_user_ids[0]

        if not assigned_user:
            _logger.warning(
                "Customer %s flagged as %s but has no salesperson or notification user.",
                self.display_name,
                new_status,
            )
            return

        self.sudo().env["mail.activity"].create(
            {
                "res_model_id": self.env.ref("base.model_res_partner").id,
                "res_id": self.id,
                "activity_type_id": activity_type.id,
                "user_id": assigned_user.id,
                "date_deadline": due_date,
                "summary": f"Follow up with {self.display_name} — {new_status}",
                "note": (
                    f"Customer <b>{self.display_name}</b> has been flagged as "
                    f"<b>{new_status}</b>. No booking has been recorded in the past "
                    f"<b>{config.inactive_days if new_status == 'inactive' else config.at_risk_days}</b> days."
                ),
            }
        )

    def _post_reactivation(self):
        self.ensure_one()
        self.sudo().message_post(
            body="Customer reactivated — a new booking has been recorded.",
            message_type="notification",
            subtype_xmlid="mail.mt_note",
        )

    def _check_and_create_activity_if_needed(self):
        today = fields.Date.context_today(self)
        for partner in self:
            config = partner._get_status_config()
            if not config:
                continue

            last_change = partner.last_status_change

            if not last_change:
                partner.sudo().write({"last_status_change": today})
                if partner.customer_status != "active":
                    partner._create_status_activity(partner.customer_status)
                continue

            if partner.customer_status == "active":
                threshold_days = config.inactive_days or 90
                if (today - last_change).days >= threshold_days:
                    partner.sudo().write({"last_status_change": today})
                    partner._post_reactivation()
                continue

            if partner.customer_status in ("at_risk", "inactive"):
                assigned_user = partner.user_id
                if not assigned_user and config.notification_user_ids:
                    assigned_user = config.notification_user_ids[0]

                if assigned_user:
                    has_open = partner.sudo().env["mail.activity"].search_count(
                        [
                            ("res_model", "=", "res.partner"),
                            ("res_id", "=", partner.id),
                            ("user_id", "=", assigned_user.id),
                            ("date_deadline", ">=", today),
                        ]
                    )
                    if not has_open:
                        partner._create_status_activity(partner.customer_status)


class MHBooking(models.Model):
    _inherit = "mh.booking"

    def write(self, vals):
        if {"partner_id", "booking_date_start"}.isdisjoint(vals.keys()):
            return super().write(vals)

        previous = {rec.id: rec.partner_id.id for rec in self if rec.partner_id}
        result = super().write(vals)

        affected = self.env["res.partner"]
        for rec in self:
            if rec.partner_id:
                affected |= rec.partner_id
        for pid in previous.values():
            if pid and pid not in affected.ids:
                affected |= self.env["res.partner"].browse(pid)

        if affected:
            affected._compute_last_booking_date()
            affected._compute_customer_status()
            affected._check_and_create_activity_if_needed()

        return result

    @api.model
    def create(self, vals):
        result = super().create(vals)
        if result.partner_id:
            result.partner_id._compute_last_booking_date()
            result.partner_id._compute_customer_status()
            result.partner_id._check_and_create_activity_if_needed()
        return result
