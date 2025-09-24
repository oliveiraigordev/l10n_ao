import time
from datetime import datetime
from dateutil import relativedelta
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
from . import common
import base64, xlsxwriter, os, tempfile


class WizardHRINSSMap(models.TransientModel):
    _name = 'wizard.hr.inss.map'
    _description = 'Print Salary Map'

    slip_filter_by = fields.Selection([('payslip_batch', 'Bayslip Batch'), ('payslip_date', 'Payslip Date')],
                                      'Filter By', required=True,
                                      help='Select the methond to capture the Payslips. You can choose Payslip Batch or by Date')
    hr_payslip_run_id = fields.Many2one('hr.payslip.run', 'Payslip Batch',
                                        help='Select the Payslip Batch for wich you want do generate the Salary map Report')
    start_date = fields.Date('Start Date', default=time.strftime('%Y-%m-01'))
    end_date = fields.Date('End Date',
                           default=str(datetime.now() + relativedelta.relativedelta(months=+1, day=1, days=-1))[:10])
    url_download = fields.Char("URL Download")
    tipe_file = fields.Selection([('normal', 'Normal'), ('complementary_first', 'Primeira Complementar')],
                                 string="File Type")
    contract_type_id = fields.Many2one('hr.contract.type', string="Contract Type")

    @api.constrains('start_date', 'end_date')
    def check_dates(self):
        if self.start_date > self.end_date:
            raise ValidationError('Start Date must be lower than End Date')

    def print_report_xlsx(self):
        if self.env.company.country_id.code == "AO":
            data = {
                'form': self.read(
                    ['slip_filter_by', 'hr_payslip_run_id', 'start_date', 'end_date', 'tipe_file', 'contract_type_id'])[
                    0]}
            self.url_download = self.env['report.l10n_ao_hr.inss_map'].bank_map_xlsx_report(self, data)
            return {"type": "ir.actions.act_url", "url": self.url_download, "target": "new"}

    def print_report(self, report_file=False):
        if self.env.company.country_id.code == "AO":
            data = {
                'form': self.read(
                    ['slip_filter_by', 'hr_payslip_run_id', 'start_date', 'end_date', 'tipe_file', 'contract_type_id'])[
                    0]}
            return self.env.ref('l10n_ao_hr.action_inss_map').report_action(self, data)

    def print_report_txt(self):
        if self.env.company.country_id.code == "AO":
            data = {
                'form': self.read(
                    ['slip_filter_by', 'hr_payslip_run_id', 'start_date', 'end_date', 'tipe_file', 'contract_type_id'])[
                    0]}
            return {"type": "ir.actions.act_url", "url": self.inss_map_txt_report(data), "target": "new"}

    def inss_map_txt_report(self, data):
        if 'form' not in data:
            raise ValidationError('This action is under development')

        if not self.env.company.company_security_number:
            raise UserError(_("Please, set the Social Security Number in the Company's settings."))

        if not self.tipe_file:
            raise UserError(_("Please, select the type of file."))

        docs, period_start_date, period_end_date = common.get_docs_values(self, data)
        if not docs:
            raise ValidationError('There is no payslips that match this criteria')

        def get_inss_map_txt(year, month, day, docs):
            # create INSS temp file
            temp_file = tempfile.NamedTemporaryFile(mode='w+b', delete=False, suffix=".txt")
            dir_path = temp_file.name
            file = temp_file.name.split('/')
            file[
                -1] = f'{self.env.company.company_security_number}{year}{month}{0 if self.tipe_file == "normal" else 1}'
            new_dir_path = '/'.join(map(str, file))
            os.rename(dir_path, new_dir_path)

            output_file = self.create_inss_text(docs, year, month, day)

            with open(new_dir_path, "w", encoding="utf-8") as inss_txt_file:
                inss_txt_file.write(output_file)

            # Fecha o arquivo
            inss_txt_file.close()
            return new_dir_path

        dir_path_file = get_inss_map_txt(period_end_date.year, f"{period_end_date.month:02}",
                                         f"{period_end_date.day:02}", docs)
        base_url = self.env['ir.config_parameter'].get_param('web.base.url')
        file_result = base64.b64encode(open(f'{dir_path_file}', 'rb').read())
        url_file = f'{base_url}/file/map/download?dir_path_file={dir_path_file}'
        return url_file

    def create_inss_text(self, docs, year, month, day):
        # O PRIMEIRa LINHA DO ARQUIVO (HEADER)
        file_reference = 'N' if self.tipe_file == "normal" else 'C'
        date = f"{day}{month}{year}"  # Garantir sempre 8 dígitos
        ref = (file_reference or "")[:10].ljust(10)  # posições 11-20
        ss = (self.env.company.company_security_number or "")[:41].ljust(41)  # posições 21-61
        vat = (self.env.company.vat or "")[:20].ljust(20)  # posições 62-81
        name = (self.env.company.name or "")[:100].ljust(100)
        header_line = f'00{date}{ref}{ss}{vat}{name}'
        lines = [header_line]
        for payslip in docs:
            # Linhas do funcionário
            employee_line = self.create_employee_lines(payslip)
            lines.append(employee_line)

        # ULTIMA LINHA DO ARQUIVO
        total_lines = (str(len(docs)) or '').ljust(10, '0')[:10]  # posições 3-12
        blank_line = ("0000000000")[:10].ljust(10)  # posições 13-22

        total_base_salary = (str(int(sum([payslip.remuneration_inss_base for payslip in docs]))))[
                            :14].ljust(14)  # posições 23-36
        total_extra_amount = (str(int(
            sum([payslip.remuneration_inss_extra for payslip in docs]))))[
                             :14].ljust(14)  # posições 37-50
        employee_id = self.env['hr.employee'].sudo().search([('user_id', '=', self.env.uid)], limit=1)
        employee_name = (employee_id.name or '')[:40].ljust(40)  # posições 51-90
        employee_email = (employee_id.work_email or '')[:50].ljust(50)  # posições 91-140
        blank_line1 = ("")[:40].ljust(40)  # posições 141-180

        footer_line = f'99{total_lines}{blank_line}{total_base_salary}{total_extra_amount}{employee_name}{employee_email}{blank_line1}'
        lines.append(footer_line)
        return "\n".join(lines)

    def create_employee_lines(self, payslip):
        # Linha do Registro
        date_end = payslip.contract_id.date_end.strftime(
            '%d%m%Y') if payslip.contract_id.date_end else False

        social_security = (payslip.employee_id.social_security or "")[:9].ljust(9)  # posições 3-11
        social_security_new = ("")[:20].ljust(20)  # posições 12-31
        name = (payslip.employee_id.name or '')[:70].ljust(70)  # posições 32-101
        category = ('00000')[:5].ljust(5)  # posições 102-106
        base_salary = (str(int(payslip.remuneration_inss_base)) or '').ljust(14, '0')[
                      :14]  # posições 107-120
        other_remuneration = (str(int(payslip.remuneration_inss_extra)) or "").ljust(14, '0')[
                             :14]  # posições 121-134
        date_start = (payslip.contract_id.date_start.strftime(
            '%d%m%Y') if payslip.contract_id.date_start else '').ljust(8, '0')[:8]  # posições 135-142
        date_end = (date_end or '').ljust(8, '0')[:8]  # posições 143-150
        blank_line = ("")[:30].ljust(30)  # posições 151-180

        employee_line = f'10{social_security}{social_security_new}{name}{category}{base_salary}{other_remuneration}{date_start}{date_end}{blank_line}'
        return employee_line
