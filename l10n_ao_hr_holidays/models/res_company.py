from odoo import fields, models, api
from datetime import datetime, timedelta, date


class ResCompany(models.Model):
    _inherit = "res.company"

    take_vacation_after_admission = fields.Integer(
        "Direito a gozar férias após a admissão (Nacional)", default=6
    )
    right_to_more_vacation = fields.Integer('Direito a mais')
    type_of_dependents = fields.Selection(
        [
            ("pai", "PAI"),
            ("mae", "Mãe"),
            ("filho(a)", "Filho(a)"),
            ("conjuge", "CÔNJUGE"),
            ("tio(a)", "Tio(a)"),
            ("sobrinho(a)", "Sobrinho(a)"),
        ],
        string="Tipo de Dependentes",
    )
    dependent_limit = fields.Integer("Limite de Dependentes", default=5)
    age_range_dependent_children = fields.Integer("Faixa etária dos dependentes")
    dependent_children_until = fields.Integer("Até", default=14)
    vacation_alert = fields.Selection(
        [
            ("1", "Janeiro"),
            ("2", "Fevereiro"),
            ("3", "Março"),
            ("4", "Abril"),
            ("5", "Maio"),
            ("6", "Junho"),
            ("7", "Julho"),
            ("8", "Agosto"),
            ("9", "Setembro"),
            ("10", "Outubro"),
            ("11", "Novembro"),
            ("12", "Dezembro"),
        ],
        string="Alerta de Férias (Mês)", default='1',
    )
    vacation_subtract_days_limit_nacional = fields.Integer(
        "Limite de Dias Subtraídos de Férias por Falta Injustificadas (Nacionais)")
    vacation_balance_report_start_date = fields.Integer(
        "Relatório de saldo de Férias: Ano de início",
    )
    vacation_balance_report_update_month = fields.Integer(
        string='Relatório de saldo de Férias: Mês de abertura do novo ano', default=10
    )
    vacation_update_balance = fields.Selection(
        [
            ("1", "Janeiro"),
            ("2", "Fevereiro"),
            ("3", "Março"),
            ("4", "Abril"),
            ("5", "Maio"),
            ("6", "Junho"),
            ("7", "Julho"),
            ("8", "Agosto"),
            ("9", "Setembro"),
            ("10", "Outubro"),
            ("11", "Novembro"),
            ("12", "Dezembro"),
        ],
        string="Mês de actualização do saldo do ano anterior (Zerar)", default='3',
    )

    @api.model
    def cron_update_month_balance_report(self):
        current_date = datetime.now().date()
        companies = self.env['res.company'].search([])
        for record in companies:
            if record.vacation_balance_report_update_month:
                if current_date.month == record.vacation_balance_report_update_month:
                    record.vacation_balance_report_start_date = current_date.year + 1
