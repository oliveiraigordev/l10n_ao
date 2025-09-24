# -*- coding: utf-8 -*-
from odoo import api, models, fields, _
from dateutil.parser import parse
from odoo.exceptions import ValidationError, UserError
from datetime import date, timedelta
from xml.dom.minidom import parseString
from dicttoxml2 import dicttoxml
import base64
import os
import tempfile
import xlsxwriter


months = {
    1: _('Janeiro'),
    2: _('Fevereiro'),
    3: _('Março'),
    4: _('Abril'),
    5: _('Maio'),
    6: _('Junho'),
    7: _('Julho'),
    8: _('Agosto'),
    9: _('Setembro'),
    10: _('Outubro'),
    11: _('Novembro'),
    12: _('Dezembro'),
}

dest_dict = {
    'MFI': '16',
    'INV': '18',
    'OBC': '20',
    'SERV': '22',
    'IMPT': '',
    'SCE': '',
}


class ReportRegSupplierAttachment(models.AbstractModel):
    _name = 'report.supplier.reg.attachment.xlsx'
    _description = 'Anexo de Regularização de Fornecedor'

    def get_docs_values(self, data):

        start_date = date(data['form_data']['year'],
                          int(data['form_data']['month']), 1)
        if int(data['form_data']['month']) == 12:
            end_date = date(data['form_data']['year'],
                            int(data['form_data']['month']), 31)
        else:
            end_date = date(data['form_data']['year'], int(
                data['form_data']['month']) + 1, 1) + timedelta(days=-1)

        docs = self.env["account.move"].search(
            [
                ("move_type", "=", "in_refund"),
                ("reversed_entry_id.name", "!=", None),
                ("state", "=", "posted"),
                ("invoice_date", ">=", start_date),
                ("invoice_date", "<=", end_date),
            ]
        )
        return docs, start_date

    def _get_supplier_reg_attch_report_values(self, docids, report_file, data=None):
        docs, start_date = self.get_docs_values(data)
        if not docs:
            raise ValidationError(
                _("Não foi encontrada nenhuma fatura para o período selecionado!"))

        def get_xlsx_dict_values(period, docs):
            data_values = []
            reversed_data_values = []
            invoice_data = []
            reversed_invoice_data = []
            counter = 0
            index = 13

            amount_supported_iva = 0
            amount_deductive_iva = 0
            

            amount_supported_iva_total = 0
            amount_deductive_iva_total = 0
            reversed_amount_supported_iva_total = 0
            reversed_amount_deductive_iva_total = 0
        

            amount_invoice_total = 0
            amount_untaxed_total = 0
            amount_reversed_invoice_total= 0
            reversed_amount_untaxed_total = 0
            reg_iva_total = 0

            for doc in docs:
                amount_invoice_total += abs(doc.amount_total_signed)
                amount_reversed_invoice_total += abs(doc.reversed_entry_id.amount_total_signed)
                counter += 1
                move_line_ids = doc.invoice_line_ids
                product_line_ids = move_line_ids.mapped('product_id')
                product_tipology_ids = product_line_ids.mapped('tipology')
                for tipology in product_tipology_ids : 
                    if not tipology:         
                        raise UserError(
                        f"Queira definir tipo de operação no produto! {product_line_ids.display_name}")
                    product_ids = product_line_ids.filtered(lambda t : t.tipology == tipology)
                    line_ids = move_line_ids.filtered(lambda l : l.product_id in product_ids) 
                    amount_untaxed = sum([
                        line.price_subtotal for line in line_ids 
                    ])

                    
                    for line in line_ids:
                        amount_untaxed_total += line.price_subtotal
                            
                    iva_tax_lines = [
                    line for line in line_ids 
                    if any(iva_tax.iva_tax_type in ('SUP', 'DEDU', 'CAT50', 'CAT100') for iva_tax in line.tax_ids.filtered(lambda r: r.tax_type == 'IVA'))
                    ]

                
                    amount_supported_iva_list = [
                        round(line.price_subtotal * (iva_tax.amount / 100), 2)
                        for line in iva_tax_lines
                        for iva_tax in line.tax_ids.filtered(lambda r: r.tax_type == 'IVA') 
                        if iva_tax.iva_tax_type == 'SUP'
                    ]

                
                    amount_deductive_iva_list = [
                        round(line.price_subtotal * (iva_tax.amount / 100), 2)
                        for line in iva_tax_lines
                        for iva_tax in line.tax_ids.filtered(lambda r: r.tax_type == 'IVA') 
                        if iva_tax.iva_tax_type == 'DEDU'
                    ]

                
                
                    
                
                    
                    amount_supported_iva = sum(amount_supported_iva_list)
                    amount_deductive_iva = sum(amount_deductive_iva_list)
                

                    amount_supported_iva_total  += amount_supported_iva
                    reg_iva_total += amount_supported_iva
                    amount_deductive_iva_total  += amount_deductive_iva
            
                
                
                    
                
                    if all(item == tipology for item in product_tipology_ids):
                        data = {'order_number' :  counter, 'ops': 'REGULARIZACAO','partner_vat' : doc.partner_id.vat, 'partner_name' : doc.partner_id.name, 'document_type' : 'NC' , 'date_invoice' : doc.invoice_date,  'document_number' : doc.name, 'amount_total' : abs(doc.amount_total_signed), 'amount_untaxed' : amount_untaxed, 'supported_iva' : amount_supported_iva,'reg_iva': amount_supported_iva ,'dedu_iva_percent' : '', 'dedu_iva_value' : amount_deductive_iva, 'tipology' : tipology, 'dest_tipology' : dest_dict[tipology],}
                        invoice_data.append(data)
                        break
                    else:
                        data = {'order_number' :  counter, 'ops': 'REGULARIZACAO', 'partner_vat' : doc.partner_id.vat, 'partner_name' : doc.partner_id.name, 'document_type' : 'NC' , 'date_invoice' : doc.invoice_date,  'document_number' : doc.name, 'amount_total' : abs(doc.amount_total_signed), 'amount_untaxed' : amount_untaxed, 'supported_iva' : amount_supported_iva,'reg_iva': amount_supported_iva ,'dedu_iva_percent' : '', 'dedu_iva_value' : amount_deductive_iva, 'tipology' : tipology, 'dest_tipology' : dest_dict[tipology],}
                        invoice_data.append(data)

            
             

                reversed_move_line_ids = doc.reversed_entry_id.invoice_line_ids
                reversed_product_line_ids = reversed_move_line_ids.mapped('product_id')
                reversed_product_tipology_ids = reversed_product_line_ids.mapped('tipology')
                for tipology in reversed_product_tipology_ids : 
                    reversed_product_ids = reversed_product_line_ids.filtered(lambda t : t.tipology == tipology)
                    reversed_line_ids = reversed_move_line_ids.filtered(lambda l : l.product_id in reversed_product_ids) 
                    reversed_amount_untaxed = sum([
                        line.price_subtotal for line in reversed_line_ids 
                    ])

                    reversed_iva_tax_lines = [
                    line for line in reversed_line_ids 
                    if any(iva_tax.iva_tax_type in ('SUP', 'DEDU', 'CAT50', 'CAT100') for iva_tax in line.tax_ids.filtered(lambda r: r.tax_type == 'IVA'))
                    ]

                
                    reversed_amount_supported_iva_list = [
                        round(line.price_subtotal * (iva_tax.amount / 100), 2)
                        for line in reversed_iva_tax_lines
                        for iva_tax in line.tax_ids.filtered(lambda r: r.tax_type == 'IVA') 
                        if iva_tax.iva_tax_type == 'SUP'
                    ]

                
                    reversed_amount_deductive_iva_list = [
                        round(line.price_subtotal * (iva_tax.amount / 100), 2)
                        for line in reversed_iva_tax_lines
                        for iva_tax in line.tax_ids.filtered(lambda r: r.tax_type == 'IVA') 
                        if iva_tax.iva_tax_type == 'DEDU'
                    ]

                    for line in reversed_line_ids:
                        reversed_amount_untaxed_total += line.price_subtotal

                    reversed_amount_supported_iva = sum(reversed_amount_supported_iva_list)
                    reversed_amount_deductive_iva = sum(reversed_amount_deductive_iva_list)
                

                    reversed_amount_supported_iva_total  += reversed_amount_supported_iva
                    reversed_amount_deductive_iva_total  += reversed_amount_deductive_iva
                    
                    if all(item == tipology for item in reversed_product_tipology_ids):
                        reversed_data = {'order_number' : counter, 'ops': 'DECL ANTERIOR',  'partner_vat' : doc.reversed_entry_id.partner_id.vat, 'partner_name' : doc.reversed_entry_id.partner_id.name, 'document_type' : doc.reversed_entry_id.journal_id.code , 'date_invoice' : doc.reversed_entry_id.invoice_date,  'document_number' : doc.reversed_entry_id.name, 'amount_total' : abs(doc.reversed_entry_id.amount_total_signed), 'amount_untaxed' : reversed_amount_untaxed, 'supported_iva' : reversed_amount_supported_iva,'reg_iva': 'Não' ,'dedu_iva_percent' : '', 'dedu_iva_value' : reversed_amount_deductive_iva, 'tipology' : tipology, 'dest_tipology' : dest_dict[tipology],}
                        invoice_data.append(reversed_data)
                        break
                    else:
                        reversed_data = {'order_number' : counter, 'ops': 'DECL ANTERIOR',  'partner_vat' : doc.reversed_entry_id.partner_id.vat, 'partner_name' : doc.reversed_entry_id.partner_id.name, 'document_type' : doc.reversed_entry_id.journal_id.code , 'date_invoice' : doc.reversed_entry_id.invoice_date,  'document_number' : doc.reversed_entry_id.name, 'amount_total' : abs(doc.reversed_entry_id.amount_total_signed), 'amount_untaxed' : reversed_amount_untaxed, 'supported_iva' : reversed_amount_supported_iva,'reg_iva': 'Não' ,'dedu_iva_percent' : '', 'dedu_iva_value' : reversed_amount_deductive_iva, 'tipology' : tipology, 'dest_tipology' : dest_dict[tipology],}
                        invoice_data.append(reversed_data)

                        
            for line in invoice_data:
                data_values.extend([
                    {
                        f'A{index}': line.get('order_number', ''),
                        f'B{index}': line.get('ops', ''),
                        f'C{index}': line.get('partner_vat') or "",
                        f'D{6}':period.split('-')[1],
                        f'E{6}':months[start_date.month],
                        f'D{index}': line.get('partner_name', ''),
                        f'G{index}': line.get('document_type', ''),
                        f'H{index}': str(line.get('date_invoice')),
                        f'I{index}': line.get('document_number', ''),
                        f'J{index}': line.get('amount_total', ''),
                        f'K{index}': line.get('amount_untaxed', ''),
                        f'L{index}': line.get('supported_iva', ''),
                        f'M{index}': line.get('reg_iva', ''),
                        f'N{index}': line.get('dedu_iva_percent', ''),
                        f'O{index}': line.get('dedu_iva_value', ''),
                        f'P{index}': line.get('tipology', ''),
                        f'Q{index}': line.get('dest_tipology', ''),
                        
                        
                    },
                ])
                index += 1
            # for line in reversed_invoice_data:
            #     data_values.extend([
            #             {
            #                 f'B{index}': "DECL ANTERIOR",
            #                 f'C{index}': line.get('partner_vat') or "",
            #                 f'D{index}': line.get('partner_name', ''),
            #                 f'G{index}': line.get('document_type', ''),
            #                 f'H{index}': str(line.get('date_invoice')),
            #                 f'I{index}': line.get('document_number', ''),
            #                 f'J{index}': line.get('amount_total', ''),
            #                 f'K{index}': line.get('amount_untaxed', ''),
            #                 f'L{index}': line.get('supported_iva', ''),
            #                 f'M{index}': "Não",
            #                 f'N{index}': line.get('dedu_iva_percent', ''),
            #                 f'O{index}': line.get('dedu_iva_value', ''),
            #                 f'P{index}': line.get('tipology', ''),
            #                 f'Q{index}': line.get('dest_tipology', ''),
            #                 f'J{5}': doc.company_id.vat,
                            
            #             },

            #     ])
            #     index += 1

            amount_invoice_total = amount_invoice_total + amount_reversed_invoice_total
            amount_untaxed_total = amount_untaxed_total + reversed_amount_untaxed_total
            amount_supported_iva_total = amount_supported_iva_total  + reversed_amount_supported_iva_total
            amount_deductive_iva_total = amount_deductive_iva_total + reversed_amount_deductive_iva_total

            # data_values.extend(reversed_data_values)

            data_values.extend([
            {
                f'I{index}': "Total",
                f'J{index}': amount_invoice_total,
                f'K{index}': amount_untaxed_total,
                f'L{index}': amount_supported_iva_total,
                f'M{index}': reg_iva_total,
                f'O{index}': amount_deductive_iva_total,
                
                
            }
            ])

            return data_values

        def create_temp_xlsx_file(period, docs):
            # create retention temp file
            temp_file = tempfile.NamedTemporaryFile(
                mode='w+b', delete=False, suffix=".xls")
            dir_path = temp_file.name
            file = temp_file.name.split('/')
            file[-1] = f"Anexo De Regularização de Fornecedores.xls"
            new_dir_path = '/'.join(map(str, file))
            os.rename(dir_path, new_dir_path)
            # Write file XLSX
            workbook = xlsxwriter.Workbook(new_dir_path)
            worksheet = workbook.add_worksheet()

            value_style = workbook.add_format({
                'font_name': 'Arial',
                'font_color': '#000000',
                'bold': False, 'align': 'center',
                'valign': 'vcenter',
                'border': 1
            })

            # Header
            # BODY
            worksheet.merge_range('A1:G1', "")
            worksheet.write_string(
                'A1', "ANEXO DE FORNECEDORES", value_style)
            worksheet.merge_range('C2:E2', "")
            worksheet.write_string('C2', "REGULARIZAÇÕES", value_style)
            worksheet.merge_range('A5:G5', "")
            worksheet.write_string(
                'A5', "PERÍODO DE TRIBUTAÇÃO E NÚMERO DE IDENTIFICAÇÃO FISCAL", value_style)
            worksheet.write_string('A6', "Ano", value_style)
            worksheet.write_string('C6', "Mês", value_style)
            worksheet.merge_range('A8:G8', "")
            worksheet.write_string(
                'A8', "REGULARIZAÇÕES DE IVA SUPORTADO", value_style)
            worksheet.merge_range('I5:I6', "")
            worksheet.write_string('I5', "NIF", value_style)
            worksheet.merge_range('J5:K6', "")
            worksheet.merge_range('Q7:R8', "")
            worksheet.merge_range('A10:A12', "")
            worksheet.write_string('A10', "Nº ORDEM", value_style)
            worksheet.merge_range('B10:B12', "")
            worksheet.write_string('B10', "OPERAÇÕES", value_style)
            worksheet.merge_range('C10:C12', "")
            worksheet.write_string(
                'C10', "Número de Identificação Fiscal", value_style)
            worksheet.merge_range('D10:F12', "")
            worksheet.write_string(
                'D10', "NOME/FIRMA", value_style)
            worksheet.merge_range('G10:G12', "")
            worksheet.write_string(
                'G10', "TIPO DE DOCUMENTO", value_style)
            worksheet.merge_range('H10:H12', "")
            worksheet.write_string(
                'H10', "DATA DO DOCUMENTO", value_style)
            worksheet.merge_range('I10:I12', "")
            worksheet.write_string(
                'I10', "NÚMERO DO DOCUMENTO", value_style)
            worksheet.merge_range('J10:J12', "")
            worksheet.write_string(
                'J10', "VALOR DA FACTURA", value_style)
            worksheet.merge_range('K10:K12', "")
            worksheet.write_string(
                'K10', "VALOR TRIBUTÁVEL", value_style)
            worksheet.merge_range('L10:L12', "")
            worksheet.write_string('L10', "IVA SUPORTADO", value_style)
            worksheet.merge_range('M10:M12', "")
            worksheet.write_string(
                'M10', "IVA REGULARIZADO", value_style)
            worksheet.merge_range('N9:O10', "")
            worksheet.write_string('N9', "IVA DEDUTIVEL", value_style)
            worksheet.merge_range('N10:N11', "")
            worksheet.write_string('N11', "%", value_style)
            worksheet.merge_range('O11:O12', "")
            worksheet.write_string('O11', "VALOR", value_style)
            worksheet.merge_range('P11:P12', "")
            worksheet.write_string('P11', "TIPOLOGIA", value_style)
            worksheet.merge_range('Q11:Q12', "")
            worksheet.write_string('Q11', "CAMPO DE DESTINO NO MODELO", value_style)
            


            xlsx_values = get_xlsx_dict_values(period, docs)
            index = 5 + len(xlsx_values)

            for dic_value in xlsx_values:
                for key, value in dic_value.items():
                    worksheet.write(key, value)

            workbook.close()
            return new_dir_path

        base_url = self.env['ir.config_parameter'].get_param('web.base.url')
        period = '%d-%s' % (start_date.year, start_date.month)
        if report_file == 'xlsx':
            dir_path_file = create_temp_xlsx_file(period, docs)
        else:
            return {}

        file_result = base64.b64encode(open(f'{dir_path_file}', 'rb').read())
        url_file = f'{base_url}/file/map/download?dir_path_file={dir_path_file}'
        return url_file

