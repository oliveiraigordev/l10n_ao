# -*- coding: utf-8 -*-

import time
from odoo import api, models, fields, _
from dateutil.parser import parse
from odoo.exceptions import ValidationError
from odoo.tools.misc import formatLang
from . import common
import base64, xlsxwriter, os, tempfile


class ReportHRIRTMap(models.AbstractModel):
    _name = 'report.l10n_ao_hr.irt_map'
    _description = 'IRT Report Map'

    def get_docs_values(self, data):
        slip_filter_by = data['form']['slip_filter_by']
        contract_tipe_id = data['form']['contract_type_id']
        if slip_filter_by == 'payslip_batch':
            slip_id = data['form']['hr_payslip_run_id'][0]
            docs = self.env['hr.payslip'].search(
                [('payslip_run_id', '=', slip_id), ('company_id', '=', self.env.company.id)])

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
                                                  ('company_id', '=', self.env.company.id),
                                                  ('state', 'in', ['done', 'paid'])])

            if contract_tipe_id:
                docs = docs.filtered(lambda p: p.contract_type_id.id == contract_tipe_id[0])

        return docs, period_start_date, period_end_date

    @api.model
    def _get_report_values(self, docids, data=None):
        if 'form' not in data:
            raise ValidationError('This action is under development')

        docs, period_start_date, period_end_date = self.get_docs_values(data)
        if not docs:
            raise ValidationError('There is no payslips that match this criteria')

        if period_start_date.month != period_end_date.month:
            period = '%s-%s' % (
                common.get_month_text(period_start_date.month).upper(),
                common.get_month_text(period_end_date.month).upper())
        else:
            period = '%s' % (common.get_month_text(period_start_date.month).upper())

        return {
            'doc_ids': docs.ids,
            'doc_model': 'hr.payslip',
            'docs': docs,
            'time': time,
            'tis': 'this is the value of tis',
            'formatLang': formatLang,
            'env': self.env,
            'period': period
        }

    def irt_map_xlsx_report(self, docids, data=None):
        if 'form' not in data:
            raise ValidationError('This action is under development')

        docs, period_start_date, period_end_date = self.get_docs_values(data)
        year = period_start_date.year
        if not docs:
            raise ValidationError(_('There is no payslips that match this criteria'))

        if period_start_date.month != period_end_date.month:
            period = '%s-%s' % (
                common.get_month_text(period_start_date.month).upper(),
                common.get_month_text(period_end_date.month).upper())
        else:
            period = '%s' % (common.get_month_text(period_start_date.month).upper())

        def get_vals_irt_payment(period, year, payslip_data):
            total_colect_amount = sum([payslip.amount_base_irt for payslip in payslip_data])
            total_liquid_amount = sum([abs(payslip.amount_irt) for payslip in payslip_data])
            total_other_amount = 0.0
            return {
                "period": period,
                "year": year,
                "payslip_values": [{
                    "code": payslip.employee_id.employee_number,
                    "employee_name": payslip.employee_id.name,
                    "irt_number": payslip.employee_id.fiscal_number,
                    "amount_base_irt": payslip.amount_base_irt,
                    "liquid_irt_amount": abs(payslip.amount_irt),
                    "other_amount": 0.0,
                    "average_rate_irt_amount": ((abs(payslip.amount_irt) * 100) / payslip.amount_base_irt)
                } for payslip in payslip_data],
                "total_colect_amount": total_colect_amount,
                "total_liquid_amount": total_liquid_amount,
                "total_other_amount": total_other_amount,
            }

        def get_irt_payment_xlsx(values):
            # TODO: create bank payment temp file
            temp_file = tempfile.NamedTemporaryFile(mode='w+b', delete=False, suffix=".xls")
            dir_path = temp_file.name
            file = temp_file.name.split('/')
            file[-1] = f"Mapa_de_IRT_{period}.xls"
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
            worksheet.merge_range("A1:F1", f"Mapa de Liquidação de IRT({values.get('period')}/{values.get('year')}",
                                  title_bold_blue)
            worksheet.write_string('G1', '(Valores em AKZ)', title_bold_blue)
            # Summary
            worksheet.write_string(f"A2", "Funcionário", bold_bordered_centered)
            worksheet.write_string(f"B2", "Nome", bold_bordered_centered)
            worksheet.write_string(f"C2", "Nº de Contribuinte", bold_bordered_centered)
            worksheet.write_string(f"D2", "Valor Colectável", bold_bordered_centered)
            worksheet.write_string(f"E2", "Liquidado", bold_bordered_centered)
            worksheet.write_string(f"F2", "Outros", bold_bordered_centered)
            worksheet.write_string(f"G2", "Taxa Média", bold_bordered_centered)

            # Content
            row = 3
            for line in values.get("payslip_values", []):
                worksheet.write_string(f"A{row}", line.get("code") if line.get("code") else " ", regular_bordered)
                worksheet.write_string(f"B{row}", line.get("employee_name"), regular_bordered)
                worksheet.write_string(f"C{row}", line.get("irt_number") if line.get("irt_number") else " ",
                                       regular_bordered)
                worksheet.write_string(f"D{row}", str(round(line.get("amount_base_irt"), 2)), regular_bordered)
                worksheet.write_string(f"E{row}", str(round(line.get("liquid_irt_amount"), 2)), regular_bordered)
                worksheet.write_string(f"F{row}", str(round(line.get("other_amount"), 2)), regular_bordered)
                worksheet.write_string(f"G{row}", str(round(line.get("average_rate_irt_amount"), 2)), regular_bordered)
                row += 1

            worksheet.merge_range(f"A{row}:C{row}", "Totais", bold_bordered_centered)
            worksheet.write_string(f"D{row}", str(values.get("total_colect_amount")), bold_bordered_centered)
            worksheet.write_string(f"E{row}", str(values.get("total_liquid_amount")), bold_bordered_centered)
            worksheet.write_string(f"F{row}", str(values.get("total_other_amount")), bold_bordered_centered)
            worksheet.write_string(f"G{row}", " ", bold_bordered_centered)

            workbook.close()
            return new_dir_path

        bank_vals = get_vals_irt_payment(period, year, docs)
        dir_path_file = get_irt_payment_xlsx(bank_vals)
        base_url = self.env['ir.config_parameter'].get_param('web.base.url')
        file_result = base64.b64encode(open(f'{dir_path_file}', 'rb').read())
        url_file = f'{base_url}/file/map/download?dir_path_file={dir_path_file}'
        return url_file
