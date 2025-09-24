from odoo import fields, api, models, _


class CashFlowStatementLineInherit(models.Model):
    _inherit = "cash.flow.statement.line"

    account_id = fields.Many2one(string="Conta", comodel_name="account.account", required=True)

