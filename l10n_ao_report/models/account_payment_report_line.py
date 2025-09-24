from odoo import models, Command, fields, api, _
from odoo.exceptions import ValidationError


class AccountPaymentReportLine(models.Model):
    _name = 'account.payment.report.line'
    _description = 'Account Payment Report Line Model'

    account_payment_id = fields.Many2one('account.payment', 'Account Payment')
    cash_flow_statement_id = fields.Many2one('cash.flow.statement', string="Fluxo", required=1)
    cash_flow_statement_line_id = fields.Many2one('cash.flow.statement.line', string='Linha do Fluxo', required=1,
                                                  )#default='default_name'
    amount = fields.Float("Amount")

    line_cashflow = fields.Boolean(string="Linha de Fluxo", default=False)

    @api.model_create_multi
    def create(self, vals):
        account_payment_id = (
            self.env['account.payment']
            .sudo()
            .search(
                [
                    ("id", "=", vals[0].get('account_payment_id'))
                ]
            )
        )

        # Verificar se o fluxo escolhido já se encontra na lista
        self.account_report_line_duplicate(vals)
        # Verificar se o valor das linhas é igual ao valor do pagamento
        amount_total_lines = self.get_amount_total_lines(account_payment_id.id)
        total_amount = sum([dictionary.get("amount") for dictionary in vals]) + sum(amount_total_lines.mapped("amount"))
        self.verify_amount_total_lines(account_payment_id, total_amount)

        res = super(AccountPaymentReportLine, self).create(vals)
        return res

    def verify_amount_total_lines(self, account_move_id, total_amount):
        if (
                abs(total_amount) > abs(account_move_id.amount)
        ):
            raise ValidationError(
                _(
                    "Os valores inseridos excedem o valor do "
                    "pagamento. Verifique o valor total do recibo."
                )
            )
        elif (
                round(abs(total_amount),2) < round(abs(account_move_id.amount),2)
        ):
            raise ValidationError(
                _(
                    "Os valores inseridos são inferiores o valor do "
                    "pagamento. Verifique o valor total do recibo."
                )
            )

    def account_report_line_duplicate(self, vals):
        values = {dictionary['cash_flow_statement_line_id'] for dictionary in vals}
        account_report_line_duplicate = len(values) != len(vals)
        if account_report_line_duplicate:
            raise ValidationError(
                _(
                    f"Não pode existir fluxos duplicados na "
                    "lista. Remova ou altere o valor do existente."
                )
            )

    def get_amount_total_lines(self, account_payment_id):
        account_move_lines = (
            self.sudo()
            .search(
                [
                    ("account_payment_id", "=", account_payment_id)
                ]
            )
        )
        return account_move_lines
