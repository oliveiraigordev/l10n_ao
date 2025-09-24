# -*- coding: utf-8 -*-
import time
from odoo import api, models, fields, _
from dateutil.parser import parse
from odoo.exceptions import ValidationError, UserError
from odoo.tools.misc import formatLang
from . import common
import base64


class ReportHRSalaryMap(models.AbstractModel):
    _name = 'report.l10n_ao_hr.salary_map'
    _description = 'Salary Report Map'

    def get_docs_values(self, data):
        slip_filter_by = data['form']['slip_filter_by']
        if slip_filter_by == 'payslip_batch':
            slip_id = data['form']['hr_payslip_run_id'][0]
            docs = self.env['hr.payslip'].search(
                [('payslip_run_id', '=', slip_id), ('company_id', '=', self.env.company.id)])
            period_date = self.env['hr.payslip.run'].browse(slip_id).date_end
        else:
            start_date = data['form']['start_date']
            end_date = data['form']['end_date']
            if type(end_date) is str:
                period_date = parse(end_date)
            else:
                period_date = end_date
            docs = self.env['hr.payslip'].search([('date_to', '>=', start_date), ('date_to', '<=', end_date),
                                                  ('company_id', '=', self.env.company.id),
                                                  ('state', 'in', ['done', 'paid'])])
        return docs, period_date

    @api.model
    def _get_report_values(self, docids, data=None):
        docs = None
        if 'form' not in data:
            raise ValidationError('This action is under development')

        docs, period_date = self.get_docs_values(data)
        if not docs:
            raise UserError(_('No documents were found in the system associated with this company'))

        return {
            'doc_ids': docs.ids,
            'doc_model': 'hr.payslip',
            'docs': docs,
            'time': time,
            'tis': 'this is the value of tis',
            'formatLang': formatLang,
            'env': self.env,
            'period': '%s/%d' % (common.get_month_text(period_date.month).upper(), period_date.year)
        }

    def salary_map_xlsx_report(self, docids, data=None):
        payslip_data = []
        if 'form' not in data:
            raise ValidationError('This action is under development')

        docs, period = self.get_docs_values(data)
        if not docs:
            raise ValidationError(_('There is no payslips that match this criteria'))

        base_url = self.env['ir.config_parameter'].get_param('web.base.url')
        year = period.year
        dir_path_file = self.create_temp_xlsx_file(period, year, docs)
        file_result = base64.b64encode(open(f'{dir_path_file}', 'rb').read())
        url_file = f'{base_url}/file/map/download?dir_path_file={dir_path_file}'
        return url_file
