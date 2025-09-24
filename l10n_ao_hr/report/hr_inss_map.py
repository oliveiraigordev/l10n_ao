# -*- coding: utf-8 -*-

from datetime import datetime, time
from odoo import api, models, fields, _
from dateutil.parser import parse
from odoo.exceptions import ValidationError
from odoo.tools.misc import formatLang
from . import common
import base64, xlsxwriter, os, tempfile


class ReportHRINSSMap(models.AbstractModel):
    _name = 'report.l10n_ao_hr.inss_map'
    _description = 'INSS Report Map'

    def get_docs_values(self, data):
        slip_filter_by = data['form']['slip_filter_by']
        contract_tipe_id = data['form']['contract_type_id']
        if slip_filter_by == 'payslip_batch':
            slip_id = data['form']['hr_payslip_run_id'][0]
            docs = self.env['hr.payslip'].search(
                [('payslip_run_id', '=', slip_id),
                 ('employee_id.contract_type.code', 'not in', ['EXPATRIADO']),
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

            docs = self.env['hr.payslip'].search(
                [('date_to', '>=', start_date), ('date_to', '<=', end_date),
                 ('employee_id.contract_type.code', 'not in', ['EXPATRIADO']),
                 ('company_id', '=', self.env.company.id), ('state', 'in', ['done', 'paid'])])

            if contract_tipe_id:
                docs = docs.filtered(lambda p: p.contract_type_id.id == contract_tipe_id[0])

        return docs, period_start_date, period_end_date

    @api.model
    def _get_report_values(self, docids, data=None):
        current_date = datetime.now()
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
            'period_month': period,
            'period_year': str(period_end_date.year),
            'day': current_date.day,
            'month': common.get_month_text(current_date.month).upper(),
            'year': current_date.year
        }

    def bank_map_xlsx_report(self, docids, data=None):
        if 'form' not in data:
            raise ValidationError('This action is under development')

        docs, period_start_date, period_end_date = self.get_docs_values(data)
        if not docs:
            raise ValidationError(_('There is no payslips that match this criteria'))

        year = period_start_date.year
        if period_start_date.month != period_end_date.month:
            period = '%s-%s' % (
                common.get_month_text(period_start_date.month).upper(),
                common.get_month_text(period_end_date.month).upper())
        else:
            period = '%s' % (common.get_month_text(period_start_date.month).upper())

        def get_vals_inss_map(period, year, payslip_data):
            total_base_salary = sum([payslip_line.total for payslip_line in payslip_data.line_ids.filtered(lambda p: p.code == 'BASE')])
            total_extra_amount = sum([payslip_line.total for payslip_line in payslip_data.line_ids.filtered(lambda p: p.salary_rule_id.inss_rule and p.code not in ['BASE', 'FAMI', 'sub_fam'])])
            total_inss_amount = sum([payslip.collected_material_inss for payslip in payslip_data])
            total_inss_3 = sum([(payslip.collected_material_inss * 0.03) for payslip in payslip_data])
            total_inss_8 = sum([(payslip.collected_material_inss * 0.08) for payslip in payslip_data])
            return {
                "activity": self.env.company.partner_id.industry_id.name,
                "zip": self.env.company.zip if self.env.company.zip else "0000",
                "num_contrib_social": self.env.company.company_security_number if self.env.company.company_security_number else "",
                "company_name": self.env.company.name,
                "address": f"{self.env.company.street}" if not self.env.company.street2 else \
                    f"{self.env.company.street}, {self.env.company.street2}",
                "location": self.env.company.city,
                "phone": self.env.company.phone,
                "identificador_pessoa_coletiva": self.env.company.vat,
                "period": period,
                "year": year,
                "doc_number": "",
                "payslip_values": [{
                    "code": payslip.employee_id.registration_number if payslip.employee_id.registration_number else "",
                    "employee_name": payslip.employee_id.name,
                    "category": payslip.employee_id.job_id.name if payslip.employee_id.job_id.name else "",
                    "base_salary": round(payslip.line_ids.filtered(lambda p: p.code == 'BASE')[0].total, 2),
                    "extra_amount": round(sum([extra_amount.total for extra_amount in payslip.line_ids.filtered(lambda p: p.salary_rule_id.inss_rule and p.code not in ['BASE', 'FAMI', 'sub_fam'])]), 2),
                    "inss_total": payslip.collected_material_inss,
                    "inss_3": (payslip.collected_material_inss * 0.03),
                    "inss_8": (payslip.collected_material_inss * 0.08),
                    "beneficiary_number": payslip.employee_id.social_security
                } for payslip in payslip_data],
                "total_base_salary": total_base_salary,
                "total_extra_amount": total_extra_amount,
                "total_inss_amount": total_inss_amount,
                "total_inss_3": total_inss_3,
                "total_inss_8": total_inss_8,
                "total_11": total_inss_3 + total_inss_8,
            }

        def get_inss_map_xlsx(values):
            # TODO: create INSS temp file
            temp_file = tempfile.NamedTemporaryFile(mode='w+b', delete=False, suffix=".xls")
            dir_path = temp_file.name
            file = temp_file.name.split('/')
            file[-1] = f"Mapa_de_INSS_{period}.xls"
            new_dir_path = '/'.join(map(str, file))
            os.rename(dir_path, new_dir_path)

            workbook = xlsxwriter.Workbook(new_dir_path)
            worksheet = workbook.add_worksheet()
            worksheet.set_column("A:I", 20)
            worksheet.set_column("F:F", 25)
            # Styles
            bold_bordered_centered = workbook.add_format(
                {"bold": True, "border": 1, "align": "center", "valign": "vcenter"})
            regular_centered = workbook.add_format({"border": 1, "valign": "vcenter", "align": "center"})
            regular_bordered = workbook.add_format({"border": 1, "valign": "vcenter"})
            regular_bold = workbook.add_format({"bold": True, "border": 1, "valign": "vcenter"})
            # Title
            worksheet.merge_range("A1:E5", "REPÚBLICA DE ANGOLA \r\n \t INSTITUTO NACIONAL DE SEGURANÇA SOCIAL",
                                  regular_centered)
            # Title Company Informations
            worksheet.write_string("F1", "ACTIVIDADE", regular_bold)
            worksheet.write_string("G1", values.get('activity'), regular_bordered)
            worksheet.write_string("H1", "Nº CONTRIB. SOCIAL", regular_bold)
            worksheet.write_string("I1", values.get('num_contrib_social'), regular_bordered)
            worksheet.write_string("F2", "NOME", regular_bold)
            worksheet.merge_range("G2:I2", values.get('company_name'), regular_bordered)
            worksheet.write_string("F3", "MORADA", regular_bold)
            worksheet.merge_range("G3:I3", values.get('address'), regular_bordered)
            worksheet.write_string("F4", "LOCALIDADE", regular_bold)
            worksheet.write_string("G4", values.get('location'), regular_bordered)
            worksheet.write_string("H4", "TELEFONE", regular_bold)
            worksheet.write_string("I4", values.get('phone'), regular_bordered)
            worksheet.write_string("F5", "CÓDIGO POSTAL", regular_bold)
            worksheet.write_string("G5", values.get('zip'), regular_bordered)
            worksheet.write_string("H5", "IDENTIFICAÇÃO PESSOA COLETIVA", regular_bold)
            worksheet.write_string("I5", values.get('identificador_pessoa_coletiva'), regular_bordered)
            # TODO: Main Table Title
            worksheet.merge_range("A7:G7",
                                  f"FOLHA DE REMUNERAÇÕES REFERENTE AO MÊS DE {values.get('period')} DE {values.get('year')}",
                                  regular_bold)
            worksheet.write_string("H7", "FOLHA Nº", regular_bold)
            worksheet.write_string("I7", values.get('doc_number'), regular_bordered)
            # TODO: Main table header
            worksheet.write_string("A9", "Nº", bold_bordered_centered)
            worksheet.write_string("B9", "Nome Completo", bold_bordered_centered)
            worksheet.write_string("C9", "Categoria", bold_bordered_centered)
            worksheet.write_string("D9", "Salário Base", bold_bordered_centered)
            worksheet.write_string("E9", "Remuneração Adicional", bold_bordered_centered)
            worksheet.write_string("F9", "Salário Líquido", bold_bordered_centered)
            worksheet.write_string("G9", "3% Salário Líquido", bold_bordered_centered)
            worksheet.write_string("H9", "8% Salário Líquido", bold_bordered_centered)
            worksheet.write_string("I9", "Nº Beneficiário", bold_bordered_centered)
            # Content
            row = 10
            for line in values.get("payslip_values", []):
                worksheet.write_string(f"A{row}", line.get("code"), regular_bordered)
                worksheet.write_string(f"B{row}", line.get("employee_name"), regular_bordered)
                worksheet.write_string(f"C{row}", line.get("category"), regular_bordered)
                worksheet.write_string(f"D{row}", str(line.get("base_salary")), regular_bordered)
                worksheet.write_string(f"E{row}", str(line.get("extra_amount")), regular_bordered)
                worksheet.write_string(f"F{row}", str(line.get("inss_total")), regular_bordered)
                worksheet.write_string(f"G{row}", str(line.get("inss_3")), regular_bordered)
                worksheet.write_string(f"H{row}", str(line.get("inss_8")), regular_bordered)
                worksheet.write_string(f"I{row}", str(line.get("beneficiary_number")), regular_bordered)
                row += 1

            worksheet.merge_range(f"A{row}:C{row}", "Totais", bold_bordered_centered)
            worksheet.write_string(f"D{row}", str(values.get("total_base_salary")), bold_bordered_centered)
            worksheet.write_string(f"E{row}", str(values.get("total_extra_amount")), bold_bordered_centered)
            worksheet.write_string(f"F{row}", str(values.get("total_inss_amount")), bold_bordered_centered)
            worksheet.write_string(f"G{row}", str(values.get("total_inss_3")), bold_bordered_centered)
            worksheet.write_string(f"H{row}", str(values.get("total_inss_8")), bold_bordered_centered)
            worksheet.write_string(f"I{row}", "", bold_bordered_centered)

            # TODO: End of page summary
            row += 2
            totals = [
                ("Total dos Salários Líquidos", values.get("total_inss_amount")),
                ("8% Sobre o Salário Líquido / Empresa", str(round(values.get("total_inss_8"), 2))),
                ("3% Sobre o Salário Líquido / Empresa", str(round(values.get("total_inss_3"), 2))),
                ("11% Total a Depositar", str(round(values.get("total_11"), 2))),
            ]
            for title, value in totals:
                worksheet.merge_range(f"A{row}:C{row}", title, regular_bold)
                worksheet.write_string(f"D{row}", str(value), regular_bold)
                row += 1

            workbook.close()
            return new_dir_path

        inss_vals = get_vals_inss_map(period, year, docs)
        dir_path_file = get_inss_map_xlsx(inss_vals)
        base_url = self.env['ir.config_parameter'].get_param('web.base.url')
        file_result = base64.b64encode(open(f'{dir_path_file}', 'rb').read())
        url_file = f'{base_url}/file/map/download?dir_path_file={dir_path_file}'
        return url_file
