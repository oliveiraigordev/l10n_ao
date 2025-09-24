from odoo import models, fields
from odoo.exceptions import UserError
from odoo.tools.date_utils import relativedelta
import xlsxwriter
import tempfile
import base64
from datetime import datetime
from num2words import num2words


class StockMoveExtractReport(models.AbstractModel):
    _name = 'report.l10n_ao_stocks.report_stock_move_extract_xlsx'
    _description = 'Stock Move Extract Report'

    def generate_excel_report(self, data: dict):
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx")
        temp_file.close()
        file_path = temp_file.name

        workbook = xlsxwriter.Workbook(file_path)
        worksheet = workbook.add_worksheet("Extracto de Movimento de Stocks")

        header_format = workbook.add_format({'bold': True, 'bg_color': '#D9EAD3', 'align': 'center', 'border': 1})
        header_date_format = workbook.add_format({'bold': True, 'num_format': 'dd/mm/yyyy', 'border': 1})
        value_format = workbook.add_format({'align': 'left', 'border': 1})
        date_format = workbook.add_format({'num_format': 'dd/mm/yyyy', 'border': 1})
        currency_format = workbook.add_format({'num_format': '#,##0.00', 'border': 1})
        bold_format = workbook.add_format({'bold': True, 'border': 1})

        self._set_column_widths(worksheet)
        self._write_headers(worksheet, header_format, header_date_format, bold_format, data)
        self._write_data(worksheet, value_format, date_format, currency_format, data)

        workbook.close()

        with open(file_path, 'rb') as f:
            file_data = base64.b64encode(f.read())
        return file_data

    def _set_column_widths(self, worksheet):
        worksheet.set_column('A:A', 30)
        worksheet.set_column('B:B', 30)
        worksheet.set_column('C:C', 20)
        worksheet.set_column('D:D', 20)
        worksheet.set_column('E:E', 20)
        worksheet.set_column('F:F', 40)
        worksheet.set_column('G:G', 40)
        worksheet.set_column('H:H', 20)
        worksheet.set_column('I:I', 15)
        worksheet.set_column('J:J', 20)
        worksheet.set_column('K:K', 15)
        worksheet.set_column('L:L', 15)

    def _write_headers(self, worksheet, header_format, header_date_format, bold_format, data):
        headers = [
            "Artigo", "Armazém", "Lote", "Data", "Hora", "Documento", "Entidade",
            "Tipo de Movimento", "Qtd. Doc.", "Unidade", "Qtd. Mov.", "Stock"
        ]
        for col_num, header in enumerate(headers):
            worksheet.write(0, col_num, header, header_format)

    def _write_data(self, worksheet, value_format, date_format, currency_format, data):
        date_start = data.get('start_date')
        date_end = data.get('end_date')
        product_type = data.get('product_type')
        location_ids = data.get('location_ids')
        product_ids = data.get('product_ids')

        if product_ids:
            if isinstance(product_ids[0], (list, tuple)) and len(product_ids[0]) > 2:
                product_list = product_ids[0][2]
            else:
                product_list = product_ids
        else:
            product_list = []
        if location_ids:
            if isinstance(location_ids[0], (list, tuple)) and len(location_ids[0]) > 2:
                location_list = location_ids[0][2]
            else:
                location_list = location_ids
        else:
            location_list = []

        if product_ids and not location_ids:
            moves = self.env['stock.move.line'].search([
                ('product_id', 'in', product_list),
                ('date', '>=', date_start),
                ('date', '<=', date_end),
                ('state', '=', 'done')
            ], order='date asc')
        
        elif location_ids and not product_ids:
            moves = self.env['stock.move.line'].search([
                ('location_id', 'in', location_list),
                ('date', '>=', date_start),
                ('date', '<=', date_end),
                ('state', '=', 'done')
            ], order='date asc')

        elif location_ids and product_ids:
            moves = self.env['stock.move.line'].search([
                ('product_id', 'in', product_list),
                ('location_id', 'in', location_list),
                ('date', '>=', date_start),
                ('date', '<=', date_end),
                ('state', '=', 'done')
            ], order='date asc')

        else:
            moves = self.env['stock.move.line'].search([
                ('product_id.detailed_type', '=', product_type),
                ('date', '>=', date_start),
                ('date', '<=', date_end),
                ('state', '=', 'done')
            ], order='date asc')

        if not moves:
            raise UserError("Nenhum movimento de stock encontrado para o intervalo de datas seleccionado.")
        
        row = 1

        for move in moves:
            worksheet.write(row, 0, move.product_id.name, value_format)
            worksheet.write(row, 1, move.location_id.name, value_format)
            worksheet.write(row, 2, move.lot_id.name if move.lot_id else '', value_format)
            worksheet.write(row, 3, move.date.strftime('%d/%m/%Y'), date_format)
            worksheet.write(row, 4, move.date.strftime('%H:%M:%S'), value_format)
            worksheet.write(row, 5, move.reference or '', value_format)
            worksheet.write(row, 6, move.picking_partner_id.name if move.picking_partner_id else '', value_format)
            worksheet.write(row, 7, move.picking_type_id.name if move.picking_type_id else '', value_format)
            worksheet.write(row, 8, move.qty_done, value_format)
            worksheet.write(row, 9, move.product_uom_id.name if move.product_uom_id else '', value_format)
            worksheet.write(row, 10, move.qty_done or 0.0, value_format)
            worksheet.write(row, 11, sum(move.product_stock_quant_ids.mapped('quantity')) if move.product_stock_quant_ids else '', currency_format)

            row += 1
