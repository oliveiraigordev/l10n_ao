from odoo import fields, api, models, _


class AccountPaymentReportLineInherit(models.Model):
    _inherit = 'account.payment.report.line'

    account_code = fields.Char(related="cash_flow_statement_line_id.account_id.code", string="Conta orçamental",
                               store=True)
    payment_state = fields.Selection(related="account_payment_id.state", string='Estado', store=True)
    payment_date = fields.Date(related="account_payment_id.date", string='Data')
