from datetime import datetime, time
from odoo import api, models, fields, _
from dateutil.parser import parse
from odoo.exceptions import ValidationError, UserError
from odoo.tools.misc import formatLang
from datetime import date, timedelta

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
            'MFI'  : '16',
            'INV'  : '18',
            'OBC'  : '20',
            'SERV' : '22', 
            'IMPT' : '',
            'SCE'  : '',

        }


class ReportSupAttach(models.AbstractModel):
    _name = 'report.l10n_ao.report_supplier_attachment'
    _description = 'Anexo de Fornecedores Map'

    

    def get_docs_values(self, data):
        start_date = date(data['form_data']['year'], int(data['form_data']['month']), 1)
        if int(data['form_data']['month']) == 12:
            end_date = date(data['form_data']['year'], int(data['form_data']['month']), 31)
        else:
            end_date = date(data['form_data']['year'], int(data['form_data']['month']) +1, 1) + timedelta(days=-1)
           
        docs = self.env["account.move"].search(
            [
                ("move_type", "=", "in_invoice"),
                ("state", "=", "posted"),
                ("invoice_date", ">=", start_date),
                ("invoice_date", "<=", end_date),
            ]
        )
        
       
      
        return docs, start_date

    @api.model
    def _get_report_values(self, docids, data=None):
        docs, start_date = self.get_docs_values(data)
        if not docs:
            raise UserError(
                "Não foi encontrada nenhuma fatura para o período selecionado!"
            )
        

        invoice_data = []
        counter = 0

        amount_supported_iva = 0
        amount_deductive_iva = 0
        amount_captive_iva = 0

        amount_supported_iva_total = 0
        amount_deductive_iva_total = 0
        amount_captive_iva_total = 0

        amount_invoice_total = 0
        amount_untaxed_total = 0

        for doc in docs:
            amount_invoice_total += abs(doc.amount_total_signed)
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

               
                amount_captive_iva_list = [
                    round(line.price_subtotal * (iva_tax.amount / 100), 2)
                    for line in iva_tax_lines
                    for iva_tax in line.tax_ids.filtered(lambda r: r.tax_type == 'IVA') 
                    if iva_tax.iva_tax_type in ('CAT50', 'CAT100')
                ]
                
               
                
                amount_supported_iva = sum(amount_supported_iva_list)
                amount_deductive_iva = sum(amount_deductive_iva_list)
                amount_captive_iva = sum(amount_captive_iva_list)

                amount_supported_iva_total  += amount_supported_iva
                amount_deductive_iva_total  += amount_deductive_iva
                amount_captive_iva_total  += amount_captive_iva
                
                    
                    
               
                if all(item == tipology for item in product_tipology_ids):
                    data = {'order_number' :  counter, 'partner_vat' : doc.partner_id.vat, 'partner_name' : doc.partner_id.name, 'document_type' : doc.journal_id.code , 'date_invoice' : doc.invoice_date,  'document_number' : doc.name, 'invoice_reference' : doc.ref, 'amount_total' : abs(doc.amount_total_signed), 'amount_untaxed' : amount_untaxed, 'supported_iva' : amount_supported_iva, 'dedu_iva_percent' : '', 'dedu_iva_value' : amount_deductive_iva, 'captive_iva_percent' : '','captive_iva_value' : amount_captive_iva, 'tipology' : tipology, 'dest_tipology' : dest_dict[tipology],}

                    invoice_data.append(data)
                    break
                else:
                    data = {'order_number' :  counter, 'partner_vat' : doc.partner_id.vat, 'partner_name' : doc.partner_id.name, 'document_type' : doc.journal_id.code , 'date_invoice' : doc.invoice_date,  'document_number' : doc.name, 'invoice_reference' : doc.ref, 'amount_total' : abs(doc.amount_total_signed), 'amount_untaxed' : amount_untaxed, 'supported_iva' : amount_supported_iva, 'dedu_iva_percent' : '', 'dedu_iva_value' : amount_deductive_iva, 'captive_iva_percent' : '','captive_iva_value' : amount_captive_iva, 'tipology' : tipology, 'dest_tipology' : dest_dict[tipology],}

                    invoice_data.append(data)

       
                
        return {
            'doc_ids': docs.ids,
            'doc_model': 'account.move',
            'docs': docs,
            'time': time,
            'tis': 'this is the value of tis',
            'formatLang': formatLang,
            'env': self.env,
            'year' : start_date.year,
            'month_number' : start_date.month,
            'month' : months[start_date.month],
            'invoice_data' : invoice_data,
            'amount_invoice_total' : amount_invoice_total,
            'amount_untaxed_total' : amount_untaxed_total,
            'amount_supported_iva_total' : amount_supported_iva_total,
            'amount_captive_iva_total' : amount_captive_iva_total,
            'amount_deductive_iva_total' : amount_deductive_iva_total,
        }