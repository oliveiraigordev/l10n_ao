from dateutil.relativedelta import relativedelta

from odoo import models, fields, api, _


def calc_age(birthday):
    # (today.year - birthday.year) - ((today.month, today.day) < (birthday.month, birthday.day))
    today = fields.Date.today()
    return (today.year - birthday.year) - (
            (today.month, today.day) < (birthday.month, birthday.day)
    )


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    holiday_processing_policy = fields.Selection(
        [('family', 'Family'), ('individual', 'Individual'), ('individual_remoto', 'Individual/Remoto')],
        'Política de processamento de férias')

    @api.depends('parent_id')
    def _compute_leave_manager(self):
        return {}

    @api.onchange('coach_id')
    def _onchange_leave_manager(self):
        trainer_manager = self.coach_id.user_id
        if trainer_manager:
            self.leave_manager_id = trainer_manager
        elif not self.leave_manager_id:
            self.leave_manager_id = False

    def calculate_vacation_days(self, start_date, end_date):
        dependent_children_number = (
                self.calculate_dependent_children_number()
                * self.env.company.right_to_more_vacation
        )

        # Para os Expatriados com a Politica Individual tem 40 dias corridos de gozo de férias
        if self.contract_type.code == 'EXPATRIADO' and self.holiday_processing_policy == 'individual':
            vacation_days = 40
        else:
            vacation_days = self.get_vacation_days(start_date, end_date)

        return vacation_days, dependent_children_number

    def calculate_dependent_children_number(self):
        self.ensure_one()
        if self.gender != "female":
            return 0

        age_range_dependent_children = self.env.company.age_range_dependent_children
        dependent_children_until = self.env.company.dependent_children_until

        # FILTRAR OS DEPENDENTES NA FICHA DO FUNCIONÁRIO QUE FOREM
        # IGUAIS AO QUE FOI ESTABELECIDO NO TIPO DE EMPRESA E QUE
        # ESTEJAM NO RANGE DE IDADE
        dependents = self.dependents_ids.filtered(
            lambda r: r.degree_of_kinship == self.env.company.type_of_dependents
            and age_range_dependent_children
            <= calc_age(r.date_of_birth)
            <= dependent_children_until
        )
        if dependents:
            dependents = len(dependents)
        else:
            dependents = self.children

        # RETORNA O NUMERO DE DEPENDENTES SE O NÚMERO NAO EXCEDE O LIMITE
        return (
            self.env.company.dependent_limit
            if dependents > self.env.company.dependent_limit
            else dependents
        )

    def get_vacation_days(self, start_date, end_date):
        if start_date.year != end_date.year:
            return 0
        days = 0
        # Adding one day so we can compute correctly
        # when reaching the end of the year.
        end_date = end_date + relativedelta(days=1)
        difference_months = (end_date.year - start_date.year) * 12 + (
            end_date.month - start_date.month
        )
        days = difference_months * 2 if difference_months < 12 else 22
        if start_date.day != 1 and difference_months < 12:
            days -= 2
        return days


class HolidaysEmployeePublic(models.Model):
    _inherit = "hr.employee.public"

    holiday_processing_policy = fields.Selection(related="employee_id.holiday_processing_policy", compute_sudo=True)
