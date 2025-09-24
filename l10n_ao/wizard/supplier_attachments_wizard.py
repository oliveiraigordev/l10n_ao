from odoo import models, fields, api
from datetime import date, timedelta
from odoo.exceptions import UserError


class SupplierAttachmentAo(models.TransientModel):
    _name = "supplier.attachment.ao"
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
        res = super(SupplierAttachmentAo, self).default_get(fields_list)
        today = fields.Date.today()
        year = today.year
        month = today.month - 1
        if month == 0:
            month = 12
            year -= 1
        res.update({"month": str(month), "year": year})
        return res



    def print_report(self):

        # start_date = date(self.year, int(self.month), 1)
        # if int(self.month) == 12:
        #     end_date = date(self.year, int(self.month), 31)
        # else:
        #     end_date = date(self.year, int(self.month) + 1, 1) + timedelta(days=-1)
        # move_ids = self.env["account.move"].search(
        #     [
        #         ("move_type", "=", "in_invoice"),
        #         ("state", "=", "posted"),
        #         ("invoice_date", ">=", start_date),
        #         ("invoice_date", "<=", end_date),
        #     ]
        # )
        # if not move_ids:
        #     raise UserError(
        #         "Não foi encontrada nenhuma fatura para o período selecionado!"
        #     )

        data = {
            'form_data' : self.read()[0]
        }
        return self.env.ref("l10n_ao.report_action_supplier_attachment").report_action(
           self,  data = data
        )
    
    def print_report_xlsx(self):
        report_file = 'xlsx'
        data = {
            'form_data': self.read([])[0]
            }
        self.url_download = self.env[
            'report.supplier.xlsx'
            ]._get_supplier_report_values(self, report_file, data=data)
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
    
    def action_download_supplier_attachment_file(self):
        return self.download_supplier_attachment_file(self.url_download)

    def download_supplier_attachment_file(self, url_download):
        self.url_download = False
        return {"type": "ir.actions.act_url", "url": url_download, "target": "new"}
