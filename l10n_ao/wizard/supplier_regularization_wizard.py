from odoo import models, fields, api
from datetime import date, timedelta
from odoo.exceptions import UserError


class SupplierRegularizationAttachmentAo(models.TransientModel):
    _name = "supplier.reg.attachment.ao"
    _description = "Anexo de Fornecedores "

    month = fields.Selection(
        [
            ("1", "Janeiro"),
            ("2", "Fevereiro"),
            ("3", "Março"),
            ("4", "Abril"),
            ("5", "Maio"),
            ("6", "Junho"),
            ("7", "Julho"),
            ("8", "Agosto"),
            ("9", "Setembro"),
            ("10", "Outubro"),
            ("11", "Novembro"),
            ("12", "Dezembro"),
        ],
        string="Mês",
    )
    year = fields.Integer(string="Ano")

    url_download = fields.Char("URL Download")
    
    @api.model
    def default_get(self, fields_list):
        res = super(SupplierRegularizationAttachmentAo, self).default_get(fields_list)
        today = fields.Date.today()
        year = today.year
        month = today.month - 1
        if month == 0:
            month = 12
            year -= 1
        res.update({"month": str(month), "year": year})
        return res



    def print_report(self):
        data = {
            'form_data' : self.read()[0]
        }
        return self.env.ref("l10n_ao.report_action_supplier_reg_attachment").report_action(
           self,  data = data
        )
    
    def print_report_xlsx(self):
        report_file = 'xlsx'
        data = {
            'form_data': self.read([])[0]
            }
        self.url_download = self.env[
            'report.supplier.reg.attachment.xlsx'
            ]._get_supplier_reg_attch_report_values(self, report_file, data=data)
        return {
            'context': self.env.context,
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': self._name,
            'res_id': self.id,
            'view_id': False,
            'type': 'ir.actions.act_window',
            'target': 'new',
        }
    
    def action_reg_supplier_xlsx_file(self):
        return self.download_salary_file(self.url_download)

    def download_salary_file(self, url_download):
        self.url_download = False
        return {"type": "ir.actions.act_url", "url": url_download, "target": "new"}
