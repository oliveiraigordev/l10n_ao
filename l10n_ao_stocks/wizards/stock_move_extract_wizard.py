from odoo import models, fields, api
from odoo.exceptions import UserError


class StockMoveExtractWizard(models.TransientModel):
    _name = 'stock.move.extract.wizard'
    _description = 'Wizard de Extracto de Movimento de Stock'

    start_date = fields.Date(string='Data de Início', required=True)
    end_date = fields.Date(string='Data de Fim', required=True)
    product_type = fields.Selection(
        selection=[('consu', 'Consumível'), ('product', 'Armazenável')],
        string='Tipo de Artigo',
        default=False,
        required=True
    )
    file_data = fields.Binary("Arquivo", readonly=True, attachment=False)
    file_name = fields.Char("Nome do Arquivo", readonly=True)
    product_ids = fields.Many2many(
        comodel_name='product.product',
        string='Produtos',
        domain="[('detailed_type', '=', product_type)]"
    )
    location_ids = fields.Many2many(
        comodel_name='stock.location',
        string='Localizações',
    )


    @api.constrains('start_date', 'end_date')
    def _check_dates(self):
        if self.start_date > self.end_date:
            raise ValueError("A data de início não pode ser posterior à data de fim.")

    def print_report_xlsx(self):
        data = self.read()[0]
        file_content = self.env['report.l10n_ao_stocks.report_stock_move_extract_xlsx'].generate_excel_report(data)
        self.file_data = file_content
        self.file_name = "extracto_de_movimento_de_stock.xlsx"

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

    def action_download_report(self):
        if not self.file_data:
            raise UserError("Nenhum arquivo para download encontrado.")
        return {
            'type': 'ir.actions.act_url',
            'url': f"/web/content/{self._name}/{self.id}/file_data/{self.file_name}",
            'target': 'self',
        }
