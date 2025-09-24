from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from dicttoxml2 import dicttoxml
from xml.dom.minidom import parseString
import datetime
from odoo.exceptions import ValidationError, UserError


class SaftAOWizard(models.TransientModel):
    _name = "angola.saft.wizard"

    _description = "Wizard para a exportação do ficheiro SAFT de Angola"

    @api.model
    def _default_company(self):
        return self.env.company.id

    @api.model
    def _get_first_day(self):
        end_date = datetime.datetime.now().replace(day=1) - datetime.timedelta(days=1)
        date_start = datetime.datetime.now().replace(day=1) - datetime.timedelta(days=end_date.day)
        return date_start

    company_id = fields.Many2one(comodel_name="res.company", string="Empresa", required=True,
                                 default=_default_company, )
    tax_accounting_basis = fields.Selection(string="TYPE OF SAFT FILE",
                                            selection=[('I', 'Contablidade integrada com a facturação'),
                                                       ('C', 'Contabilidade'),
                                                       ('F', 'Facturação'),
                                                       # ('P', 'Facturação Parcial'),
                                                       ('R', 'Recibos'),
                                                       # ('S', 'Auto-Facturação'), # adicionar este elemento ao módulo l10n_ao_autoinvoice
                                                       ('A', 'Aquisição de bens e serviços'),
                                                       (
                                                           'Q',
                                                           'Aquisição de bens e serviços integrada com a facturação')],
                                            help="Tipo de ficheiro")

    date_end = fields.Date("Date End", default=datetime.datetime.now().replace(day=1) - datetime.timedelta(days=1))
    date_start = fields.Date("Date Start", default=_get_first_day)
    description_saft = fields.Char("Description")

    def get_pos_saft(self, invoice_saft):
        return invoice_saft

    def get_pos_partners(self):
        return self.env["res.partner"]

    def get_pos_products(self):
        return self.env['product.product']

    def get_pos_taxes(self):
        return self.env['account.tax']

    def helper_funct(self, parent):
        if parent == "GeneralLedgerAccounts":
            return "Account"
        if parent == "Product":
            return "Product"  # { 'name': parent, 'should_fold': False }
        if parent == "Supplier":
            return "Supplier"
        if parent == "TaxTable":
            return "TaxTable"

    def generate_saft_file_xml(self):
        if not self.company_id.vat:
            raise ValidationError(_("Cannot Generate SAFT data without Company NIF!"))
        if not self.company_id.company_registry:
            raise ValidationError(_("Cannot Generate SAFT data without Company Registry!"))

        header = {
            "AuditFileVersion": "1.01_01",  # self.company_id.audit_file_version,
            "CompanyID": str(self.company_id.company_registry)[0:49] if self.company_id.company_registry else " ",
            "TaxRegistrationNumber": self.company_id.vat if self.company_id.vat else "",
            "TaxAccountingBasis": self.tax_accounting_basis,
            "CompanyName": self.company_id.name,
            "BusinessName": self.company_id.partner_id.industry_id.name if self.company_id.partner_id.industry_id.name
            else self.company_id.name[0:59],
            "CompanyAddress": {
                # "BuildingNumber": "","
                "StreetName": self.company_id.partner_id.street if self.company_id.partner_id.street else "",
                "AddressDetail": str(self.company_id.partner_id.contact_address)[0:80],
                "City": self.company_id.partner_id.city,
                "PostalCode": self.company_id.partner_id.zip if self.company_id.partner_id.zip else "",
                "Province": self.company_id.partner_id.state_id.name if self.company_id.partner_id.state_id.name else "Desconhecido",
                "Country": str(self.company_id.partner_id.country_id.code)[
                           0:2] if self.company_id.partner_id.country_id.code else "Desconhecido"
            },
            "FiscalYear": int(fields.Date.to_string(self.date_start)[0:4]),
            "StartDate": fields.Date.to_string(self.date_start),
            "EndDate": fields.Date.to_string(self.date_end),
            "CurrencyCode": self.company_id.currency_id.name,
            "DateCreated": fields.Date.to_string(fields.Date.today()),
            "TaxEntity": "Global",
            "ProductCompanyTaxID": "50089546358",
            # self.company_id.product_company_tax_id, TODO: DEVO PREENCHER DEPOIS COM O VALOR REAL
            "SoftwareValidationNumber": self.company_id.software_id,
            # self.company_id.software_validation_number, TODO: DEVO PREENCHER DEPOIS COM O VALOR REAL
            "ProductID": "Odoo Angola Localização/Tistech, LDA",
            # self.company_id.software_id, TODO: DEVO PREENCHER DEPOIS COM O VALOR REAL
            "ProductVersion": "16.0",  # self.company_id.product_version,
            "HeaderComment": self.description_saft,
            "Telephone": self.company_id.phone and self.company_id.phone[0:19] or '',
            # "Fax": "",
            "Email": self.company_id.email,
            "Website": self.company_id.website if self.company_id.website else "Desconhecido",
        }

        saft_dict = {
            "Header": header,
            "MasterFiles": "",
            "GeneralLedgerEntries": "",
            "SourceDocuments": "",
        }

        master_files = {
            "GeneralLedgerAccounts": "",
            "Customer": "",
            "Supplier": "",
            "Product": "",
            "TaxTable": "",
        }

        source_documents = {

            "SalesInvoices": "",
            "MovementOfGoods": "",
            "WorkingDocuments": "",
            "Payments": "",
            "PurchaseInvoices": "",
        }

        partners = self.env["res.partner"]
        suppliers = self.env["res.partner"]
        taxes = self.env["account.tax"]
        journals = self.env["account.journal"]
        products = self.env["product.product"]

        invoices = self.env["account.move"].search(
            [("invoice_date", ">=", fields.Date.to_string(self.date_start)),
             ("invoice_date", "<=", fields.Date.to_string(self.date_end)),
             ("system_entry_date", "!=", None),
             ("state", "in", ["posted","cancel"])], order="system_entry_date asc")

        if self.tax_accounting_basis in ["A"]:
            invoices = invoices.filtered(lambda r: r.move_type == "in_invoice")
            partners |= invoices.mapped("partner_id")
            taxes |= invoices.invoice_line_ids.mapped("tax_ids")
            master_files["Supplier"] = partners.get_saft_data().get("Supplier")
            master_files["TaxTable"] = taxes.get_saft_data().get("TaxTable")
            source_documents["PurchaseInvoices"] = invoices.get_supplier_saft_data().get("PurchaseInvoices")
            saft_dict['SourceDocuments'] = source_documents
            [source_documents.pop(keys) for keys in
             ["SalesInvoices", "Payments", "MovementOfGoods", "WorkingDocuments"]]
            master_files.pop("Customer")
            master_files.pop("Product")
            master_files.pop("GeneralLedgerAccounts")
            saft_dict.pop("GeneralLedgerEntries")

        if self.tax_accounting_basis in ["F"]:
            invoices = invoices.filtered(lambda r: r.move_type in ["out_invoice", "out_refund"])
            partners |= invoices.mapped("partner_id")
            partners |= self.get_pos_partners() if self.get_pos_partners() != None else self.env['res.partner']
            taxes |= invoices.invoice_line_ids.tax_ids.filtered(
                lambda r: r.tax_type in ['IVA', 'IS', 'NS'] and r.is_withholding == False)
            taxes |= self.get_pos_taxes() if self.get_pos_taxes() != None else self.env['account.tax']
            products |= invoices.invoice_line_ids.mapped("product_id")
            products |= self.get_pos_products() if self.get_pos_products() != None else self.env['product.product']
            master_files["TaxTable"] = taxes.get_saft_data().get("TaxTable")
            master_files["Product"] = products.get_saft_data().get("Product")
            source_documents["SalesInvoices"] = invoices.get_saft_data().get("SalesInvoices")
            source_documents["SalesInvoices"] = self.get_pos_saft(source_documents["SalesInvoices"])
            saft_dict.pop("GeneralLedgerEntries")
            if source_documents["SalesInvoices"]["NumberOfEntries"] == 0:
                raise ValidationError("Não Existem Facturas Emitidas para este periodo")
            saft_dict['SourceDocuments'] = source_documents
            [master_files.pop(keys) for keys in ["Supplier", "GeneralLedgerAccounts"]]
            [source_documents.pop(keys) for keys in
             ["PurchaseInvoices", "Payments", "MovementOfGoods", "WorkingDocuments"]]
            master_files["Customer"] = [{'CustomerID': '01', 'AccountID': '31.1.2.1', 'CustomerTaxID': '999999999',
                                         'CompanyName': 'CONSUMIRDOR FINAL',
                                         'BillingAddress': {'StreetName': 'Desconhecido',
                                                            'AddressDetail': 'Desconhecido', 'City': 'Luanda',
                                                            'PostalCode': 'Desconhecido', 'Province': 'Desconhecido',
                                                            'Country': 'AO'},
                                         'ShipToAddress': {'StreetName': 'Desconhecido',
                                                           'AddressDetail': 'Desconhecido', 'City': 'Luanda',
                                                           'PostalCode': 'Desconhecido', 'Province': 'Desconhecido',
                                                           'Country': 'AO'}, 'Telephone': '000000000',
                                         'Email': 'Desconhecido', 'Website': 'Desconhecido',
                                         'SelfBillingIndicator': '0'}]
            master_files["Customer"].extend(partners.filtered(lambda p: p.vat and '999999999' not in p.vat).get_saft_data().get("Customer"))

        if self.tax_accounting_basis in ["R"]:
           payments = self.env["account.payment"].search([('date','>=',self.date_start),('date','<=',self.date_end),
             ("state", "in", ["posted"])])
           taxes |= payments.reconciled_invoice_ids.mapped("tax_ids")
           partners |= payments.mapped("partner_id")
           master_files["TaxTable"] = taxes.get_saft_data().get("TaxTable")
           master_files["Customer"] = taxes.get_saft_data().get("Customer")
           source_documents["Payments"] = payments.get_saft_data().get("Payment")
           [master_files.pop(keys) for keys in ["GeneralLedgerAccounts", "Supplier", "Product"]]
           [saft_dict.pop(keys) for keys in ["GeneralLedgerEntries"]]
           [source_documents.pop(keys) for keys in
             ["SalesInvoices", "PurchaseInvoices", "MovementOfGoods", "WorkingDocuments"]]

        saft_dict["MasterFiles"] = master_files
        saft_xml = dicttoxml(saft_dict, custom_root='AuditFile', attr_type=False, item_func=self.helper_funct,
                             fold_list=False)
        dom = str(saft_xml, 'utf-8')
        dom = parseString(dom).toprettyxml()

        saft_file_data = {

            "name": "SAFT_AO_%s_%s_PERIOD_%s-%s" % (
            fields.Date.to_string(self.date_start)[0:4], self.tax_accounting_basis,
            fields.Date.to_string(self.date_start)[5:7],
            fields.Date.to_string(self.date_end)[5:7]),
            "audit_file_version": "1.01_01",
            "tax_account_Basis": self.tax_accounting_basis,
            "company_id": self.company_id.id,
            "fiscal_year": int(fields.Date.to_string(fields.Date.today())[0:4]),
            "date_start": fields.Date.to_string(self.date_start),
            "date_end": fields.Date.to_string(self.date_end),
            "invoice_ids": [(6, 1, invoices.ids)],
            "product_company_tax_id": "50089546358",
            # self.company_id.product_company_tax_id,  TODO: DEPOIS DEVO DESCOMENTAR O CAMPO E PREENCHER COM REAL VALOR
            "software_validation_number": self.company_id.software_id,
            # self.company_id.software_validation_number, TODO: DEPOIS DEVO DESCOMENTAR O CAMPO E PREENCHER COM REAL VALOR
            "software_id": self.company_id.software_id,
            "Product_version": '16.0',
            "description_saft": self.description_saft,
            "xml_text": dom.replace("–", "-").replace("<AuditFile>",
                                                      '<AuditFile xmlns:ns="urn:OECD:StandardAuditFile-Tax:AO_1.01_01" xmlns="urn:OECD:StandardAuditFile-Tax:AO_1.01_01">').replace(
                '<?xml version="1.0" ?>', '<?xml version="1.0" encoding="UTF-8" ?>'),
            "user_id": self.env.user.id,
        }

        saft_file = self.env["saft.register.file"].create(saft_file_data)
        action = self.sudo().env.ref('l10n_ao.l10nao_saft_register_file_action').read()[0]
        action['views'] = [(self.env.ref('l10n_ao.saft_register_file_view').id, 'form')]
        action['res_id'] = saft_file.id
        return action
