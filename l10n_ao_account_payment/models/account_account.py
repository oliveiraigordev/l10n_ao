from odoo import fields, models, api

class AccountAccount(models.Model):
    _inherit = 'account.account'

    force_same_account_on_reconcile = fields.Boolean(
        string="Usar Conta Principal na Reconciliação",
        help="Se habilitado, sistema reconciliará lançamentos da conta suspensa, na conta principal",
        default=False
    )