import time
from datetime import datetime
from dateutil import relativedelta
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class WizardHRRemunerationMap(models.TransientModel):
    _name = 'wizard.hr.remuneration.map'
    _description = 'Print Remuneration Map'

    slip_filter_by = fields.Selection([('payslip_batch', 'Bayslip Batch'), ('payslip_date', 'Payslip Date')],
                                      'Filter By', required=True,
                                      help='Select the methond to capture the Payslips. You can choose Payslip Batch or by Date')
    hr_payslip_run_id = fields.Many2one('hr.payslip.run', 'Payslip Batch',
                                        help='Select the Payslip Batch for wich you want do generate the Salary map Report')
    start_date = fields.Date('Start Date', default=time.strftime('%Y-%m-01'))
    end_date = fields.Date('End Date',
                           default=str(datetime.now() + relativedelta.relativedelta(months=+1, day=1, days=-1))[:10])
    url_download = fields.Char("URL Download")
    contract_type_id = fields.Many2one('hr.contract.type', string="Contract Type")

    @api.constrains('start_date', 'end_date')
    def check_dates(self):
        if self.start_date > self.end_date:
            raise ValidationError('Start Date must be lower than End Date')

    def print_report_xlsx(self):
        if self.env.company.country_id.code == "AO":
            data = {
                'form': self.read(
                    [
                        'slip_filter_by',
                        'hr_payslip_run_id',
                        'start_date',
                        'end_date',
                        'contract_type_id'])[
                    0]}
            self.url_download = self.env['report.remuneration_map'].remuneration_map_report(self, 'xlsx', data=data)
            return {"type": "ir.actions.act_url", "url": self.url_download, "target": "new"}

    def print_report_xml(self):
        if self.env.company.country_id.code == "AO":
            data = {
                'form': self.read(
                    [
                        'slip_filter_by',
                        'hr_payslip_run_id',
                        'start_date',
                        'end_date',
                        'contract_type_id'])[
                    0]}
            self.url_download = self.env['report.remuneration_map'].remuneration_map_report(self, 'xml', data=data)
            return {"type": "ir.actions.act_url", "url": self.url_download, "target": "new"}
