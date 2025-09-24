from odoo import models, fields


class AccountTaxRepartitionLine(models.Model):
    _inherit = "account.tax.repartition.line"
    
    repartition_type = fields.Selection(
        selection_add=[('captive', 'Cativo')],
        ondelete={'captive': 'cascade'},
        )
