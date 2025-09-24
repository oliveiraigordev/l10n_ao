from odoo import fields, models, api, _


class AccountChartTemplateAngola(models.Model):
    _inherit = 'account.chart.template'

    partner_receivable_code_prefix = fields.Char(_('Partner receivable Account Code Prefix'), size=64, required=False,
                                                 help=_(
                                                     """This prefix will allow to automatically create the client chart account"""))
    partner_payable_code_prefix = fields.Char(_('Partner payable Account Code Prefix'), size=64, required=False,
                                              help=_(
                                                  """This prefix will allow to automatically create the supplier chart account"""))

    fpartner_receivable_code_prefix = fields.Char(_('Foreign Partner receivable Account Code Prefix'), size=64,
                                                  required=False,
                                                  help=_(
                                                      """This prefix will allow to automatically create the client chart account"""))
    fpartner_payable_code_prefix = fields.Char(_('Foreign Partner payable Account Code Prefix'), size=64,
                                               required=False,
                                               help=_(
                                                   """This prefix will allow to automatically create the supplier chart account"""))

    employee_payslip_code_prefix = fields.Char(_('Employee Payslip Account Code Prefix'), size=64, required=False,
                                               help=_(
                                                   """This prefix will allow to automatically create the Employee PaySlip chart account"""))

    employee_advance_code_prefix = fields.Char(_('Employee Payslip Advance Account Code Prefix'), size=64,
                                               required=False,
                                               help=_(
                                                   """This prefix will allow to automatically create the Employee Advance chart account"""))
    company_inss_account_code = fields.Char(_('Company INSS account Code'), size=64, required=False,
                                            help=_("""This will add to the account the company INSS Number"""))
    employee_inss_account_code = fields.Char(_('Employee INSS account Code'), size=64, required=False,
                                             help=_("""This will add to the account the Employee INSS Number"""))
    company_inss_account_code = fields.Char(_('Company INSS account Code'), size=64, required=False,
                                            help=_("""This will add to the account the company INSS Number"""))

    tax_withhold_journal_id = fields.Many2one('account.journal', _("Tax Withhold Journal"), required=False)

    property_account_income_credit_id = fields.Many2one('account.account.template',
                                                        _('Category of Income Credit Account'))

    property_account_expense_credit_id = fields.Many2one('account.account.template',
                                                         _('Category of Expense Credit Account'))

    tax_cash_basis_account_id = fields.Many2one('account.account.template',
                                                _('Account Id for Tax Cash Basis'))

    # Override the journal creation codes for default
    @api.model
    def generate_journals(self, acc_template_ref, company, journals_dict=None):
        """
   #     This method is used for creating journals.
   #
   #     :param chart_temp_id: Chart Template Id.
   #     :param acc_template_ref: Account templates reference.
   #     :param company_id: company_id selected from wizards.multi.charts.accounts.
   #     :returns: True
   #     """
        JournalObj = self.env['account.journal']
        for vals_journal in self._prepare_all_journals(acc_template_ref, company, journals_dict=journals_dict):
            journal = JournalObj.create(vals_journal)
            if vals_journal['type'] == 'general' and vals_journal['code'] == _('CAMB'):
                company.write({'currency_exchange_journal_id': journal.id})
            if vals_journal['type'] == 'general' and vals_journal['code'] == _('TAX'):
                company.write({'tax_cash_basis_journal_id': journal.id})
        return True

        # Override the journal creation codes for default

    def _prepare_all_journals(self, acc_template_ref, company, journals_dict=None):
        def _get_default_account(journal_vals, type='debit'):
            # Get the default accounts
            default_account = False
            if journal['type'] == 'sale':
                default_account = acc_template_ref.get(self.property_account_income_categ_id).id
            elif journal['type'] == 'purchase':
                default_account = acc_template_ref.get(self.property_account_expense_categ_id).id

            return default_account

        #
        journals = [{'name': _('Customer Invoices'), 'type': 'sale', 'code': _('FT'),'document_type':'FT', 'favorite': True, 'sequence': 5,'refund_sequence': True, 'restrict_mode_hash_table': True},
                    {'name': _('Vendor Bills'), 'type': 'purchase', 'code': _('FTF'),'document_type':'FTF', 'favorite': True, 'sequence': 6,'refund_sequence': True, 'restrict_mode_hash_table': True},
                    {'name': _('Miscellaneous Operations'), 'type': 'general', 'code': _('DIV'), 'favorite': False,
                     'sequence': 7},
                    {'name': _('Exchange Difference'), 'type': 'general', 'code': _('CAMB'), 'favorite': False,
                     'sequence': 9},
                    {'name': _('Tax Cash Basis'), 'type': 'general', 'code': _('TAX'), 'favorite': False,
                     'sequence': 10}
                    ]
        if journals_dict != None:
            journals.extend(journals_dict)

        self.ensure_one()
        journal_data = []
        for journal in journals:
            vals = {
                'type': journal['type'],
                'name': journal['name'],
                'code': journal['code'],
                'company_id': company.id,
                'default_account_id': _get_default_account(journal, 'credit'),
                'show_on_dashboard': journal['favorite'],
            }

            if journal['type'] in ['sale', 'purchase'] and company.country_id.code == "AO":
                journal['refund_sequence'] = True
                journal['restrict_mode_hash_table'] = True
            journal_data.append(vals)

        return journal_data
