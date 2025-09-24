from collections import defaultdict
import json
from odoo.tools import format_date
from odoo import models, fields, api, _, osv

class JournalReportAo(models.AbstractModel):
    _name = 'account.journal.report.ao'
    _inherit = 'account.journal.report.handler'
    _description = 'Journal Report Custom Ao'

    acc_code = fields.Char(string="Account Code")

    def _get_first_move_line(self, options, parent_key, line_key, values, is_unreconciled_payment):
 
        report = self.env['account.report']
        columns = []
        for column_group_key, column_group_options in report._split_options_per_column_group(options).items():
            values = values[column_group_key]
            balance = False if column_group_options.get('show_payment_lines') and is_unreconciled_payment else values.get('cumulated_balance')
            not_receivable_with_partner = values['partner_name'] and values['account_type'] not in ('asset_receivable', 'liability_payable')
            columns.extend([
                {'name': values['journal_id'], 'class': 'o_account_report_line_ellipsis', 'style': 'text-align:left;min-width: 120px !important;max-width: 120px !important;'},
                {'name': "", 'class': 'o_account_report_line_ellipsis', 'style': 'text-align:left;min-width: 120px !important;max-width: 120px !important;'},
                {'name': '%s %s' % (values['account_code'], '' if values['partner_name'] else values['account_name']), 'name_right': values['partner_name'], 'class': 'o_account_report_line_ellipsis' + (' color-blue' if not_receivable_with_partner else ''), 'template': 'account_reports.cell_template_journal_audit_report', 'style': 'text-align:left;min-width: 120px !important;max-width: 120px !important;'},
                {'name': report.format_value(values['debit'], figure_type='monetary'), 'no_format': values['debit'], 'class': 'number'},
                {'name': report.format_value(values['credit'], figure_type='monetary'), 'no_format': values['credit'], 'class': 'number'},
            ] + self._get_move_line_additional_col(column_group_options, balance, values, is_unreconciled_payment))

        return {
            'id': line_key,
            'name': values['date'],
            'level': 3,
            'columns': columns,
            'parent_id': parent_key,
            'move_id': values['move_id'],
            'class': 'o_account_reports_ja_move_line',
        }
    

    def _get_aml_line(self, options, parent_key, eval_dict, line_index, journal, is_unreconciled_payment):

        report = self.env['account.report']
        columns = []
        general_vals = next(col_group_val for col_group_val in eval_dict.values())
        journal_obj = self.env['account.move.line'].search([('journal_id', '=', journal.id)])

        tax_account_nmbr = ""
        for j in journal_obj:
            if j['tax_ids']:
                tax_account_nmbr = j['product_id']['product_tmpl_id']['property_account_income_id']['code']

        if general_vals['journal_type'] == 'bank' and general_vals['account_type'] in ('liability_credit_card', 'asset_cash'):
            # Do not display bank account lines for bank journals
            return None
        
        for column_group_key, column_group_options in report._split_options_per_column_group(options).items():
            values = eval_dict[column_group_key]
            if values['journal_type'] == 'bank':  # For additional lines still showing in the bank journal, make sure to use the partner on the account if available.
                not_receivable_with_partner = values['partner_name'] and values['account_type'] not in ('asset_receivable', 'liability_payable')
                account_name = '%s %s' % (values['account_code'], '' if values['partner_name'] else values['account_name'])
                account_name_col = {'name': account_name, 'class': 'o_account_report_line_ellipsis' + (' color-blue' if not_receivable_with_partner else ''), 'name_right': values.get('partner_name'), 'style': 'text-align:left;min-width: 120px !important;max-width: 120px !important;', 'template': 'account_reports.cell_template_journal_audit_report'}
            else:
                account_name = '%s %s' % (values['account_code'], values['account_name'])
                account_name_col = {'name': account_name, 'class': 'o_account_report_line_ellipsis', 'style': 'text-align:left;min-width: 120px !important;max-width: 120px !important;'}

            balance = False if column_group_options.get('show_payment_lines') and is_unreconciled_payment else values.get('cumulated_balance')
            
            if not values['taxes']:
                values['account_code'] = tax_account_nmbr
            else:
                values['account_code'] = ""
                
            columns.extend([
               {'name': "", 'class': 'o_account_report_line_ellipsis', 'style': 'text-align:left;min-width: 120px !important;max-width: 120px !important;'},
               {'name': values['name'], 'class': 'o_account_report_line_ellipsis', 'style': 'text-align:left;min-width: 120px !important;max-width: 120px !important;'},
               account_name_col,
               {'name': report.format_value(values['debit'], figure_type='monetary'), 'no_format': values['debit'], 'class': 'number'},
               {'name': report.format_value(values['credit'], figure_type='monetary'), 'no_format': values['credit'], 'class': 'number'},
               {'name': 'AML', 'class': 'o_account_report_line_ellipsis', 'style': 'text-align:left;min-width: 120px !important;max-width: 120px !important;'},
               {'name': values['journal_code'], 'class': 'o_account_report_line_ellipsis', 'style': 'text-align:left;min-width: 120px !important;max-width: 120px !important;'},
               {'name':  values['account_code'], 'class': 'o_account_report_line_ellipsis', 'style': 'text-align:left;min-width: 120px !important;max-width: 120px !important;'},
            ] )
            # + self._get_move_line_additional_col(column_group_options, balance, values, is_unreconciled_payment)
        
            
        return {
            'id': report._get_generic_line_id('account.move.line', values['move_line_id'], parent_line_id=parent_key),
            'name': self._get_aml_line_name(options, journal, line_index, eval_dict, is_unreconciled_payment),
            'level': 3,
            'parent_id': parent_key,
            'columns': columns,
            'class': 'o_account_reports_ja_name_muted',
        }

    def _get_columns_line(self, options, parent_key, journal_type):

        columns = []
        has_multicurrency = self.user_has_groups('base.group_multi_currency')
        for dummy in options['column_groups']:
            columns.extend([
                {'name': _('Data'), 'class': 'o_account_report_line_ellipsis', 'style': 'text-align: left;min-width: 120px !important;max-width: 120px !important;'},
                {'name': _('N.º Diário'), 'class': 'o_account_report_line_ellipsis', 'style': 'text-align: left;min-width: 120px !important;max-width: 120px !important;'},
                {'name': _('Label'), 'class': 'o_account_report_line_ellipsis', 'style': 'text-align: left;min-width: 120px !important;max-width: 120px !important;'},
                {'name': _('Account'), 'class': 'o_account_report_line_ellipsis', 'style': 'text-align: left;min-width: 120px !important;max-width: 120px !important;'},
                {'name': _('Debit'), 'class': 'number'},
                {'name': _('Credit'), 'class': 'number'},
                {'name': _('Doc.'), 'class': 'o_account_report_line_ellipsis', 'style': 'text-align: left;min-width: 120px !important;max-width: 120px !important;'},
                {'name': _('N.º Doc.'), 'class': 'o_account_report_line_ellipsis', 'style': 'text-align: left;min-width: 120px !important;max-width: 120px !important;'},
                {'name': _('Conta Origem'), 'class': 'o_account_report_line_ellipsis', 'style': 'text-align: left;min-width: 120px !important;max-width: 120px !important;'},
            ])
            if journal_type in ['sale', 'purchase']:
                continue
                columns.extend([
                    {'name': _('Taxes'), 'class': 'text-start'},
                    {'name': _('Tax Grids')},
                ])
            elif journal_type == 'bank':
                columns.extend([
                    {'name': _('Balance'), 'class': 'number'},
                    {'name': ''} if not has_multicurrency else {'name': _('Amount In Currency'), 'class': 'text-end number'},
                ])
            else:
                columns.extend([
                    {'name': ''},
                    {'name': ''},
                ])

        return {
            'id': self.env['account.report']._get_generic_line_id(None, None, parent_line_id=parent_key, markup='headers'),
            'name': columns[0]['name'],
            'columns': columns[1:],
            'level': 3,
            'parent_id': parent_key,
            'class': 'o_account_reports_ja_header_line',
        }