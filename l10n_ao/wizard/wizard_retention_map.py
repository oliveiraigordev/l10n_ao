from datetime import date, timedelta

from odoo import models, fields, api
from odoo.tools import float_is_zero
from odoo.exceptions import UserError


class WizardRetentionMap(models.TransientModel):
    _name = "wizard.retention.map"
    _description = "Wizard Retention Map"

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
        res = super(WizardRetentionMap, self).default_get(fields_list)
        today = fields.Date.today()
        year = today.year
        month = today.month - 1
        if month == 0:
            month = 12
            year -= 1
        res.update({"month": str(month), "year": year})
        return res

    def print_report(self):
        start_date = date(self.year, int(self.month), 1)
        if int(self.month) == 12:
            end_date = date(self.year, int(self.month), 31)
        else:
            end_date = date(self.year, int(self.month) + 1, 1) + timedelta(days=-1)

        move_ids = self.env["account.move"].search(
            [
                ("move_type", "=", "out_invoice"),
                ("state", "=", "posted"),
                ("invoice_date", ">=", start_date),
                ("invoice_date", "<=", end_date),
                ('company_id', '=', self.env.company.id),
            ]
        )
        move_ids = move_ids.filtered(
            lambda x: float_is_zero(
                x.amount_residual, precision_digits=x.currency_id.rounding
            )
                      and any(tax.is_withholding for tax in x.mapped("invoice_line_ids.tax_ids"))
                      or x.late_wth_amount
        )

        if not move_ids:
            raise UserError(
                "Não foi encontrada nenhuma fatura paga com "
                "retenção para o período selecionado!"
            )
        return self.env.ref("l10n_ao.report_action_retention_map").report_action(
            move_ids
        )

    def print_report_xlsx(self):
        report_file = 'xlsx'
        data = {
            'form_data': self.read([])[0]
            }
        self.url_download = self.env[
            'report.retention.map.xlsx'
            ]._get_retention_map_report_values(self, report_file, data=data)
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
    
    def action_download_retention_map_file(self):
        return self.retention_map_file(self.url_download)

    def retention_map_file(self, url_download):
        self.url_download = False
        return {"type": "ir.actions.act_url", "url": url_download, "target": "new"}

    
