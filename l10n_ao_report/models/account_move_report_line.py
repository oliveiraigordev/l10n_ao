from odoo import models, Command, fields, api, _
from odoo.exceptions import ValidationError


class AccountMoveReportLine(models.Model):
    _name = 'account.move.report.line'
    _description = 'Account Move Report Line Model'

    account_move_id = fields.Many2one('account.move', 'Account Move')
    account_id = fields.Many2one('account.account', 'Account')
    cash_flow_statement_id = fields.Many2one('cash.flow.statement', string="Fluxo", required=1)
    cash_flow_statement_line_id = fields.Many2one('cash.flow.statement.line', string='Linha do Fluxo',  required=0,
                                                  )#default='default_name'
    amount = fields.Float("Amount")

    line_cashflow = fields.Boolean(string="Linha de Fluxo", default=False)

    def write(self, vals):
        for inv in self:
            # update cash flow statement map
            cash_flow_map = self.env['cash.flow.statement.map'].search(
                [('cash_flow_statement_line_id', '=', inv.cash_flow_statement_line_id.id),
                 ('date', '=', inv.account_move_id.date)])

            if (
                    vals.get("amount")
            ):
                vals['amount'] = vals.get("amount") if inv.account_move_id.asset_cash_amount_total > 0 else vals.get(
                    "amount") * -1

                cash_flow_map.write(
                    {
                        'debit': vals['amount'] if inv.account_move_id.asset_cash_amount_total > 0 else 0,
                        'credit': vals['amount'] if inv.account_move_id.asset_cash_amount_total < 0 else 0,
                    }
                )

            if (
                    vals.get("cash_flow_statement_line_id")
            ):
                cash_flow_map.write(
                    {
                        'cash_flow_statement_line_id': vals.get("cash_flow_statement_line_id")
                    }
                )

        report_line = super(AccountMoveReportLine, self).write(vals)
        return report_line

    @api.model_create_multi
    def create(self, vals):
        account_move_id = (
            self.env['account.move']
            .sudo()
            .search(
                [
                    ("id", "=", vals[0].get('account_move_id'))
                ]
            )
        )

        move_line_id = account_move_id.line_ids.filtered(
            lambda r: r.account_id.account_type in ['asset_cash', 'asset_current']
        )
        # Verificar se o fluxo escolhido já se encontra na lista
        self.account_report_line_duplicate(vals)
        # Verificar se o valor das linhas é igual ao valor do pagamento
        amount_total_lines = self.get_amount_total_lines(account_move_id.id)
        total_amount = sum([dictionary.get("amount") for dictionary in vals]) + sum(amount_total_lines.mapped("amount"))
        self.verify_amount_total_lines(account_move_id, total_amount)

        for dict_value in vals:
            dict_value['account_id'] = move_line_id.account_id.id
            dict_value['amount'] = dict_value.get('amount') if \
                account_move_id.asset_cash_amount_total > 0 else dict_value.get('amount') * -1

        cash_flow_result = self.create_cash_flow_statement_map(account_move_id, vals)
        if not cash_flow_result:
            raise ValidationError(
                _(
                    f"O Fluxo não pode ser salvo na"
                    "lista, Porque teve erro ao salvar no Extracto do Fluxo de Caixa."
                )
            )

        res = super(AccountMoveReportLine, self).create(vals)
        return res

    def unlink(self):
        for aml in self:
            # delete_cash_flow_statement_map
            cash_flow_map = self.env['cash.flow.statement.map'].search(
                [('cash_flow_statement_line_id', '=', aml.cash_flow_statement_line_id.id),
                 ('date', '=', aml.account_move_id.date)])
            cash_flow_map.unlink()
        return super(AccountMoveReportLine, self).unlink()

    def verify_amount_total_lines(self, account_move_id, total_amount):
        if (
                abs(total_amount) > abs(account_move_id.asset_cash_amount_total)
        ):
            raise ValidationError(
                _(
                    "Os valores inseridos excedem o valor do "
                    "pagamento. Verifique o valor total do recibo."
                )
            )
        elif (
                round(abs(total_amount),2) < round(abs(account_move_id.asset_cash_amount_total),2)
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

    def get_amount_total_lines(self, account_move_id):
        account_move_lines = (
            self.env["account.move.report.line"]
            .sudo()
            .search(
                [
                    ("account_move_id", "=", account_move_id)
                ]
            )
        )
        return account_move_lines

    def create_cash_flow_statement_map(self, account_move_id, vals):
        data_value = []
        for value in vals:
            move_line_id = account_move_id.line_ids.filtered(
                lambda r: r.account_id.id == value['account_id']
            )
            cash_flow_statement_map_values = {
                'description': move_line_id.name,
                'journal_id': account_move_id.journal_id.journal_ao_id.id,
                'origin_account_id': value['account_id'],
                'cash_flow_statement_line_id': value['cash_flow_statement_line_id'],
                'debit': value['amount'] if account_move_id.asset_cash_amount_total > 0 else 0,
                'credit': value['amount'] if account_move_id.asset_cash_amount_total < 0 else 0,
                'balance': False,
                'document': account_move_id.journal_id.code,
                'doc_number': account_move_id.name,
                'date': account_move_id.date
            }
            data_value.append(self.env['cash.flow.statement.map'].create(cash_flow_statement_map_values))

        return data_value