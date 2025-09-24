from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class L1ONCashFlowStatement(models.Model):
    _name = 'cash.flow.statement'
    _description = 'Cash Flow Statement Model'

    name = fields.Char('Descrição')
    code = fields.Char('Código', required=1)
    account_report_id = fields.Many2one('account.report', string='Relatório de Contas', required=1)
    account_report_line_id = fields.Many2one('account.report.line', string="Linha do Relatório de Contas", required=1)
    cash_flow_statement_ids = fields.One2many('cash.flow.statement.line', 'cash_flow_statement_id',
                                              'Linhas do Extracto do Fluxo de Caixa')
    register_cashflow = fields.Boolean(string="Criar Linha de Fluxo", default=False)

    @api.onchange('account_report_line_id')
    def onchange_account_report_line_id(self):
        if self.account_report_line_id:
            self.name = f'Fluxo: {self.code} - {self.account_report_line_id.name}'

    @api.model_create_multi
    def create(self, vals):
        # Verificar se o fluxo escolhido já se encontra na lista
        if 'account_report_line_id' in vals[0]:
            report_line = self.search([('account_report_line_id', '=', vals[0]['account_report_line_id'])])
            if report_line:
                raise ValidationError(
                    _(
                        f"Não pode existir fluxos duplicados na "
                        "lista. Remova ou altere o valor do existente."
                    )
                )
        res = super(L1ONCashFlowStatement, self).create(vals)
        return res

    def write(self, vals):
        for inv in self:
            if vals.get("account_report_line_id"):
                report_line = self.search([('account_report_line_id', '=', vals['account_report_line_id'])])
                if report_line:
                    raise ValidationError(
                        _(
                            f"Não pode existir fluxos duplicados na "
                            "lista. Remova ou altere o valor do existente."
                        )
                    )

        report_line = super(L1ONCashFlowStatement, self).write(vals)
        return report_line

    def account_report_line_duplicate(self, vals):
        if 'account_report_line_id' in vals[0]:
            report_line = self.search([('account_report_line_id', '=', vals[0]['account_report_line_id'])])
            return report_line
        return False


class L1ONCashFlowStatementLine(models.Model):
    _name = 'cash.flow.statement.line'
    _description = 'Cash Flow Statement Line Model'

    name = fields.Char('Descrição', required=1)
    code = fields.Char('Código')
    sequence = fields.Integer('Sequence')
    cash_flow_statement_id = fields.Many2one('cash.flow.statement', string='Extracto do Fluxo de Caixa')
    date = fields.Date('Data')

    def name_get(self):
        result = []
        for record in self:
            name = f'Fluxo: {record.code} - {record.name}'
            result.append((record.id, name))
        return result

    # @api.model_create_multi
    @api.model
    def create(self, vals):
        cash_flow_id = self.env['cash.flow.statement'].browse([vals['cash_flow_statement_id']])
        line_id = self.search([('cash_flow_statement_id', '=', cash_flow_id.id)])
        line_id = line_id[-1] if line_id else line_id
        vals['sequence'] = line_id.sequence + 1
        vals['code'] = f'{int(cash_flow_id.code)}0{vals["sequence"]}'
        return super(L1ONCashFlowStatementLine, self).create(vals)
