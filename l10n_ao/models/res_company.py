from odoo import fields, models,api,_
from odoo.exceptions import ValidationError, UserError

class ResCompanyAo(models.Model):
    _inherit = "res.company"

    inss = fields.Char("INSS", size=12)
    software_id = fields.Char("software ID", readonly=True, default="426/AGT/2023")
    create_partner_account = fields.Boolean(_("Create Chart Account for Partners"), required=False, readonly=False,
                                            help=_(
                                                """This will create a Chart of account for client if client bit is marked and/or for supplier"""))

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

    tax_regime_id = fields.Many2one("account.tax.regime",string="Tax Regime")

    software_validation_number = fields.Char("Software Validation Number", readonly=True, default="###/AGT/2023")
    invoice_page_printing = fields.Selection([('2', "Print Duplicate"), ('3', 'Print Triplicated')], default="2")
    product_company_tax_id = fields.Char("Product Company Tax ID", readonly=True, default="55637485901")

    def write(self, values):
        if values.get("chart_template_id") == self.env.ref('l10n_ao.ao_chart_template').id:
            if self.env.company.country_id.code == "AO" and self.env.company.id >= 1:
                self.env.company._create_partner_sequences()
                values["partner_receivable_code_prefix"] = "31121"
                values["partner_payable_code_prefix"] = "32121"
                values["fpartner_receivable_code_prefix"] = "31122"
                values["fpartner_payable_code_prefix"] = "32122"

        return super(ResCompanyAo, self).write(values)

    def _create_partner_sequences(self):
        """This function creates a no_gap sequence on each companies in self that will ensure
        a unique number is given to all posted account.move in such a way that we can always
        find the previous move of a journal entry.
        """
        for company in self:
            exists = self.env['ir.sequence'].search([("code", '=', f'customer_account_{company.id}')])
            customer_ext = self.env['ir.sequence'].search([("code", '=', f'customer_ext_account_{company.id}')])
            if not exists:
                vals = {
                    'name': f"{company.name} Customer sequence",
                    'code': f'customer_account_{company.id}',
                    'implementation': 'no_gap',
                    'prefix': '',
                    'suffix': '',
                    'padding': 4,
                    'use_date_range': False,
                    'company_id': company.id
                }
                seq = self.env['ir.sequence'].create(vals)
            if not customer_ext:
                    vals = {
                        'name': f"{company.name} Customer Ext sequence",
                        'code': f'customer_ext_account_{company.id}',
                        'implementation': 'no_gap',
                        'prefix': '',
                        'suffix': '',
                        'padding': 4,
                        'use_date_range': False,
                        'company_id': company.id
                    }
                    seq = self.env['ir.sequence'].create(vals)
            exists = self.env['ir.sequence'].search([("code", '=', f'supplier_account_{company.id}')])
            supplier_ext = self.env['ir.sequence'].search([("code", '=', f'supplier_ext_account_{company.id}')])
            if not exists:
                vals = {
                    'name': f"{company.name} Supplier sequence",
                    'code': f'supplier_account_{company.id}',
                    'implementation': 'no_gap',
                    'prefix': '',
                    'suffix': '',
                    'padding': 4,
                    'use_date_range': False,
                    'company_id': company.id
                }
                seq = self.env['ir.sequence'].create(vals)

            if not supplier_ext:
                vals = {
                    'name': f"{company.name} Supplier Ext sequence",
                    'code': f'supplier_ext_account_{company.id}',
                    'implementation': 'no_gap',
                    'prefix': '',
                    'suffix': '',
                    'padding': 4,
                    'use_date_range': False,
                    'company_id': company.id
                }
                seq = self.env['ir.sequence'].create(vals)

            exists = self.env['ir.sequence'].search([("code", '=', f'supplier_immobilized_account_{company.id}')])
            if not exists:
                vals = {
                    'name': f"{company.name} Supplier sequence",
                    'code': f'supplier_immobilized_account_{company.id}',
                    'implementation': 'no_gap',
                    'prefix': '',
                    'suffix': '',
                    'padding': 4,
                    'use_date_range': False,
                    'company_id': company.id
                }
                seq = self.env['ir.sequence'].create(vals)
