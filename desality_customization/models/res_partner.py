from odoo import models, fields, api


class ResPartner(models.Model):
    _inherit = 'res.partner'

    referral_commission = fields.Float(
        string='Referral Commission (%)',
        digits=(5, 2),
    )
    
    ambassador_commission = fields.Float(
        string='Ambassador Commission (%)',
        digits=(5, 2),
    )
    
    is_referral_partner = fields.Boolean(
        string='Is Referral Partner',
        default=False,
        index=True,
    )