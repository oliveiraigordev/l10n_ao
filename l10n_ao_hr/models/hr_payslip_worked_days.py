# -*- coding:utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class PayslipWorkedDays(models.Model):
    _inherit = 'hr.payslip.worked_days'

    @api.depends('is_paid', 'number_of_hours', 'payslip_id', 'contract_id.wage', 'payslip_id.sum_worked_hours')
    def _compute_amount(self):
        if self.env.company.country_id.code == "AO":
            for worked_days in self:
                if worked_days.payslip_id.edited or worked_days.payslip_id.state not in ['draft', 'verify']:
                    continue
                if not worked_days.contract_id or worked_days.code == 'OUT':
                    worked_days.amount = 0
                    continue
                if worked_days.payslip_id.wage_type == "hourly":
                    worked_days.amount = worked_days.payslip_id.contract_id.hourly_wage * worked_days.number_of_hours if worked_days.is_paid else 0
                else:
                    contract_wage = 0
                    if worked_days.payslip_id.contract_type_id.code in ['EXPATRIADO', 'EXPATRIADO_RESIDENTE']:
                        if worked_days.payslip_id.contract_type_id.code in ['EXPATRIADO',
                                                                            'EXPATRIADO_RESIDENTE'] and worked_days.payslip_id.process_automatically_exchange:
                            if not worked_days.payslip_id.salary_kz:
                                if self.env.company.currency == 'USD' or self.env.company.currency == 'AOA':
                                    contract_wage = worked_days.payslip_id.contract_id.get_kz_amount(
                                        worked_days.payslip_id.contract_id.total_paid_usd)
                                elif self.env.company.currency == 'EUR':
                                    contract_wage = worked_days.payslip_id.contract_id.get_euro_kz_amount(
                                        worked_days.payslip_id.contract_id.total_paid_usd)
                            else:
                                contract_wage = worked_days.payslip_id.contract_id.contract_wage
                        elif worked_days.payslip_id.contract_type_id.code in ['EXPATRIADO',
                                                                              'EXPATRIADO_RESIDENTE'] and not worked_days.payslip_id.process_automatically_exchange:
                            if not worked_days.payslip_id.salary_kz:
                                contract_wage = (
                                        worked_days.payslip_id.contract_id.total_paid_usd * worked_days.payslip_id.exchange_rate)
                            else:
                                contract_wage = worked_days.payslip_id.contract_id.contract_wage
                    else:
                        contract_wage = worked_days.payslip_id.contract_id.contract_wage

                    # CALCULAR O SALARIO BASE COM BASE NOS DIAS TRABALHADOS
                    amount = (contract_wage / self.env.company.calendar_days_moth_salary) * worked_days.number_of_days
                    worked_days.amount = amount if worked_days.is_paid else 0
        else:
            return super(PayslipWorkedDays, self)._compute_amount()
