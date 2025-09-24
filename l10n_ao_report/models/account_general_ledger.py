from odoo import models, _, fields
from collections import defaultdict


class GeneralLedgerCustomHandler(models.AbstractModel):
    _inherit = 'account.general.ledger.report.handler'
    _description = 'General Ledger Custom Handler'

    def _dynamic_lines_generator(self, report, options, all_column_groups_expression_totals):
        """
            Check account statement filter by account is active to search account_move_line (aml) from it
        """
        if options.get("filter_by_account", False):
            lines = []
            date_from = fields.Date.from_string(options['date']['date_from'])
            company_currency = self.env.company.currency_id
            totals_by_column_group = defaultdict(lambda: {'debit': 0, 'credit': 0, 'balance': 0})

            # Split filter_search_bar as list to search all account like in frontend
            filter_search_bar = options.get("filter_search_bar", "").split(",")

            for filter in filter_search_bar:
                options["filter_search_bar"] = filter

                for account, column_group_results in self._query_values(report, options):
                    eval_dict = {}
                    has_lines = False
                    for column_group_key, results in column_group_results.items():
                        account_sum = results.get('sum', {})
                        account_un_earn = results.get('unaffected_earnings', {})

                        account_debit = account_sum.get('debit', 0.0) + account_un_earn.get('debit', 0.0)
                        account_credit = account_sum.get('credit', 0.0) + account_un_earn.get('credit', 0.0)
                        account_balance = account_sum.get('balance', 0.0) + account_un_earn.get('balance', 0.0)

                        eval_dict[column_group_key] = {
                            'amount_currency': account_sum.get('amount_currency', 0.0) + account_un_earn.get(
                                'amount_currency', 0.0),
                            'debit': account_debit,
                            'credit': account_credit,
                            'balance': account_balance,
                        }

                        max_date = account_sum.get('max_date')
                        has_lines = has_lines or (max_date and max_date >= date_from)

                        totals_by_column_group[column_group_key]['debit'] += account_debit
                        totals_by_column_group[column_group_key]['credit'] += account_credit
                        totals_by_column_group[column_group_key]['balance'] += account_balance

                    lines.append(self._get_account_title_line(report, options, account, has_lines, eval_dict))

            # Report total line.
            for totals in totals_by_column_group.values():
                totals['balance'] = company_currency.round(totals['balance'])

            # Tax Declaration lines.
            journal_options = report._get_options_journals(options)
            if len(options['column_groups']) == 1 and len(journal_options) == 1 and journal_options[0]['type'] in (
            'sale', 'purchase'):
                lines += self._tax_declaration_lines(report, options, journal_options[0]['type'])

            # Total line
            lines.append(self._get_total_line(report, options, totals_by_column_group))

            return [(0, line) for line in lines]
        else:
            return super(GeneralLedgerCustomHandler, self)._dynamic_lines_generator(report, options,
                                                                                    all_column_groups_expression_totals)

    def _get_account_title_line(self, report, options, account, has_lines, eval_dict):
        line_columns = []
        for column in options['columns']:
            col_value = eval_dict[column['column_group_key']].get(column['expression_label'])
            col_expr_label = column['expression_label']

            if col_value is None or (col_expr_label == 'amount_currency' and not account.currency_id):
                line_columns.append({})

            else:
                if col_expr_label == 'amount_currency':
                    formatted_value = report.format_value(col_value, currency=account.currency_id, figure_type=column['figure_type'])
                else:
                    formatted_value = report.format_value(col_value, figure_type=column['figure_type'], blank_if_zero=col_expr_label != 'balance')

                line_columns.append({
                    'name': formatted_value,
                    'no_format': col_value,
                    'class': 'number',
                })

        unfold_all = self._context.get('print_mode') or options.get('unfold_all')
        line_id = report._get_generic_line_id('account.account', account.id)
        return {
            'id': line_id,
            'name':  account.code if options.get('available_variants')[0].get('name') == 'Balancete Periodo' or options.get('available_variants')[0].get('name') == 'Balancete Anterior. Periodo. Acumulado.' else f'{account.code} {account.name}',
            'description': account.name,
            'search_key': account.code,
            'type_balancete': options.get('available_variants')[0].get('name'),
            'columns': line_columns,
            'level': 1,
            'unfoldable': has_lines,
            'unfolded': has_lines and (line_id in options.get('unfolded_lines') or unfold_all),
            'expand_function': '_report_expand_unfoldable_line_general_ledger',
            'class': 'o_account_reports_totals_below_sections' if self.env.company.totals_below_sections else '',
        }