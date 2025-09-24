from odoo import _
from dateutil.parser import parse

months_collection = {
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


def get_month_text(month_number):
    return months_collection[month_number]


def get_docs_values(self, data):
    slip_filter_by = data['form']['slip_filter_by']
    if slip_filter_by == 'payslip_batch':
        slip_id = data['form']['hr_payslip_run_id'][0]
        docs = self.env['hr.payslip'].search(
            [('payslip_run_id', '=', slip_id),
             ('employee_id.contract_type.code', 'not in', ['EXPATRIADO', 'EXPATRIADO_RESIDENTE']),
             ('company_id', '=', self.env.company.id)])
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
             ('employee_id.contract_type.code', 'not in', ['EXPATRIADO', 'EXPATRIADO_RESIDENTE']),
             ('company_id', '=', self.env.company.id), ('state', 'in', ['done', 'paid'])])

    return docs, period_start_date, period_end_date
