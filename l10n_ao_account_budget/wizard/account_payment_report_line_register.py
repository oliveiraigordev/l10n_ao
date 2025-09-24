from odoo import fields, api, models, _


class AccountPaymentReportLineRegister(models.TransientModel):
    _inherit = 'account.payment.report.line.register'

    account_code = fields.Char(related="cash_flow_statement_line_id.account_id.code", string="Conta orçamental")
