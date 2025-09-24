from odoo import models, fields, tools, api, _
import logging

_logger = logging.getLogger(__name__)


class ExtraHoursReport(models.Model):
    _name = 'extra.hours.report'
    _description = ' Overtime Posting Report'
    _order = 'id desc'

    employee_id = fields.Many2one('hr.employee', string='Funcionário')
    department_id = fields.Many2one("hr.department", string='Departamento')
    country_id = fields.Many2one("res.country", string='Nacionalidade')
    job_id = fields.Many2one("hr.job", string='Cargo/Função')
    gender = fields.Char(string='Gênero')
    company_id = fields.Many2one('res.company', string="Empresa")
    input_type_id = fields.Many2one('hr.payslip.input', string="Tipo de entrada da folha de pagamento", ondelete='cascade')
    type_of_overtime = fields.Selection([('normal', 'Normal'), ('weekend', 'Weekend')], string="Tipo de horas Extra")
    date = fields.Date("Data")
    hours = fields.Float("Total de Horas")
    amount = fields.Float("Valor")
    year = fields.Char(string='Ano')
