from odoo import models, _, fields
from odoo.tools.misc import DEFAULT_SERVER_DATE_FORMAT
from odoo.tools import float_compare
import calendar

class TrialBalanceCustomHandler(models.AbstractModel):
    _name = 'account.trial.balance.report.handler_ao'
    _inherit = "account.trial.balance.report.handler"
    _description = "Trial Balance Custom Handler"


    def _dynamic_lines_generator(self, report, options, all_column_groups_expression_totals):
        lines = super(TrialBalanceCustomHandler, self)._dynamic_lines_generator(report, options, all_column_groups_expression_totals)
  
        for i, line in enumerate(lines):
            if i != len(lines) - 1:
                name = line[1]['name']
                desc = line[1]['description']
                line[1]['name'] = f'{name} {desc}'
            columns = line[1].get("columns", [])
            for index in range(len(columns)):
                if index and (index + 1) % 3 == 0:
                    value = (
                        columns[index - 2]["no_format"] - columns[index - 1]["no_format"]
                    )
                    columns[index] = {
                        "class": "number",
                        "name": self.env["account.report"].format_value(
                            value, figure_type="monetary", blank_if_zero=True
                        ),
                        "no_format": value,
                    }

        if options['available_variants'][0]['name'] == 'Balancete Anterior. Periodo. Acumulado.':
            for account in lines:
                index = 0
                previous_period_credit = 0
                previous_period_debit = 0
                previous_period_balance = 0
                present_period_credit = 0
                present_period_debit = 0
                present_period_balance = 0
                for move in enumerate(account[1]['columns']):
                    if index == 0:
                        previous_period_credit += round(move[1]['no_format'], 2)
                    elif index == 1:
                        previous_period_debit += round(move[1]['no_format'], 2)
                    elif index == 2:
                        previous_period_balance += round(move[1]['no_format'], 2)
                    elif index == 3:
                        present_period_credit += round(move[1]['no_format'], 2)
                    elif index == 4:
                        present_period_debit += round(move[1]['no_format'], 2)
                    elif index == 5:
                        present_period_balance += round(move[1]['no_format'], 2)
                    index += 1
                
                balance = round(previous_period_balance + present_period_balance, 2)
                credit = round(previous_period_credit + present_period_credit, 2)
                debit = round(previous_period_debit + present_period_debit, 2)
                account[1]['columns'][-1]['no_format'] = balance
                account[1]['columns'][-2]['no_format'] = credit
                account[1]['columns'][-3]['no_format'] = debit

                account[1]['columns'][-1]['name'] = balance
                account[1]['columns'][-2]['name'] = credit
                account[1]['columns'][-3]['name'] = debit
                
                lines[-1][1]['columns'][-1]['name'] = balance
                lines[-1][1]['columns'][-1]['no_format'] = balance
            
        elif options['available_variants'][0]['name'] == 'Balancete Periodo':
            index = 1
            for i in range(0, (len(lines)-1) // 2):
                value = lines[index][1]['columns'][1]['no_format']
                lines[index][1]['columns'][1]['no_format'] = value
                lines[index][1]['columns'][1]['name'] = value

                value = lines[index][1]['columns'][2]['no_format']
                lines[index][1]['columns'][2]['no_format'] = value
                lines[index][1]['columns'][2]['name'] = value
                index += 2
            
            saldo_acumulado = 0
            for line in lines[0:len(lines)-1]:
                saldo_acumulado += (line[1]['columns'][-1]['no_format'])
            
            lines[-1][1]['columns'][-1]['name'] = self.env["account.report"].format_value(
                            saldo_acumulado, figure_type="monetary", blank_if_zero=True
                        )
            lines[-1][1]['columns'][-1]['no_format'] = saldo_acumulado
          
        credito_acumulado = 0
        for line in lines[0:len(lines)-1]:
            credito_acumulado += (line[1]['columns'][-2]['no_format'])
        
        lines[-1][1]['columns'][-2]['name'] = self.env["account.report"].format_value(
                            credito_acumulado, figure_type="monetary", blank_if_zero=True
                        )
        lines[-1][1]['columns'][-2]['no_format'] = credito_acumulado
        
        if 'columns' in lines[-1][1]:
            balance_columns = lines[-1][1]['columns']
            for balance_column in balance_columns:
                if 'name' in balance_column:
                    if balance_column['name'] == '':
                        balance_column['name'] = 0.0
    
        return lines


    def _custom_options_initializer(self, report, options, previous_options=None, data=None):
        """ Modifies the provided options to add a column group for initial balance and end balance, as well as the appropriate columns.
        """
     
        default_group_vals = {'horizontal_groupby_element': {}, 'forced_options': {}}

        options['column_headers'][0][0]['name'] = f"De {options['date']['date_from']} a {options['date']['date_to']}"

        # Columns between initial and end balance must not include initial balance; we use a special option key for that in general ledger
        for column_group in options['column_groups'].values():
            column_group['forced_options']['general_ledger_strict_range'] = True

        if options['comparison']['periods']:
            # Reverse the order the group of columns with the same column_group_key while keeping the original order inside the group
            new_columns_order = []
            current_column = []
            current_column_group_key = options['columns'][-1]['column_group_key']

            for column in reversed(options['columns']):
                if current_column_group_key != column['column_group_key']:
                    current_column_group_key = column['column_group_key']
                    new_columns_order += current_column
                    current_column = []

                current_column.insert(0, column)
            new_columns_order += current_column

            options['columns'] = new_columns_order
            options['column_headers'][0][:] = reversed(options['column_headers'][0])
        
        if options['available_variants'][0]['name'] == 'Balancete Anterior. Periodo. Acumulado.':
            # Initial balance
            initial_balance_options = self.env['account.general.ledger.report.handler']._get_options_initial_balance(options)
            comparison = {
                'filter': 'previous_period', 
                'number_period': 1, 
                'date_from': options['date']['date_from'], 
                'date_to': options['date']['date_to'], 
                'string': f"{options['date']['date_from'].split('-')[0]}",
                'periods': [
                    {
                        'string': f'{options["date"]["date_from"].split("-")[0]}',
                        'period_type': 'fiscalyear',
                        'mode': 'range',
                        'date_from': options['date']['date_from'],
                        'date_to': options['date']['date_to'],
                    },
                    {
                        'string': f'{initial_balance_options["date"]["date_from"].split("-")[0]}',
                        'period_type': 'fiscalyear',
                        'mode': 'range',
                        'date_from': initial_balance_options['date']['date_from'],
                        'date_to': initial_balance_options['date']['date_to'],
                    }
                ],
                'period_type': 'fiscalyear', 
                'mode': 'range'
            }
            options['comparison'] = comparison

            # End balance
            end_date_to = options['date']['date_to']
            end_date_from = options['comparison']['periods'][-1]['date_from'] if options['comparison']['periods'] else options['date']['date_from']
            end_forced_options = {
                'date': {
                    'mode': 'range',
                    'date_to': fields.Date.from_string(end_date_to).strftime(DEFAULT_SERVER_DATE_FORMAT),
                    'date_from': fields.Date.from_string(end_date_from).strftime(DEFAULT_SERVER_DATE_FORMAT)
                }
            }
            end_header_element = [{'name': _("End Balance"), 'forced_options': end_forced_options}]
            col_headers_end = [
                end_header_element,
                *options['column_headers'][1:],
            ]
            end_column_group_vals = report._generate_columns_group_vals_recursively(col_headers_end, default_group_vals)
            end_columns, end_column_groups = report._build_columns_from_column_group_vals(end_forced_options, end_column_group_vals)

            # Update options
            options['column_headers'][0] = options['column_headers'][0] + end_header_element

            periodo = {options['column_headers'][0][1]['name']}
            options['column_headers'][0][-1]['name'] = 'Acumulado'

            options['column_groups'].update(end_column_groups)
            options['columns'] = options['columns'] + end_columns
            options['ignore_totals_below_sections'] = True # So that GL does not compute them
        
        elif options['available_variants'][0]['name'] == 'Balancete Periodo':
            # Update options
            options['column_headers'][0] =  options['column_headers'][0]
            options['columns'] = options['columns'] 
            options['ignore_totals_below_sections'] = True # So that GL does not compute them


        report._init_options_order_column(options, previous_options)