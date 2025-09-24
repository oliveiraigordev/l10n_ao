# -*- coding: utf-8 -*-
from odoo import fields, models, api, _


class ResCompany(models.Model):
    _inherit = 'res.company'

    close_date_payroll = fields.Integer('Close Date', default=eval('25'), help='Salary Processing End Date')
    show_paid_usd = fields.Boolean(default=False, string='Paid in USD', help='Show Amount Paid in USD')
    rate_date_at = fields.Selection([('payslip_close_date', 'Payslip Close Date'), ('current_date', 'Current Date')],
                                    default='current_date', string="Rate Date")
    company_scale = fields.Selection(
        [('big', 'Big Company'), ('average', 'Average Company'), ('small', 'Small Company'),
         ('micro', 'Micro Company'), ('others', 'Others')],
        string="Company Type", default='big',
        help='Each company must select the type of company to which it corresponds. Depending on '
             'of the company"s scale, the calculations of the system"s earnings and discounts will be carried out')
    term_responsibility = fields.Boolean('Term Responsibility')
    shift_work = fields.Float('Shift Work', help="Percentagem dos Preventos e Descontos")
    night_work = fields.Float('Night Work', help="Percentagem dos Preventos e Descontos")
    limit_of_30_hours_per_month = fields.Float('Percentage Limit Of 30 Hours Per Month')
    limit_hours = fields.Integer('Limit Of Hours Per Month', default=30)
    hours_exceeding_30_hours_per_month = fields.Float('Percentage Hours Exceeding 30 Hours Per Month')
    work_on_rest_days = fields.Float('Percentage Work on Rest Days')
    seniority_limit = fields.Integer('Seniority Limit')
    seniority_percentage = fields.Float('Seniority Percentage')
    not_influence_number_of_years = fields.Boolean('Does not influence the number of years worked by the employee')
    availability_system = fields.Float('Availability System')
    working_days_moth_salary = fields.Float('Working days representing a month for salary calculations', default=22)
    calendar_days_moth_salary = fields.Float('Calendar days representing a month for salary calculations', default=30)
    extra_hour_are_not_fractions_time_less_than = fields.Float('Are not considered fractions of time less than',
                                                               default=15)
    extra_hour_counted_half_hour = fields.Float('Are counted as half an hour fractions of time of', default=15)
    extra_hour_half_hour_of_until = fields.Float('Until', default=44)
    extra_hour_considered_as_one = fields.Float('Are considered as one hour Fractions of', default=45)
    extra_hour_as_on_hour_of_until = fields.Float('Until', default=60)
    hour_left_are_not_fractions_time_less_than = fields.Float('Are not considered fractions of time less than')
    hour_left_counted_half_hour = fields.Float('Are counted as half an hour fractions of time of')
    hour_left_half_hour_of_until = fields.Float('Until')
    hour_left_considered_as_one = fields.Float('Are considered as one hour Fractions of')
    hour_left_as_on_hour_of_until = fields.Integer('Until')
    type_of_dependents = fields.Selection(
        [('pai', 'PAI'), ('mae', 'Mãe'), ('filho(a)', 'Filho(a)'), ('conjuge', 'CÔNJUGE'),
         ('tio(a)', 'Tio(a)'), ('sobrinho(a)', 'Sobrinho(a)')],
        string='Type of Dependents')
    dependent_limit = fields.Integer('Dependent Limit', default=5)
    age_range_dependent_children = fields.Integer('Age range of dependent children')
    dependent_children_until = fields.Integer('Until', default=14)
    christmas_bonus = fields.Selection([('100', '100%'), ('50', '50%')], string='Christmas Bonus', default='100')
    take_vacation_after_admission = fields.Integer('Right to take vacation after admission', default=6)
    right_to_more_vocation = fields.Integer('Right to more')
    enjoyment_collaborators_for_children = fields.Integer('Of enjoyment the collaborators for children under',
                                                          default=0)
    vocation_until = fields.Integer('Until', default=14)
    vocation_bonus = fields.Integer('Vacation Bonus', default=50)
    discount_of_vocation_days_for_justified_absences = fields.Integer(
        'Discount of vacation days for justified absences without pay',
        default=1)
    vocation_days_for_justified_absences_for_each = fields.Integer('For Each', default=2)
    discount_of_vocation_days_for_unjustified_absences = fields.Integer(
        'Vacation days discount for unjustified absences', default=1)
    vocation_days_for_unjustified_absences_for_each = fields.Integer('For Each', default=1)
    maximum_number_vacation_days_off = fields.Integer('Maximum number of vacation days off', default=6)
    vacation_payment = fields.Selection(
        [('proportionally_in_month_before_vacation', 'Proportionally in the month before vacation'),
         ('full_payment_month_before_vacation', 'Full payment in month before vacation'),
         ('full_payment_fixed_month', 'Full payment in a fixed month')],
        string='Vacation Payment', default='proportionally_in_month_before_vacation')
    vocation_pay_month = fields.Date('Pay Month')
    national_minimum_wage = fields.Float('National Minimum Wage')
    process_automatically_vacation = fields.Boolean('Bonus and vacation salary processing automatically')
    process_automatically_exchange = fields.Boolean('Process exchange automatically')
    currency = fields.Selection([('USD', 'USD'), ('Euro', 'Euro')], string='Currency')
    initial_date = fields.Date('Initial Date')
    end_date = fields.Date('End Date')
    exchange_rate = fields.Float('Exchange Rate')
    variable_working_days = fields.Integer('Variable Working Days', default=30)
    fixed_days = fields.Integer('Fixed Days', default=30)
    christmas_payment_date = fields.Date('Christmas Payment Date')
    holidays_processing_day_start = fields.Integer(
        string="Dia para início de processamento de ausências (Mês Anteriror)", default=14
    )
    holidays_processing_day_end = fields.Integer(
        string="Dia para fim de processamento de ausências (Mês Actual)", default=15
    )
    process_tis = fields.Boolean('Regras de Processamento TIS', default=False)
    vacation_expatri_payment_date = fields.Date('Data de Pagamento de Férias para Expatriados')
    company_security_number = fields.Char('Nº de Segurança Social')


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    close_date_payroll = fields.Integer(related='company_id.close_date_payroll')
    show_paid_usd = fields.Boolean(related='company_id.show_paid_usd', readonly=False)
    rate_date_at = fields.Selection([('current_date', 'Current Date'), ('payslip_close_date', 'Payslip Close Date')],
                                    related='company_id.rate_date_at', readonly=False)
    company_scale = fields.Selection(
        [('big', 'Big Company'), ('average', 'Average Company'), ('small', 'Small Company'),
         ('micro', 'Micro Company'), ('others', 'Others')],
        related='company_id.company_scale', readonly=False)
    term_responsibility = fields.Boolean('Term Responsibility', related='company_id.term_responsibility',
                                         readonly=False)
    shift_work = fields.Float(related='company_id.shift_work', readonly=False)
    night_work = fields.Float(related='company_id.night_work', readonly=False)
    limit_of_30_hours_per_month = fields.Float(related='company_id.limit_of_30_hours_per_month', readonly=False)
    limit_hours = fields.Integer(related='company_id.limit_hours', readonly=False)
    hours_exceeding_30_hours_per_month = fields.Float(related='company_id.hours_exceeding_30_hours_per_month',
                                                      readonly=False)
    work_on_rest_days = fields.Float(related='company_id.work_on_rest_days', readonly=False)
    seniority_limit = fields.Integer(related='company_id.seniority_limit', readonly=False)
    seniority_percentage = fields.Float(related='company_id.seniority_percentage', readonly=False)
    not_influence_number_of_years = fields.Boolean(related='company_id.not_influence_number_of_years', readonly=False)
    availability_system = fields.Float(related='company_id.availability_system', readonly=False)
    working_days_moth_salary = fields.Float(related='company_id.working_days_moth_salary', readonly=False)
    calendar_days_moth_salary = fields.Float(related='company_id.calendar_days_moth_salary', readonly=False)
    extra_hour_are_not_fractions_time_less_than = fields.Float(
        related='company_id.extra_hour_are_not_fractions_time_less_than',
        readonly=False)
    extra_hour_counted_half_hour = fields.Float(related='company_id.extra_hour_counted_half_hour', readonly=False)
    extra_hour_half_hour_of_until = fields.Float(related='company_id.extra_hour_half_hour_of_until', readonly=False)
    extra_hour_considered_as_one = fields.Float(related='company_id.extra_hour_considered_as_one',
                                                readonly=False)
    extra_hour_as_on_hour_of_until = fields.Float(related='company_id.extra_hour_as_on_hour_of_until',
                                                  readonly=False)
    hour_left_are_not_fractions_time_less_than = fields.Float(
        related='company_id.hour_left_are_not_fractions_time_less_than',
        readonly=False)
    hour_left_counted_half_hour = fields.Float(related='company_id.hour_left_counted_half_hour', readonly=False)
    hour_left_half_hour_of_until = fields.Float(related='company_id.hour_left_half_hour_of_until', readonly=False)
    hour_left_considered_as_one = fields.Float(related='company_id.hour_left_considered_as_one',
                                               readonly=False)
    hour_left_as_on_hour_of_until = fields.Integer(related='company_id.hour_left_as_on_hour_of_until', readonly=False)
    type_of_dependents = fields.Selection(
        [('pai', 'PAI'), ('mae', 'Mãe'), ('filho(a)', 'Filho(a)'), ('conjuge', 'CÔNJUGE'),
         ('tio(a)', 'Tio(a)'), ('sobrinho(a)', 'Sobrinho(a)')],
        related='company_id.type_of_dependents', readonly=False)
    dependent_limit = fields.Integer(related='company_id.dependent_limit', readonly=False)
    age_range_dependent_children = fields.Integer(related='company_id.age_range_dependent_children', readonly=False)
    dependent_children_until = fields.Integer(related='company_id.dependent_children_until', readonly=False)
    christmas_bonus = fields.Selection([('100', '100%'), ('50', '50%')], string='Christmas Bonus',
                                       related='company_id.christmas_bonus',
                                       readonly=False)
    take_vacation_after_admission = fields.Integer(related='company_id.take_vacation_after_admission', readonly=False)
    right_to_more_vocation = fields.Integer(related='company_id.right_to_more_vocation', readonly=False)
    enjoyment_collaborators_for_children = fields.Integer(related='company_id.enjoyment_collaborators_for_children',
                                                          readonly=False)
    vocation_until = fields.Integer(related='company_id.vocation_until', readonly=False)
    vocation_bonus = fields.Integer(related='company_id.vocation_bonus', readonly=False)
    discount_of_vocation_days_for_justified_absences = fields.Integer(
        related='company_id.discount_of_vocation_days_for_justified_absences',
        readonly=False)
    vocation_days_for_justified_absences_for_each = fields.Integer(
        related='company_id.vocation_days_for_justified_absences_for_each',
        readonly=False)
    discount_of_vocation_days_for_unjustified_absences = fields.Integer(
        related='company_id.discount_of_vocation_days_for_unjustified_absences',
        readonly=False)
    vocation_days_for_unjustified_absences_for_each = fields.Integer(
        related='company_id.vocation_days_for_unjustified_absences_for_each',
        readonly=False)
    maximum_number_vacation_days_off = fields.Integer(related='company_id.maximum_number_vacation_days_off',
                                                      readonly=False)
    vacation_payment = fields.Selection(
        [('proportionally_in_month_before_vacation', 'Proportionally in the month before vacation'),
         ('full_payment_month_before_vacation', 'Full payment in month before vacation'),
         ('full_payment_fixed_month', 'Full payment in a fixed month')],
        string='Vacation Payment', related='company_id.vacation_payment',
        readonly=False)
    vocation_pay_month = fields.Date(related='company_id.vocation_pay_month', readonly=False)
    national_minimum_wage = fields.Float(related='company_id.national_minimum_wage', string='National Minimum Wage',
                                         readonly=False)
    process_automatically_vacation = fields.Boolean(related='company_id.process_automatically_vacation',
                                                    string='Bonus and vacation salary processing automatically',
                                                    readonly=False)
    process_automatically_exchange = fields.Boolean(related='company_id.process_automatically_exchange',
                                                    string='Process exchange automatically', readonly=False)

    currency = fields.Selection([('USD', 'USD'), ('Euro', 'Euro')], string='Currency',
                                related='company_id.currency', readonly=False)
    initial_date = fields.Date(related='company_id.initial_date', readonly=False)
    end_date = fields.Date(related='company_id.end_date', readonly=False)
    exchange_rate = fields.Float(related='company_id.exchange_rate', readonly=False)
    variable_working_days = fields.Integer(related='company_id.variable_working_days', readonly=False)
    fixed_days = fields.Integer(related='company_id.fixed_days', readonly=False)
    christmas_payment_date = fields.Date(related='company_id.christmas_payment_date', readonly=False)
    holidays_processing_day_start = fields.Integer(
        related='company_id.holidays_processing_day_start', readonly=False
    )
    holidays_processing_day_end = fields.Integer(
        related='company_id.holidays_processing_day_end', readonly=False
    )
    process_tis = fields.Boolean('Regras de Processamento TIS', related='company_id.process_tis', readonly=False)
    vacation_expatri_payment_date = fields.Date('Data de Pagamento de Férias para Expatriados',
                                                related='company_id.vacation_expatri_payment_date', readonly=False)
    company_security_number = fields.Char('Nº de Segurança Social',
                                          related='company_id.company_security_number', readonly=False)

    @api.onchange('national_minimum_wage')
    def _onchange_national_minimum_wage(self):
        if self.national_minimum_wage:
            self.env.company.national_minimum_wage = self.national_minimum_wage

    @api.onchange('process_automatically_exchange')
    def _onchange_process_automatically_exchange(self):
        if self.process_automatically_exchange:
            self.env.company.currency = False
            self.env.company.initial_date = False
            self.env.company.end_date = False
            self.env.company.exchange_rate = 0
