from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class AccountMove(models.Model):
    _inherit = "account.move"

    iva_origin_account = fields.Char("Origin account")
    account_move_report_line_ids = fields.One2many('account.move.report.line', 'account_move_id',
                                                   string='Cash Flow Insertion')
    asset_cash_amount_total = fields.Monetary(string="Total Balance", compute='_compute_asset_cash_balance')
    journal_type = fields.Selection(string='Journal Type', related='journal_id.type')
    cash_flow_in_payment = fields.Boolean("Registar Fluxo de Caixa no Pagamento",
                                          related="company_id.cash_flow_in_payment", readonly=False)

    payment_line_cashflow = fields.Boolean(string="Linha de Fluxo", default=False)
    line_cashflow = fields.Boolean(string="Linha de Fluxo", default=False)

    computed_line_cashflow = fields.Float(
        string='line_cashflow',
        compute='_compute_line_cashflow',
        store=True,
    )

    @api.depends('line_cashflow')
    def _compute_line_cashflow(self):
        for record in self:
            if not record.line_cashflow:
                pagamento = self.env['account.payment'].search([('ref', '=', record.name)], limit=1)
                if pagamento:
                    cash_flow_map = self.env['cash.flow.statement.map'].search(
                        [('doc_number', '=', pagamento.display_name)])
                    for i in cash_flow_map:
                        i.unlink()
            record.computed_line_cashflow = 0

    def _compute_asset_cash_balance(self):
        for record in self:
            move_line_ids = record.line_ids.filtered(
                lambda r: r.account_id.account_type in ['asset_cash', 'asset_current'])
            record.asset_cash_amount_total = sum([line.balance for line in move_line_ids]) if len(
                move_line_ids) == 1 else 0
