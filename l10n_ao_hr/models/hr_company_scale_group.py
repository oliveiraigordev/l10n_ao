from odoo import models, fields, api


class HRSalaryScaleSteps(models.Model):
    _name = 'hr.salary.scale.steps'
    _description = 'Employee Salary Scale steps'

    salary_scale_id = fields.Many2one('hr.salary.scale', string='Escala Salarial', required=True)
    name = fields.Char('Nome', required=True)
    percentage = fields.Char('Percentual', default='Base Step')
    amount_in_dollar = fields.Float('Montante em Dólares')
    amount_in_euro = fields.Float('Montante em Euro')
    amount_in_kwanza = fields.Float('Montante em Kwanza', required=True)
    irt_akz_compensation_amount = fields.Float('Montante da Compensação de IRT/Akz')


class HRSalaryScale(models.Model):
    _name = 'hr.salary.scale'
    _description = 'Employee Salary Scale'

    name = fields.Char('Nome', required=True)
    hierarchical_level_id = fields.Many2one('hr.hierarchical.level', string='Nível hierárquico', required=True)
    job_id = fields.Many2one('hr.job', string='Função/Cargo', required=True)
    steps_ids = fields.One2many('hr.salary.scale.steps', 'salary_scale_id', string='Nível')


class HRCompanyScale(models.Model):
    _name = 'hr.company.scale.group'
    _description = 'Company Scale Group'
    _order = 'name'

    name = fields.Char('Nome', compute='_compute_name')
    scale = fields.Selection([('big', 'Grande Empresa'), ('average', 'Média Empresa'), ('small', 'Pequena Empresa'),
                              ('micro', 'Micro Empresa'), ('others', 'Outros')],
                             string="Tipo de Empesa", required=True)
    shift_work = fields.Float('Trabalho por Turnos', help="Percentagem dos Preventos e Descontos", required=True)
    night_work = fields.Float('Trabalho Noturno', help="Percentagem dos Preventos e Descontos", required=True)
    limit_of_30_hours_per_month = fields.Float('Limite Percentual de 30 Horas por Mês', required=True)
    limit_hours = fields.Integer('Limite de Horas por Mês', required=True)
    hours_exceeding_30_hours_per_month = fields.Float('Percentagem de Horas que Excedem 30 Horas por Mês')
    work_on_rest_days = fields.Float('Percentagem de Trabalho nos dias de Descanso')
    seniority_limit = fields.Integer('Limite de Antiguidade', required=True)
    seniority_percentage = fields.Float('Percentagem de Antiguidade', required=True)
    availability_system = fields.Float('Sistema de Disponibilidade', required=True)
    not_influence_number_of_years = fields.Boolean('Não influencia o número de anos de trabalho do trabalhador')
    working_days_moth_salary = fields.Float('Dias úteis que representam um mês para o cálculo do salário', default=22)
    calendar_days_moth_salary = fields.Float('Dias corridos que representam um mês para cálculos salariais', default=30)
    extra_hour_are_not_fractions_time_less_than = fields.Float('Não são consideradas fracções de tempo inferiores a',
                                                               default=15)
    extra_hour_counted_half_hour = fields.Float('São contadas como meia hora as fracções de tempo de', default=15)
    extra_hour_half_hour_of_until = fields.Float('Até', default=44)
    extra_hour_considered_as_one = fields.Float('São consideradas como uma hora Fracções de', default=45)
    extra_hour_as_on_hour_of_until = fields.Float('Até', default=60)
    hour_left_are_not_fractions_time_less_than = fields.Float('Não são consideradas fracções de tempo inferiores a')
    hour_left_counted_half_hour = fields.Float('São contadas como meia hora as fracções de tempo de')
    hour_left_half_hour_of_until = fields.Float('Até')
    hour_left_considered_as_one = fields.Float('São consideradas como uma hora Fracções de')
    hour_left_as_on_hour_of_until = fields.Integer('Até')
    type_of_dependents = fields.Selection(
        [('pai', 'PAI'), ('mae', 'Mãe'), ('filho(a)', 'Filho(a)'), ('conjuge', 'CÔNJUGE'),
         ('tio(a)', 'Tio(a)'), ('sobrinho(a)', 'Sobrinho(a)')], default='filho(a)',
        string='Tipo de Dependentes')
    dependent_limit = fields.Integer('Limite de Dependentes', default=5)
    age_range_dependent_children = fields.Integer('Faixa etária dos dependentes')
    dependent_children_until = fields.Integer('Até', default=14)
    christmas_bonus = fields.Selection([('100', '100%'), ('50', '50%')], string='Bónus de Natal', default='100')
    take_vacation_after_admission = fields.Integer('Direito a gozar férias após a admissão', default=6)
    right_to_more_vocation = fields.Integer('Direito a mais')
    enjoyment_collaborators_for_children = fields.Integer(
        'Mais dias de férias, os colaboradores com crianças menores de',
        default=0)
    vocation_until = fields.Integer('Até', default=14)
    vocation_bonus = fields.Integer('Bónus de férias', default=50)
    discount_of_vocation_days_for_justified_absences = fields.Integer(
        'Desconto de dias de férias por faltas justificadas sem remuneração',
        default=1)
    vocation_days_for_justified_absences_for_each = fields.Integer('For Each', default=2)
    discount_of_vocation_days_for_unjustified_absences = fields.Integer(
        'Desconto de dias de férias por faltas injustificadas', default=1)
    vocation_days_for_unjustified_absences_for_each = fields.Integer('Para Cada', default=1)
    maximum_number_vacation_days_off = fields.Integer('Número máximo de dias de férias', default=6)
    vacation_payment = fields.Selection(
        [('proportionally_in_month_before_vacation', 'Proporcional no mês anterior às férias'),
         ('full_payment_month_before_vacation', 'Pagamento completo no mês anterior às férias'),
         ('full_payment_fixed_month', 'Pagamento completo num mês fixo')],
        string='Pagamento de Férias', default='proportionally_in_month_before_vacation')
    vocation_pay_month = fields.Date('Mês de Pagamento')
    process_automatically_vacation = fields.Boolean('Processamento automático da gratificação e do subsídio de férias')
    variable_working_days = fields.Integer('Dias úteis variáveis', default=30)
    fixed_days = fields.Integer('Dias Fixos', default=30)
    christmas_payment_date = fields.Date('Data de pagamento de subsídio de Natal')
    set_active = fields.Boolean(default=True, string="Padrão",
                                help="Definir como verdadeiro para ser utilizado como a escala predefinida em utilização")
    vacation_expatri_payment_date = fields.Date('Data de Pagamento de Férias para Expatriados')

    def write(self, vals):
        res = super(HRCompanyScale, self).write(vals)
        if self.set_active:
            self.get_fields_values()

        return res

    @api.depends('scale')
    def _compute_name(self):
        for record in self:
            record.name = f'{record.scale.upper() if record.scale else record.scale} COMPANY' or ''

    @api.onchange('set_active')
    def action_set_active(self):
        for record in self:
            if type(record.id) is int:
                record.set_active = True
                record.set_active_false()
                record.get_fields_values()
            else:
                record.set_active = False

    def set_active_false(self):
        scale_group_ids = self.env['hr.company.scale.group'].sudo().search([('id', '!=', self.id)])
        scale_group_ids.set_active = False

    def get_fields_values(self):
        data_values = {
            "company_scale": self.scale,
            "shift_work": self.shift_work,
            "night_work": self.night_work,
            "limit_of_30_hours_per_month": self.limit_of_30_hours_per_month,
            "hours_exceeding_30_hours_per_month": self.hours_exceeding_30_hours_per_month,
            "work_on_rest_days": self.work_on_rest_days,
            "seniority_limit": self.seniority_limit,
            "seniority_percentage": self.seniority_percentage,
            "availability_system": self.availability_system,
            "working_days_moth_salary": self.working_days_moth_salary,
            "calendar_days_moth_salary": self.calendar_days_moth_salary,
            "extra_hour_are_not_fractions_time_less_than": self.extra_hour_are_not_fractions_time_less_than,
            "extra_hour_counted_half_hour": self.extra_hour_counted_half_hour,
            "extra_hour_half_hour_of_until": self.extra_hour_half_hour_of_until,
            "extra_hour_considered_as_one": self.extra_hour_considered_as_one,
            "extra_hour_as_on_hour_of_until": self.extra_hour_as_on_hour_of_until,
            "hour_left_are_not_fractions_time_less_than": self.hour_left_are_not_fractions_time_less_than,
            "hour_left_counted_half_hour": self.hour_left_counted_half_hour,
            "hour_left_half_hour_of_until": self.hour_left_half_hour_of_until,
            "hour_left_considered_as_one": self.hour_left_considered_as_one,
            "hour_left_as_on_hour_of_until": self.hour_left_as_on_hour_of_until,
            "type_of_dependents": self.type_of_dependents,
            "dependent_limit": self.dependent_limit,
            "age_range_dependent_children": self.age_range_dependent_children,
            "dependent_children_until": self.dependent_children_until,
            "christmas_bonus": self.christmas_bonus,
            "take_vacation_after_admission": self.take_vacation_after_admission,
            "right_to_more_vocation": self.right_to_more_vocation,
            "enjoyment_collaborators_for_children": self.enjoyment_collaborators_for_children,
            "vocation_until": self.vocation_until,
            "vocation_bonus": self.vocation_bonus,
            "discount_of_vocation_days_for_justified_absences": self.discount_of_vocation_days_for_justified_absences,
            "vocation_days_for_justified_absences_for_each": self.vocation_days_for_justified_absences_for_each,
            "discount_of_vocation_days_for_unjustified_absences": self.discount_of_vocation_days_for_unjustified_absences,
            "vocation_days_for_unjustified_absences_for_each": self.vocation_days_for_unjustified_absences_for_each,
            "maximum_number_vacation_days_off": self.maximum_number_vacation_days_off,
            "vacation_payment": self.vacation_payment,
            "vocation_pay_month": self.vocation_pay_month if self.vacation_payment == 'full_payment_fixed_month' else False,
            "process_automatically_vacation": self.process_automatically_vacation,
            "variable_working_days": self.variable_working_days,
            "fixed_days": self.fixed_days,
            "christmas_payment_date": self.christmas_payment_date,
            "limit_hours": self.limit_hours,
            "vacation_expatri_payment_date": self.vacation_expatri_payment_date,
        }
        self.env.company.write(data_values)
