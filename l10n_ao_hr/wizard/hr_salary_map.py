import time
from datetime import datetime
from dateutil import relativedelta
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class WizardHRSalaryMap(models.TransientModel):
    _name = 'wizard.hr.salary.map'
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

    @api.constrains('start_date', 'end_date')
    def check_dates(self):
        if self.start_date > self.end_date:
            raise ValidationError('Start Date must be lower than End Date')

    def print_report_xlsx(self):
        if self.env.company.country_id.code == "AO":
            result = self.print_report(report_file='xlsx')
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

    def action_download_salary_file(self):
        if self.env.company.country_id.code == "AO":
            return self.download_salary_file(self.url_download)

    def download_salary_file(self, url_download):
        self.url_download = False
        return {"type": "ir.actions.act_url", "url": url_download, "target": "new"}

    def print_report(self, report_file=False):
        if self.env.company.country_id.code == "AO":
            data = {'form': self.read(['slip_filter_by', 'hr_payslip_run_id', 'start_date', 'end_date'])[0]}
            if report_file:
                self.url_download = self.env['report.l10n_ao_hr.salary_map'].salary_map_xlsx_report(self, data)
            else:
                return self.env.ref('l10n_ao_hr.action_salary_map').report_action(self, data)
