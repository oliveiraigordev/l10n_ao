from datetime import date

from odoo import models, fields, api


class VacationBalanceReport(models.Model):  #
    _name = "vacation.balance.report"
    _description = "Vacation Balance Report"
    _order = "employee_id asc, vacation_year desc"

    employee_id = fields.Many2one("hr.employee", string="Funcionário")
    department_id = fields.Many2one(related="employee_id.department_id", store=True, compute_sudo=True,
                                    string="Departamento")
    country_id = fields.Many2one(related="employee_id.country_id", store=True, compute_sudo=True,
                                 string="Nacionalidade")
    job_id = fields.Many2one(related="employee_id.job_id", store=True, compute_sudo=True, string="Cargo/Função")
    gender = fields.Char(string="Genêro")
    company_id = fields.Many2one("res.company", string="Empresa")
    leave_type_id = fields.Many2one("hr.leave.type", string="Tipo de Ausêcia")
    admission_date = fields.Date(string="Data de Admissão")
    vacation_days = fields.Integer(string="Dias de Férias")
    additional_per_dependent_days = fields.Integer(string="Adicional Por Dependentes")
    subtracted_days = fields.Integer("Dias Subtraídos por Falta")
    total_vacation_days = fields.Integer(
        string="Total de Dias de Gozo",
        help="Total days for vacation minus the missing hours",
        compute="_compute_totals",
        store=True,
    )
    days_already_enjoyed = fields.Integer("Dias Usufruídos/Validados")
    days_requested = fields.Integer("Dias Solicitados")
    days_not_taken = fields.Integer(
        string="Dias não Gozados no Ano Passado",
        related="previous_report_id.total_balance_days",
    )
    overdue_days = fields.Integer(
        string="Dias de Atraso",
        help="Days lost because it took too long for the employee to claim the vacation days",
    )
    current_balance_days = fields.Integer(
        string="Saldo de Dias Ano Actual", compute="_compute_totals", store=True
    )
    total_balance_days = fields.Integer(
        string="Total de Dias de Gozo", compute="_compute_totals", store=True
    )
    vacation_year = fields.Integer(string="Year")
    state = fields.Selection(
        [("active", "Activo"), ("close", "Fechado")],
        string="Estado",
        compute="_compute_totals",
        store=True,
    )
    date_from = fields.Date(
        string="Data Inicial",
        help="Data inicial para calculo dos dias de férias",
    )
    date_to = fields.Date(
        string="Data Final",
        help="Data final para calculo dos dias de férias",
    )
    previous_report_id = fields.Many2one(
        comodel_name="vacation.balance.report", string="Relatório Anterior"
    )
    contract_type_id = fields.Many2one(related='employee_id.contract_type', compute_sudo=True, store=True, )
    direction_id = fields.Many2one("hr.direction", string='Direcção', compute="_compute_direction",
                                   store=True)
    discount_days_out_of_country = fields.Integer(
        string="Fora do País",
        help="Desconto devido a ausência do expatriado no país por mais de 3 meses",
    )
    # days_not_taken_lost = fields.Integer(
    #     string="Dias não gozados perdidos"
    # )

    _sql_constraints = [
        (
            "employee_year_uniq",
            "unique(employee_id,vacation_year)",
            "Only one record per year and employee is allowed!",
        )
    ]

    @api.depends(
        "department_id",
    )
    def _compute_direction(self):
        for report in self:
            if report.employee_id:
                report.direction_id = report.employee_id.direction_id
            else:
                report.direction_id = False

    @api.depends(
        "vacation_days",
        "days_already_enjoyed",
        "subtracted_days",
        "previous_report_id",
        "previous_report_id.days_not_taken",
        "days_not_taken",
    )
    def _compute_totals(self):
        for report in self:
            today = fields.Date.today()
            report.total_vacation_days = (
                    report.vacation_days
                    + report.additional_per_dependent_days
                    - report.subtracted_days
            )
            report.current_balance_days = (
                    report.total_vacation_days
                    - report.days_already_enjoyed
                    - report.overdue_days
            )
            if report.employee_id.contract_type.code == "EXPATRIADO":
                report.total_balance_days = (
                        report.current_balance_days + report.days_not_taken
                )
            else:
                report.total_balance_days = (
                    report.current_balance_days + report.days_not_taken if today.month < int(
                        self.env.company.vacation_update_balance) else report.current_balance_days
                )

            dependent_children_number = (
                    report.employee_id.calculate_dependent_children_number()
                    * self.env.company.right_to_more_vacation
            )
            # Para os Expatriados com a Politica Individual tem 40 dias corridos de gozo de férias
            if (
                    report.employee_id.contract_type.code == "EXPATRIADO"
                    and report.employee_id.holiday_processing_policy == "individual"
            ):
                vacation_days = 40
            else:
                vacation_days = 22 + dependent_children_number

            if report.total_balance_days > vacation_days:
                report.total_balance_days = vacation_days

            if report.vacation_year == today.year - 1 and report.employee_id.contract_type.code == "Nacional":
                if report.total_balance_days < 6:
                    report.vacation_days = 6

            if report.current_balance_days <= 0:
                report.state = "close"
            else:
                report.state = "active"

    @api.model
    def vacation_leave_notification_report_cron(self):
        leave_type_vocation_id = self.env.ref("l10n_ao_hr_holidays.l10n_ao_hr_leave_type_vocation")
        currente_year = fields.Date.today()
        # Pesquisar todos os colaboradores ativos e que estão associados a um utilizador
        employees = self.get_employees()
        for employee in employees:
            # Verificar o saldo do colaborador
            year = (
                currente_year.year - 1
                if employee.contract_type.code == "NACIONAL"
                else currente_year.year
            )
            vacation_balance = self.get_vacation_leaves(employee, year)
            if not vacation_balance:
                continue

            # Search for other leaves not approved yet
            # other_leave_ids = self.env["hr.leave"].search(
            #     [
            #         ("employee_ids", "in", employee.ids),
            #         ("state", "not in", ("validate", "refuse")),
            #         ("holiday_status_id", "=", leave_type_vocation_id.id),
            #     ],
            #     order="request_date_from",
            # )
            # balance_days -= sum(item.number_of_days_display for item in other_leave_ids)

            if currente_year.month >= int(self.env.company.vacation_alert):
                # Enviar email de lembrete ao colaborador sobre os dias que tem para gozar férias
                vacation_balance.send_vacation_leave_notification_email()

    @api.model
    def update_balance_vacation_leave_report_cron(self):
        currente_year = fields.Date.today()
        employees = self.get_employees()
        for employee in employees:
            # Verificar o saldo do colaborador
            year = (
                currente_year.year - 1
                if employee.contract_type.code in ["NACIONAL", 'EXPATRIADO_RESIDENTE']
                else currente_year.year
            )
            vacation_balance = self.get_vacation_leaves(employee, year)
            if not vacation_balance:
                continue

            if currente_year.month >= int(self.env.company.vacation_update_balance):
                if vacation_balance.state == 'active':
                    # Zerar os dias de gozo do ano anterior
                    vacation_balance.write({
                        'state': 'close'})  # 'days_not_taken_lost': vacation_balance.current_balance_days,'total_balance_days': 0

    @api.model
    def cron_create_vacation_balance_report(self):
        # Pesquisar todos os colaboradores ativos e que estão associados a um utilizador
        employees = self.get_employees()
        for employee in employees:
            # Criar os planos de férias dos colaboradores, de acordo com a sua data de Admissão, ou do contracto em execução
            self.with_context(cron=True).create_vacation_balance_report(employee)

    @api.model
    def cron_check_vacation_balance_report(self):
        # Pesquisar todos os colaboradores ativos e que estão associados a um utilizador
        employees = self.get_employees()
        for employee in employees:
            # Verificar se o colaborador já pode ter difeito a férias,
            # de acordo com a sua data de Admissão, ou do contracto em execução
            self.set_vacation_days_enjoyed_overdue(employee)

    def get_employees(self):
        employees = self.env["hr.employee"].search(
            [
                ("active", "=", True),
                ("company_id", "=", self.env.company.id),
                ("first_contract_date", "!=", False),
            ]
        )
        return employees

    def get_vacation_leaves(self, employee, year):
        vacation_balance = self.sudo().search(
            [
                ("employee_id", "=", employee.id),
                ("vacation_year", "=", year),
                ("total_balance_days", "!=", 0),
            ]
        )
        return vacation_balance

    def get_vacation_report_values(self, employee, start_date, end_date):
        vacation_days = 0
        if employee.contract_type.code == "EXPATRIADO" and employee.holiday_processing_policy == "individual":
            vacation_days = 40
        elif employee.contract_type.code == "EXPATRIADO" and employee.holiday_processing_policy != "individual":
            vacation_days = 22

        year = start_date.year
        previous_report = self.env["vacation.balance.report"].search(
            [("employee_id", "=", employee.id), ("vacation_year", "=", year - 1)]
        )
        data = {
            "company_id": self.env.company.id,
            "leave_type_id": self.env.ref(
                "l10n_ao_hr_holidays.l10n_ao_hr_leave_type_vocation"
            ).id,
            "employee_id": employee.id,
            "gender": employee.gender if employee.gender else False,
            "admission_date": employee.first_contract_date
            if employee.first_contract_date
            else False,
            "vacation_year": year,
            "previous_report_id": previous_report.id,
            "state": "active",
            "date_from": start_date,
            "date_to": end_date,
        }
        if vacation_days != 0:
            data['vacation_days'] = vacation_days

        return data

    # TODO Add this method on the default l10n_ao_hr module
    # def get_total_missed_days(self, employee, start_date, end_date):
    #     data = self.env.company.get_scale_group_values()
    #     (
    #         falta_injustificada_days,
    #         falta_justificada_sem_remuneracao_days,
    #     ) = self.get_faltas_sem_remuneracao(employee, start_date, end_date)
    #     total_missed_days = 0
    #     if falta_injustificada_days or falta_justificada_sem_remuneracao_days:
    #         falta_injust_discount_days = 0
    #         falta_just_sem_remun_discount_days = 0
    #         # Verificar se dias subtraidos por faltas já atingitam o limite maximo
    #         # definido no Tipo de Empresa
    #         if falta_injustificada_days:
    #             falta_injust_discount_days = (
    #                 falta_injustificada_days
    #                 // data["vocation_days_for_unjustified_absences_for_each"]
    #                 * data["vocation_days_for_unjustified_absences"]
    #             )

    #         if falta_justificada_sem_remuneracao_days:
    #             falta_just_sem_remun_discount_days = (
    #                 falta_justificada_sem_remuneracao_days
    #                 // data["vocation_days_for_justified_absences_for_each"]
    #                 * data["vocation_days_for_justified_absences"]
    #             )

    #         # subtrair o saldo de férias, de acordo com as faltas
    #         total_missed_days = (
    #             falta_injust_discount_days + falta_just_sem_remun_discount_days
    #         )
    #     return total_missed_days

    @api.model
    def create_vacation_balance_report(self, employee, limit_date=False):
        cron = self.env.context.get('cron') if 'cron' in self.env.context else False
        valid_to_create_vacation_report = False
        current_date = fields.Date.today()
        if not limit_date:
            limit_date = current_date
        limit_year = limit_date.year

        if employee.contract_type.code == "EXPATRIADO":
            limit_date = date(date.today().year if not limit_date else limit_date.year, 12, 31)

        VacationReport = self.env["vacation.balance.report"]
        employee_admission = employee.admission_date
        # if limit_year < employee_admission.year:
        #     return

        if cron:
            vacation_after_admission = self.env.company.take_vacation_after_admission
            # Buscar o total de meses trabalhados
            work_months = (current_date.year - employee_admission.year) * 12 + (
                    current_date.month - employee_admission.month)
            # Verificar se o colaborar já tem 6 meses de trabalho
            if employee_admission.year == current_date.year and work_months >= vacation_after_admission and employee.contract_type.code in [
                "NACIONAL", 'EXPATRIADO_RESIDENTE']:
                years = [employee_admission.year]
                valid_to_create_vacation_report = True
            else:
                if employee.contract_type.code == "EXPATRIADO":
                    years = range(employee_admission.year, self.env.company.vacation_balance_report_start_date + 1)
                else:
                    years = range(employee_admission.year, limit_year + 1)
        else:
            if employee.contract_type.code == "EXPATRIADO":
                years = range(employee_admission.year, self.env.company.vacation_balance_report_start_date + 1)
            else:
                years = range(employee_admission.year, limit_year + 1)

        for year in years:

            if year > current_date.year:
                continue

            if not valid_to_create_vacation_report and employee.contract_type.code in ["NACIONAL",
                                                                                       'EXPATRIADO_RESIDENTE']:

                # Verificar se quem solicita é o colaborador do tipo Nacional, se for subtrair \
                # menos um ao ano passado em configurações paara a criação do plano de férias
                vacation_balance_report_start_date = self.env.company.vacation_balance_report_start_date
                vacation_balance_report_start_date = vacation_balance_report_start_date - 1
                # if year == self.env.company.vacation_balance_report_start_date:
                #     continue

                # Verificar se o mes da solicitação é o permitido para solicitação de férias, caso sim, avançar e se não validar
                if current_date.month != self.env.company.vacation_balance_report_update_month:
                    # Verificar se o ano é inferior ao ano passado em configurações\
                    # como início de Criação re Relatório de Saldo de Férias
                    # Verificar se o ano escolhido for maior que ano actual, não vançar
                    if year < vacation_balance_report_start_date or limit_year < vacation_balance_report_start_date:
                        continue

            vacation_report = VacationReport.search(
                [("employee_id", "=", employee.id), ("vacation_year", "=", year)]
            )
            end_date = limit_date if type(limit_date) == date else limit_date.date()
            if end_date.year > year:
                end_date = date(year, 12, 31)

            start_date = employee.admission_date
            if start_date.year < year:
                start_date = date(year, 1, 1)
            if not vacation_report:
                vacation_report = VacationReport.create(
                    self.get_vacation_report_values(employee, start_date, end_date)
                )
            vals_to_write = {}

            # TODO Add this method on the default l10n_ao_hr module
            # missed_days = self.get_total_missed_days(employee, start_date, end_date)
            # subtracted_days = (
            #     missed_days
            #     if missed_days <= data["maximum_number_vacation_days_off"]
            #     else data["maximum_number_vacation_days_off"]
            # )
            # vals_to_write = {
            #     "subtracted_days": subtracted_days,
            # }

            if end_date > vacation_report.date_to or not vacation_report.vacation_days:
                vacation_days, dependent_number = employee.calculate_vacation_days(
                    start_date, end_date
                )
                vals_to_write.update(
                    {
                        "vacation_days": vacation_days,
                        "additional_per_dependent_days": dependent_number,
                        "date_to": end_date,
                    }
                )
            if vals_to_write:
                vacation_report.write(vals_to_write)

            # Check if employee left the country for a period and use the value
            # as discount days
            if employee.contract_type.code == "EXPATRIADO":
                hr_leave_country_ids = self.env["hr.leave.country.period"].search(
                    [("employee_id", "=", employee.id), ("vacation_year", "=", year)]
                )
                if hr_leave_country_ids:
                    vacation_report.write(
                        {
                            "discount_days_out_of_country": sum(
                                hr_leave_country_ids.mapped("days_to_discount")
                            )
                        }
                    )

    # TODO Add this method on the default l10n_ao_hr module
    # def get_faltas_sem_remuneracao(self, employee, start_date, end_date):
    #     payslip_model = self.env["hr.payslip"]
    #     hours_week = (
    #         falta_injustificada_days
    #     ) = falta_justificada_sem_remuneracao_days = 0

    #     # PEGAR O EXTERNAR ID DAS FALTAS
    #     falta_injustificada_id = self.env.ref(
    #         "l10n_ao_hr.l10n_ao_hr_type_missed_hours_falta_injustificada"
    #     ).id
    #     falta_justificada_sem_remuneracao_id = self.env.ref(
    #         "l10n_ao_hr.l10n_ao_hr_type_missed_hours_falta_just_nao_remunerada"
    #     ).id

    #     # REVER OS STADOS
    #     payslips_ids = payslip_model.sudo().search(
    #         [
    #             ("employee_id", "=", employee.id),
    #             ("state", "in", ["done", "paid"]),
    #             ("date_from", ">=", start_date),
    #             ("date_to", "<", end_date),
    #         ]
    #     )

    #     falta_injustificada_lines = payslips_ids.input_line_ids.filtered(
    #         lambda r: r.input_type_id.id == falta_injustificada_id
    #     )
    #     falta_justificada_sem_remuneracao_lines = payslips_ids.input_line_ids.filtered(
    #         lambda r: r.input_type_id.id == falta_justificada_sem_remuneracao_id
    #     )
    #     if payslips_ids:
    #         hours_week = payslips_ids[-1].contract_id.resource_calendar_id.hours_per_day

    #     if falta_justificada_sem_remuneracao_lines:
    #         total_hours = sum(falta_justificada_sem_remuneracao_lines.mapped("hours"))
    #         falta_justificada_sem_remuneracao_days = total_hours // hours_week

    #     if falta_injustificada_lines:
    #         total_hours = sum(falta_injustificada_lines.mapped("hours"))
    #         falta_injustificada_days = total_hours // hours_week

    #     return falta_injustificada_days, falta_justificada_sem_remuneracao_days

    def set_vacation_days_enjoyed_overdue(self, employee):
        leave_type_vocation_id = self.env.ref(
            "l10n_ao_hr_holidays.l10n_ao_hr_leave_type_vocation"
        )
        vacation_reports = self.search(
            [
                ("employee_id", "=", employee.id),
            ], order="vacation_year"
        )

        approved_leaves = self.env["hr.leave"].search(
            [
                ("employee_ids", "in", employee.ids),
                ("state", "=", "validate"),
                ("holiday_status_id", "=", leave_type_vocation_id.id),
            ],
            order="request_date_from",
        )
        days_per_leave = {
            leave.id: leave.number_of_days_display for leave in approved_leaves
        }
        for report in vacation_reports:
            date_overdue = date(report.vacation_year + 2, 3, 31)
            leaves = approved_leaves.filtered(
                lambda x: x.request_date_from < date_overdue
                          and x.request_date_from.year >= report.vacation_year
            )
            days_enjoyed = 0
            total_vacation_days = report.total_vacation_days
            # Sum all the validated vacation days
            for leave in leaves:
                days = days_per_leave.get(leave.id)
                if days >= total_vacation_days:
                    days_enjoyed += total_vacation_days
                    days_per_leave[leave.id] -= total_vacation_days
                    break
                else:
                    days_enjoyed += days
                    total_vacation_days -= days
                    days_per_leave[leave.id] -= days

            report.days_already_enjoyed = days_enjoyed
            if date_overdue < fields.Date.today():
                report.overdue_days = total_vacation_days
            else:
                report.overdue_days = 0

    def getVacationBalance(self, user_id, year_selected):
        employee = self.env["hr.employee"].sudo().search([("user_id", "=", user_id)])
        year = (
            year_selected - 1
            if employee.contract_type.code in ["NACIONAL", 'EXPATRIADO_RESIDENTE']
            else year_selected
        )
        vacation_balance_report = self.sudo().search(
            [("employee_id", "=", employee.id), ("vacation_year", "=", year)]
        )
        if vacation_balance_report:
            return [vacation_balance_report.total_balance_days]
        else:
            return []

    def getYearSelected(self, user_id, year_selected):
        employee = self.env["hr.employee"].sudo().search([("user_id", "=", user_id)])
        year = (
            year_selected - 1
            if employee.contract_type.code in ["NACIONAL", 'EXPATRIADO_RESIDENTE']
            else year_selected
        )
        if employee:
            return [year]
        else:
            return [year_selected]

    def send_vacation_leave_notification_email(self):
        template = self.env.ref(
            "l10n_ao_hr_holidays.vacation_leave_notification_email_template"
        )
        template.send_mail(self.id, force_send=True)
