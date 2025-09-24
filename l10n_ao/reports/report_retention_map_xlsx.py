# -*- coding: utf-8 -*-
from datetime import date, timedelta
from odoo import api, models, fields, _
from dateutil.parser import parse
from odoo.exceptions import ValidationError, UserError
from xml.dom.minidom import parseString
from dicttoxml2 import dicttoxml
import base64, os, tempfile
import xlsxwriter
from odoo.tools import float_is_zero


class ReportRetentionMap(models.AbstractModel):
    _name = 'report.retention.map.xlsx'
    _description = 'Mapa de Retenção'

    def get_docs_values(self, data):
        
        month = data['form_data']['month']
        year = data['form_data']['year']

        start_date = date(data['form_data']['year'],
                          int(data['form_data']['month']), 1)
        if int(data['form_data']['month']) == 12:
            end_date = date(data['form_data']['year'],
                            int(data['form_data']['month']), 31)
        else:
            end_date = date(data['form_data']['year'], int(
                data['form_data']['month']) + 1, 1) + timedelta(days=-1)

        if type(month) is str:
            period_month = parse(month)
        if type(year) is str:
            period_year = parse(year)
        else:
            period_month = month
            period_year = year

        docs = self.env['account.move'].search([
                ("move_type", "=", "out_invoice"),
                ("state", "=", "posted"),
                ("invoice_date", ">=", start_date),
                ("invoice_date", "<=", end_date),
                ('company_id', '=', self.env.company.id),
        ])

        docs = docs.filtered(
            lambda x: float_is_zero(
                x.amount_residual, precision_digits=x.currency_id.rounding
            )
                      and any(tax.is_withholding for tax in x.mapped("invoice_line_ids.tax_ids"))
                      or x.late_wth_amount
        )

        return docs, period_month, period_year

    def _get_retention_map_report_values(self, docids, report_file, data=None):

        docs, month, year = self.get_docs_values(data)
        if not docs:
            raise ValidationError(_("Não foi encontrado nenhum pagamento com "
                "retenção para o período selecionado!"))

        months = {1: _('01'), 2: _('02'), 3: _('03'), 4: _('04'), 5: _('05'), 6: _('06'), 7: _('07'), 8: _('08'),
                  9: _('09'), 10: _('10'), 11: _('11'), 12: _('12'), }

        def get_xlsx_dict_values(docs):
            data_values = []
            index = 15
            counter = 0
            for doc in docs:
                counter += 1
                retention_tax = doc.invoice_line_ids.tax_ids.filtered(lambda x: x.is_withholding)
                amount_wth_tax = doc.amount_total - (doc.amount_total_wth if retention_tax else doc.late_wth_amount)
                current_symbol = doc.currency_id.symbol
                amount_untaxed = doc.amount_untaxed
                payment_date = doc.get_customer_payment_date()
                data_values.extend([
                    {f'B{index}': counter, f'C{index}': "SIM" if doc.line_ids.partner_id.commercial_partner_id.country_id.code == "AO" else "NÃO",
                    f'D{index}': doc.partner_vat if doc.line_ids.partner_id.commercial_partner_id.country_id.code == "AO" and doc.partner_vat else "",
                    f'E{index}': doc.partner_id.name if doc.partner_id.name else "",
                    f'F{index}': doc.name if doc.name else '',
                    f'G{index}': doc.invoice_line_ids.mapped('name')[0] or "",
                    f'H{index}': str(doc.invoice_date),
                    f'I{index}': payment_date[0] if payment_date else "", 
                    f'J{index}': f"{current_symbol} {doc.amount_total}" if doc.amount_total else "",
                    f'K{index}': f"{current_symbol} {doc.amount_total_wth}" if doc.amount_total_wth else "",
                    f'L{index}': f" {current_symbol} {amount_untaxed}" if amount_untaxed else "",
                    f'M{index}': f"{str(retention_tax.amount) + '%'}" if retention_tax else "", 
                    f'N{index}': f"{current_symbol} {amount_wth_tax}"
                    },
                    {f'I{index + 1}': "Total", 
                    f'J{index + 1}': f"{current_symbol} {sum(doc.amount_total for doc in docs)}",
                    f'K{index + 1}': f"{current_symbol} {sum(doc.amount_total_wth for doc in docs)}",
                    f'L{index + 1}': f"{current_symbol} {sum(doc.amount_untaxed for doc in docs)}",
                    f'N{index + 1}': f"{current_symbol} {sum(doc.amount_total - (doc.amount_total_wth or doc.late_wth_amount)  for doc in docs)}"}])
                index += 1

            return data_values


        def create_temp_xlsx_file(period, docs):
            # create retention temp file
            temp_file = tempfile.NamedTemporaryFile(mode='w+b', delete=False, suffix=".xls")
            dir_path = temp_file.name
            file = temp_file.name.split('/')
            file[-1] = f"Mapa_de_retenção_{period}.xls"
            new_dir_path = '/'.join(map(str, file))
            os.rename(dir_path, new_dir_path)
            # Write file XLSX
            workbook = xlsxwriter.Workbook(new_dir_path)
            worksheet = workbook.add_worksheet()
            primary_header_row = 2
            cell_format = workbook.add_format(
                {'bold': True, 'align': 'center', 'valign': 'vcenter', 'border': 1, 'bg_color': '#808080'})
            # Header
            # BODY

            value_style = workbook.add_format({
                'font_name': 'Arial',
                'font_color': '#000000',
                'bold': False, 'align': 'center',
                'valign': 'vcenter',
                'border': 1
            })

            worksheet.merge_range('B10:U10', "")
            worksheet.write_string('B10', "LISTA DE FACTURAS DISCRIMINADAS E RESPECTIVO VALOR RETIDO DE IMPOSTO INDUSTRIAL", value_style)
            worksheet.merge_range('B12:B14', "")
            worksheet.write_string('B12', "Nº", value_style)
            worksheet.merge_range('C12:E12', "")
            worksheet.write_string('C12', "IDENTIFICAÇÃO DO PRESTADOR DE SERVIÇO", value_style)
            worksheet.merge_range('F12:L12', "")
            worksheet.write_string('F12', "DETALHES DA FACTURA", value_style)
            worksheet.merge_range('C13:C14', "")
            worksheet.write_string('C13', "NIF EM ANGOLA", value_style) 
            worksheet.merge_range('D13:D14', "")
            worksheet.write_string('D13', "NIF", value_style)
            worksheet.merge_range('E13:E14', "")
            worksheet.write_string('E13', "NOME", value_style)
            worksheet.merge_range('F13:F14', "")
            worksheet.write_string('F13', "Nº DA FACTURA", value_style)
            worksheet.merge_range('G13:G14', "")
            worksheet.write_string('G13', "DESCRIÇÃO DO SERVIÇO", value_style)
            worksheet.merge_range('H13:H14', "")
            worksheet.write_string('H13', "DATA DA FACTURA", value_style)
            worksheet.merge_range('I13:I14', "")
            worksheet.write_string('I13', "DATA DO PAGAMENTO", value_style)
            worksheet.merge_range('J13:J14', "")
            worksheet.write_string('J13', "VALOR DA FACTURA", value_style)
            worksheet.merge_range('K13:K14', "")
            worksheet.write_string('K13', "VALOR PAGO", value_style)
            worksheet.merge_range('L13:L14', "")
            worksheet.write_string('L13', "VALOR SUJEITO A RETENÇÃO", value_style)
            worksheet.merge_range('M12:M14', "")
            worksheet.write_string('M12', "TAXA", value_style)
            worksheet.merge_range('N12:N14', "")
            worksheet.write_string('N12', "IMPOSTO RETIDO", value_style)
           
            xlsx_values = get_xlsx_dict_values(docs)
            index = 5 + len(xlsx_values)
            for dic_value in xlsx_values:
                for key, value in dic_value.items():
                        worksheet.write(key, value)

            workbook.close()
            return new_dir_path

        base_url = self.env['ir.config_parameter'].get_param('web.base.url')
        period = '%d-%s' % (year, months[int(month)])
        if report_file == 'xlsx':
            dir_path_file = create_temp_xlsx_file(period, docs)
        else:
            return {}

        file_result = base64.b64encode(open(f'{dir_path_file}', 'rb').read())
        url_file = f'{base_url}/file/map/download?dir_path_file={dir_path_file}'
        return url_file
