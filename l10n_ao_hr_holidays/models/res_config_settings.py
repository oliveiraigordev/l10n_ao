from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    take_vacation_after_admission = fields.Integer(
        "Direito a gozar férias após a admissão (Nacional)",
        default=6,
        related="company_id.take_vacation_after_admission",
        readonly=False,
    )
    right_to_more_vacation = fields.Integer(
        "Direito a mais",
        related="company_id.right_to_more_vacation",
        readonly=False,
    )
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
        related="company_id.type_of_dependents",
        readonly=False,
    )
    dependent_limit = fields.Integer(
        "Limite de Dependentes",
        default=5,
        related="company_id.dependent_limit",
        readonly=False,
    )
    age_range_dependent_children = fields.Integer(
        "Faixa etária dos dependentes",
        related="company_id.age_range_dependent_children",
        readonly=False,
    )
    dependent_children_until = fields.Integer(
        "Até",
        default=14,
        related="company_id.dependent_children_until",
        readonly=False,
    )
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
        related="company_id.vacation_alert",
        string="Alerta de Férias (Mês)",
        readonly=False,
    )
    vacation_subtract_days_limit_nacional = fields.Integer(
        "Limite de Dias Subtraídos de Férias por Falta Injustificadas (Nacionais)",
        related="company_id.vacation_subtract_days_limit_nacional",
        readonly=False,
    )
    # dont_validate_vacation = fields.Boolean(string='Não valida regras de férias',
    #                                         related="company_id.dont_validate_vacation",
    #                                         readonly=False, )
    vacation_balance_report_start_date = fields.Integer(string='Relatório de saldo de Férias: Ano de início',
                                                        related="company_id.vacation_balance_report_start_date",
                                                        readonly=False, )
    vacation_balance_report_update_month = fields.Integer(
        string='Relatório de saldo de Férias: Mês de abertura do novo ano',
        related="company_id.vacation_balance_report_update_month",
        readonly=False, )
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
        related="company_id.vacation_update_balance",
        string="Mês de actualização do saldo do ano anterior (Zerar)",
        readonly=False,
    )
