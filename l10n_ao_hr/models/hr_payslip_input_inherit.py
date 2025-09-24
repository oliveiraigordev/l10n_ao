from odoo import api, fields, models, tools, _
from datetime import datetime, timedelta, date
import calendar


def calc_age(birthday):
    today = fields.Date.today()
    return (today.year - birthday.year) - (
            (today.month, today.day) < (birthday.month, birthday.day)
    )


class HRPayslipInput(models.Model):
    _inherit = 'hr.payslip.input'

    type_of_overtime = fields.Selection([('normal', 'Normal'), ('weekend', 'Final de Semana')],
                                        string="Tipo de H. Extra")
    type_missed_hours = fields.Selection(
        [('unjustified', 'Injustificado'), ('justified_with_remuneration', 'Justificado com Remuneração'),
         ('justified_without_remuneration', 'Justificado sem Remuneração')], string="Tipo de H. de Falta")
    date = fields.Date("D. Fim", default=lambda self: fields.Date.today())
    date_start = fields.Date("D. Início", default=lambda self: fields.Date.today())
    date_end = fields.Date("D. Fim", default=lambda self: fields.Date.today())
    hours = fields.Float("Horas")
    quantity_days = fields.Integer(string='Q. de Dias')
    description = fields.Char()

    @api.model
    def create(self, values):
        if self.env.company.country_id.code == "AO":
            result = 0
            payslip_id = self.env["hr.payslip"].search([('id', '=', values.get("payslip_id"))])
            input_type_id = self.env["hr.payslip.input.type"].search([('id', '=', values.get("input_type_id"))])
            if values.get("hours"):

                # calculate_extra_hours
                if input_type_id.code == 'HEXTRAS':
                    result = self.calculate_extra_hours(values.get("type_of_overtime"), payslip_id, values)

                # calculate_missed_hours
                if input_type_id.code == 'ATRA':
                    result = self.calculate_delay_hours(payslip_id, values)

            # Calcular Faltas
            if input_type_id.code == 'MISSING_HOUR' and values.get('quantity_days') == 0:
                days = self.get_num_work_days_base_salary(values, payslip_id)
                values['quantity_days'] = days
                hours_per_day = payslip_id.employee_id.resource_calendar_id.hours_per_day
                if values.get("type_missed_hours") in ['unjustified', 'justified_without_remuneration']:
                    hours = days * hours_per_day
                    result = self.calculate_missed_hours(hours, payslip_id)
                    values['hours'] = hours
                else:
                    values['hours'] = hours_per_day

            # Calcular Licenças sem Remuneração
            if input_type_id.code == 'LSV' and values.get('quantity_days') == 0:
                days = self.get_num_work_days_base_salary(values, payslip_id)
                values['quantity_days'] = days
                hours_per_day = payslip_id.employee_id.resource_calendar_id.hours_per_day
                hours = days * hours_per_day
                result = self.calculate_missed_hours(hours, payslip_id)
                values['hours'] = hours

            if input_type_id.code == 'gozo_ferias':
                if values.get('amount') == 0:
                    salary_hour = self.get_mount_hour_salary_employee(payslip_id)
                    days = self.get_num_work_days_base_salary(values, payslip_id)
                    values['quantity_days'] = days
                    hours_per_day = payslip_id.employee_id.resource_calendar_id.hours_per_day
                    hours = hours_per_day * days
                    values['hours'] = hours
                    result = round(hours * salary_hour, 2)

            # Calcular Gratificação de Férias de forma manual
            if input_type_id.code == 'GRATIF_FER':
                hours_per_day = payslip_id.employee_id.resource_calendar_id.hours_per_day
                if values.get('quantity_days') == 0:
                    days = self.get_num_work_days_base_salary(values, payslip_id)
                    values['quantity_days'] = days
                else:
                    days = values.get('quantity_days')

                if days:
                    hours = days * hours_per_day
                    result = payslip_id.calculate_vocation_allowance(days)
                    values['hours'] = hours

            # calculate_family_llowance
            if input_type_id.code == 'FAMI':
                if values.get('amount') == 0:
                    # FILTRAR OS DEPENDENTES NA FICHA DO FUNCIONÁRIO QUE FOREM IGUAIS AO QUE FOI ESTABELECIDO NO TIPO DE EMPRESA
                    dependents = payslip_id.employee_id.dependents_ids.filtered(
                        lambda
                            r: r.degree_of_kinship == self.env.company.type_of_dependents and self.env.company.age_range_dependent_children <= calc_age(
                            r.date_of_birth) <= self.env.company.dependent_children_until)
                    if dependents:
                        result = payslip_id.employee_id.calculate_family_allowance(dependents,
                                                                                   payslip_id.contract_id.wage)

            # Calcular a compensação de Antiguidade
            if input_type_id.code == 'ANTI':
                if values.get('quantity_days') == 0:
                    result = payslip_id.contract_id.calculate_seniority_allowance()
                else:
                    result = payslip_id.contract_id.calculate_seniority_allowance(values.get('quantity_days'))

            # Calcular a compensação Aviso Previo
            if input_type_id.code == 'AVPREVIOCOMP':
                if values.get('amount') == 0:
                    result = (payslip_id.contract_id.wage / self.env.company.calendar_days_moth_salary) * \
                             values.get('quantity_days')

            # Calcular Aviso Previo Desconto
            if input_type_id.code == 'AVPREVIODESC':
                if values.get('amount') == 0:
                    result = (payslip_id.contract_id.wage / self.env.company.working_days_moth_salary) * \
                             values.get('quantity_days')

            # calculate_christmas_llowance
            if input_type_id.code == 'NAT' and not self.env.company.christmas_payment_date:
                result = self.calculate_christmas_allowance(payslip_id)

            # Calcular Férias Proporcional
            if input_type_id.code in ['R89', 'R891']:
                if 'quantity_days' in values:
                    if values.get('quantity_days') != 0:
                        hours_per_day = payslip_id.employee_id.resource_calendar_id.hours_per_day
                        hours = values.get('quantity_days') * hours_per_day
                        result = payslip_id.calculate_vocation_proportional(values.get('quantity_days'))
                        values['hours'] = hours

            # Calcular Proporcional Subsídio Natal
            if input_type_id.code == 'R36':
                if 'quantity_days' in values:
                    if values.get('quantity_days') != 0:
                        hours_per_day = payslip_id.employee_id.resource_calendar_id.hours_per_day
                        hours = values.get('quantity_days') * hours_per_day
                        employee_salary = payslip_id.contract_id[-1].wage
                        result = (employee_salary / 12) * values.get('quantity_days')
                        # result = payslip_id.calculate_vocation_proportional(values.get('quantity_days'))
                        values['hours'] = hours

            # Calcular Retroactivos de Ajuda de Custo, Alimentação e Transporte
            if input_type_id.code in ['R92', 'R68', 'R67']:
                if values.get('quantity_days') != 0:
                    hours_per_day = payslip_id.employee_id.resource_calendar_id.hours_per_day
                    values['hours'] = values.get('quantity_days') * hours_per_day
                    # Filtar o Valor do Retroactivo no contracto do colaborador
                    if input_type_id.code == 'R92':
                        result = payslip_id.calculate_retroactive_amount(values.get('quantity_days'), 'R92')
                    elif input_type_id.code == 'R67':
                        result = payslip_id.calculate_retroactive_amount(values.get('quantity_days'), 'R67')
                    elif input_type_id.code == 'R68':
                        result = payslip_id.calculate_retroactive_amount(values.get('quantity_days'), 'R68')

            if result != 0:
                values['amount'] = result

        result = super(HRPayslipInput, self).create(values)
        return result

    def write(self, values):
        if self.env.company.country_id.code == "AO":
            for record in self:
                payslip_id = record.payslip_id if record.payslip_id else values.get("payslip_id")
                payslip_id = self.env["hr.payslip"].search([('id', '=', payslip_id.id)])
                result = 0
                if values.get("hours"):

                    # calculate_extra_hours
                    if record.input_type_id.code == 'HEXTRAS':
                        type_of_overtime = record.type_of_overtime if record.type_of_overtime else values.get(
                            "type_of_overtime")
                        result = record.calculate_extra_hours(type_of_overtime, payslip_id, values)

                    # calculate_delay_hours
                    if record.input_type_id.code == 'ATRA':
                        result = record.calculate_delay_hours(payslip_id, values)

                # Calcular Faltas
                if record.input_type_id.code == 'MISSING_HOUR':
                    type_missed_hours = record.type_missed_hours if record.type_missed_hours else values.get(
                        "type_missed_hours")
                    days = self.get_num_work_days_base_salary(values, payslip_id)
                    values['quantity_days'] = days
                    hours_per_day = payslip_id.employee_id.resource_calendar_id.hours_per_day
                    if type_missed_hours in ['unjustified', 'justified_without_remuneration']:
                        hours = hours_per_day * days
                        result = record.calculate_missed_hours(hours, payslip_id)
                        values['hours'] = hours
                    else:
                        values['hours'] = hours_per_day

                # Calcular Licenças sem Remuneração
                if record.input_type_id.code == 'LSV':
                    days = self.get_num_work_days_base_salary(values, payslip_id)
                    values['quantity_days'] = days
                    hours_per_day = payslip_id.employee_id.resource_calendar_id.hours_per_day
                    hours = days * hours_per_day
                    result = record.calculate_missed_hours(hours, payslip_id)
                    values['hours'] = hours

                if record.input_type_id.code == 'gozo_ferias':
                    if values.get('amount') == 0:
                        salary_hour = self.get_mount_hour_salary_employee(payslip_id)
                        days = self.get_num_work_days_base_salary(values, payslip_id)
                        values['quantity_days'] = days
                        hours_per_day = payslip_id.employee_id.resource_calendar_id.hours_per_day
                        hours = hours_per_day * days
                        values['hours'] = hours
                        result = round(hours * salary_hour, 2)
                        # if payslip_id.contract_type_id.code == 'NACIONAL':
                        #     result = round(hours * salary_hour, 2)
                        # else:
                        #     working_days_moth_salary = self.env.company.calendar_days_moth_salary
                        #     amount = round(hours * salary_hour, 2)
                        #     result = (amount / working_days_moth_salary) * (working_days_moth_salary - days)

                # Calcular Gratificação de Férias de forma manual
                if record.input_type_id.code == 'GRATIF_FER':
                    hours_per_day = payslip_id.employee_id.resource_calendar_id.hours_per_day
                    if values.get('quantity_days') == 0:
                        days = self.get_num_work_days_base_salary(values, payslip_id)
                        values['quantity_days'] = days
                    else:
                        days = values.get('quantity_days')

                    if days:
                        hours = days * hours_per_day
                        result = payslip_id.calculate_vocation_allowance()
                        values['hours'] = hours

                # calculate_family_allowance
                if record.input_type_id.code == 'FAMI':
                    if values.get('amount') == 0:
                        # FILTRAR OS DEPENDENTES NA FICHA DO FUNCIONÁRIO QUE FOREM IGUAIS AO QUE FOI ESTABELECIDO NO TIPO DE EMPRESA
                        dependents = record.payslip_id.employee_id.dependents_ids.filtered(
                            lambda
                                r: r.degree_of_kinship == self.env.company.type_of_dependents and self.env.company.age_range_dependent_children <= calc_age(
                                r.date_of_birth) <= self.env.company.dependent_children_until)
                        if dependents:
                            result = payslip_id.employee_id.calculate_family_allowance(dependents,
                                                                                       payslip_id.contract_id.wage)

                # calculate_christmas_llowance
                if record.code == 'NAT' and not self.env.company.christmas_payment_date:
                    result = record.calculate_christmas_allowance(payslip_id)

                # Calcular a compensação de Antiguidade
                if record.code == 'ANTI':
                    if 'quantity_days' in values:
                        if values.get('quantity_days') == 0:
                            result = payslip_id.contract_id.calculate_seniority_allowance()
                        else:
                            result = payslip_id.contract_id.calculate_seniority_allowance(values.get('quantity_days'))

                # Calcular a compensação Aviso Previo
                if record.code == 'AVPREVIOCOMP':
                    if 'quantity_days' in values:
                        result = (payslip_id.contract_id.wage / self.env.company.calendar_days_moth_salary) * \
                                 values.get('quantity_days')
                        values['amount'] = result

                # Calcular Aviso Previo Desconto
                if record.code == 'AVPREVIODESC':
                    if 'quantity_days' in values:
                        result = (payslip_id.contract_id.wage / self.env.company.working_days_moth_salary) * \
                                 values.get('quantity_days')
                        values['amount'] = result

                # Calcular Férias Proporcional
                if record.input_type_id.code in ['R89', 'R891']:
                    if 'quantity_days' in values:
                        if values.get('quantity_days') != 0:
                            hours_per_day = payslip_id.employee_id.resource_calendar_id.hours_per_day
                            hours = values.get('quantity_days') * hours_per_day
                            result = payslip_id.calculate_vocation_proportional(values.get('quantity_days'))
                            values['hours'] = hours

                # Calcular Proporcional Subsídio Natal
                if record.input_type_id.code == 'R36':
                    if 'quantity_days' in values:
                        if values.get('quantity_days') != 0:
                            hours_per_day = payslip_id.employee_id.resource_calendar_id.hours_per_day
                            hours = values.get('quantity_days') * hours_per_day
                            employee_salary = payslip_id.contract_id[-1].wage
                            result = (employee_salary / 12) * values.get('quantity_days')
                            # result = payslip_id.calculate_vocation_proportional(values.get('quantity_days'))
                            values['hours'] = hours

                # Calcular Retroactivos de Ajuda de Custo, Alimentação e Transporte
                if record.input_type_id.code in ['R92', 'R68', 'R67']:
                    if values.get('quantity_days') != 0:
                        hours_per_day = payslip_id.employee_id.resource_calendar_id.hours_per_day
                        values['hours'] = values.get('quantity_days') * hours_per_day
                        # Filtar o Valor do Retroactivo no contracto do colaborador
                        if record.input_type_id.code == 'R92':
                            result = payslip_id.calculate_retroactive_amount(values.get('quantity_days'), 'R92')
                        elif record.input_type_id.code == 'R67':
                            result = payslip_id.calculate_retroactive_amount(values.get('quantity_days'), 'R67')
                        elif record.input_type_id.code == 'R68':
                            result = payslip_id.calculate_retroactive_amount(values.get('quantity_days'), 'R68')

                if result != 0:
                    values['amount'] = result

        res = super(HRPayslipInput, self).write(values)
        return res

    def get_num_work_days_base_salary(self, values, payslip_id):
        if 'date_start' in values:
            if type(values['date_start']) is str:
                date_start = date(
                    int(values['date_start'].split('-')[0]),
                    int(values['date_start'].split('-')[1]),
                    int(values['date_start'].split('-')[2])
                )
            else:
                date_start = values['date_start']
        else:
            date_start = self.date_start

        if 'date_end' in values:
            if type(values['date_start']) is str:
                date_end = date(
                    int(values['date_end'].split('-')[0]),
                    int(values['date_end'].split('-')[1]),
                    int(values['date_end'].split('-')[2]),
                )
            else:
                date_end = values['date_start']
        else:
            date_end = self.date_end

        intervale_dates = (
            date_start + timedelta(days=idx)
            for idx in range((date_end - date_start).days + 1)
        )
        # Para os Expatriados com a Politica Individual tem 40 dias corridos
        if payslip_id.employee_id.contract_type.code == "NACIONAL" and not payslip_id.contract_id.calendar_days:
            """Filtra apenas os dias úteis dias da semana"""
            num_work_days = len([day for day in intervale_dates if day.weekday() < 5])
            if num_work_days > int(self.env.company.working_days_moth_salary):
                num_work_days = int(self.env.company.working_days_moth_salary)
            return num_work_days
        else:
            """Filtra todos os dias corridos dias da semana"""
            num_work_days = len([day for day in intervale_dates])
            if num_work_days > int(self.env.company.calendar_days_moth_salary):
                num_work_days = int(self.env.company.calendar_days_moth_salary)
            return num_work_days

    def calculate_christmas_allowance(self, payslip_id):
        work_month = payslip_id.contract_id.get_employee_work_complete_month(payslip_id.date_from)
        christmas_amount = (payslip_id.wage * int(self.env.company.christmas_bonus)) / 100
        christmas_amount = round((christmas_amount / 12) * work_month, 2)
        return christmas_amount

    def get_mount_hour_salary_employee(self, payslip_id):
        venc = abs(payslip_id.contract_id.wage)
        salary_hour = round((venc * 12) / (52 * payslip_id.contract_id.resource_calendar_id.hours_per_week), 2)
        return salary_hour

    def get_hour_minutes(self, values):
        hours = int(values.get("hours"))
        minutes = int((values.get("hours") - hours) * 60)
        return hours, minutes

    def calculate_extra_hours(self, type_of_overtime, payslip_id, values):

        def get_hour_value(hours, salario_hora):
            return hours * salario_hora

        def get_minute_values(salario_hora):#-d l10n_hr
            return salario_hora / 2

        extra_value = 0
        if values.get("hours"):
            salary_hour = self.get_mount_hour_salary_employee(payslip_id)
            hours, minutes = self.get_hour_minutes(values)
            data = self.get_scale_group_values()
            # Horas Extras - Não são consideradas as fracções de tempo inferiores a: 15 minutos
            if hours > 0 or minutes >= data.get('extra_hour_are_not_fractions_time_less_than'):
                # Horas Extras - São contadas como meia hora as fracções de tempo de quinze (15) a quarenta (44) minutos, pelo que será calculado a metade do valor total de uma hora extra;
                if data.get('extra_hour_counted_half_hour') <= minutes <= data.get('extra_hour_half_hour_of_until'):
                    minutes = 30
                # Horas Extras - São consideradas como uma hora as fracções de tempo de quarenta e cinco (45) a sessenta (60) minutos
                elif data.get('extra_hour_considered_as_one') <= minutes <= data.get('extra_hour_as_on_hour_of_until'):
                    hours += 1
                    minutes = 0

                if type_of_overtime == 'normal':
                    if hours:
                        if hours > data.get('limit_hours'):
                            hour_execed = hours - data.get('limit_hours')
                            normal_total = (data.get('limit_hours') * salary_hour) + (
                                    (data.get('limit_hours') * salary_hour) * (
                                    data.get('limit_of_30_hours_per_month') / 100))

                            value_total1 = (hour_execed * salary_hour) + ((hour_execed * salary_hour) *
                                                                          (data.get(
                                                                              'hours_exceeding_30_hours_per_month') / 100))
                            extra_value = round(normal_total + value_total1, 2)
                        else:
                            extra_value = get_hour_value(hours, salary_hour) + (get_hour_value(hours, salary_hour) * (
                                    data.get('limit_of_30_hours_per_month') / 100))

                    if minutes:
                        extra_value += (salary_hour / 2) + (
                                (salary_hour / 2) * (data.get('limit_of_30_hours_per_month') / 100))
                elif type_of_overtime == 'weekend':
                    total_hours = total_minutes = 0
                    if hours:
                        total_hours = get_hour_value(hours, salary_hour) + (get_hour_value(hours, salary_hour) * (
                                data.get('hours_exceeding_30_hours_per_month') / 100))

                    if minutes:
                        total_minutes = get_minute_values(salary_hour) + (get_minute_values(salary_hour) * (
                                data.get('hours_exceeding_30_hours_per_month') / 100))

                    extra_value = total_hours + total_minutes

        return extra_value

    def calculate_delay_hours(self, payslip_id, values):

        def get_hour_value(hours, salario_hora):
            return hours * salario_hora

        def get_minute_values(salario_hora):
            return salario_hora / 2

        extra_value = 0
        if values.get("hours"):
            salary_hour = self.get_mount_hour_salary_employee(payslip_id)
            hours, minutes = self.get_hour_minutes(values)
            data = self.get_scale_group_values()
            # Horas Falta - Não são consideradas as fracções de tempo inferiores a: X minutos
            if hours > 0 or minutes >= data.get('hour_left_are_not_fractions_time_less_than'):
                # Horas Falta - São contadas como meia hora as fracções de tempo de quinze X a X minutos, pelo que será calculado a metade do valor total de uma hora extra;
                if data.get('hour_left_counted_half_hour') <= minutes <= data.get('hour_left_half_hour_of_until'):
                    minutes = 30
                # Horas Extras - São consideradas como uma hora as fracções de tempo de quarenta e cinco x a sessenta x minutos
                elif data.get('hour_left_considered_as_one') <= minutes <= data.get('hour_left_as_on_hour_of_until'):
                    hours += 1
                    minutes = 0

                if hours:
                    extra_value = round(get_hour_value(hours, salary_hour), 2)

                if minutes:
                    total_minutes = get_minute_values(salary_hour)
                    extra_value += total_minutes

        return extra_value

    def calculate_missed_hours(self, hours, payslip_id):
        def get_hour_value(hours, salario_hora):
            return hours * salario_hora

        salary_hour = self.get_mount_hour_salary_employee(payslip_id)
        amount = round(get_hour_value(hours, salary_hour), 2)
        return amount

    def get_scale_group_values(self):
        data = {
            'extra_hour_counted_half_hour': self.env.company.extra_hour_counted_half_hour,
            'extra_hour_half_hour_of_until': self.env.company.extra_hour_half_hour_of_until,
            'extra_hour_considered_as_one': self.env.company.extra_hour_considered_as_one,
            'extra_hour_as_on_hour_of_until': self.env.company.extra_hour_as_on_hour_of_until,
            'extra_hour_are_not_fractions_time_less_than': self.env.company.extra_hour_are_not_fractions_time_less_than,
            'limit_of_30_hours_per_month': self.env.company.limit_of_30_hours_per_month,
            'hours_exceeding_30_hours_per_month': self.env.company.hours_exceeding_30_hours_per_month,
            'hour_left_are_not_fractions_time_less_than': self.env.company.hour_left_are_not_fractions_time_less_than,
            'hour_left_counted_half_hour': self.env.company.hour_left_counted_half_hour,
            'hour_left_half_hour_of_until': self.env.company.hour_left_half_hour_of_until,
            'hour_left_considered_as_one': self.env.company.hour_left_considered_as_one,
            'hour_left_as_on_hour_of_until': self.env.company.hour_left_as_on_hour_of_until,
            'type_of_dependents': self.env.company.type_of_dependents,
            'dependent_limit': self.env.company.dependent_limit,
            'age_range_dependent_children': self.env.company.age_range_dependent_children,
            'dependent_children_until': self.env.company.dependent_children_until,
            'national_minimum_wage': self.env.company.national_minimum_wage,
            'limit_hours': self.env.company.limit_hours,
        }
        return data
