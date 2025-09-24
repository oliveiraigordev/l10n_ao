from odoo import _, api, fields, models, tools, Command


class BankRecWidgetlineAOA(models.Model):
    _inherit = "bank.rec.widget.line"

    margin_value = fields.Float(string="Margin (%)", default="0", readonly=False)