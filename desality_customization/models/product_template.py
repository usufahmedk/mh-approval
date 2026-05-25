from odoo import models, fields


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    is_commission_product = fields.Boolean(
        string='Commission Product',
        default=False,
        index=True,
    )