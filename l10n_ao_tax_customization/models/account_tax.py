from odoo import models, fields

class AccountTax(models.Model):
    _inherit = 'account.tax'

    iva_balance_debit_account_id = fields.Many2one(
        comodel_name='account.account',
        string="Conta de Custo (débito)"
    )
