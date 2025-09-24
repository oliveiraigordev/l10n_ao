from datetime import date
import json
import re
from ast import literal_eval
from collections import defaultdict
from odoo import models, fields, api, _, osv, _lt

REPORT_LINE_CODE = [
    'CX_RECEBI', 'CX_PAGAMEN_FORN', 'CX_PAGAMEN_EMPRE', 'CX_JUROS_PAGOS', 'CX_IMPOSTO_LUCRO_PAGOS',
    'CX_RECEB_RELAC_RUBRIC_EXTRAOR_OPE', 'CX_PAGAM_RELAC_RUBRIC_EXTRAOR_OPE', 'CX_IMOBI_CORPO', 'CX_IMOBI_INCORPOR',
    'CX_INVEST_FINANCEIROS', 'CX_SUBSID_INVEST', 'CX_JUROS_PROVEITOS_SIMILA', 'CX_DIVID_LUCRO_RECEBI', 'CX_IMOB_CORP',
    'CX_IMOB_INCORP', 'CX_INVEST_FIN', 'CX_RECEB_RELAC_RUBRIC_EXTRAOR_INVEST', 'CX_PAGAM_RELAC_RUBRIC_EXTRAOR_INVEST',
    'CX_AUMENTO_CAPITAL_PREST_SUPLE_VENDA', 'CX_COBERT_PREJUI', 'CX_EMPREST_OBTIDO', 'CX_SUBS_EXPLOR_DOAC',
    'CX_REDUCOES_CAPITAL', 'CX_COMPRA_ACCOES', 'CX_DIVIDENDO_LUCROS', 'CX_EMPRESTIMO_OBTIDOS',
    'CX_AMORTI_CONTRATOS_LOCAC', 'CX_JUROS_CUSTOS_SIMILARES', 'CX_RECEB_RELAC_RUBRIC_EXTRAOR_FINA',
    'CX_PAGAM_RELAC_RUBRIC_EXTRAOR_FINAN', 'CXA_EQUIVALEN_INICIO_PERIOD'
]


class AOAccountReport(models.Model):
    _inherit = "account.report"

    filter_by_account = fields.Boolean(
        string="Filtro multi Conta",
        compute=lambda x: x._compute_report_option_filter('filter_by_account'), readonly=False,
        store=True, depends=['root_report_id'],
    )

    def _get_options(self, previous_options=None):
        options = super(AOAccountReport, self)._get_options(previous_options=previous_options)
        options["filter_by_account"] = self.filter_by_account
        return options

    def _get_static_line_dict(self, options, line, all_column_groups_expression_totals, parent_id=None):
        line_id = self._get_generic_line_id('account.report.line', line.id, parent_line_id=parent_id)
        columns = self._build_static_line_columns(line, options, all_column_groups_expression_totals)

        rslt = {
            'id': line_id,
            'name': line.name,
            'groupby': line.groupby,
            'unfoldable': line.foldable and (any(col['has_sublines'] for col in columns) or bool(line.children_ids)),
            'unfolded': bool(
                (not line.foldable and (line.children_ids or line.groupby)) or line_id in options.get('unfolded_lines',
                                                                                                      {})) or options.get(
                'unfold_all'),
            'columns': columns,
            'level': line.hierarchy_level,
            'page_break': line.print_on_new_page,
            'action_id': line.action_id.id,
            'expand_function': line.groupby and '_report_expand_unfoldable_line_with_groupby' or None,
        }

        if parent_id:
            rslt['parent_id'] = parent_id

        if options['show_debug_column']:
            first_group_key = list(options['column_groups'].keys())[0]
            column_group_totals = all_column_groups_expression_totals[first_group_key]
            # Only consider the first column group, as show_debug_column is only true if there is but one.

            engine_selection_labels = dict(
                self.env['account.report.expression']._fields['engine']._description_selection(self.env))
            expressions_detail = defaultdict(lambda: [])
            col_expression_to_figure_type = {
                column.get('expression_label'): column.get('figure_type') for column in options['columns']
            }
            for expression in line.expression_ids:
                engine_label = engine_selection_labels[expression.engine]
                figure_type = expression.figure_type or col_expression_to_figure_type.get(expression.label) or 'none'
                expressions_detail[engine_label].append((
                    expression.label,
                    {'formula': expression.formula, 'subformula': expression.subformula,
                     'value': self.format_value(column_group_totals[expression]['value'], figure_type=figure_type,
                                                blank_if_zero=False)}
                ))

            # Sort results so that they can be rendered nicely in the UI
            for details in expressions_detail.values():
                details.sort(key=lambda x: x[0])
            sorted_expressions_detail = sorted(expressions_detail.items(), key=lambda x: x[0])

            rslt['debug_popup_data'] = json.dumps({'expressions_detail': sorted_expressions_detail})

        # Growth comparison column.
        if self._display_growth_comparison(options):
            compared_expression = line.expression_ids.filtered(
                lambda expr: expr.label == rslt['columns'][0]['expression_label'])
            first_value = columns[0]['no_format']
            second_value = columns[1]['no_format']
            if not first_value and not second_value:  # For layout lines and such, with no values
                rslt['growth_comparison_data'] = {'name': '', 'class': ''}
            else:
                rslt['growth_comparison_data'] = self._compute_growth_comparison_column(
                    options, first_value, second_value, green_on_positive=compared_expression.green_on_positive)

        return rslt

    @api.model
    def _build_static_line_columns(self, line, options, all_column_groups_expression_totals):
        line_expressions_map = {expr.label: expr for expr in line.expression_ids}
        columns = []
        for column_data in options['columns']:
            current_group_expression_totals = all_column_groups_expression_totals[column_data['column_group_key']]
            target_line_res_dict = {expr.label: current_group_expression_totals[expr] for expr in line.expression_ids}

            column_expr_label = column_data['expression_label']
            column_res_dict = target_line_res_dict.get(column_expr_label, {})
            column_value = column_res_dict.get('value')
            column_has_sublines = column_res_dict.get('has_sublines', False)
            column_expression = line_expressions_map.get(column_expr_label, self.env['account.report.expression'])
            figure_type = column_expression.figure_type or column_data['figure_type']

            # Handle info popup
            info_popup_data = {}

            # Check carryover
            carryover_expr_label = '_carryover_%s' % column_expr_label
            carryover_value = target_line_res_dict.get(carryover_expr_label, {}).get('value', 0)
            if self.env.company.currency_id.compare_amounts(0, carryover_value) != 0:
                info_popup_data['carryover'] = self.format_value(carryover_value, figure_type='monetary')

                carryover_expression = line_expressions_map[carryover_expr_label]
                if carryover_expression.carryover_target:
                    info_popup_data['carryover_target'] = carryover_expression._get_carryover_target_expression(
                        options).display_name
                # If it's not set, it means the carryover needs to target the same expression

            applied_carryover_value = target_line_res_dict.get('_applied_carryover_%s' % column_expr_label, {}).get(
                'value', 0)
            if self.env.company.currency_id.compare_amounts(0, applied_carryover_value) != 0:
                info_popup_data['applied_carryover'] = self.format_value(applied_carryover_value,
                                                                         figure_type='monetary')
                info_popup_data['allow_carryover_audit'] = self.user_has_groups('base.group_no_one')
                info_popup_data['expression_id'] = line_expressions_map['_applied_carryover_%s' % column_expr_label][
                    'id']

            # Handle manual edition popup
            edit_popup_data = {}
            if column_expression.engine == 'external' and column_expression.subformula \
                    and len(options.get('multi_company', [])) < 2 \
                    and (not options['available_vat_fiscal_positions'] or options['fiscal_position'] != 'all'):

                # Compute rounding for manual values
                rounding = None
                rounding_opt_match = re.search(r"\Wrounding\W*=\W*(?P<rounding>\d+)", column_expression.subformula)
                if rounding_opt_match:
                    rounding = int(rounding_opt_match.group('rounding'))
                elif figure_type == 'monetary':
                    rounding = self.env.company.currency_id.rounding

                if 'editable' in column_expression.subformula:
                    edit_popup_data = {
                        'column_group_key': column_data['column_group_key'],
                        'target_expression_id': column_expression.id,
                        'rounding': rounding,
                    }

                formatter_params = {'digits': rounding}
            else:
                formatter_params = {}

            # Build result
            blank_if_zero = column_expression.blank_if_zero or column_data.get('blank_if_zero')

            if column_value is None:
                formatted_name = ''
            else:
                formatted_name = self.format_value(
                    column_value,
                    figure_type=figure_type,
                    blank_if_zero=blank_if_zero,
                    **formatter_params
                )

            column_data = {
                'name': formatted_name,
                # add line report for AO REPORT ACCOUNTING
                'note': line.note,
                'style': 'white-space:nowrap; text-align:right;',
                'no_format': column_value,
                'column_group_key': options['columns'][len(columns)]['column_group_key'],
                'auditable': column_value is not None and column_expression.auditable,
                'expression_label': column_expr_label,
                'has_sublines': column_has_sublines,
                'report_line_id': line.id,
                'class': 'number' if isinstance(column_value, (int, float)) else '',
                'is_zero': column_value is None or (
                        figure_type in ('float', 'integer', 'monetary') and self.is_zero(column_value,
                                                                                         figure_type=figure_type,
                                                                                         **formatter_params)),
            }

            if info_popup_data:
                column_data['info_popup_data'] = json.dumps(info_popup_data)

            if edit_popup_data:
                column_data['edit_popup_data'] = json.dumps(edit_popup_data)

            columns.append(column_data)

        return columns

    def _compute_formula_batch(self, column_group_options, formula_engine, date_scope, formulas_dict, current_groupby,
                               next_groupby, offset=0, limit=None):
        """ Evaluates a batch of formulas.

        :param column_group_options: The options for the column group being evaluated, as obtained from _split_options_per_column_group.

        :param formula_engine: A string identifying a report engine. Must be one of account.report.expression's engine field's technical labels.

        :param date_scope: The date_scope under which to evaluate the fomulas. Must be one of account.report.expression's date_scope field's
                           technical labels.

        :param formulas_dict: A dict in the dict(formula, expressions), where:
                                - formula: a formula to be evaluated with the engine referred to by parent dict key
                                - expressions: a recordset of all the expressions to evaluate using formula (possibly with distinct subformulas)

        :param current_groupby: The groupby to evaluate, or None if there isn't any. In case of multi-level groupby, only contains the element
                                that needs to be computed (so, if unfolding a line doing 'partner_id,account_id,id'; current_groupby will only be
                                'partner_id'). Subsequent groupby will be in next_groupby.

        :param next_groupby: Full groupby string of the groups that will have to be evaluated next for these expressions, or None if there isn't any.
                             For example, in the case depicted in the example of current_groupby, next_groupby will be 'account_id,id'.

        :param offset: The SQL offset to use when computing the result of these expressions.

        :param limit: The SQL limit to apply when computing these expressions' result.

        :return: The result might have two different formats depending on the situation:
            - if we're computing a groupby: {(formula, expressions): [(grouping_key, {'result': value, 'has_sublines': boolean}), ...], ...}
            - if we're not: {(formula, expressions): {'result': value, 'has_sublines': boolean}, ...}

            'result' key is the default; different engines might use one or multiple other keys instead, depending of the subformulas they allow
            (e.g. 'sum', 'sum_if_pos', ...)
        """

        engine_function_name = f'_compute_formula_batch_with_engine_{formula_engine}'
        # Mudanças para se adecuar ao fluxo de caixa directo e indirecto
        if '_report_custom_engine_custom_function_account_move' in formulas_dict:
            expressions = formulas_dict.get('_report_custom_engine_custom_function_account_move')
            if len(expressions.report_line_id) == 1 and expressions.report_line_id.code in REPORT_LINE_CODE and current_groupby:
                if expressions.report_line_id.foldable:
                    engine_function_name = f'_l10n_ao_report_compute_formula_batch_with_engine_domain'

        return getattr(self, engine_function_name)(
            column_group_options, date_scope, formulas_dict, current_groupby, next_groupby,
            offset=offset, limit=limit
        )

    def _compute_formula_batch_with_engine_domain(self, options, date_scope, formulas_dict, current_groupby,
                                                  next_groupby, offset=0, limit=None):
        """ Report engine.

        Formulas made for this engine consist of a domain on account.move.line. Only those move lines will be used to compute the result.

        This engine supports a few subformulas, each returning a slighlty different result:
        - sum: the result will be sum of the matched move lines' balances

        - sum_if_pos: the result will be the same as sum only if it's positive; else, it will be 0

        - sum_if_neg: the result will be the same as sum only if it's negative; else, it will be 0

        - count_rows: the result will be the number of sublines this expression has. If the parent report line has no groupby,
                      then it will be the number of matching amls. If there is a groupby, it will be the number of distinct grouping
                      keys at the first level of this groupby (so, if groupby is 'partner_id, account_id', the number of partners).
        """

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

        self._check_groupby_fields(
            (next_groupby.split(',') if next_groupby else []) + ([current_groupby] if current_groupby else []))

        groupby_sql = f'account_move_line.{current_groupby}' if current_groupby else None
        ct_query = self.env['res.currency']._get_query_currency_table(options)

        rslt = {}

        for formula, expressions in formulas_dict.items():

            for expression in expressions:

                line_domain = literal_eval(formula)
                tables, where_clause, where_params = self._query_get(options, date_scope, domain=line_domain)

                tail_query, tail_params = self._get_engine_query_tail(offset, limit)

                query = f"""
                    SELECT
                        COALESCE(SUM(ROUND(account_move_line.balance * currency_table.rate, currency_table.precision)), 0.0) AS sum,
                        COALESCE(SUM(CASE WHEN account_move_line.date_maturity::date <= (account_move_line.date::date + '1 year'::interval) 
                        THEN ROUND(account_move_line.balance * currency_table.rate, currency_table.precision) END), 0.0) AS sum_if_less1year,
                        COALESCE(SUM(CASE WHEN account_move_line.date_maturity::date > (account_move_line.date::date + '1 year'::interval) 
                        THEN ROUND(account_move_line.balance * currency_table.rate, currency_table.precision) END), 0.0) AS sum_if_plus1year,
                        COALESCE(SUM(CASE WHEN account_move_line.date_maturity <= account_move_line.date + '5 year'::interval 
                        AND account_move_line.date_maturity > account_move_line.date + '1 year'::interval 
                        THEN ROUND(account_move_line.balance * currency_table.rate, currency_table.precision) END), 0.0) AS sum_if_5year,
                        COALESCE(SUM(CASE WHEN account_move_line.date_maturity > account_move_line.date + '5 year'::interval 
                        THEN ROUND(account_move_line.balance * currency_table.rate, currency_table.precision) END), 0.0) AS sum_if_plus5year,
                        COUNT(DISTINCT account_move_line.{next_groupby.split(',')[0] if next_groupby else 'id'}) AS count_rows
                        {f', {groupby_sql} AS grouping_key' if groupby_sql else ''}
                    FROM {tables}
                    JOIN {ct_query} ON currency_table.company_id = account_move_line.company_id
                    WHERE {where_clause}
                    {f' GROUP BY {groupby_sql}' if groupby_sql else ''}
                    {tail_query}
                """

                # Fetch the results.
                formula_rslt = []
                self._cr.execute(query, where_params + tail_params)
                all_query_res = self._cr.dictfetchall()

                total_sum = 0
                for query_res in all_query_res:
                    res_sum = query_res['sum']
                    total_sum += res_sum
                    totals = {
                        'sum': res_sum,
                        'sum_if_pos': 0,
                        'sum_if_neg': 0,
                        'sum_if_plus1year': query_res['sum_if_plus1year'],
                        'sum_if_less1year': query_res['sum_if_less1year'],
                        'sum_if_5year': query_res['sum_if_5year'],  # Added for Angola reports
                        'sum_if_plus5year': query_res['sum_if_plus5year'],  # Added for Angola Reports
                        'count_rows': query_res['count_rows'],
                        'has_sublines': query_res['count_rows'] > 0,
                    }
                    formula_rslt.append((query_res.get('grouping_key', None), totals))

                # Handle sum_if_pos, -sum_if_pos, sum_if_neg and -sum_if_neg
                expressions_by_sign_policy = defaultdict(lambda: self.env['account.report.expression'])
                # subformula_without_sign = 0
                # for expression in expressions:

                subformula_without_sign = expression.subformula.replace('-', '').strip()
                if subformula_without_sign in ('sum_if_pos', 'sum_if_neg'):
                    expressions_by_sign_policy[subformula_without_sign] += expression
                elif subformula_without_sign in (
                        'sum_if_less1year', 'sum_if_plus1year', 'sum_if_5year', 'sum_if_plus5year'):
                    expressions_by_sign_policy[subformula_without_sign] += expression
                else:
                    expressions_by_sign_policy['no_sign_check'] += expression

                if expressions_by_sign_policy['sum_if_less1year'] or expressions_by_sign_policy['sum_if_plus1year'] or \
                        expressions_by_sign_policy['sum_if_5year'] or expressions_by_sign_policy['sum_if_plus5year']:
                    for subformula, expression in expressions_by_sign_policy.items():
                        if subformula in ('sum_if_less1year', 'sum_if_plus1year', 'sum_if_5year', 'sum_if_plus5year'):
                            formula_rslt_with_sign = [(grouping_key, {**totals, subformula: totals[subformula], }) for
                                                      grouping_key, totals in formula_rslt]

                            if expressions_by_sign_policy[subformula]:
                                rslt[(
                                    formula,
                                    expressions_by_sign_policy[subformula])] = _format_result_depending_on_groupby(
                                    formula_rslt_with_sign)
                            else:
                                rslt[(
                                    formula,
                                    expressions_by_sign_policy[subformula])] = _format_result_depending_on_groupby(
                                    [])
                        elif expressions_by_sign_policy['no_sign_check']:
                            rslt[(
                                formula,
                                expressions_by_sign_policy['no_sign_check'])] = _format_result_depending_on_groupby(
                                formula_rslt)

                # Then we have to check the total of the line and only give results if its sign matches the desired policy.
                # This is important for groupby managements, for which we can't just check the sign query_res by query_res
                if expressions_by_sign_policy['sum_if_pos'] or expressions_by_sign_policy['sum_if_neg']:
                    sign_policy_with_value = 'sum_if_pos' if self.env.company.currency_id.compare_amounts(total_sum,
                                                                                                          0.0) >= 0 else 'sum_if_neg'
                    # >= instead of > is intended; usability decision: 0 is considered positive

                    formula_rslt_with_sign = [(grouping_key, {**totals, sign_policy_with_value: totals['sum']}) for
                                              grouping_key, totals in formula_rslt]

                    for sign_policy in ('sum_if_pos', 'sum_if_neg'):
                        policy_expressions = expressions_by_sign_policy[sign_policy]

                        if policy_expressions:
                            if sign_policy == sign_policy_with_value:
                                rslt[(formula, policy_expressions)] = _format_result_depending_on_groupby(
                                    formula_rslt_with_sign)
                            else:
                                rslt[(formula, policy_expressions)] = _format_result_depending_on_groupby([])

                if expressions_by_sign_policy['no_sign_check']:
                    rslt[(formula, expressions_by_sign_policy['no_sign_check'])] = _format_result_depending_on_groupby(
                        formula_rslt)

        return rslt

    def _get_static_line_dict(self, options, line, all_column_groups_expression_totals, parent_id=None):
        rslt = super()._get_static_line_dict(options, line, all_column_groups_expression_totals, parent_id=None)
        rslt.update(note=line.note)
        return rslt

    def _compute_formula_batch_with_engine_custom(self, options, date_scope, formulas_dict, current_groupby,
                                                  next_groupby, offset=0, limit=None):
        self._check_groupby_fields(
            (next_groupby.split(',') if next_groupby else []) + ([current_groupby] if current_groupby else []))

        rslt = {}
        for formula, expressions in formulas_dict.items():
            for expression in expressions:
                custom_engine_function = self._get_custom_report_function(formula, 'custom_engine')
                rslt[(formula, expression)] = custom_engine_function(
                    expression, options, date_scope, current_groupby, next_groupby, offset=offset, limit=limit)
        return rslt

    def _l10n_ao_report_compute_formula_batch_with_engine_domain(self, options, date_scope, formulas_dict,
                                                                 current_groupby, next_groupby, offset=0, limit=None):
        rslt = {}
        for formula, expressions in formulas_dict.items():
            expressions_by_sign_policy = defaultdict(lambda: self.env['account.report.expression'])
            expressions_by_sign_policy['no_sign_check'] += expressions
            tables, where_clause, where_params = self._query_get(options, date_scope, domain=[])
            formula_rslt = self._get_result_depending_on_groupby_total(expressions, where_params)
            rslt[(formula, expressions_by_sign_policy['no_sign_check'])] = formula_rslt
        return rslt

    def _get_result_depending_on_groupby_total(self, expressions, date_scope):
        first_period = False
        # Verificar se foi escolhido o primeiro período de acordo com o filtro escolhido
        if expressions.report_line_id == self.env.ref(
                'l10n_ao_report.account_financial_report_caixa_equivale_inicio_period'):
            first_period = True

        account_move_ids = self.get_account_move_ids(date_scope, first_period)
        # move_report_line_ids = account_move_ids.account_move_report_line_ids if first_period else account_move_ids.account_move_report_line_ids.filtered(
        #     lambda r: r.account_report_line_id.code == expressions.report_line_id.code)
        # Filtrar os Fluxos
        move_report_line_ids = account_move_ids.account_move_report_line_ids if first_period else \
            account_move_ids.account_move_report_line_ids.filtered(
                lambda r: r.cash_flow_statement_id.account_report_line_id.code == expressions.report_line_id.code)
        # Obter as contas associadas ao fluxo lançado no Diário
        account_ids = self.get_account_ids(expressions) if first_period else move_report_line_ids.mapped('account_id')
        group_total_values = []
        for account_id in account_ids:
            move_line_ids = move_report_line_ids.filtered(
                lambda r: r.account_id == account_id) if not first_period else move_report_line_ids.filtered(
                lambda r: r.account_id.id == account_id)
            if move_line_ids:
                group_total_values.append(
                    (account_id.id if not first_period else account_id,
                     {
                         'sum': sum([line.amount for line in move_line_ids]),
                         'sum_if_pos': 0,
                         'sum_if_neg': 0,
                         'sum_if_plus1year': 0.0,
                         'sum_if_less1year': 0,
                         'sum_if_5year': 0.0,
                         'sum_if_plus5year': 0.0,
                         'count_rows': len(move_line_ids),
                         'has_sublines': True
                     }
                     )
                )
        return group_total_values

    def get_account_ids(self, expressions):
        account_ids = []
        account_codes = [f'{number}%' for number in expressions.carryover_target.split(',')]
        for code in account_codes:
            account_id = self.env['account.account'].sudo().search([('code', '=ilike', code)])
            if account_id:
                account_ids.extend(account_id.mapped('id'))
        return account_ids

    def get_account_move_ids(self, where_params, first_period):
        date_form = date(
            int(where_params[3].split('-')[0]),
            int(where_params[3].split('-')[1]),
            int(where_params[3].split('-')[2])
        )
        if first_period:
            date_to = date(
                int(where_params[3].split('-')[0]),
                int(where_params[3].split('-')[1]),
                31
            )
        else:
            date_to = date(
                int(where_params[2].split('-')[0]),
                int(where_params[2].split('-')[1]),
                int(where_params[2].split('-')[2])
            )
        account_move_ids = self.env['account.move'].sudo().search([
            ('move_type', '=', 'entry'),
            ('state', 'in', ['posted']),
            ("date", ">=", date_form),
            ("date", "<=", date_to),
            ('company_id', '=', self.env.company.id),
        ])
        return account_move_ids
