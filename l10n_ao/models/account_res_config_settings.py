from odoo import fields, models, api, _


class AOAccountConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    create_partner_account = fields.Boolean(_("Create Chart Account for Partners"), store=True, readonly=False,
                                            related="company_id.create_partner_account",
                                            help=_(
                                                """This will create a Chart of account for client if client bit is marked and/or for supplier"""))

    partner_receivable_code_prefix = fields.Char(_('Partner receivable Account Code Prefix'),
                                                 related="company_id.partner_receivable_code_prefix",
                                                 help=_(
                                                     """This prefix will allow to automatically create the client chart account"""))
    partner_payable_code_prefix = fields.Char(_('Partner payable Account Code Prefix'),
                                              related="company_id.partner_payable_code_prefix",
                                              help=_(
                                                  """This prefix will allow to automatically create the supplier chart account"""))

    fpartner_receivable_code_prefix = fields.Char(_('Foreign Partner receivable Account Code Prefix'),
                                                  related="company_id.fpartner_receivable_code_prefix",
                                                  help=_(
                                                      """This prefix will allow to automatically create the client chart account"""))
    fpartner_payable_code_prefix = fields.Char(_('Foreign Partner payable Account Code Prefix'),
                                               related="company_id.fpartner_payable_code_prefix",
                                               help=_(
                                                   """This prefix will allow to automatically create the supplier chart account"""))

    employee_payslip_code_prefix = fields.Char(_('Employee Payslip Account Code Prefix'),
                                               related="company_id.employee_payslip_code_prefix",
                                               help=_(
                                                   """This prefix will allow to automatically create the Employee PaySlip chart account"""))

    employee_advance_code_prefix = fields.Char(_('Employee Payslip Advance Account Code Prefix'),
                                               related="company_id.employee_advance_code_prefix",
                                               help=_(
                                                   """This prefix will allow to automatically create the Employee Advance chart account"""))
    company_inss_account_code = fields.Char(_('Company INSS account Code'),
                                            related="company_id.company_inss_account_code",
                                            help=_("""This will add to the account the company INSS Number"""))

    # invoice_printing = fields.Selection(related="company_id.invoice_printing", readonly=False)
    #
    # product_company_name = fields.Char(related="company_id.product_company_name", )
    # product_company_website = fields.Char(related="company_id.product_company_website", )
    # product_company_tax_id = fields.Char(related="company_id.product_company_tax_id", )
    # software_validation_number = fields.Char(related="company_id.software_validation_number")
    # product_id = fields.Char(related="company_id.product_id")
    # product_version = fields.Char(related="company_id.product_version")
    # audit_file_version = fields.Char(related="company_id.audit_file_version")
    # country_id = fields.Many2one(related="company_id.country_id")
    # module_l10n_ao_autoinvoice = fields.Boolean("Add support for Auto Invoice")

    @api.model
    def get_values(self):
        res = super(AOAccountConfigSettings, self).get_values()
        return res

    # Override to not set the company with tax_exigibility
    @api.onchange('tax_exigibility')
    def _onchange_tax_exigibility(self):
        res = {}
        tax = self.env['account.tax'].search([
            ('company_id', '=', self.env.company.id), ('tax_exigibility', '=', 'on_payment')
        ], limit=1)
        if not self.tax_exigibility and tax and tax.company_id.country_id and not tax.company_id.country_id.code == "AO":
            self.tax_exigibility = True
            res['warning'] = {
                'title': _('Error!'),
                'message': _('You cannot disable this setting because some of your taxes are cash basis. '
                             'Modify your taxes first before disabling this setting.')
            }
        return res


