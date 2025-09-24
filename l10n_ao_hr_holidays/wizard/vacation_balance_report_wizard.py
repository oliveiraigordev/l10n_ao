from datetime import date
import re

from odoo import models, fields, api
from odoo.exceptions import ValidationError
from ..models.vacation_balance_report import VacationBalanceReport


class VacationBalanceReportWizard(models.TransientModel):
    _name = 'vacation.balance.report.wizard'
    _description = 'Wizard Criar de relatório saldo de férias'

    company_id = fields.Many2one('res.company', string='Empresa', defaul=lambda self: self.env.company.id)
    year = fields.Integer(string='Ano de referência', required=True, default=lambda self: fields.Date.today().year)
    employee_ids = fields.Many2many(comodel_name="hr.employee", string="Funcionários", domain=[('active', '=', True)])
    all_employees = fields.Boolean(string="Todos os funcionários", default=True)

    def _check_year_pattern(self, year):
        pattern = r'^\d{4}$'
        if bool(re.match(pattern, str(year))):
            year_pattern = year
            return year_pattern <= fields.Date.today().year
        return False

    def get_employees(self):
        domain = [("active", "=", True)]
        if self.env.context.get('report_creation', False):
            domain.extend([
                ("company_id", "=", self.company_id.id),
                ("first_contract_date", "!=", False)
            ])
        else:
            company_id = self.env.company
            domain.append(("company_id", "=", company_id.id))

        employees = self.env["hr.employee"].search(domain)
        return employees

    def action_create_vacation_balance_report(self):
        if not self.all_employees:
            filtered_employees = self.employee_ids.filtered(lambda e: e.admission_date)
        else:
            employees = self.with_context(report_creation=True).get_employees()
            filtered_employees = employees.filtered(
                lambda e: (
                        e.contract_type and (
                        (e.admission_date) and
                        (e.contract_type.code == "EXPATRIADO" and e.holiday_processing_policy) or
                        (e.contract_type.code in ["NACIONAL", "EXPATRIADO_RESIDENTE"])
                )
                )
            )

        for employee in filtered_employees:
            vacation_report = VacationBalanceReport.with_context(
                self.env['vacation.balance.report']).create_vacation_balance_report(employee, date(self.year, 12, 31))
        return

    def update_vacation_balance_report(self):
        employees = self.get_employees()
        filtered_employees = employees.filtered(
            lambda e: (
                    e.contract_type and (
                    (e.admission_date) and
                    (e.contract_type.code == "EXPATRIADO" and e.holiday_processing_policy) or
                    (e.contract_type.code in ["NACIONAL", "EXPATRIADO_RESIDENTE"])
            )
            )
        )
        for employee in filtered_employees:
            VacationBalanceReport.with_context(self.env['vacation.balance.report']).set_vacation_days_enjoyed_overdue(
                employee)
        return
