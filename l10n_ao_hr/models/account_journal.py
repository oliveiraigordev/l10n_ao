from odoo import fields, models, api, _
from odoo.exceptions import UserError, ValidationError


class L10nHRAccountJournalAng(models.Model):
    _inherit = "account.journal"

    default_account_salary_id = fields.Many2one("account.account", string="Conta do Plano")
