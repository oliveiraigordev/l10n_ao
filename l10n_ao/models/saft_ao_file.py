

from odoo import models, fields, api, _
import xmlschema
from . import saft_xsd_file
from odoo.exceptions import ValidationError
def saft_clean_void_values(value, var):
    new_dict = {}
    if hasattr(var, 'items'):
        for k, v in var.copy().items():
            if v == value:
                var.pop(k, None)
            elif isinstance(v, dict):
                new_v = saft_clean_void_values(value, v)
                new_dict[k] = new_v
            elif isinstance(v, list):
                val_list = []
                for d in v:
                    new_v = saft_clean_void_values(value, d)
                    val_list.append(new_v)
                new_dict[k] = val_list
            else:
                new_dict[k] = v

    return new_dict

class L10naoSaftFile(models.Model):
    _name= "saft.register.file"
    _description = "Saft register file"

    name = fields.Char("Name",readonly=True, required=True)
    state = fields.Selection([('draft', 'Draft'), ('valid', 'Valid'), ('not_valid', 'Not Valid'), ('sented', 'Sented')],
                             "State", default="draft")
    user_id = fields.Many2one('res.users', string="User", readonly=True)
    xml_text = fields.Text(string="XML Text", readonly=True)
    date_start = fields.Date(string="Date Start", required=True, readonly=True)
    date_end = fields.Date(string=" Date End", required=True, readonly=True)
    company_id = fields.Many2one("res.company", required=True, string="Company", readonly=True,
                                 default=lambda self: self.env.user.company_id.id)
    fiscal_year = fields.Char("Fiscal Year", required=True, readonly=True)
    product_company_tax_id = fields.Char(string="NIF", size=20, required=True, readonly=True,
                                         help="Identidade Fiscal da Empresa Produtora do Software")
    software_validation_number = fields.Char(string="Software Number", required=True, readonly=True,
                                             help="Número de validação de de software atribuito pela AGT")
    Product_version = fields.Char(string="Product Version", size=30, required=True, readonly=True,
                                  help="Deve ser indicada a versão da aplicação produtora do ficheiro.")
    description_saft = fields.Char(string="Description SAFT", size=255, help="Comentários Adicionais")

    software_id = fields.Char(string="Software Name")

    audit_file_version = fields.Char("Audit File Version", readonly=True, default="1.01_01")

    tax_account_Basis = fields.Selection(string="Document Type",
                                         selection=[('I', 'Contablidade integrada com facturação'),
                                                    ('C', 'Contablidade'),
                                                    ('F', 'Facturação'),
                                                    # ('P', 'Facturação parcial'),
                                                    ('R', 'Recibos'),
                                                    ('S', 'Autofacturação'),
                                                    ('A', 'Aquisição de bens e serviços'),
                                                    ('Q', 'Aquisição de bens e serviços integrada com a facturação')],
                                         help="Tipos de Documentos, na exportação do SAFT", required=True,
                                         readonly=True,
                                         default="I")
    is_valid = fields.Boolean(string="Valid", default="False")
    total_invoiced = fields.Monetary(string="Total Facturado")
    total_refund = fields.Monetary(string="Total Notas de Crédito")
    currency_id = fields.Many2one(related="company_id.currency_id")
    invoice_ids = fields.Many2many("account.move")

    def action_validate(self):
        if self.tax_account_Basis in ["I"]:
            i_xsd_instance = saft_xsd_file.SAFT_FILE_XSD
            i_xsd_f = xmlschema.XMLSchema(i_xsd_instance)
            if i_xsd_f.is_valid(self.xml_text):
                self.is_valid = True
                self.state = "valid"
            else:
                self.is_valid = False
                self.state = "not_valid"
                raise ValidationError(
                    _("Cannot validate the Saft file because of this error \n %s") % i_xsd_f.validate(self.xml_text))
        if self.tax_account_Basis in ["R"]:
            c_xsd_instance = saft_xsd_file.SAFT_FILE_XSD
            c_xsd_f = xmlschema.XMLSchema(c_xsd_instance)
            print(c_xsd_f)
            if c_xsd_f.is_valid(self.xml_text):
                self.is_valid = True
                self.state = "valid"
            else:
                self.is_valid = False
                self.state = "not_valid"
                raise ValidationError(
                    _("you cannot validate the Saft file because of this error %s") % c_xsd_f.validate(self.xml_text))
        if self.tax_account_Basis in ["A"]:
            a_xsd_instance = saft_xsd_file.SAFT_FILE_XSD
            a_xsd_f = xmlschema.XMLSchema(a_xsd_instance)
            print(a_xsd_f)
            if a_xsd_f.is_valid(self.xml_text):
                self.is_valid = True
                self.state = "valid"
            else:
                self.is_valid = False
                self.state = "not_valid"
                raise ValidationError(
                    _("you cannot validate the Saft file because of this error %s") % a_xsd_f.validate(self.xml_text))
        if self.tax_account_Basis in ["F"]:
            f_xsd_instance = saft_xsd_file.SAFT_FILE_XSD
            f_xsd = xmlschema.XMLSchema(f_xsd_instance)
            print(f_xsd)
            if f_xsd.is_valid(self.xml_text):
                self.is_valid = True
                self.state = "valid"
            else:
                self.is_valid = False
                self.state = "not_valid"
                raise ValidationError(
                    _("you cannot validate the Saft file because of this error %s") % f_xsd.validate(self.xml_text))

    def action_download(self):
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/download/saft_ao_file/%s' % (self.id),
            'target': 'new',
        }

    def action_view_saft_invoices(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("account.action_move_out_invoice_type")
        domain =  [
            ('move_type', '=','out_invoice'),
            ('id', 'in', self.invoice_ids.ids)
        ]
        self.total_invoiced = sum(self.env['account.move'].search(domain).mapped("amount_untaxed"))
        action['domain'] = domain
        action['context'] = {'default_move_type': 'out_invoice', 'move_type': 'out_invoice', 'journal_type': 'sale',
                             'search_default_unpaid': 1}
        return action

    def action_view_saft_refund(self):
         self.ensure_one()
         action = self.env["ir.actions.actions"]._for_xml_id("account.action_move_out_refund_type")
         domain =  [
             ('move_type', '=', 'out_refund'),
             ('id', 'in', self.invoice_ids.ids)
         ]
         self.total_refund = sum(self.env['account.move'].search(domain).mapped("amount_untaxed"))
         action['domain'] = domain
         action['context'] = {'default_move_type': 'out_refund', 'move_type': 'out_refund', 'journal_type': 'sale',
                              'search_default_unpaid': 1}
         return action










