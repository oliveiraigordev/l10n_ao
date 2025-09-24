from odoo import models, fields, api, _


class AOAccountFinancialReportLine(models.Model):
    _inherit = "account.report.line"
    _rec_name = 'default_name'

    note = fields.Char("Note")
    default_name = fields.Char("Default Name")
    active_account_move = fields.Boolean("Visible In Account Move")
