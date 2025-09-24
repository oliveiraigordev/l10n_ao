from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

from datetime import datetime, date


class L1ONCashFlowStatementMap(models.Model):
    _name = 'cash.flow.statement.map'
    _description = 'Cash Flow Statement Map Model'

    description = fields.Char(string='Descrição')
    journal_id = fields.Many2one('account.journal.ao', 'Diário')
    origin_account_id = fields.Many2one('account.account', 'Conta Origem')
    cash_flow_statement_line_id = fields.Many2one('cash.flow.statement.line', "Linha do Fluxo")
    debit = fields.Float('Débito')
    credit = fields.Float('Crédito')
    balance = fields.Float(string='Saldo', compute="_compute_balance", store=True)
    document = fields.Char('Doc.')
    doc_number = fields.Char('Nº Doc')
    date = fields.Date('Data')
    line_cashflow = fields.Boolean(string="Linha de Fluxo", default=False)

    @api.depends(
        "debit",
        "credit",
    )
    def _compute_balance(self):
        for record in self:
            record.balance = record.debit - record.credit

    def get_amount_accumulated_total(self, domain, domain_selected=False):
        if not domain_selected:
            domain_selected = []
        else:
            domain_selected = domain

        cash_flow_map_ids = self.sudo().search(domain_selected)
        if domain_selected:
            cash_flow_map_ids_all = self.sudo().search([])
            credit_accumulated_total_balance = sum([record.credit for record in cash_flow_map_ids_all]) - sum(
                [record.credit for record in cash_flow_map_ids])
            debit_accumulated_total_balance = sum([record.debit for record in cash_flow_map_ids_all]) - sum(
                [record.debit for record in cash_flow_map_ids])
            amount_accumulated_total_balance = sum([record.balance for record in cash_flow_map_ids_all]) - sum(
                [record.balance for record in cash_flow_map_ids])
        else:
            credit_accumulated_total_balance = sum([record.credit for record in cash_flow_map_ids])
            debit_accumulated_total_balance = sum([record.debit for record in cash_flow_map_ids])
            amount_accumulated_total_balance = sum([record.balance for record in cash_flow_map_ids])

        amount_values = {
            'credit_total': credit_accumulated_total_balance,
            'debit_balance': debit_accumulated_total_balance,
            'balance_total': amount_accumulated_total_balance
        }
        return amount_values

    def get_amount_total(self, domain_selected):
        today = fields.Date.today()
        date_from = date(
            today.year,
            1,
            1,
        )
        date_to = date(
            today.year,
            12,
            31,
        )
        if domain_selected:
            domain_selected = domain_selected
        else:
            domain_selected = [("date", ">=", date_from), ("date", "<=", date_to), ]

        cash_flow_map_ids = self.sudo().search(domain_selected)
        credit_total_balance = sum([record.credit for record in cash_flow_map_ids])
        debit_total_balance = sum([record.debit for record in cash_flow_map_ids])
        amount_total_balance = sum([record.balance for record in cash_flow_map_ids])
        amount_values = {
            'credit_total': credit_total_balance,
            'debit_balance': debit_total_balance,
            'balance_total': amount_total_balance
        }

        return amount_values
