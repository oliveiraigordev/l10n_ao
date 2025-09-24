# -*- coding: utf-8 -*-
import time
from odoo import api, models, fields, _
from dateutil.parser import parse
from odoo.exceptions import ValidationError
from odoo.tools.misc import formatLang
from . import common
import base64, os, tempfile
import xlsxwriter


class ReportHRBankMap(models.AbstractModel):
    _name = 'report.l10n_ao_hr.bank_map'
    _description = 'Bank Report Map'

    def get_docs_values(self, data):
        slip_filter_by = data['form']['slip_filter_by']
        bank = data['form']['bank']
        contract_tipe_id = data['form']['contract_type_id']

        if slip_filter_by == 'payslip_batch':
            slip_id = data['form']['hr_payslip_run_id'][0]
            docs = self.env['hr.payslip'].search(
                [('payslip_run_id', '=', slip_id), ('state', 'in', ['done', 'paid']),
                 ('company_id', '=', self.env.company.id)])

            if contract_tipe_id:
                docs = docs.filtered(lambda p: p.contract_type_id.id == contract_tipe_id[0])

            period_start_date = self.env['hr.payslip.run'].browse(slip_id).date_start
            period_end_date = self.env['hr.payslip.run'].browse(slip_id).date_end
        else:
            start_date = data['form']['start_date']
            end_date = data['form']['end_date']
            if type(end_date) is str:
                period_start_date = parse(start_date)
                period_end_date = parse(end_date)
            else:
                period_start_date = start_date
                period_end_date = end_date

            docs = self.env['hr.payslip'].search([('date_to', '>=', start_date), ('date_to', '<=', end_date),
                                                  ('state', 'in', ['done', 'paid']),
                                                  ('company_id', '=', self.env.company.id)])

            if contract_tipe_id:
                docs = docs.filtered(lambda p: p.contract_type_id.id == contract_tipe_id[0])

        return docs, bank, period_start_date, period_end_date

    def get_payslip_data(self, docs, bank):
        payslip_data = []
        # FILTRAR OS TIPOS DE FUNCIONÁRIOS
        employee_type = docs.mapped('employee_id.contract_type')
        # VERIFICAR SE FOI SELECIONADO UM BANCO ESPECIFICO
        if bank:
            for empl_type in employee_type:
                docs = docs.filtered(lambda r: r.employee_id.bank_bank.id == bank[0])
                docs_values = docs.filtered(lambda r: r.employee_id.contract_type.id == empl_type.id)
                payslip_data.append(
                    {'employee_type': empl_type.name, 'bank': bank[1], 'payslip_ids': docs_values})
        else:
            for empl_type in employee_type:
                docs_data = docs.filtered(lambda r: r.employee_id.contract_type.id == empl_type.id)
                # FILTRAR OS Bancos
                banks = docs_data.mapped('employee_id.bank_bank')
                for bank in banks:
                    docs_values = docs_data.filtered(lambda r: r.employee_id.bank_bank.id == bank.id)
                    payslip_data.append(
                        {'employee_type': empl_type.name, 'bank': bank.display_name, 'payslip_ids': docs_values})
        return payslip_data

    @api.model
    def _get_report_values(self, docids, data=None):
        if 'form' not in data:
            raise ValidationError('This action is under development')

        docs, bank, period_start_date, period_end_date = self.get_docs_values(data)
        if not docs:
            raise ValidationError(_('There is no payslips that match this criteria'))

        payslip_data = self.get_payslip_data(docs, bank)

        total_amount = sum(docs.mapped("total_paid"))
        docs.sorted(key=lambda r: r.name)
        return {
            'doc_ids': docs.ids,
            'doc_model': 'hr.payslip',
            'docs': docs,
            'payslip_data': payslip_data,
            'sum_total_paid': total_amount,
            'time': time,
            'tis': 'this is the value of tis',
            'formatLang': formatLang,
            'env': self.env,
            'year': period_end_date.year,
            'period': '%s-%s' % (common.get_month_text(period_start_date.month).upper(),
                                 common.get_month_text(
                                     period_end_date.month).upper()) if period_start_date.month != period_end_date.month else '%s' % (
                common.get_month_text(period_start_date.month).upper())
        }

    def bank_map_xlsx_report(self, docids, data=None):
        if 'form' not in data:
            raise ValidationError('This action is under development')

        docs, bank, period_start_date, period_end_date = self.get_docs_values(data)
        if not docs:
            raise ValidationError(_('There is no payslips that match this criteria'))

        payslip_data = self.get_payslip_data(docs, bank)
        total_amount = sum(docs.mapped("total_paid"))
        year = period_end_date.year
        if period_start_date.month != period_end_date.month:
            period = '%s-%s' % (
                common.get_month_text(period_start_date.month).upper(),
                common.get_month_text(period_end_date.month).upper())
        else:
            period = '%s' % (common.get_month_text(period_start_date.month).upper())

        def get_vals_bank_payment(period, year, total_amount, payslip_data):
            return {
                "period": period,
                "year": year,
                "total": total_amount,
                "curency_code": "AKZ",
                "doc_values": [
                    {
                        "employee_type": payslip.get('employee_type'),
                        "bank": payslip.get('bank'),
                        "payslip_values": [{
                            "employee_name": line.employee_id.name,
                            "acc_number": line.employee_id.bank_account,
                            "iban": line.employee_id.bank_iban_account,
                            "nib": line.employee_id.bank_nib_account,
                            "amount": line.total_paid
                        } for line in payslip.get('payslip_ids')]
                    }
                    for payslip in payslip_data],
            }

        def get_bank_payment_xlsx(values):
            # TODO: create bank payment temp file
            temp_file = tempfile.NamedTemporaryFile(mode='w+b', delete=False, suffix=".xls")
            dir_path = temp_file.name
            file = temp_file.name.split('/')
            file[-1] = f"Mapa_de_banco_{period}.xls"
            new_dir_path = '/'.join(map(str, file))
            os.rename(dir_path, new_dir_path)

            workbook = xlsxwriter.Workbook(new_dir_path)
            worksheet = workbook.add_worksheet()

            worksheet.set_column("A:F", 20)
            # Styles
            title_bold_blue = workbook.add_format(
                {"bold": True, "color": "000080", "align": "center", "valign": "vcenter"})
            bold_bordered_centered = workbook.add_format(
                {"bold": True, "border": 1, "align": "center", "valign": "vcenter"})
            regular_bordered = workbook.add_format({"border": 1, "valign": "vcenter"})
            # Title
            worksheet.merge_range("A1:F1", "Relatório de Pagamento Bancário", title_bold_blue)
            # Summary
            worksheet.write_string('A2', 'Período', bold_bordered_centered)
            worksheet.write_string('B2', values.get('period'), regular_bordered)
            worksheet.write_string('C2', 'Ano', bold_bordered_centered)
            worksheet.write_string('D2', str(values.get('year')), regular_bordered)
            worksheet.write_string('E2', f"Total ({values.get('curency_code')})", bold_bordered_centered)
            worksheet.write_string('F2', str(round(values.get('total'), 2)), regular_bordered)
            # Content
            row = 4
            for docs in values.get("doc_values", []):
                # Main table header
                worksheet.merge_range(f"A{row}:F{row}", f"Folha Pagamento - {docs.get('employee_type')}",
                                      bold_bordered_centered)
                row += 1
                worksheet.merge_range(f"A{row}:F{row}", f"Conta: {docs.get('bank')} / {values.get('curency_code')}",
                                      bold_bordered_centered)
                row += 1
                worksheet.merge_range(f"A{row}:B{row}", "Nome", bold_bordered_centered)
                worksheet.write_string(f"C{row}", "Nº Conta", bold_bordered_centered)
                worksheet.write_string(f"D{row}", "IBAN", bold_bordered_centered)
                worksheet.write_string(f"E{row}", "NIB", bold_bordered_centered)
                worksheet.write_string(f"F{row}", f"Valor ({values.get('curency_code')})", bold_bordered_centered)
                # Values
                row += 1
                for line in docs.get("payslip_values", []):
                    worksheet.merge_range(f"A{row}:B{row}", line.get("employee_name"), regular_bordered)
                    worksheet.write_string(f"C{row}", line.get("acc_number"), regular_bordered)
                    worksheet.write_string(f"D{row}", line.get("iban"), regular_bordered)
                    worksheet.write_string(f"E{row}", line.get("nib"), regular_bordered)
                    worksheet.write_string(f"F{row}", str(round(line.get("amount"), 2)), regular_bordered)
                    row += 1

                # TODO: RESERVAR DUAS LINHAS EM BRANCO PARA PROXIMA LINHA
                row = row + 2

            workbook.close()
            return new_dir_path

        bank_vals = get_vals_bank_payment(period, year, total_amount, payslip_data)
        dir_path_file = get_bank_payment_xlsx(bank_vals)
        base_url = self.env['ir.config_parameter'].get_param('web.base.url')
        file_result = base64.b64encode(open(f'{dir_path_file}', 'rb').read())
        url_file = f'{base_url}/file/map/download?dir_path_file={dir_path_file}'
        return url_file
