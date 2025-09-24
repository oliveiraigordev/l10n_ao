import io
import base64
import xlsxwriter
from odoo import models, fields
from datetime import datetime
from odoo.tools.misc import formatLang

class WizardCustomerInvoice(models.TransientModel):
    _name = "wizard.customer_invoice"
    _description = "Wizard Customer Invoice"

    date_start = fields.Date(
        strig="Data de início"
    )

    date_end = fields.Date(
        strig="Data Final"
    )

    def values(self):
        invoices = self.env['account.move'].search([
            ('move_type',    '=', 'out_invoice'),
            ('invoice_date', '>=', self.date_start),
            ('invoice_date', '<=', self.date_end),
        ], order='invoice_date')

        vals        = []
        vals_totals = []
        num_order   = 0
        total_untaxed  = total_tax = total_ret_rate = total_retained = total_overall = 0.0

        for inv in invoices:
            num_order += 1
            tax_list     = []
            withhold_list = []
            retention_rate = 0.0

            # coleta de taxas
            for line in inv.line_ids:
                for tx in line.tax_ids:
                    if not tx.is_withholding:
                        tax_list.append(tx.name)
                    else:
                        withhold_list.append(tx.name)
                        retention_rate += (tx.amount * inv.amount_untaxed) / 100

            # cálculo do valor retido
            amt_retained = (retention_rate - inv.amount_untaxed) - inv.amount_tax

            # formatações de data e valores conforme idioma/moeda do Odoo
            date_str = inv.invoice_date.strftime('%d/%m/%Y') if inv.invoice_date else ''
            str_untaxed  = formatLang(self.env, inv.amount_untaxed,  currency_obj=inv.currency_id, grouping=True)
            str_tax      = formatLang(self.env, inv.amount_tax,      currency_obj=inv.currency_id, grouping=True)
            str_total    = formatLang(self.env, inv.amount_total,    currency_obj=inv.currency_id, grouping=True)
            str_ret_rate = formatLang(self.env, retention_rate,                           grouping=True)
            str_amt_ret  = formatLang(self.env, abs(amt_retained),                          grouping=True)

            vals.append([
                num_order,
                inv.name or '',
                date_str,
                inv.partner_id.name or '',
                str_untaxed,
                ', '.join(tax_list) or '-',
                str_tax,
                ', '.join(withhold_list) or '-',
                str_ret_rate,
                str_amt_ret,
                str_total,
            ])

            # acumula totais
            total_untaxed  += inv.amount_untaxed
            total_tax      += inv.amount_tax
            total_ret_rate += retention_rate
            total_retained += amt_retained
            total_overall  += inv.amount_total

        # formata totais finais
        currency = invoices and invoices[0].currency_id or self.env.user.company_id.currency_id
        vals_totals.append([
            formatLang(self.env, total_untaxed,  currency_obj=currency, grouping=True),
            formatLang(self.env, total_tax,      currency_obj=currency, grouping=True),
            formatLang(self.env, total_ret_rate, currency_obj=currency, grouping=True),
            formatLang(self.env, abs(total_retained), currency_obj=currency, grouping=True),
            formatLang(self.env, total_overall,  currency_obj=currency, grouping=True),
        ])

        return vals, vals_totals

    def print_report(self):
        
        vals, vals_totals = self.values()

        data = {
            'invoices': vals,
            'totais': vals_totals
        }

        return self.env.ref("l10n_ao_report.l10n_ao_report_customer_invoice_rpt").report_action(self, data=data)
    
    def print_excel_report(self):
        # Obtém os dados e os totais
        vals, totals = self.values()
        total_vals = totals[0] if totals else [0, 0, 0, 0, 0]

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet("Faturas")

        # Formato para o título (linha mesclada de A1 até J1)
        title_format = workbook.add_format({
            'bold': True,
            'align': 'center',
            'valign': 'vcenter',
            'font_size': 10,
            'bg_color': '#ced9e0',
            'border': 1
        })

        # Formatos dos cabeçalhos e células
        header_format = workbook.add_format({
            'bold': True,
            'font_color': 'black',
            'align': 'center',
            'font_size': 10,
            'border': 1
        })
        cell_format = workbook.add_format({
            'align': 'center',
            'border': 1
        })
        total_format = workbook.add_format({
            'bold': True,
            'align': 'right',
            'border': 1
        })

        headers = [
            "Nº da factura",
            "Referência",
            "Data da factura",
            "Nome do cliente",
            "Valor sem imposto",
            "Taxa de imposto",
            "Valor do imposto",
            "Taxa de retenção",
            "Valor da retenção",
            "Valor total retido",
            "Valor total da factura"
        ]

        # Linha de título: mescla de A1 até J1 (linha 0 no índice Python)
        worksheet.merge_range(0, 0, 0, 10, "Resumo de facturação de venda", title_format)

        # Cabeçalhos na linha 1
        header_row = 1
        for col, header in enumerate(headers):
            worksheet.write(header_row, col, header, header_format)

        # Dados a partir da linha 2
        data_start_row = 2
        row = data_start_row
        for rec in vals:
            for col, value in enumerate(rec):
                worksheet.write(row, col, value, cell_format)
            row += 1

        # Linha de totalização logo após os dados
        # Mescla as três primeiras células para o rótulo "Totais:"
        worksheet.merge_range(row, 0, row, 3, "Totais:", total_format)
        worksheet.write(row, 4, total_vals[0], total_format)
        worksheet.write(row, 5, "", total_format)  # Taxa de imposto não totalizada
        worksheet.write(row, 6, total_vals[1], total_format)
        worksheet.write(row, 7, "", total_format)  # Taxa de retenção não totalizada
        worksheet.write(row, 8, total_vals[2], total_format)
        worksheet.write(row, 9, total_vals[3], total_format)
        worksheet.write(row, 10, total_vals[4], total_format)

        workbook.close()
        output.seek(0)
        file_data = output.read()

        attachment = self.env['ir.attachment'].create({
            'name': 'Relatorio_Faturas.xlsx',
            'datas': base64.b64encode(file_data),
            'type': 'binary',
            'mimetype': 'application/vnd.ms-excel'
        })

        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/%s?download=true' % attachment.id,
            'target': 'self',
        }

