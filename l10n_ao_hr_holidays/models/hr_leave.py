import logging
from datetime import datetime, timedelta, date, time
from odoo import api, models, fields, _
from odoo.exceptions import UserError, ValidationError
import pytz
from odoo.addons.base.models.res_partner import _tz_get

_logger = logging.getLogger(__name__)


class HRLeave(models.Model):
    _inherit = "hr.leave"
    _order = "date_from asc"

    contract_type_id = fields.Many2one(related='employee_id.contract_type', compute_sudo=True, store=True)
    direction_id = fields.Many2one("hr.direction", string='Direcção', compute="_compute_direction",
                                   store=True)
    number_extra_hours = fields.Float(string="Hours Worked", digits=(16, 6), compute='_compute_date_check_in_to')
    check_in = fields.Datetime(string="Check-in")
    check_out = fields.Datetime(string="Check-out")
    time_type = fields.Selection(related='holiday_status_id.time_type', readonly=True)
    extra_hours_date = fields.Date(string="Extra Hours Date")
    extra_hours_time_from = fields.Float(string="Hours From")
    extra_hours_time_to = fields.Float(string="Hours To")
    tz = fields.Selection(_tz_get, string='Timezone', default=lambda self: self._context.get('tz'))

    @api.constrains('check_in', 'check_out')
    def _check_dates(self):
        if self.check_in > self.check_out:
            raise ValidationError(_("The start date of disciplinary action must be earlier than the end date."))

    @api.constrains('date_from', 'date_to', 'employee_id')
    def _check_date(self):
        for record in self:
            leave_extra_hours_id = self.env['hr.leave.type'].search(
                [('time_type', '=', 'extra_hour'), ('company_id', '=', self.env.company.id)], limit=1).id
            if record.holiday_status_id == leave_extra_hours_id:
                return

        result = super(HRLeave, self)._check_date()
        return result

    @api.onchange('check_in')
    def _onchange_check_in(self):
        if self.check_in:
            self.request_date_from = self.check_in.date()

    @api.onchange('check_out')
    def _onchange_check_out(self):
        if self.check_out:
            self.request_date_to = self.check_out.date()

    @api.constrains('check_in', 'check_out')
    def _constrains_dates(self):
        for record in self:
            if record.check_in and record.check_out:
                record.write({
                    'date_from': record.check_in,
                    'date_to': record.check_out,
                })

    def _check_overtime_deductible(self, leaves):
        # If the type of leave is overtime deductible, we have to check that the employee has enough extra hours

        for leave in leaves:
            if leave.time_type in ['extra_hour', 'delay']:
                continue

            if not leave.overtime_deductible:
                continue
            employee = leave.employee_id.sudo()
            duration = leave.number_of_hours_display
            if duration > employee.total_overtime:
                if employee.user_id == self.env.user:
                    raise ValidationError(_('You do not have enough extra hours to request this leave'))
                raise ValidationError(_('The employee does not have enough extra hours to request this leave.'))
            if not leave.overtime_id:
                leave.sudo().overtime_id = self.env['hr.attendance.overtime'].sudo().create({
                    'employee_id': employee.id,
                    'date': leave.date_from,
                    'adjustment': True,
                    'duration': -1 * duration,
                })

    @api.constrains('extra_hours_date', 'extra_hours_time_from', 'extra_hours_time_to')
    def _check_extra_hours_import(self):
        for record in self:
            if record.extra_hours_date and record.extra_hours_time_from and record.extra_hours_time_to:
                if record.extra_hours_time_from > self.extra_hours_time_to:
                    raise ValidationError(_("The start time of extra hours must be earlier than the end time."))

    @api.depends('check_in', 'check_out', 'employee_id')
    def _compute_date_check_in_to(self):
        for holiday in self:
            number_extra_hours = 0
            if holiday.check_in and holiday.check_out:
                time_difference = holiday.check_out - holiday.check_in
                total_seconds = time_difference.total_seconds()
                total_hours = total_seconds // 3600
                total_minutes = (total_seconds % 3600) // 60
                total_seconds = total_hours * 3600 + total_minutes * 60
                number_extra_hours = total_seconds / 3600

                holiday.number_of_days = (holiday.check_out - holiday.check_in).days + 1

            holiday.number_extra_hours = number_extra_hours

    def _combine_date_and_hour(self, date, hour_float):
        """Helper para combinar data com hora decimal (ex: 18.5 => 18:30)"""
        hours = int(hour_float)
        minutes = int((hour_float - hours) * 60)
        return datetime.combine(date, datetime.min.time()) + timedelta(hours=hours, minutes=minutes)

    @api.constrains('extra_hours_date', 'extra_hours_time_from', 'extra_hours_time_to')
    def _constrains_extra_hours_import(self):
        for record in self:
            if record.extra_hours_date and record.extra_hours_time_from is not None and record.extra_hours_time_to is not None:
                check_in = self._combine_date_and_hour(record.extra_hours_date, record.extra_hours_time_from)
                check_out = self._combine_date_and_hour(record.extra_hours_date, record.extra_hours_time_to)
                record.write({
                    'check_in': check_in,
                    'check_out': check_out,
                    'date_from': check_in,
                    'date_to': check_out,
                })

    @api.depends(
        "department_id",
    )
    def _compute_direction(self):
        for record in self:
            if record.employee_id:
                record.direction_id = record.employee_id.direction_id
            else:
                record.direction_id = False

    def action_approve(self):
        super(HRLeave, self).action_approve()
        for leave in self:
            if not (
                    leave.employee_id.leave_manager_id.id == self.env.user.id
                    or self.user_has_groups("hr_holidays.group_hr_holidays_manager")
            ):
                raise UserError(
                    _(
                        "Não pode Aprovar um pedido de Férias por não ser o "
                        "Gestor de Ausências do Colaborador. "
                        "Entre em contato com o Departamento do Capital Humano."
                    )
                )

    def action_validate(self):
        super(HRLeave, self).action_validate()
        for leave in self:
            if not self.user_has_groups("hr_holidays.group_hr_holidays_manager"):
                if leave.holiday_status_id.leave_validation_type in ['hr', 'both']:
                    if leave.holiday_status_id.leave_validation_type == 'hr':
                        if not leave.holiday_status_id.responsible_id.id == self.env.user.id:
                            raise UserError(
                                _(
                                    "Não pode Validar um pedido de Férias por não ser o "
                                    "Responsável de Ausências. "
                                    "Entre em contato com o Departamento do Capital Humano."
                                )
                            )
                    elif leave.holiday_status_id.leave_validation_type == 'both':
                        responsible_ids = leave.holiday_status_id.responsible_ids.ids
                        responsible_ids += leave.holiday_status_id.responsible_id.id
                        if self.env.user.id not in responsible_ids:
                            raise UserError(
                                _(
                                    "Não pode Validar um pedido de Férias por não ser o "
                                    "Responsável de Ausências. "
                                    "Entre em contato com o Departamento do Capital Humano."
                                )
                            )

    def action_refuse(self):
        for leave in self:
            leave_type_vocation_id = self.env.ref(
                "l10n_ao_hr_holidays.l10n_ao_hr_leave_type_vocation"
            ).id
            leave_falta_injustificadas_id = self.env.ref(
                "l10n_ao_hr_holidays.l10n_ao_hr_leave_typ_falta_injustificada"
            ).id
            # Verificar se o utilizador é Administrador de Ausências para recusar mesmo estando validado
            if not self.user_has_groups("hr_holidays.group_hr_holidays_manager") and leave.state == "validate":
                if leave.holiday_status_id.id in [leave_type_vocation_id, leave_falta_injustificadas_id]:
                    raise UserError(
                        _(
                            "Não pode recusar um pedido de Férias ou Falta Injustificada já validado. "
                            "Entre em contato com o Departamento do Capital Humano."
                        )
                    )

        return super().action_refuse()

    # Get the number of months since admission for one employee
    def get_employee_months_since_admission(self, employee):
        self.ensure_one()
        start_date = employee.first_contract_date
        if start_date:
            return (self.date_from.year - start_date.year) * 12 + (
                    self.date_from.month - start_date.month
            )
        return 0

    def get_employees_from_leave(self):
        self.ensure_one()
        if self.holiday_type == "employee":
            employees = self.employee_ids
        elif self.holiday_type == "category":
            employees = self.category_id.employee_ids
        elif self.holiday_type == "company":
            employees = self.env["hr.employee"].search(
                [("company_id", "=", self.mode_company_id.id)]
            )
        else:
            employees = self.department_id.member_ids
        return employees

    def rule_vacation_minimun_days(self, employee):
        dayofweek = employee.resource_calendar_id.attendance_ids.mapped("dayofweek")
        # if round(self.number_of_days_display) < len(set(dayofweek)):
        #     raise UserError(
        #         _(
        #             f"O Colaborador {employee.name} não pode tirar férias "
        #             f"com dias menor que {len(set(dayofweek))}, de lembrar "
        #             "que os dias devem ser maior ou igual ao total do dia da semana."
        #         )
        #     )

    def rule_vacation_year_change(self, employee):
        # if (
        #         employee.first_contract_date
        #         and employee.first_contract_date.year == self.date_from.year
        # ) or not employee.first_contract_date:
        #     raise UserError(
        #         _(
        #             f"O colaborador {employee.name} não tem permissão para "
        #             "solicitar férias, pois deve mudar de ano ano para ter acesso às férias."
        #         )
        #     )
        return True

    def rule_vacation_work_period(self, employee):
        vacation_after_admission = self.env.company.take_vacation_after_admission
        work_months = self.get_employee_months_since_admission(employee)
        if not self.holiday_status_id.dont_validate_vacation:
            if vacation_after_admission > work_months:
                raise UserError(
                    _(
                        f"O colaborador {employee.name} não pode gozar férias, por não "
                        f"cumprir os {vacation_after_admission} meses definidos para "
                        "gozo de férias."
                    )
                )

    # This method can be inherited to easily add new rules
    def run_vacation_rules(self, employee):
        self.rule_vacation_minimun_days(employee)
        self.rule_vacation_work_period(employee)
        self.rule_vacation_year_change(employee)

    def write(self, vals):
        res = super().write(vals)
        leave_type_vocation_id = self.env.ref(
            "l10n_ao_hr_holidays.l10n_ao_hr_leave_type_vocation"
        )
        leave_falta_injustificadas_id = self.env.ref(
            "l10n_ao_hr_holidays.l10n_ao_hr_leave_typ_falta_injustificada"
        )
        for record in self:
            employees = record.get_employees_from_leave()
            if (
                    leave_type_vocation_id == record.holiday_status_id
                    and record.state != "refuse"
            ):
                current_date = datetime.now().date()
                date_from = record.date_from.date()
                # VERIFICAR SE NÃO FOI ESCOLHIDA A DATA NO PASSADO
                if not record.holiday_status_id.dont_validate_vacation:
                    if date_from < current_date and record.state in ["draft", "confirm"]:
                        raise UserError(
                            _(
                                "Não é permitido selecionar uma data que esteja no passado,"
                                " corrija-a para prosseguir."
                            )
                        )

                # employees = record.get_employees_from_leave()
                for employee in employees:
                    if record.state == "validate":
                        # Reduzir os dias no relatório de férias do colaborador
                        self.env["vacation.balance.report"].sudo().set_vacation_days_enjoyed_overdue(employee)

                        # Criar as presenças no módulo de ATTENDANCE
                        lista_datas = [(record.date_from + timedelta(days=i))
                                       for i in range((record.date_to - record.date_from).days + 1)]
                        for date_time in lista_datas:
                            dayofweek = str(date_time.weekday())
                            # Filtrar os horários de trabalho do calendário do funcionário para o dia do ponto
                            attendance_start_line = employee.resource_calendar_id.attendance_ids.filtered(
                                lambda x: x.dayofweek == dayofweek and x.day_period == 'morning'
                            )
                            attendance_end_lines = employee.resource_calendar_id.attendance_ids.filtered(
                                lambda x: x.dayofweek == dayofweek and x.day_period == 'afternoon'
                            )
                            if attendance_start_line and attendance_end_lines:
                                work_start_hour = min(attendance_start_line.mapped('hour_from'))
                                official_start_time = datetime.combine(date_time.date(),
                                                                       time(int(work_start_hour),
                                                                            int((work_start_hour % 1) * 60)))
                                work_end_hour = max(attendance_end_lines.mapped('hour_to'))
                                official_end_time = date_time.replace(hour=int(work_end_hour),
                                                                      minute=int((work_end_hour % 1) * 60),
                                                                      second=0)
                                # Criar um registo de presença para o funcionário
                                self.create_attendance(employee, official_start_time, official_end_time)
                            elif attendance_start_line and not attendance_end_lines:
                                work_start_hour = min(attendance_start_line.mapped('hour_from'))
                                official_start_time = datetime.combine(date_time.date(),
                                                                       time(int(work_start_hour),
                                                                            int((work_start_hour % 1) * 60)))
                                work_end_hour = max(attendance_start_line.mapped('hour_to'))
                                official_end_time = date_time.replace(hour=int(work_end_hour),
                                                                      minute=int((work_end_hour % 1) * 60),
                                                                      second=0)
                                # Criar um registo de presença para o funcionário
                                self.create_attendance(employee, official_start_time, official_end_time)
                    else:
                        record.run_vacation_rules(employee)
                        record.check_vacation_balance_report(employee)
            elif (
                    leave_falta_injustificadas_id == record.holiday_status_id
                    and vals.get("state") == "validate"
            ):
                for employee in employees:
                    record.set_vacation_report_subtracted_days(employee)

        return res

    def set_vacation_report_subtracted_days(self, employee):
        # Subtrair os dias de férias do colaborador quando existe uma falta injustificada
        currente_year = fields.Date.today()
        year = currente_year.year
        vacation_balance_report = (
            self.env["vacation.balance.report"].sudo().search([
                ("employee_id", "=", employee.id),
                ("vacation_year", "=", year - 1 if employee.contract_type.code == "NACIONAL" else year)])
        )
        if vacation_balance_report:
            if (
                    vacation_balance_report.subtracted_days
                    < self.env.company.vacation_subtract_days_limit_nacional
            ):
                vacation_balance_report.subtracted_days += self.number_of_days_display

    def get_vacation_report(self, employee_id):
        leave_type_vocation_id = self.env.ref(
            "l10n_ao_hr_holidays.l10n_ao_hr_leave_type_vocation"
        )
        VacationReport = self.env["vacation.balance.report"].sudo()
        VacationReport.create_vacation_balance_report(employee_id, self.date_from)
        VacationReport.set_vacation_days_enjoyed_overdue(employee_id)
        return VacationReport, leave_type_vocation_id

    def get_validate_leave(self, employee_ids, leave_id):
        try:
            leave_ids = self.env["hr.leave"].search(
                [
                    ("employee_ids", "in", employee_ids),
                    ("state", "=", "validate"),
                    ("holiday_status_id", "=", leave_id)
                ]
            )
            return leave_ids
        except Exception as e:
            _logger.info(e)
            return False

    def get_other_leave_ids(self, employee_ids, leave_type_vocation_id):
        other_leave_ids = self.env["hr.leave"].search(
            [
                ("employee_ids", "in", employee_ids),
                ("state", "not in", ("validate", "refuse")),
                ("holiday_status_id", "=", leave_type_vocation_id.id),
                ("id", "!=", self.id),
            ],
            order="request_date_from",
        )
        return other_leave_ids

    def get_validate_vacation_leave_ids(self, employee_ids):
        leave_type_vocation_id = self.env.ref('l10n_ao_hr_holidays.l10n_ao_hr_leave_type_vocation').id
        current_date = datetime.now()
        current_year = current_date.year
        first_day_year = date(current_year, 1, 1)
        last_day_year = date(current_year, 12, 31)
        leave_id = self.env["hr.leave"].search(
            [
                ("employee_ids", "in", employee_ids),
                ("state", "=", "validate"),
                ('date_from', '>=', first_day_year),
                ('date_to', '<', last_day_year),
                ("holiday_status_id", "=", leave_type_vocation_id),
            ], limit=1, order='date_from'
        )
        return leave_id

    def get_validate_leave_ids(self, employee_ids, first_date, end_date):
        leave_id = self.env["hr.leave"].search(
            [
                ("employee_ids", "in", employee_ids),
                ("state", "=", "validate"),
                ('date_from', '<=', end_date),
                ('date_to', '>=', first_date),
            ]
        )
        return leave_id

    def create_attendance(self, employee, start_time, end_time):
        attendance_id = self.env['hr.attendance'].sudo().search([('employee_id', '=', employee.id)])
        attendance_id = attendance_id.filtered(
            lambda x: x.check_in.date() == start_time.date() or x.check_out == end_time.date())
        if not attendance_id:
            attendance_id = self.env['hr.attendance'].sudo().create({
                'employee_id': employee.id,
                'check_in': self.set_default_timezone(start_time),
                'check_out': self.set_default_timezone(end_time),
            })

    def check_vacation_balance_report(self, employee_id, year=False):
        if not year:
            year = self.date_from.year - 1

        vacation_after_admission = self.env.company.take_vacation_after_admission
        current_date = fields.Date.today()
        employee_admission = employee_id.first_contract_date
        # Buscar o total de meses trabalhados
        work_months = (self.date_from.year - employee_admission.year) * 12 + (
                self.date_from.month - employee_admission.month)

        # Check the total of vacNACIONALations days on balance report
        # to see if the user can request vacations
        # Get Vacation Report and prevent current leave being added to the days enjoyed
        VacationReport, leave_type_vocation_id = self.with_context(
            filter_leave_ids=self.ids
        ).get_vacation_report(employee_id)

        # Verificar se o colaborar já tem 6 meses de trabalho
        if employee_admission.year >= current_date.year and work_months <= vacation_after_admission:
            vacation_report_ids = VacationReport.search(
                [
                    ("employee_id", "=", employee_id.id),
                    ("vacation_year", "=", employee_admission.year),
                    ("state", "=", 'active'),
                ],
                order="vacation_year desc",
            )
        else:
            vacation_report_ids = VacationReport.search(
                [
                    ("employee_id", "=", employee_id.id),
                    ("state", "=", 'active'),
                    # ("vacation_year", "=", year),
                ],
                order="vacation_year desc",
            )

        # balance_days = sum(vacation_report_ids.mapped("total_balance_days")) + sum(
        #     vacation_report_ids.mapped("days_not_taken"))
        balance_days = sum(vacation_report_ids.mapped("total_balance_days"))

        # Search for other leaves not approved yet
        other_leave_ids = self.get_other_leave_ids(
            self.employee_ids.ids, leave_type_vocation_id
        )
        balance_days -= sum(item.number_of_days_display for item in other_leave_ids)

        if balance_days < round(self.number_of_days_display):
            raise UserError(
                _(
                    f"O colaborador tem apenas {balance_days} "
                    "dias para gozar de férias!"
                )
            )
        if vacation_report_ids and vacation_report_ids[0].total_balance_days < round(
                self.number_of_days_display
        ):
            raise UserError(
                _(
                    f"O colaborador pode solicitar apenas {vacation_report_ids[0].total_balance_days} "
                    "dias em uma único período de férias!"
                )
            )

    # This method created the analytic lines for the
    # holidays, but we are doing that using a cron.
    def _timesheet_create_lines(self):
        return

    @api.depends("number_of_days")
    def _compute_number_of_days_display(self):
        for holiday in self:
            # Verificar se foi escolhido o tipo de ausência Férias
            if (
                    not holiday.holiday_status_id
                    or holiday.holiday_status_id.id
                    != self.env.ref("l10n_ao_hr_holidays.l10n_ao_hr_leave_type_vocation").id
            ):
                holiday.number_of_days_display = holiday.number_of_days

            _logger.info(
                f'_compute_number_of_days_display: {holiday.holiday_status_id.id} == {self.env.ref("l10n_ao_hr_holidays.l10n_ao_hr_leave_type_vocation").id}'
            )
            interval_dates = holiday.get_interval_dates(
                holiday.date_from, holiday.date_to
            )
            if holiday.employee_id.holiday_processing_policy != "individual":
                """Calcular total de dias de feriado para subtrair ao total de dias de gozo"""
                holiday_days = holiday.get_holiday_days(interval_dates)
                _logger.info(
                    f"interval_dates: {len(interval_dates)} - holiday_days: {holiday_days}"
                )
                """Subtrair o total de dias solicitados com base nos dias de feriados"""
                holiday.number_of_days_display = len(interval_dates) - holiday_days
            else:
                holiday.number_of_days_display = interval_dates

    @api.depends("date_from", "date_to", "employee_id")
    def _compute_number_of_days(self):
        for holiday in self:
            if holiday.date_from and holiday.date_to:
                # Verificar se foi escolhido o tipo de ausência Férias
                if (
                        holiday.holiday_status_id.id
                        != self.env.ref(
                    "l10n_ao_hr_holidays.l10n_ao_hr_leave_type_vocation"
                ).id
                ):
                    holiday.number_of_days = holiday._get_number_of_days(
                        holiday.date_from, holiday.date_to, holiday.employee_id.id
                    )["days"]

                _logger.info(
                    f'_compute_number_of_days: {holiday.holiday_status_id.id} == {self.env.ref("l10n_ao_hr_holidays.l10n_ao_hr_leave_type_vocation").id}'
                )
                interval_dates = holiday.get_interval_dates(
                    holiday.date_from, holiday.date_to
                )
                # if holiday.employee_id.contract_type.code == "EXPATRIADO" and holiday.employee_id.holiday_processing_policy == "individual":
                if holiday.employee_id.holiday_processing_policy == "individual":
                    holiday.number_of_days = interval_dates
                else:
                    """Calcular total de dias de feriado para subtrair ao total de dias de gozo"""
                    holiday_days = holiday.get_holiday_days(interval_dates)
                    _logger.info(
                        f"interval_dates: {len(interval_dates)} - holiday_days: {holiday_days}"
                    )
                    """Subtrair o total de dias solicitados com base nos dias de feriados"""
                    holiday.number_of_days = len(interval_dates) - holiday_days
            else:
                holiday.number_of_days = 0

    def get_holiday_days(self, interval_date_list):
        interval_date_list = [date.date() for date in interval_date_list]
        days = 0
        """ Buscar todos os registos de feriados"""
        calendar_leave_ids = (
            self.env["resource.calendar.leaves"]
            .sudo()
            .search([("is_active", "=", True), ("holiday_id", "=", False), ('company_id', '=', self.env.company.id)])
        )

        for calendar_leave in calendar_leave_ids:
            interval_dates = (
                calendar_leave.date_from + timedelta(days=idx)
                for idx in range(
                (calendar_leave.date_to - calendar_leave.date_from).days + 1
            ))
            interval_dates = [day.date() for day in interval_dates]
            """ Filtra apenas os dias úteis dias da semana """
            for date in [day for day in interval_dates]:
                if date in interval_date_list:
                    days += 1
        return days

    def get_extra_holiday_days(self, interval_date_list, first_date, end_date):
        interval_date_list = [date for date in interval_date_list]
        days = []
        """ Buscar todos os registos de feriados"""
        calendar_leave_ids = (
            self.env["resource.calendar.leaves"]
            .sudo()
            .search([("is_active", "=", True), ('company_id', '=', self.env.company.id)])
        )
        calendar_leave_ids = calendar_leave_ids.filtered(
            lambda x: x.date_from.date() <= end_date and x.date_to.date() >= first_date
        )
        for calendar_leave in calendar_leave_ids:
            # calendar_leave.date_from = calendar_leave.date_from + timedelta(hours=1)
            date_from = self.set_default_timezone(calendar_leave.date_from)
            interval_dates = (
                date_from + timedelta(days=idx)
                for idx in range(
                (calendar_leave.date_to - date_from).days + 1
            ))
            interval_dates = [day.date() for day in interval_dates]
            days.extend([date for date in interval_dates if date in interval_date_list])

        return days

    def set_default_timezone(self, date_time):
        """
        Set the default timezone for the given datetime object.
        If the datetime object is naive (no timezone info), it will be localized to the user's timezone.
        If the datetime object is aware (has timezone info), it will be converted to the user's timezone.
        """
        for record in self:
            user_tz_name = record.tz or 'UTC'
            timezone = pytz.timezone(user_tz_name)

            if date_time.tzinfo is None:
                date_time = timezone.localize(date_time)
            else:
                date_time = date_time.astimezone(timezone)

            return date_time.astimezone(pytz.utc).replace(tzinfo=None)

    def get_interval_dates(self, date_from, date_to):
        # Para os da Politica Individual tem 40 dias corridos de gozo de férias
        if (
                self.employee_id.holiday_processing_policy == "individual"
        ):
            intervale_dates = (
                date_from + timedelta(days=idx)
                for idx in range((date_to - date_from).days + 1)
            )
            # [day for day in intervale_dates]
            """Filtra todos os dias corridos dias da semana"""
            return (date_to - date_from).days + 1
        else:
            intervale_dates = (
                date_from + timedelta(days=idx)
                for idx in range((date_to - date_from).days + 1)
            )
            """Filtra apenas os dias úteis dias da semana"""
            return [day for day in intervale_dates if day.weekday() < 5]

    def unlink(self):
        if not self.holiday_status_id.dont_validate_vacation:
            raise UserError(
                _(
                    "Por mótivos de segurança não é permitido eliminar um registo "
                    "de Ausências. Para actualizar as informações basta retornar para o estado rascunho"
                    "ou Entrar em contacto com suporte Odoo"
                )
            )
        return super(HRLeave, self).unlink()
