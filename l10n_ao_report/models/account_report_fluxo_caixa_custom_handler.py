# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models, fields, api, _
from datetime import datetime, date
from collections import defaultdict


class FluxoCaixaCustomHandler(models.AbstractModel):
    _name = 'account.fluxo.caixa.report.handler'
    _inherit = 'account.report.custom.handler'

    def _custom_options_initializer(self, report, options, previous_options=None):
        super()._custom_options_initializer(report, options, previous_options=previous_options)
        return True

    def _report_custom_engine_custom_function_account_move(self, options, date_scope, formulas_dict, current_groupby,
                                                           next_groupby,
                                                           offset=0, limit=None):

        def _format_result_depending_on_groupby(formula_rslt):
            if not current_groupby:
                if formula_rslt:
                    # There should be only one element in the list; we only return its totals (a dict) ; so that a list is only returned in case
                    # of a groupby being unfolded.
                    return formula_rslt[0][1]
                else:
                    # No result at all
                    return {
                        'sum': 0,
                        'sum_if_pos': 0,
                        'sum_if_neg': 0,
                        'sum_if_plus1year': 0,  # Added for Angola reports
                        'sum_if_less1year': 0,  # Added for Angola Reports
                        'sum_if_5year': 0,  # Added for Angola reports
                        'sum_if_plus5year': 0,  # Added for Angola Reports
                        'count_rows': 0,
                        'has_sublines': False,
                    }
            return formula_rslt

        # Buscar o primeiro período de acordo com o filtro escolhido
        if options.report_line_id == self.env.ref(
                'l10n_ao_report.account_financial_report_caixa_equivale_inicio_period'):
            # Mudanças para se adecuar ao fluxo de caixa directo e indirecto
            balance_total = self._get_balance_total_first_period(options, date_scope)
        else:
            balance_total = self._get_balance_total(options, date_scope)

        totals = {
            'sum': balance_total,
            'sum_if_pos': 0,
            'sum_if_neg': 0,
            'sum_if_plus1year': 0,
            'sum_if_less1year': 0,
            'sum_if_5year': 0,  # Added for Angola reports
            'sum_if_plus5year': 0,  # Added for Angola Reports
            'count_rows': 0,
            'has_sublines': True if balance_total != 0 else False,
        }
        return _format_result_depending_on_groupby([((options.formula), totals)])

    def _get_balance_total(self, options, date_scope):
        date_form = date(
            int(date_scope['date']['date_from'].split('-')[0]),
            int(date_scope['date']['date_from'].split('-')[1]),
            int(date_scope['date']['date_from'].split('-')[2])
        )
        date_to = date(
            int(date_scope['date']['date_to'].split('-')[0]),
            int(date_scope['date']['date_to'].split('-')[1]),
            int(date_scope['date']['date_to'].split('-')[2])
        )
        account_move_ids = self.env['account.move'].sudo().search([
            ('move_type', '=', 'entry'),
            ('state', 'in', ['posted']),
            ("date", ">=", date_form),
            ("date", "<=", date_to),
            ('company_id', '=', self.env.company.id),
        ])
        # Filtrar os Fluxos
        cash_flow_statement_ids = account_move_ids.account_move_report_line_ids.filtered(
            lambda r: r.cash_flow_statement_id.account_report_line_id.code == options.report_line_id.code)
        cash_flow_statement_line_ids = cash_flow_statement_ids.cash_flow_statement_line_id
        # move_line_ids = account_move_ids.account_move_report_line_ids.filtered(
        #     lambda r: r.account_report_line_id.code == options.report_line_id.code)
        return sum([line.amount for line in cash_flow_statement_ids])

    def _get_balance_total_first_period(self, options, date_scope):
        date_form = date(
            int(date_scope['date']['date_from'].split('-')[0]),
            int(date_scope['date']['date_from'].split('-')[1]),
            int(date_scope['date']['date_from'].split('-')[2])
        )
        date_to = date(
            int(date_scope['date']['date_from'].split('-')[0]),
            int(date_scope['date']['date_from'].split('-')[1]),
            31
        )
        account_move_ids = self.env['account.move'].sudo().search([
            ('move_type', '=', 'entry'),
            ('state', 'in', ['posted']),
            ("date", ">=", date_form),
            ("date", "<=", date_to),
        ])
        account_ids = self.get_account_ids(options)
        move_line_ids = account_move_ids.account_move_report_line_ids.filtered(lambda r: r.account_id.id in account_ids)
        return sum([line.amount for line in move_line_ids])

    def get_account_ids(self, options):
        account_ids = []
        account_codes = [f'{number}%' for number in options.carryover_target.split(',')]
        for code in account_codes:
            account_id = self.env['account.account'].sudo().search([('code', '=ilike', code)])
            if account_id:
                account_ids.extend(account_id.mapped('id'))
        return account_ids
