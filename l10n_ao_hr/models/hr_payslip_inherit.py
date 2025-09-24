from datetime import datetime, timedelta, date
from odoo import api, fields, models, tools, _
from odoo.addons import decimal_precision as dp
from . import amount_currency_translate_pt
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_round, date_utils, convert_file, html2plaintext, is_html_empty, format_amount
from collections import defaultdict
from dateutil.relativedelta import relativedelta
from odoo.tools import format_date
import logging
import random
import calendar

_logger = logging.getLogger(__name__)


def calc_age(birthday):
    today = fields.Date.today()
    return (today.year - birthday.year) - (
            (today.month, today.day) < (birthday.month, birthday.day)
    )


class HRPayslip(models.Model):
    _inherit = 'hr.payslip'

    user_id = fields.Many2one("res.users", string="Utilizador", default=lambda self: self.env.user)
    remuneration = fields.Float(compute='compute_remuneration', digits=(10, 2), string='Remuneração',
                                help='This is the Wage amount')
    overtimes = fields.Float(compute='compute_overtimes', digits=(10, 2), string='Horas Extras',
                             help='This is the total amount for Overtimes')
    extra_remunerations = fields.Float(compute='compute_extra_remunerations', digits=(10, 2),
                                       string='Remuneração Extra')
    misses = fields.Float(compute='compute_misses', digits=(10, 2), string='Misses',
                          help='This is the total discount for misses')
    remuneration_inss_base = fields.Float(compute='compute_remuneration_inss_base', digits=(10, 2),
                                          string='Base Remuneração INSS',
                                          help='This is the Wage plus Overtime minus Misses')
    remuneration_inss_extra = fields.Float(compute='compute_remuneration_inss_extra', digits=(10, 2),
                                           string='Remuneração Extra INSS',
                                           help='Those are other INSS collectible remunerations')
    remuneration_inss_total = fields.Float(compute='compute_remuneration_inss_total', digits=(10, 2),
                                           string='Remuneração Bruta')
    amount_inss = fields.Float(compute='compute_amount_inss', digits=(10, 2), string='Valor de INSS')
    amount_inss8 = fields.Float(compute='compute_amount_inss8', digits=(10, 2), string='Valor de INSS 8%')
    amount_irt = fields.Float(compute='compute_amount_irt', digits=(10, 2), string='Valor de IRT')
    extra_deductions = fields.Float(compute='compute_extra_deductions', digits=(10, 2), string='Dedução Extra')
    amount_base_irt = fields.Float(compute='compute_amount_base_irt', digits=(10, 2), string='Valor Base de IRT')
    period_working_days = fields.Integer(compute='compute_period_working_days', string='Dias de Pagamento')
    payslip_period = fields.Char(compute='compute_payslip_period', string='Período de Processamento')
    total_remunerations = fields.Float(compute='compute_total_remunerations', digits=(10, 2),
                                       string='Total das Remunerações')
    total_deductions = fields.Float(compute='compute_total_deductions', digits=(10, 2), string='Total das Deduções')
    total_paid = fields.Float(compute='compute_total_paid', digits=(10, 2), string='Total Líquido')
    currency_rate = fields.Float('Taxa de Câmbio', dp.get_precision('Payroll Rate'), compute='compute_currency_rate',
                                 store=True)
    total_paid_usd = fields.Float(compute='compute_total_paid_usd', digits=(10, 2), string='Contra Valor (USD)')
    total_paid_euro = fields.Float(compute='compute_total_paid_euro', digits=(10, 2), string='Contra Valor (EURO)')
    show_total_paid_usd = fields.Boolean(compute='compute_show_total_paid_usd', string='Mostrar total líquido (USD)')
    wage = fields.Monetary(compute='compute_payslip_line', string='Salário Base')
    total_paid_words = fields.Char(string="Total pago em extenso")
    hour_salary = fields.Float(compute='compute_hour_salary', digits=(10, 2), string='Salário Hora')
    worked_days = fields.Float(compute='compute_worked_days', string='Dias Trabalhados')
    contract_type_id = fields.Many2one(related='contract_id.contract_type_id')
    exchange_rate_id = fields.Many2one('hr.exchange.rate', string='Taxa de Câmbio')
    exchange_rate = fields.Float(string='Câmbio de Processamento', readonly=True, store=True)
    process_automatically_exchange = fields.Boolean(related='company_id.process_automatically_exchange')
    salary_kz = fields.Boolean(related='contract_id.salary_kz')
    employee_register_number = fields.Char(related='employee_id.registration_number')
    total_recept_kz = fields.Float(compute='compute_total_receipt_kz', digits=(10, 2), string='Total Líquido (KZ)')
    total_recept_usd_kz = fields.Float(compute='compute_total_receipt_usd_kz', digits=(10, 2),
                                       string='Total Líquido (KZ)')
    total_remunerations_exp = fields.Float(digits=(10, 2), string='Total das Remunerações')
    allowance_exp = fields.Float(digits=(10, 2), string='Ajuda de Custo')
    process_irt_vacation = fields.Boolean(string='Processar o valor do IRT do subsídio de férias separado')
    dont_fixed_remunerations = fields.Boolean(string='Não Existe Subsídios Fixos', default=False)
    dont_process_allowance_automatically = fields.Boolean(string='Não processar faltas e atrasos automaticamente',
                                                          default=False)
    dont_return_irt = fields.Boolean(string='Não efectuar o reboot do IRT', default=False)
    dont_process_christmas_allowance = fields.Boolean(string='Não processar Subsídio de Natal', default=False)
    collected_material_irt = fields.Float("Collected Material IRT")
    collected_material_irt_with_exedent = fields.Float("Collected Material IRT with Exedent")
    collected_material_inss = fields.Float("Collected Material INSS")
    fam_allowance_amount = fields.Float("Fam Allowance Amount")
    dont_include_base_rule = fields.Boolean(string="Não processar salário base")

    @api.onchange('exchange_rate_id')
    def _onchange_exchange_rate_id(self):
        if self.employee_id and self.exchange_rate_id and self.env.company.country_id.code == "AO":
            self.exchange_rate = self.exchange_rate_id.name
            # Voltar a chamar o metodo de calcular o valor do salário base com base no cámbio
            result = self.worked_days_line_ids._compute_amount()

    @api.constrains("employee_id")
    def _check_employee_id(self):
        if self.env.company.country_id.code == "AO":
            for line in self:
                if (
                        line.contract_type_id.id != self.env.ref(
                    'l10n_ao_hr.l10n_ao_hr_contract_type_nacional').id and not line.process_automatically_exchange
                ):
                    if not line.exchange_rate_id and not line.salary_kz:
                        raise ValidationError(
                            _(
                                f"Deve Fornecer a Taxa de Câmbio de processamento do colaborador {line.employee_id.name} "
                                "para prosseguir.!"
                            )
                        )

    @api.model
    def create(self, vals):
        if self.env.company.country_id.code == "AO":
            date_from = self.fecth_date(vals.get('date_from')) if type(vals.get('date_from')) is str else vals.get(
                'date_from')
            date_to = self.fecth_date(vals.get('date_to')) if type(vals.get('date_to')) is str else vals.get('date_to')
            employee_id = self.env['hr.employee'].browse([vals.get('employee_id')])
            payslip_exist = self.verify_payslip_exist(employee_id, date_from, date_to)
            if payslip_exist:
                raise UserError(
                    _("Já existe um processamento salarial do funcionário %s para o mês de %d.", employee_id.name,
                      date_from.month))

            input_lines = False
            # pegar o mes anterior ao mes selecionado no processamento
            # before_month = date_from.month - 1
            # if before_month > 0:
            if self.env.company.holidays_processing_day_start > 0:
                first_date = date(date_from.year, date_from.month - 1 if date_from.month > 1 else 1,
                                  self.env.company.holidays_processing_day_start)
            else:
                first_date = date(date_from.year, date_from.month, date_from.day)

            if self.env.company.holidays_processing_day_end > 0:
                end_date = date(date_from.year, date_from.month, self.env.company.holidays_processing_day_end)
            else:
                end_date = date(date_from.year, date_from.month, date_to.day)

            leave_delays_hours_id = self.env['hr.leave.type'].search(
                [('time_type', '=', 'delay'), ('company_id', '=', self.env.company.id)], limit=1).id
            # HORAS EXTRAS
            leave_extra_hours_id = self.env['hr.leave.type'].search(
                [('time_type', '=', 'extra_hour'), ('company_id', '=', self.env.company.id)],
                limit=1).id
            extra_leave_ids = self.env['hr.leave'].get_validate_leave(employee_id.ids,
                                                                      leave_extra_hours_id)
            extra_leave_ids = extra_leave_ids.filtered(
                lambda x: x.check_in.date() <= end_date and x.check_out.date() >= first_date)
            if extra_leave_ids:
                input_lines = self.check_leave_type_extra_hours(extra_leave_ids, first_date, end_date)

            delays_leave_ids = self.env['hr.leave'].get_validate_leave([employee_id.id],
                                                                       leave_delays_hours_id)
            delays_leave_ids = delays_leave_ids.filtered(
                lambda
                    x: x.check_in.date() <= end_date and x.check_out.date() >= first_date) if delays_leave_ids else []
            if delays_leave_ids:
                input_lines = input_lines + self.check_delays_type(
                    delays_leave_ids) if input_lines else self.check_delays_type(delays_leave_ids)

            # Computar Faltas e atrasos, gozo férias e outras ausencias
            leave_ids = self.check_leave_type(employee_id, first_date, end_date)
            if leave_ids:
                input_lines = input_lines + leave_ids if input_lines else leave_ids

            payslip = super(HRPayslip, self).create(vals)
            if input_lines:
                payslip.input_line_ids = input_lines
            return payslip
        else:
            return super(HRPayslip, self).create(vals)

    def check_delays_type(self, leave_delays_ids):
        input_list = []
        leave_atraso_id = self.env.ref('nk_ao_hr_payroll_attendance.l10n_ao_hr_type_atraso').id
        if leave_delays_ids:
            total_hours = sum([leave.number_extra_hours for leave in leave_delays_ids])
            input_list.append(self.input_type_values(leave_atraso_id, '', len(leave_delays_ids), total_hours))

        return input_list

    def check_leave_type(self, employee_id, first_date, end_date):
        input_list = []
        hours_per_day = employee_id.resource_calendar_id.hours_per_day
        # venc = abs(employee_id.contract_id.contract_wage)
        salary_hour = employee_id.contract_id.wage_hour

        leave_ids = self.env['hr.leave'].get_validate_leave_ids(employee_id.ids, first_date, end_date)

        # Casamaneto
        leave_type_casam_ids = leave_ids.filtered(
            lambda
                x: x.date_from.date() <= end_date and x.date_to.date() >= first_date and x.holiday_status_id == self.env.ref(
                'l10n_ao_hr_holidays.l10n_ao_hr_leave_typ_licenca_casamento'))
        if leave_type_casam_ids:
            lice_casamento_id = self.env.ref('l10n_ao_hr.l10n_ao_hr_licenca_casamento').id
            total_days = sum([leave.number_of_days for leave in leave_type_casam_ids])
            hours = hours_per_day * total_days
            amount = (hours * salary_hour)
            if len(leave_type_casam_ids) > 1:
                input_list.append(
                    self.input_type_values(lice_casamento_id, False, False, total_days, amount, hours))
            else:
                input_list.append(
                    self.input_type_values(lice_casamento_id, leave_type_casam_ids.date_from,
                                           leave_type_casam_ids.date_to, total_days, amount, hours))

        # Licença Paternal
        leave_type_patern_ids = leave_ids.filtered(
            lambda
                x: x.date_from.date() <= end_date and x.date_to.date() >= first_date and x.holiday_status_id == self.env.ref(
                'l10n_ao_hr_holidays.l10n_ao_hr_leave_typ_licenca_paternal'))
        if leave_type_patern_ids:
            lice_paternal_id = self.env.ref('l10n_ao_hr.l10n_ao_hr_licenca_paternal').id
            total_days = sum([leave.number_of_days for leave in leave_type_patern_ids])
            hours = hours_per_day * total_days
            amount = (hours * salary_hour)
            if len(leave_type_patern_ids) > 1:
                input_list.append(
                    self.input_type_values(lice_paternal_id, False, False, total_days, amount, hours))
            else:
                input_list.append(
                    self.input_type_values(lice_paternal_id, leave_type_patern_ids.date_from,
                                           leave_type_patern_ids.date_to, total_days, amount, hours))

        # Licença sem Vencimento
        leave_type_sem_venc_ids = leave_ids.filtered(
            lambda
                x: x.date_from.date() <= end_date and x.date_to.date() >= first_date and x.holiday_status_id == self.env.ref(
                'l10n_ao_hr_holidays.l10n_ao_hr_leave_typ_licenca_sem_remunercao'))
        if leave_type_sem_venc_ids:
            lice_sem_remunera_id = self.env.ref('l10n_ao_hr.l10n_ao_hr_licenca_sem_vencimento').id
            total_days = sum([leave.number_of_days for leave in leave_type_sem_venc_ids])
            hours = hours_per_day * total_days
            amount = (hours * salary_hour)
            if len(leave_type_sem_venc_ids) > 1:
                input_list.append(
                    self.input_type_values(lice_sem_remunera_id, False, False, total_days, amount, hours))
            else:
                input_list.append(
                    self.input_type_values(lice_sem_remunera_id, leave_type_sem_venc_ids.date_from,
                                           leave_type_sem_venc_ids.date_to, total_days, amount, hours))

        # Trabalho Remoto
        leave_type_remote_ids = leave_ids.filtered(
            lambda
                x: x.date_from.date() <= end_date and x.date_to.date() >= first_date and x.holiday_status_id == self.env.ref(
                'l10n_ao_hr_holidays.l10n_ao_hr_leave_typ_trabalho_remoto'))
        if leave_type_remote_ids:
            traba_remoto_id = self.env.ref('l10n_ao_hr.l10n_ao_hr_remote_work').id
            total_days = sum([leave.number_of_days for leave in leave_type_remote_ids])
            hours = hours_per_day * total_days
            amount = (hours * salary_hour)
            if len(traba_remoto_id) > 1:
                input_list.append(
                    self.input_type_values(traba_remoto_id, False, False, total_days, amount, hours))
            else:
                input_list.append(
                    self.input_type_values(traba_remoto_id, leave_type_remote_ids.date_from,
                                           leave_type_remote_ids.date_to, total_days, amount, hours))

        # Gozo Férias
        leave_type_gozo_ids = leave_ids.filtered(
            lambda
                x: x.date_from.date() <= end_date and x.date_to.date() >= first_date and x.holiday_status_id == self.env.ref(
                'l10n_ao_hr_holidays.l10n_ao_hr_leave_type_vocation'))
        if leave_type_gozo_ids:
            gozo_feria_id = self.env.ref('l10n_ao_hr.l10n_ao_hr_gozo_ferias').id
            total_days = sum([leave.number_of_days for leave in leave_type_gozo_ids])
            hours = hours_per_day * total_days
            amount = (hours * salary_hour)
            if len(leave_type_gozo_ids) > 1:
                input_list.append(
                    self.input_type_values(gozo_feria_id, False, False, total_days, amount, hours))
            else:
                input_list.append(
                    self.input_type_values(gozo_feria_id, leave_type_gozo_ids.date_from,
                                           leave_type_gozo_ids.date_to, total_days, amount, hours))

        # Licença Maternidade
        leave_type_lice_matern_ids = leave_ids.filtered(
            lambda
                x: x.date_from.date() <= end_date and x.date_to.date() >= first_date and x.holiday_status_id == self.env.ref(
                'l10n_ao_hr_holidays.l10n_ao_hr_leave_typ_licenca_maternidade'))
        if leave_type_lice_matern_ids:
            lice_maternidade_id = self.env.ref('l10n_ao_hr.l10n_ao_hr_licenca_maternidade').id
            total_days = sum([leave.number_of_days for leave in leave_type_lice_matern_ids])
            hours = hours_per_day * total_days
            amount = (hours * salary_hour)
            if len(leave_type_lice_matern_ids) > 1:
                input_list.append(
                    self.input_type_values(lice_maternidade_id, False, False, total_days, amount, hours))
            else:
                input_list.append(
                    self.input_type_values(lice_maternidade_id, leave_type_lice_matern_ids.date_from,
                                           leave_type_lice_matern_ids.date_to, total_days, amount, hours))

            # Licença Pré-Maternidade
        leave_type_pre_matern_ids = leave_ids.filtered(
            lambda
                x: x.date_from.date() <= end_date and x.date_to.date() >= first_date and x.holiday_status_id == self.env.ref(
                'l10n_ao_hr_holidays.l10n_ao_hr_leave_typ_licenca_pre_maternidade'))
        if leave_type_pre_matern_ids:
            lice_maternidade_id = self.env.ref('l10n_ao_hr.l10n_ao_hr_licenca_pre_maternidade').id
            total_days = sum([leave.number_of_days for leave in leave_type_pre_matern_ids])
            hours = hours_per_day * total_days
            amount = (hours * salary_hour)
            if len(leave_type_pre_matern_ids) > 1:
                input_list.append(
                    self.input_type_values(lice_maternidade_id, False, False, total_days, amount, hours))
            else:
                input_list.append(
                    self.input_type_values(lice_maternidade_id, leave_type_pre_matern_ids.date_from,
                                           leave_type_pre_matern_ids.date_to, total_days, amount, hours))

        # FALTA INJUSTIFICADA
        leave_type_fi_ids = leave_ids.filtered(
            lambda
                x: x.date_from.date() <= end_date and x.date_to.date() >= first_date and x.holiday_status_id == self.env.ref(
                'l10n_ao_hr_holidays.l10n_ao_hr_leave_typ_falta_injustificada'))
        if leave_type_fi_ids:
            leave_falta_injustificada_id = self.env.ref(
                'l10n_ao_hr.l10n_ao_hr_type_missed_hours_falta_injustificada').id
            total_days = sum([leave.number_of_days for leave in leave_type_fi_ids])
            hours = hours_per_day * total_days
            amount = (hours * salary_hour)
            input_list.append(self.get_input_type_values(leave_falta_injustificada_id, amount, total_days))

        # FALTA JUSTIFICADA NÃO REMUNERADA
        leave_type_fjnr_ids = leave_ids.filtered(
            lambda
                x: x.date_from.date() <= end_date and x.date_to.date() >= first_date and x.holiday_status_id == self.env.ref(
                'l10n_ao_hr_holidays.l10n_ao_hr_leave_typ_falta_justificada_sem_remuneracao'))
        if leave_type_fjnr_ids:
            leave_falta_justi_nao_remunerada_id = self.env.ref(
                'l10n_ao_hr.l10n_ao_hr_type_missed_hours_falta_just_nao_remunerada').id
            total_days = sum([leave.number_of_days for leave in leave_type_fjnr_ids])
            hours = hours_per_day * total_days
            amount = (hours * salary_hour)
            input_list.append(self.get_input_type_values(leave_falta_justi_nao_remunerada_id, amount, total_days))

        # FALTA JUSTIFICADA REMUNERADA
        leave_type_fjr_ids = leave_ids.filtered(
            lambda
                x: x.date_from.date() <= end_date and x.date_to.date() >= first_date and x.holiday_status_id == self.env.ref(
                'l10n_ao_hr_holidays.l10n_ao_hr_leave_typ_falta_justificada_remunerada'))
        if leave_type_fjr_ids:
            leave_falta_justi_remunerada_id = self.env.ref(
                'l10n_ao_hr.l10n_ao_hr_type_missed_hours_falta_just_remunerada').id
            total_days = sum([leave.number_of_days for leave in leave_type_fjr_ids])
            hours = hours_per_day * total_days
            amount = (hours * salary_hour)
            input_list.append(self.get_input_type_values(leave_falta_justi_remunerada_id, amount, total_days))

        return input_list

    def check_leave_type_extra_hours(self, leave_ids, first_date, end_date):
        input_list = []
        leave_extra_hours = self.env.ref('l10n_ao_hr.l10n_ao_hr_horas_extras')
        date_list = []
        # Buscar as datas de feriado
        check_in_values = [check_in + timedelta(hours=1) for check_in in leave_ids.mapped('check_in') if check_in]
        check_out_values = [check_out + timedelta(hours=1) for check_out in leave_ids.mapped('check_out') if check_out]
        combined_values = check_in_values + check_out_values
        unique_combined_values_ordered = []
        [unique_combined_values_ordered.append(value.date()) for value in combined_values if
         value.date() not in unique_combined_values_ordered]

        holidays = leave_ids.get_extra_holiday_days(unique_combined_values_ordered, first_date, end_date)
        if holidays:
            total_horas_float = 0
            # CHECK IN
            check_in_extra_hours_holidays = [leave_ids.filtered(lambda r: r.check_in.date() == day)
                                             for day in holidays]
            check_in_extra_hours_holidays = [item for sublist in check_in_extra_hours_holidays if sublist for item in
                                             sublist]
            for leave in check_in_extra_hours_holidays:
                total_horas_float += self.get_check_in_hours(leave.check_in, leave.check_out)

            # CHECK OUT
            check_out_extra_hours_holidays = [
                leave_ids.filtered(lambda r: r.check_out.date() == day) for day in
                holidays]
            check_out_extra_hours_holidays = [item for sublist in check_out_extra_hours_holidays if sublist for item in
                                              sublist]
            # Remover duplicados que já estão nos check-ins
            check_out_extra_hours_holidays = [leave for leave in check_out_extra_hours_holidays if
                                              leave not in check_in_extra_hours_holidays]
            for leave in check_out_extra_hours_holidays:
                total_horas_float += self.get_check_out_hours(leave.check_out)

            if total_horas_float > 0:
                extra_hours_holidays = len(check_in_extra_hours_holidays) + len(check_out_extra_hours_holidays)
                values = {'type_of_overtime': 'weekend', 'input_type_id': leave_extra_hours.id,
                          'quantity_days': extra_hours_holidays, 'hours': total_horas_float, }

                input_list.append((0, 0, values))
                date_list.extend(holidays)

        # Filtrar as datas de domingo
        sundays = [day for day in unique_combined_values_ordered if
                   day.weekday() in [5, 6] and day not in date_list]
        if sundays:
            total_horas_holidays_total = 0
            # CHECK_IN
            check_in_extra_hours_holidays = [leave_ids.filtered(lambda r: r.check_in.date() == day)
                                             for day in sundays]
            check_in_extra_hours_holidays = [item for sublist in check_in_extra_hours_holidays if sublist for item in
                                             sublist]
            for leave in check_in_extra_hours_holidays:
                total_horas_holidays_total += self.get_check_in_hours(leave.check_in, leave.check_out)

            # CHECK_OUT
            check_out_extra_hours_holidays = [
                leave_ids.filtered(lambda r: r.check_out.date() == day) for day in
                sundays]
            check_out_extra_hours_holidays = [item for sublist in check_out_extra_hours_holidays if sublist for item in
                                              sublist]

            # Remover duplicados que já estão nos check-ins
            check_out_extra_hours_holidays = [leave for leave in check_out_extra_hours_holidays if
                                              leave not in check_in_extra_hours_holidays]
            for leave in check_out_extra_hours_holidays:
                total_horas_holidays_total += self.get_check_out_hours(leave.check_out)

            if total_horas_holidays_total > 0:
                extra_hours_holidays = len(check_in_extra_hours_holidays) + len(check_out_extra_hours_holidays)
                values = {'type_of_overtime': 'weekend', 'input_type_id': leave_extra_hours.id,
                          'quantity_days': extra_hours_holidays, 'hours': total_horas_holidays_total, }

                input_list.append((0, 0, values))
                date_list.extend([sunday for sunday in sundays])

        # Buscar as datas normais
        if date_list:
            extra_hours_normal = []
            extra_hour_normal_total = 0
            # CHECK_IN
            for leave in leave_ids:
                if leave.check_in.date() not in date_list:
                    extra_hour_normal_total += self.get_check_in_hours(leave.check_in, leave.check_out)
                    extra_hours_normal.append(leave)
                    date_list.append(leave.check_in.date())

            # CHECK_OUT
            for leave in leave_ids:
                if leave.check_out.date() not in date_list:
                    extra_hour_normal_total += self.get_check_out_hours(leave.check_out)
                    extra_hours_normal.append(leave)

            if extra_hour_normal_total > 0:
                values = {'type_of_overtime': 'normal', 'input_type_id': leave_extra_hours.id,
                          'quantity_days': len(extra_hours_normal), 'hours': len(extra_hours_normal), }

                input_list.append((0, 0, values))
        else:
            extra_hour_normal_total = 0
            # CHECK_IN
            check_in_list = [leave_ids.filtered(lambda r: r.check_in.date()) for day in leave_ids]
            check_in_list = [item for sublist in check_in_list if sublist for item in sublist]
            check_in_list = set(check_in_list)
            for leave in check_in_list:
                extra_hour_normal_total += self.get_check_in_hours(leave.check_in, leave.check_out)

            # CHECK_OUT
            check_out_list = [leave_ids.filtered(lambda r: r.check_out.date()) for day in leave_ids]
            check_out_list = [item for sublist in check_out_list if sublist for item in sublist]
            # Remover duplicados que já estão nos check-ins
            check_out_list = [leave for leave in check_out_list if leave not in check_in_list]
            for leave in check_out_list:
                extra_hour_normal_total += self.get_check_out_hours(leave.check_out)

            if extra_hour_normal_total > 0:
                values = {'type_of_overtime': 'normal', 'input_type_id': leave_extra_hours.id,
                          'quantity_days': len(leave_ids), 'hours': extra_hour_normal_total, }

                input_list.append((0, 0, values))

        return input_list

    def get_check_in_hours(self, hour_date, check_out):
        start_of_day_utc = hour_date + timedelta(hours=1)
        end_of_day_utc = datetime(hour_date.year, hour_date.month, hour_date.day, 23, 59, 59)
        if hour_date.date() == check_out.date():
            check_out_date = check_out + timedelta(hours=1)
            time_difference = check_out_date - start_of_day_utc
        else:
            time_difference = end_of_day_utc - start_of_day_utc

        total_seconds = time_difference.total_seconds()
        total_hours = total_seconds // 3600
        total_minutes = (total_seconds % 3600) // 60
        total_seconds = total_hours * 3600 + total_minutes * 60
        return total_seconds / 3600

    def get_check_out_hours(self, hour_date):
        end_of_day_utc = hour_date + timedelta(hours=1)
        check_date = end_of_day_utc.strftime('%H:%M')
        hours, minutes = map(int, check_date.split(':'))
        return hours + (minutes / 60)

    def fecth_date(self, payslip_date):
        new_date = payslip_date.split('-')
        new_date = date(int(new_date[0]), int(new_date[1]), int(new_date[2]))
        return new_date

    def verify_payslip_exist(self, employee_id, date_from, date_to):
        return True if self.env['hr.payslip'].search(
            [('employee_id', '=', employee_id.id), ('date_from', '<=', date_from),
             ('date_to', '>=', date_to), ('state', '!=', 'cancel')]) else False

    def write(self, vals):
        res = super().write(vals)
        if self.env.company.country_id.code == "AO":
            if 'state' in vals and vals['state'] == 'done':
                for record in self:
                    # CRIAR AS HORAS EXTRAS QUANDO EXISTIR LINHAS DE HORAS EXTRAS NA FOLHA SALARIAL
                    record.create_extra_hours_report()
        return res

    def compute_sheet(self, remove_wizard=False, add_wizard=False):
        if self.env.company.country_id.code == "AO":
            # ORIGINAL Compute_Sheet Function
            payslips = self.filtered(lambda slip: slip.state in ['draft', 'verify'])
            # delete old payslip lines
            payslips.line_ids.unlink()
            # this guarantees consistent results
            self.env.flush_all()
            today = fields.Date.today()
            # PEGAR O EXTERNAR ID DAS input line
            input_type_gratificacao_ferias = self.env.ref('l10n_ao_hr.l10n_ao_hr_gratificacao_feria').id
            input_type_abono_natal_id = self.env.ref('l10n_ao_hr.l10n_ao_hr_horas_abono_natal').id
            horas_extras_50_id = self.env.ref('l10n_ao_hr.l10n_ao_hr_horas_extras_50%').id
            horas_extras_dom_75_id = self.env.ref(
                'l10n_ao_hr.l10n_ao_hr_horas_extras_75%').id

            for payslip in payslips:
                # PEGAR A SEQUENCIA DO RECIBO SALARIAL
                number = payslip.number or self.env['ir.sequence'].next_by_code('salary.slip')

                input_type_ids = payslip.input_line_ids if payslip.input_line_ids else False
                verify_old_vocation_allowance, christmas_allowance, vacation_allowance = False, False, False
                input_line_values = []
                if input_type_ids:
                    # Create EXtra Hour 50% and 75%
                    if input_type_ids.filtered(lambda r: r.input_type_id.code == 'HEXTRAS'):
                        input_extra_hours_line_values = self.create_extra_hours(input_type_ids)

                        if input_extra_hours_line_values:
                            input_line_values.extend(input_extra_hours_line_values)

                    # Create Horas Falta Injustificada e Justificada sem remuneração e remunerada
                    if input_type_ids.filtered(lambda r: r.input_type_id.code == 'MISSING_HOUR'):
                        input_missed_hours_line_values = payslip.create_missed_hours(input_type_ids)

                        if input_missed_hours_line_values:
                            input_line_values.extend(input_missed_hours_line_values)

                    # Verificar se o funcionário tem abono de natal
                    christmas_allowance = input_type_ids.filtered(
                        lambda r: r.input_type_id.id == input_type_abono_natal_id)
                    # Verificar se o funcionário tem gratificação de férias
                    vacation_allowance = input_type_ids.filtered(
                        lambda r: r.input_type_id.id == input_type_gratificacao_ferias)

                if not christmas_allowance:
                    # Create Abono de Natal
                    if self.env.company.christmas_payment_date and not payslip.dont_process_christmas_allowance:
                        if payslip.date_from.month == self.env.company.christmas_payment_date.month:
                            christmas_amount = payslip.calculate_christmas_amount()
                            input_christmas_values = [
                                payslip.get_input_type_values(input_type_abono_natal_id, christmas_amount)]

                            if input_christmas_values:
                                input_line_values.extend(input_christmas_values)

                if not vacation_allowance:
                    # VERIFICAR SE A OPÇÃO PROCESSAMENTO AUTOMATIVCO DE GRATIFICAÇÃO FÉRIAS ESTA MARCADO NO TIPO DE EMPRESA
                    if self.env.company.process_automatically_vacation and not payslip.dont_process_christmas_allowance:
                        # VERIFICAR SE JÁ FOI PAGO A GRATIFICAÇÃO DE FERIAS AO FUNCIONÁRIO
                        verify_old_vocation_allowance = payslip.verify_old_vocation_allowance()
                        if not verify_old_vocation_allowance:
                            # Verificar se o tipo de processqento de férias no tipo de empresa esta num mês especifico
                            if self.env.company.vacation_payment in ['full_payment_fixed_month',
                                                                     'full_payment_month_before_vacation']:
                                month = 0
                                if payslip.contract_type_id.code == 'EXPATRIADO':
                                    month = self.env.company.vacation_expatri_payment_date.month
                                else:
                                    if self.env.company.vacation_payment == 'full_payment_month_before_vacation':
                                        leave_id = self.env['hr.leave'].get_validate_vacation_leave_ids(
                                            [payslip.employee_id.id])
                                        if leave_id:
                                            month = leave_id.date_from.month - 1
                                    elif self.env.company.vacation_payment == 'full_payment_fixed_month':
                                        if self.env.company.vocation_pay_month.month:
                                            month = self.env.company.vocation_pay_month.month

                                if month != 0:
                                    # Verificar se o mês escolhido do processamnto é igual ao mẽs do ano corrente
                                    if payslip.date_from.month == month:
                                        gratificacao_ferias_amount = payslip.calculate_vocation_allowance()
                                        input_salario_feria_values = [payslip.get_input_type_values(
                                            input_type_gratificacao_ferias, gratificacao_ferias_amount)]

                                        if input_salario_feria_values:
                                            input_line_values.extend(input_salario_feria_values)

                payslip.write({
                    'number': number,
                    'state': 'verify',
                    'compute_date': today
                })

                if input_line_values:
                    extra_input_type_ids = False
                    if input_type_ids:
                        # Verificar se existe nas outras entradas os abonos de horas extras e remover caso existir
                        extra_input_type_ids = input_type_ids.filtered(
                            lambda r: r.input_type_id.id in [horas_extras_50_id, horas_extras_dom_75_id])

                    if add_wizard:
                        input_line_values += add_wizard

                    # Adicionar as novas entradas de abono
                    payslip.input_line_ids = input_line_values
                    if extra_input_type_ids:
                        # Remover as linhas das horas extras no processamento
                        extra_input_type_ids.unlink()
                else:
                    if add_wizard:
                        # Adicionar as novas entradas de abono
                        payslip.input_line_ids = add_wizard

                payslip_lines = payslip._get_payslip_lines(
                    verify_old_vocation_allowance) if not remove_wizard else payslip._get_payslip_lines(
                    verify_old_vocation_allowance, remove_wizard)
                self.env['hr.payslip.line'].create(payslip_lines)
            return True
        else:
            return super(HRPayslip, self).compute_sheet()

    def _get_payslip_lines(self, old_vocation_allowance=False, remove_wizard=False):
        if self.env.company.country_id.code == "AO":
            line_vals = []
            for payslip in self:
                if not payslip.contract_id:
                    raise UserError(
                        _("There's no contract set on payslip %s for %s. Check that there is at least a contract set on the employee form.",
                          payslip.name, payslip.employee_id.name))

                localdict = self.env.context.get('force_payslip_localdict', None)
                if localdict is None:
                    localdict = payslip._get_localdict()

                rules_dict = localdict['rules'].dict
                result_rules_dict = localdict['result_rules'].dict

                blacklisted_rule_ids = self.env.context.get('prevent_payslip_computation_line_ids', [])

                result = {}
                for rule in sorted(payslip.struct_id.rule_ids, key=lambda x: x.sequence):
                    if rule.id in blacklisted_rule_ids:
                        continue

                    # Verificar se o funcionáerio é expatriado ou expatriado residente tem campo ISENTO A INSS esta marcado no tipo de funcionário
                    if payslip.employee_id.contract_type.code in ['EXPATRIADO',
                                                                  'EXPATRIADO_RESIDENTE'] and \
                            payslip.employee_id.contract_type.is_exempt_inss:
                        if rule.code == 'INSS':
                            continue

                    # Verificar se o funcionáerio tem campo ISENTO DE IRT esta marcado no tipo de funcionário ou no contracto
                    if payslip.contract_id.irt_exempt and payslip.employee_id.contract_type.code == 'NACIONAL':
                        if 'IRT' in rule.code:
                            continue

                    if payslip.employee_id.contract_type.is_exempt_irt:
                        if 'IRT' in rule.code:
                            continue

                    if remove_wizard and rule.code in remove_wizard:
                        continue

                    if payslip.dont_include_base_rule and rule.code in 'BASE':
                        continue

                    localdict.update({
                        'result': None,
                        'result_qty': 1.0,
                        'result_rate': 100,
                        'result_name': False
                    })
                    if rule._satisfy_condition(localdict):
                        # Retrieve the line name in the employee's lang
                        employee_lang = payslip.employee_id.sudo().address_home_id.lang
                        # This actually has an impact, don't remove this line
                        context = {'lang': employee_lang}
                        if rule.code in localdict['same_type_input_lines']:
                            for multi_line_rule in localdict['same_type_input_lines'][rule.code]:
                                localdict['inputs'].dict[rule.code] = multi_line_rule
                                amount, qty, rate = rule._compute_rule(localdict)

                                # Calcular o valor das remunerações com base nos dias trabalhados
                                amount = payslip.get_rule_amount(rule, amount) if payslip.get_rule_amount(rule,
                                                                                                          amount) != 0 else amount
                                tot_rule = amount * qty * rate / 100.0
                                localdict = rule.category_id._sum_salary_rule_category(localdict,
                                                                                       tot_rule)
                                rule_name = payslip._get_rule_name(localdict, rule, employee_lang)
                                # Verificar se já existe a remuneração na lista
                                rule_exist = [p for p in line_vals if rule.code in p.get('code')]

                                if payslip.contract_type_id.code in ['EXPATRIADO',
                                                                     'EXPATRIADO_RESIDENTE'] and rule.code == 'BASE' and payslip.process_automatically_exchange:
                                    if not payslip.salary_kz:
                                        if self.env.company.currency == 'USD' or self.env.company.currency == 'AOA':
                                            amount = payslip.contract_id.get_kz_amount(
                                                payslip.contract_id.total_paid_usd)
                                        elif self.env.company.currency == 'EUR':
                                            amount = payslip.contract_id.get_euro_kz_amount(
                                                payslip.contract_id.total_paid_usd)
                                elif payslip.contract_type_id.code in ['EXPATRIADO',
                                                                       'EXPATRIADO_RESIDENTE'] and rule.code == 'BASE' and not payslip.process_automatically_exchange:
                                    if not payslip.salary_kz:
                                        amount = (payslip.contract_id.total_paid_usd * payslip.exchange_rate)

                                if not rule_exist:
                                    line_vals.append({
                                        'sequence': rule.sequence,
                                        'code': rule.code,
                                        'name': rule_name,
                                        'note': html2plaintext(rule.note) if not is_html_empty(rule.note) else '',
                                        'salary_rule_id': rule.id,
                                        'contract_id': localdict['contract'].id,
                                        'employee_id': localdict['employee'].id,
                                        'amount': amount,
                                        'quantity': qty,
                                        'rate': rate,
                                        'slip_id': payslip.id,
                                        'quantity_days': qty,
                                        'amount_before_discount': amount,
                                    })
                        else:
                            amount, qty, rate = rule._compute_rule(localdict)
                            # Calcular o valor das remunerações com base nos dias trabalhados
                            amount = payslip.get_rule_amount(rule, amount) if payslip.get_rule_amount(rule,
                                                                                                      amount) != 0 else amount
                            # check if there is already a rule computed with that code
                            previous_amount = rule.code in localdict and localdict[rule.code] or 0.0
                            # set/overwrite the amount computed for this rule in the localdict
                            tot_rule = amount * qty * rate / 100.0
                            localdict[rule.code] = tot_rule
                            result_rules_dict[rule.code] = {'total': tot_rule, 'amount': amount, 'quantity': qty}
                            rules_dict[rule.code] = rule
                            # sum the amount for its salary category
                            localdict = rule.category_id._sum_salary_rule_category(localdict,
                                                                                   tot_rule - previous_amount)
                            rule_name = payslip._get_rule_name(localdict, rule, employee_lang)

                            if payslip.contract_type_id.code in ['EXPATRIADO',
                                                                 'EXPATRIADO_RESIDENTE'] and rule.code == 'BASE' and payslip.process_automatically_exchange:
                                if not payslip.salary_kz:
                                    if self.env.company.currency == 'USD' or self.env.company.currency == 'AOA':
                                        amount = payslip.contract_id.get_kz_amount(payslip.contract_id.total_paid_usd)
                                    elif self.env.company.currency == 'EUR':
                                        amount = payslip.contract_id.get_euro_kz_amount(
                                            payslip.contract_id.total_paid_usd)
                            elif payslip.contract_type_id.code in ['EXPATRIADO',
                                                                   'EXPATRIADO_RESIDENTE'] and rule.code == 'BASE' and not payslip.process_automatically_exchange:
                                if not payslip.salary_kz:
                                    amount = (payslip.contract_id.total_paid_usd * payslip.exchange_rate)

                            # create/overwrite the rule in the temporary results
                            result[rule.code] = {
                                'sequence': rule.sequence,
                                'code': rule.code,
                                'name': rule_name,
                                'note': html2plaintext(rule.note) if not is_html_empty(rule.note) else '',
                                'salary_rule_id': rule.id,
                                'contract_id': localdict['contract'].id,
                                'employee_id': localdict['employee'].id,
                                'amount': amount,
                                'quantity': qty,
                                'rate': rate,
                                'slip_id': payslip.id,
                                'quantity_days': qty,
                                'amount_before_discount': amount,
                            }

                line_vals += list(result.values())

                # Deduzir o total das remunerações que sofre desconto de ausencias , faltas e trasos
                # SUBTRAIR O TOTAL DE ATRASOS E Ausencias NA REMUNERAÇÃO BASE
                if not payslip.dont_include_base_rule:
                    base_line = [line for line in line_vals if line.get('code') == 'BASE'][0]
                    # Arredondar o base
                    base_line['amount'] = self.round_up(base_line.get('amount'))
                    base_line['amount_before_discount'] = self.round_up(base_line.get('amount'))

                    # Verificar se o funcionário tem desconto de faltas e trasos
                    missed_amount = payslip.get_base_missed_total(base_line, line_vals)
                    base_line['amount'] = base_line.get('amount') - missed_amount
                    base_line['amount'] = 0 if base_line.get('amount') < 0 else base_line.get('amount')
                    # Filtrar as regras que se deduzem as faltas
                    other_missed_amount = payslip.get_other_missed_total(line_vals, missed_amount)

                # Recalcular o valor do IRT e INSS
                line_vals = payslip.recalculating_irt_inss_amount(localdict, line_vals)

            return line_vals
        else:
            return super(HRPayslip, self)._get_payslip_lines()

    def round_up(self, valor, casas_decimais=2):
        # fator = 10 ** casas_decimais  # Calcula a potência de 10 para ajustar as casas decimais
        # return math.ceil(valor * fator) / fator  # Arredonda para cima e retorna o valor ajustado
        return round(valor, casas_decimais)

    def irt_collectable_material(self, total_remuneration, excess_amount):
        inss_amount = 0
        if self.contract_type_id.code == 'EXPATRIADO_RESIDENTE':
            # Calcular o novo valor do segundo INSS
            inss_amount = self.round_up(total_remuneration * 0.03)
            # Calcular o valor da segunda materia coletavel
            irt_collectable_material = self.round_up(total_remuneration - inss_amount - excess_amount)
        else:
            # Calcular o valor da primeira materia coletavel
            irt_collectable_material = self.round_up(total_remuneration - excess_amount)

        return irt_collectable_material, inss_amount

    def codes_inss(self, line):
        line_code = line['code']
        inss_code_rules = self.env['hr.salary.rule'].search(
            [('struct_id', '=', self.struct_id.id), ('inss_rule', '=', True)]).mapped('code')
        return line_code in inss_code_rules

    def codes_not_irt(self, line):
        line_code = line['code']
        if self.contract_type_id.code == 'NACIONAL':
            return not (line_code.startswith('IRT') or line_code in ['INSS', 'INSS8', 'EAT', 'ALI', 'TRANS',
                                                                     'Desc_Seguro', 'ADI', 'DES_ADI_SALARIO',
                                                                     'FJNR', 'FI', 'FJR', 'ATRA', 'remote_work', 'LSV',
                                                                     'R105', 'R1005', 'R1007', 'R1006', 'gozo_ferias',
                                                                     'FAMI', 'D44', 'AVPREVIODESC', 'D19', 'D32', 'D33',
                                                                     'D34', 'D35', 'D38', 'D38', 'D40', 'R67', 'R68'])
        elif self.contract_type_id.code in ['EXPATRIADO', 'EXPATRIADO_RESIDENTE'] and self.process_irt_vacation:
            return not (line_code.startswith('IRT') or line_code in ['INSS', 'INSS8', 'FJNR', 'FJR', 'FI', 'R105', 'R1005',
                                                                     'R1007', 'ADI', 'DES_ADI_SALARIO',
                                                                     'R1006', 'gozo_ferias', 'remote_work', 'LSV',
                                                                     'EAT', 'ATRA', 'Desc_Seguro', 'FAMI',
                                                                     'D44', 'AVPREVIODESC', 'R67', 'R68', 'D19',
                                                                     'D32', 'D33', 'D34', 'D35', 'D38', 'D38',
                                                                     'D40', 'FER', 'GRATIF_FER', 'SAL_FER', 'R89',
                                                                     'R891'])

        elif self.contract_type_id.code in ['EXPATRIADO', 'EXPATRIADO_RESIDENTE'] and not self.process_irt_vacation:
            return not (line_code.startswith('IRT') or line_code in ['INSS' ,'INSS8', 'FJNR', 'FJR', 'FI', 'R105', 'R1005',
                                                                     'R1007', 'ADI', 'DES_ADI_SALARIO',
                                                                     'R1006', 'gozo_ferias', 'remote_work', 'LSV',
                                                                     'EAT', 'ATRA', 'Desc_Seguro', 'FAMI',
                                                                     'D44', 'AVPREVIODESC', 'R67', 'R68', 'D19',
                                                                     'D32', 'D33', 'D34', 'D35', 'D38', 'D38',
                                                                     'D40', ])

    def recalculating_irt_inss_amount(self, localdict, line_vals):

        def vacation_irt_calculation(vacation_rules, irt_collectable_material2):
            # Calcular o valor do subsidio de férias
            vacation_amount = self.round_up(
                sum(rules.get('amount', 0) for rules in vacation_rules if rules.get('amount', 0) >= 0))
            # Achar IRT de Subsidio de férias
            tax_vacation, cool_parcel_vacation, excess_of_salary_vacation, rule_id_vacation = self.get_irt_range(
                vacation_amount)
            vacationirt_amount = self.round_up(
                ((vacation_amount - excess_of_salary_vacation) * tax_vacation) + cool_parcel_vacation)
            # Materia Colectavel Global
            irt_collectable_material_global = vacation_amount + irt_collectable_material2
            # Achar IRT final
            tax_final, cool_parcel_final, excess_of_salary_final, rule_id_final = self.get_irt_range(
                irt_collectable_material_global)
            irt_amount = self.round_up(
                ((irt_collectable_material_global - excess_of_salary_final) * tax_final) + cool_parcel_final)
            return irt_amount, rule_id_final[0], irt_collectable_material_global

        # Filtrar as regras de Salario BASE
        base_rule = [p for p in line_vals if p.get('code') in ['BASE']]
        # Filtrar o subsidio IRT
        irt_rule = [p for p in line_vals if 'IRT' in p.get('code')]
        # Filtrar o subsidio INSS
        inss_rule = [p for p in line_vals if 'INSS' in p.get('code')]
        # Filtrar o subsidio de alimentação ou transporte como também os retroativos
        trans_rule = [p for p in line_vals if 'TRANS' in p.get('code')]
        ali_rule = [p for p in line_vals if 'ALI' in p.get('code')]
        retro_ali_rule = [p for p in line_vals if 'R68' in p.get('code')]
        retro_trans_rule = [p for p in line_vals if 'R67' in p.get('code')]
        # Verificar se existe o subsídio de férias para ser removido da base de incidencia do total do INSS
        vacation_rule = [p for p in line_vals if 'GRATIF_FER' in p.get('code')]
        fami_rule = [p for p in line_vals if 'FAMI' in p.get('code')]
        # Filtrar as regras de férias
        vacation_rules = [p for p in line_vals if p.get('code') in ['FER', 'GRATIF_FER', 'SAL_FER', 'R89', 'R891']]
        # Ajuda de Custo
        allowance_exp = [p for p in line_vals if p.get('code') in ['R75', 'A_CUSTO']]
        # Filtrar a regra de excesso
        excess_rule_id = self.struct_id.rule_ids.filtered(lambda r: r.code == 'EAT')
        # Verificar se contem o excesso de alimentação e transporte
        trans_ali_excess_rule = [p for p in line_vals if 'EAT' in p.get('code')]

        trans_amount, ali_amount, irt_collectable_material, excess_amount, irt_amount, total_remuneration2, total_remuneration3, \
            irt_collectable_material2, inss_amount, inss_amount2, irt_collectable_material_global, diferenca_irt, diferencaIRT2 = 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0
        trans_amount_total, ali_amount_total = 0, 0
        rule_id, trans_excess, ali_excess = False, False, False
        if trans_ali_excess_rule:
            if excess_rule_id.excess_amount == 0:
                raise UserError(
                    _(f'Não é possível efectuar o processamento, deve fornecer o valor do excesso na regra de excesso de Alimentação e Transporte \n'
                      f'Vá em regras salariais e active a opção  "Valor de Excesso dos Subsídios", ou Contacte o Administrador do Sistema.'))

            # Calcular o valor do excesso de transporte
            if trans_rule or retro_trans_rule:
                trans_amount_total = trans_rule[0].get('amount') if trans_rule else 0
                trans_amount_total += retro_trans_rule[0].get('amount') if retro_trans_rule else 0
                if round(trans_amount_total) > excess_rule_id.excess_amount:
                    trans_amount = trans_amount_total - excess_rule_id.excess_amount
                    excess_amount += excess_rule_id.excess_amount
                    trans_excess = True

            # Calcular o valor do excesso de alimentação
            if ali_rule or retro_ali_rule:
                ali_amount_total = ali_rule[0].get('amount') if ali_rule else 0
                ali_amount_total += retro_ali_rule[0].get('amount') if retro_ali_rule else 0
                if round(ali_amount_total) > excess_rule_id.excess_amount:
                    ali_amount = ali_amount_total - excess_rule_id.excess_amount
                    excess_amount += excess_rule_id.excess_amount
                    ali_excess = True

            trans_ali_excess_rule[0]['amount'] = (ali_amount + trans_amount) if (ali_amount + trans_amount) > 0 else \
                trans_ali_excess_rule[0]['amount']
            trans_ali_excess_rule[0]['amount_before_discount'] = (
                    ali_amount + trans_amount) if (ali_amount + trans_amount) > 0 else trans_ali_excess_rule[0][
                'amount_before_discount']

        # Filtrar as Regras salariais diferente de INSS, e Ausencias
        inss_rules_value = list(filter(self.codes_inss, line_vals))
        # Valor total das remunerações
        inss_total_remuneration = sum(rules.get('amount') for rules in inss_rules_value)

        if fami_rule:
            # Ajustar o valor do abono de família com base na porcentagem de desconto da materia colectavel
            fam_amount = fami_rule[0]['amount'] if fami_rule else fami_rule[0]['amount']
            amount_percent = (fam_amount / base_rule[0]['amount']) * 100
            if amount_percent > 5:
                amount_excedent = (amount_percent - 5)
                self.fam_allowance_amount = (amount_excedent / 100) * base_rule[0]['amount']

        # Achar a base de insidencia do INSS
        inss_tax_base = self.round_up(inss_total_remuneration)
        self.collected_material_inss = inss_tax_base
        if inss_tax_base <= 0 and self.contract_type_id.code == 'NACIONAL':
            raise UserError(
                _(f'Não é possível efectuar o processamento, o valor da base de insidência do INSS do colaborador {self.employee_id.name} é negativa. \n'
                  f'Verifique o contracto do colaborador ou Contacte o Suporte Odoo.'))

        if self.contract_type_id.code == 'NACIONAL':
            if inss_rule:
                # Remover o dicionario que tiver a chave INSS
                line_vals = [line_vals[i] for i in range(len(line_vals)) if line_vals[i].get('code') not in ['INSS']]
                inss_rule = [self.create_inss_rule(inss_tax_base)]
                line_vals.append(inss_rule[0])
            else:
                inss_rule = [self.create_inss_rule(inss_tax_base)]
                line_vals.append(inss_rule[0])

        # === INSS 8% com a MESMA base do INSS (NACIONAL e EXPATRIADO_RESIDENTE) ===
        if self.contract_type_id.code in ('NACIONAL', 'EXPATRIADO_RESIDENTE') \
                and not self.employee_id.contract_type.is_exempt_inss:
            inss8_line = self.create_inss8_rule(inss_tax_base)
            if inss8_line:
                line_vals = [l for l in line_vals if l.get('code') != 'INSS8']
                line_vals.append(inss8_line)


        # Filtrar as Regras salariais diferente de IRT, e Ausencias
        irt_rules_value = list(filter(self.codes_not_irt, line_vals))
        # Valor total das remunerações
        total_remuneration = self.round_up(sum(rules.get('amount') for rules in
                                               irt_rules_value)) if self.contract_type_id.code == 'NACIONAL' else self.round_up(
            sum(rules.get('amount', 0) for rules in irt_rules_value if rules.get('amount', 0) >= 0))
        # Achar a Matéria colectável do IRT
        if self.contract_type_id.code == 'NACIONAL':
            amount_excess = 0
            if trans_excess:
                amount_excess += trans_amount_total

            if ali_excess:
                amount_excess += ali_amount_total

            if inss_rule:
                irt_collectable_material = self.round_up((total_remuneration + amount_excess) - (
                        (inss_rule[0].get('amount') * -1) + excess_amount)) if excess_amount > 0 else \
                    self.round_up((total_remuneration + amount_excess) - (inss_rule[0].get('amount') * -1))
                self.collected_material_irt = irt_collectable_material
            else:
                irt_collectable_material = self.round_up((total_remuneration + amount_excess) - excess_amount) \
                    if excess_amount > 0 else self.round_up((total_remuneration + amount_excess))
                self.collected_material_irt = irt_collectable_material
        elif self.contract_type_id.code in ['EXPATRIADO_RESIDENTE', 'EXPATRIADO'] and self.env.company.process_tis:
            # Calcular o INSS e Materia Coletavel
            irt_collectable_material, inss_amount = self.irt_collectable_material(total_remuneration, excess_amount)
            self.collected_material_irt = irt_collectable_material

        # Entrar só no caso de houver um subsidio fixo no processamento ou o campo Não fazer reboot estiver ativo
        if not self.dont_return_irt and self.env.company.process_tis:
            if trans_rule or ali_rule or allowance_exp:
                # Achar o IRT correspondente de acordo ao valor total das remunerações
                tax1, cool_parcel1, excess_of_salary1, rule_id = self.get_irt_range(irt_collectable_material)
                if not self.contract_id.irt_exempt and self.contract_type_id.code == 'NACIONAL':
                    excess_of_salary = irt_collectable_material - excess_of_salary1
                    irt_amount = self.round_up((excess_of_salary * tax1) + cool_parcel1)
                elif self.contract_type_id.code in ['EXPATRIADO',
                                                    'EXPATRIADO_RESIDENTE'] and not self.contract_id.irt_exempt and self.env.company.process_tis:
                    # Calcular a primeira diferença de IRT
                    diferencaIRT = self.round_up(
                        (((irt_collectable_material - (((excess_of_salary1) * (tax1)) - cool_parcel1)) / (
                                1 - (tax1)))) - irt_collectable_material)
                    # Total de remunerações
                    total_remuneration2 = self.round_up(total_remuneration + diferencaIRT)
                    # Calcular o NOVO INSS e Materia Coletavel
                    irt_collectable_material2, inss_amount2 = self.irt_collectable_material(total_remuneration2,
                                                                                            excess_amount)
                    # Verificar novamente se o novo valor ultrapassa o limite de IRT
                    tax2, cool_parcel2, excess_of_salary2, rule_id = self.get_irt_range(irt_collectable_material2)
                    # Verificar se o irt mudou de escala para recalcuar os valores
                    if tax1 != tax2:
                        # Calcular a segunda diferença de IRT
                        diferencaIRT2 = self.round_up(
                            (((irt_collectable_material - (((excess_of_salary2) * (tax2)) - cool_parcel2)) / (
                                    1 - (tax2)))) - irt_collectable_material)
                        # Total de remunerações
                        total_remuneration3 = self.round_up(total_remuneration + diferencaIRT2)
                        # Calcular o NOVO INSS e Materia Coletavel
                        irt_collectable_material2, inss_amount2 = self.irt_collectable_material(total_remuneration3,
                                                                                                excess_amount)
                        self.collected_material_irt = irt_collectable_material2
                        # Verificar novamente se o novo valor ultrapassa o limite de IRT
                        tax3, cool_parcel3, excess_of_salary3, rule_id = self.get_irt_range(irt_collectable_material2)
                        if tax2 != tax3:
                            # Calcular a segunda diferença de IRT
                            diferencaIRT3 = self.round_up(
                                (((irt_collectable_material - (((excess_of_salary3) * (tax3)) - cool_parcel3)) / (
                                        1 - (tax3)))) - irt_collectable_material)
                            # Total de remunerações
                            total_remuneration4 = self.round_up(total_remuneration + diferencaIRT3)
                            # Calcular o NOVO INSS e Materia Coletavel
                            irt_collectable_material2, inss_amount2 = self.irt_collectable_material(total_remuneration4,
                                                                                                    excess_amount)
                            tax2 = tax3
                            diferencaIRT2 = diferencaIRT3
                            self.collected_material_irt = irt_collectable_material2
                        else:
                            irt_collectable_material2 = irt_collectable_material2
                            self.collected_material_irt = irt_collectable_material2
                    else:
                        irt_collectable_material2 = irt_collectable_material2
                        self.collected_material_irt = irt_collectable_material2

                    # Calcular IRT FINAL
                    if tax1 != tax2:
                        if not vacation_rules:
                            # Verificar novamente se o novo valor ultrapassa o limite de IRT
                            tax2, cool_parcel2, excess_of_salary2, rule_id = self.get_irt_range(
                                irt_collectable_material2)
                            irt_amount = self.round_up(
                                ((irt_collectable_material2 - excess_of_salary2) * tax2) + cool_parcel2)
                        else:
                            if self.process_irt_vacation:
                                irt_amount, rule_id_final, irt_collectable_material_global = vacation_irt_calculation(
                                    vacation_rules, irt_collectable_material2, )
                                diferenca_irt = diferencaIRT2 if tax1 != tax2 else diferencaIRT
                            else:
                                # Verificar novamente se onovo valor ultrapassa o limite de IRT
                                tax2, cool_parcel2, excess_of_salary2, rule_id = self.get_irt_range(
                                    irt_collectable_material2)
                                irt_amount = self.round_up(
                                    ((irt_collectable_material2 - excess_of_salary2) * tax2) + cool_parcel2)
                    else:
                        if not vacation_rules:
                            # Verificar novamente se onovo valor ultrapassa o limite de IRT
                            tax1, cool_parcel1, excess_of_salary1, rule_id = self.get_irt_range(
                                irt_collectable_material2)
                            irt_amount = self.round_up(
                                ((irt_collectable_material2 - excess_of_salary1) * tax1) + cool_parcel1)
                        else:
                            if self.process_irt_vacation:
                                irt_amount, rule_id_final, irt_collectable_material_global = vacation_irt_calculation(
                                    vacation_rules, irt_collectable_material2, )
                                diferenca_irt = diferencaIRT2 if tax1 != tax2 else diferencaIRT
                            else:
                                # Verificar novamente se onovo valor ultrapassa o limite de IRT
                                tax1, cool_parcel1, excess_of_salary1, rule_id = self.get_irt_range(
                                    irt_collectable_material2)
                                irt_amount = self.round_up(
                                    ((irt_collectable_material2 - excess_of_salary1) * tax1) + cool_parcel1)

                    if self.contract_type_id.code == 'EXPATRIADO_RESIDENTE':
                        inss_rule[0]['amount'] = inss_amount2 * -1
                        inss_rule[0]['amount_before_discount'] = inss_amount2 * -1

                    # Verificar se o campo Compensação IRT esta marcado no tipo de funcionário
                    if self.employee_id.contract_type.is_irt_compensation:
                        irt_compensation_amount = irt_amount + allowance_exp[0].get(
                            'amount') if allowance_exp else irt_amount
                        if self.process_irt_vacation:
                            irt_compensation_amount = diferenca_irt

                        line_vals = self.get_compesation_irt(line_vals, irt_compensation_amount)
                        # Remover o dicionario que tiver a chave Ajuda de custo, para não aparecer no processamento
                        line_vals = [line_vals[i] for i in range(len(line_vals)) if
                                     line_vals[i].get('code') not in ['R75', 'A_CUSTO', 'EAT', 'gozo_ferias']]

                        # Passar valores nas remunerações
                        if irt_collectable_material_global != 0:
                            if self.process_irt_vacation:
                                self.total_remunerations_exp = 0
                            else:
                                self.total_remunerations_exp = irt_collectable_material_global
                        else:
                            self.total_remunerations_exp = total_remuneration3 if total_remuneration3 != 0 else total_remuneration2

                        self.allowance_exp = allowance_exp[0].get('amount') if allowance_exp else 0
                        # Verificar se existe a regra da dedução de Adiantamento de subsídios
                        deduction_rules = [p for p in line_vals if p.get('code') in ['D44']]
                        if not trans_rule and not ali_rule and not allowance_exp and deduction_rules:
                            self.dont_fixed_remunerations = True
                        else:
                            self.dont_fixed_remunerations = False
            else:
                # NOVO CASO HOUVER PROBLEMA RETORNA SEM ELSE, E VOLTAR IF DE BAIXO
                if self.contract_type_id.code == 'EXPATRIADO_RESIDENTE':
                    if inss_rule:
                        inss_rule[0]['amount'] = inss_amount * -1
                        inss_rule[0]['amount_before_discount'] = inss_amount * -1

                # Achar o IRT correspondente de acordo ao valor total das remunerações
                tax1, cool_parcel1, excess_of_salary1, rule_id = self.get_irt_range(irt_collectable_material)
                irt_amount = ((irt_collectable_material - excess_of_salary1) * tax1) + cool_parcel1
                self.total_remunerations_exp = 0
                # CRIAR AS REGRAS DE REBOOT DE IRT
                if not self.dont_return_irt:
                    self.dont_fixed_remunerations = True
                else:
                    self.dont_fixed_remunerations = False
        else:
            # NOVO CASO HOUVER PROBLEMA RETORNA SEM ELSE, E VOLTAR IF DE BAIXO
            if self.contract_type_id.code == 'EXPATRIADO_RESIDENTE':
                if inss_rule:
                    inss_rule[0]['amount'] = inss_amount * -1
                    inss_rule[0]['amount_before_discount'] = inss_amount * -1

            # Achar o IRT correspondente de acordo ao valor total das remunerações
            tax1, cool_parcel1, excess_of_salary1, rule_id = self.get_irt_range(irt_collectable_material)
            irt_amount = ((irt_collectable_material - excess_of_salary1) * tax1) + cool_parcel1
            self.total_remunerations_exp = 0
            # CRIAR AS REGRAS DE REBOOT DE IRT
            if not self.dont_return_irt:
                self.dont_fixed_remunerations = True
            else:
                self.dont_fixed_remunerations = False

        # Mudar o valor do IRT para o novo de acordo com a compensação
        if irt_rule and irt_amount > 0:
            # Remover o dicionario que tiver a chave IRT
            line_vals = [line_vals[i] for i in range(len(line_vals)) if not line_vals[i].get('code').startswith('IRT')]
            irt_rule = self.create_irt_rule(irt_rule, rule_id, irt_amount)
            line_vals.append(irt_rule)
        else:
            if rule_id and irt_amount > 0:
                irt_rule = self.create_irt_rule(False, rule_id, irt_amount)
                line_vals.append(irt_rule)

        if self.fam_allowance_amount > 0:
            self.collected_material_irt_with_exedent = self.collected_material_irt + self.fam_allowance_amount
        else:
            self.collected_material_irt_with_exedent = 0

        return line_vals

        # inss 8%

    def create_inss8_rule(self, inss_tax_base):
        """
        Cria a linha de INSS 8% usando a mesma base do INSS,
        pegando a regra pelo external id: l10n_ao_hr.hr_salary_rule_seguranca_social8
        """
        self.ensure_one()
        rule_id = self.env.ref('l10n_ao_hr.hr_salary_rule_seguranca_social8', raise_if_not_found=False)
        if not rule_id:
            return None

        percent = getattr(rule_id, 'inss8_tax', 0.0) or 8.0
        amount = self.round_up(inss_tax_base * (percent / 100.0))
        return {
            'sequence': rule_id.sequence,
            'code': rule_id.code,
            'name': rule_id.name,
            'note': html2plaintext(rule_id.note) if not is_html_empty(rule_id.note) else '',
            'salary_rule_id': rule_id.id,
            'contract_id': self.contract_id.id,
            'employee_id': self.employee_id.id,
            'amount': amount,
            'amount_before_discount': amount,
            'quantity': 1,
            'rate': 100,
            'slip_id': self.id,
            'quantity_days': 1,
        }

    def create_inss_rule(self, inss_tax_base):
        rule_id = self.env.ref('l10n_ao_hr.hr_salary_rule_seguranca_social')
        if rule_id.inss_tax == 0:
            raise UserError(
                _(f"Deve fornecer a taxa de INSS {rule_id.code} para avançar."))

        inss_rule = {
            'sequence': rule_id.sequence,
            'code': rule_id.code,
            'name': rule_id.name,
            'note': html2plaintext(rule_id.note) if not is_html_empty(rule_id.note) else '',
            'salary_rule_id': rule_id.id,
            'contract_id': self.contract_id.id,
            'employee_id': self.employee_id.id,
            'amount': (inss_tax_base * (rule_id.inss_tax / 100)) * -1,
            'amount_before_discount': (inss_tax_base * (rule_id.inss_tax / 100)) * -1,
            'quantity': 1,
            'rate': 100,
            'slip_id': self.id,
            'quantity_days': 1,

        }
        return inss_rule

    def create_irt_rule(self, irt_rule, rule_id, irt_amount):
        note = html2plaintext(rule_id.note) if rule_id else ''
        irt_rules = {
            'sequence': rule_id.sequence if rule_id else irt_rule[0].get('sequence'),
            'code': rule_id.code if rule_id else irt_rule[0].get('code'),
            'name': rule_id.name if rule_id else irt_rule[0].get('name'),
            'note': note,
            'salary_rule_id': rule_id.id if rule_id else irt_rule[0].get('salary_rule_id'),
            'contract_id': self.contract_id.id,
            'employee_id': self.employee_id.id,
            'amount': irt_amount * -1,
            'amount_before_discount': irt_amount * -1,
            'quantity': 1,
            'rate': 100,
            'slip_id': self.id,
            'quantity_days': 1,
        }
        return irt_rules

    def get_irt_range(self, irt_collectable_material):
        # Achar o IRT correspondente de acordo ao valor total das remunerações
        irt_rule_id1 = self.struct_id.rule_ids.filtered(
            lambda
                r: r.category_id == self.env.ref('l10n_ao_hr.hr_payroll_salary_rule_category_irt') and \
                   irt_collectable_material >= r.condition_range_min and irt_collectable_material <= r.condition_range_max)
        if irt_rule_id1:
            rule_id = irt_rule_id1[0]
            if rule_id.irt_tax == 0:
                raise UserError(
                    _(f"Deve fornecer a taxa de IRT {rule_id.code} para avançar."))

            tax = rule_id.irt_tax / 100
            cool_parcel = rule_id.cool_parcel
            excess_of_salary = rule_id.condition_range_min
            return tax, cool_parcel, excess_of_salary, rule_id
        return 0, 0, 0, None

    def get_amount_subs(self, amount, quantity_days, type=False):
        if self.employee_id.contract_type.code == 'NACIONAL' and not self.contract_id.calendar_days:
            working_days_moth_salary = self.env.company.working_days_moth_salary
        else:
            working_days_moth_salary = self.env.company.calendar_days_moth_salary

        if type == 'base':
            hours_per_day = self.employee_id.resource_calendar_id.hours_per_day
            hours = quantity_days * hours_per_day
            salary_hour = self.get_mount_hour_salary_employee()
            amount = hours * salary_hour
        else:
            amount = (amount / working_days_moth_salary) * (working_days_moth_salary - quantity_days)
        return amount

    def get_base_missed_total(self, base_line, line_vals):
        base_amount = 0
        line_ATRA = [line for line in line_vals if line.get('code') == 'ATRA']
        if line_ATRA and not self.dont_process_allowance_automatically:
            base_amount = line_ATRA[0].get('amount') * -1

        other_lines = [line for line in line_vals if line.get('code') in ['FJNR', 'FI', 'LSV']]
        for line in other_lines:
            # if self.env.company.process_tis:
            #     input_type = self.input_line_ids.filtered(lambda r: r.input_type_id.code == line.get('code'))
            #     base_amount += self.get_amount_subs(base_line.get('amount'), input_type[0].quantity_days, 'base')
            # else:
            base_amount += line.get('amount') * -1

        return base_amount

    def get_other_missed_total(self, line_vals, missed_total=0):
        record_rules = self.env['hr.salary.rule'].search(
            [('struct_id', '=', self.struct_id.id), ('is_suffer_absence_discounts', '=', True)]).mapped('code')
        if not record_rules:
            raise UserError(
                _(f'Não é possível efectuar o processamento, por falta de regras que devem sofrer descontos por ausẽncias. \n'
                  f'Vá em regras salariais e active a opção  "Sofrer descontos por faltas", ou Contacte o Administrador do Sistema.'))

        other_lines = [line.get('code') for line in line_vals if
                       line.get('code') in ['FJNR' if not self.dont_process_allowance_automatically else '',
                                            'FI' if not self.dont_process_allowance_automatically else '',
                                            'FJR' if not self.dont_process_allowance_automatically else '',
                                            'gozo_ferias',
                                            'R1005', 'R1007', 'R1006', 'R105', 'remote_work', 'LSV']]

        # Buscar quantidade de dias de ausencia nas outras entradas
        input_types = self.input_line_ids.filtered(lambda r: r.input_type_id.code in other_lines)
        if input_types:
            input_type_quantity_days = sum(self.input_line_ids.filtered(
                lambda r: r.input_type_id.code in other_lines).mapped('quantity_days'))
            # Filtrar as regras para servir de desconto
            lines = [line for line in line_vals if line.get('code') in record_rules]
            for line in lines:
                if line.get('code') != 'BASE':
                    # Calcular o valor do desconto
                    amount = self.get_amount_subs(line.get('amount'), input_type_quantity_days)
                    line['amount'] = amount

        return line_vals

    def get_input_type_values(self, input_type_id, amount, quantity_days=0):
        values = {'payslip_id': self.id,
                  'input_type_id': input_type_id,
                  'amount': amount,
                  'date_start': fields.Date.today(),
                  'date_end': fields.Date.today()}
        if quantity_days > 0:
            values['quantity_days'] = quantity_days
        return (0, 0, values)

    def get_compesation_irt(self, line_vals, diferencaIRT):

        # PESQUISAR TODAS AS REGRAS SALARIAIS QUE ESTÃO HABILITADOS PARA COMPENSAÇÃO DE IRT
        irt_compensation_rules = self.get_salary_rules_is_irt_compensation(self.struct_id.rule_ids)
        if irt_compensation_rules:
            # VERIFICAR SE JÁ FOI PROCESSADO A REGRA NA FOLHA ANTERIOR DO FUNCIONÁRIO
            compensation_rules = self.verify_old_irt_compensation_rule(irt_compensation_rules)
            if not compensation_rules:
                irt_compensation_rule_ids = irt_compensation_rules
            else:
                irt_compensation_rule_ids = irt_compensation_rules.filtered(
                    lambda r: r.id not in compensation_rules.ids)

            # GERAR REGRAS ALEATORIAMENTE
            if len(irt_compensation_rule_ids) > 2:
                compensation_rule_ids = self.random_irt_compesation_rules(irt_compensation_rule_ids.ids)
                irt_compensation_rule_ids = irt_compensation_rules.filtered(lambda r: r.id in compensation_rule_ids)

            line_vals.extend(self.create_irt_compensation_rules(irt_compensation_rule_ids, diferencaIRT))
        else:
            raise ValidationError(
                f"Não é possível efectuar o cálculo desta folha, por não possuir regras auxiliares para, "
                f"a Compensação IRT do colaborador {self.employee_id.name}. Contacte o Administrador do R.H.")

        return line_vals

    def get_rule_amount(self, rule, rule_amount):
        amount = 0
        if rule.code == 'BASE':
            return (rule_amount / self.env.company.calendar_days_moth_salary) * self.get_num_work_days_base_salary()
        elif rule.code in ['TRANS', 'ALI', 'R75']:
            # Verificar se o contrato começou no mesmo mẽs que esta a se processar o salário, se sim não deve descontar os subsídios de ALimentação e Transporte com base nos dias trabalhados
            if self.contract_id.date_start.month == self.date_from.month:
                return rule_amount

            hours_per_day = self._get_worked_day_lines_hours_per_day()
            num_work_days = self.get_num_work_days()
            # CALCULAR OS DIAS TRABALHADOS DE ACORDO COM AS HORAS POR DIA
            hours = num_work_days * hours_per_day
            worked_days = (hours / hours_per_day) if hours_per_day else 0
            # CALCULAR O SALARIO BASE COM BASE NOS DIAS TRABALHADOS
            if self.employee_id.contract_type.code == 'NACIONAL' and not self.contract_id.calendar_days:
                days = self.env.company.working_days_moth_salary
            else:
                days = self.env.company.calendar_days_moth_salary

            amount = (rule_amount / days) * worked_days

        return amount

    def create_irt_compensation_rules(self, irt_compensation_rules, diferencaIRT):
        if len(irt_compensation_rules) == 2:
            amount_65 = (diferencaIRT * 60) / 100
            amount_35 = (diferencaIRT * 40) / 100
            result = [{
                'sequence': rule.sequence,
                'code': rule.code,
                'name': rule.name,
                'note': html2plaintext(rule.note) if not is_html_empty(rule.note) else '',
                'salary_rule_id': rule.id,
                'contract_id': self.contract_id.id,
                'employee_id': self.employee_id.id,
                'amount': amount_65 if index == 0 else amount_35,
                'amount_before_discount': amount_65 if index == 0 else amount_35,
                'quantity': 1,
                'quantity_days': 1,
                'rate': 100,
                'slip_id': self.id,
            } for index, rule in enumerate(irt_compensation_rules)]
        else:
            result = [{
                'sequence': irt_compensation_rules[0].sequence,
                'code': irt_compensation_rules[0].code,
                'name': irt_compensation_rules[0].name,
                'note': html2plaintext(irt_compensation_rules[0].note) if not is_html_empty(
                    irt_compensation_rules[0].note) else '',
                'salary_rule_id': irt_compensation_rules[0].id,
                'contract_id': self.contract_id.id,
                'employee_id': self.employee_id.id,
                'amount': diferencaIRT,
                'amount_before_discount': diferencaIRT,
                'quantity': 1,
                'quantity_days': 1,
                'rate': 100,
                'slip_id': self.id,
            }]
        return result

    def random_irt_compesation_rules(self, rules_ids):
        random.shuffle(rules_ids)
        return rules_ids[:2]

    def _get_worked_day_lines_values(self, domain=None):
        if self.env.company.country_id.code == "AO":
            self.ensure_one()
            res = []
            num_work_days = self.get_num_work_days_base_salary()
            hours_per_day = self._get_worked_day_lines_hours_per_day()
            date_from = datetime.combine(self.date_from, datetime.min.time())
            date_to = datetime.combine(self.date_to, datetime.min.time())
            # work_hours = self.contract_id._get_work_hours(date_from, date_to, domain=domain)
            # work_hours_ordered = sorted(work_hours.items(), key=lambda x: x[1])
            # biggest_work = work_hours_ordered[-1][0] if work_hours_ordered else 0
            add_days_rounding = 0
            # for work_entry_type_id, hours in work_hours_ordered:
            #     work_entry_type = self.env['hr.work.entry.type'].browse(work_entry_type_id)
            #     # CALCULAR OS DIAS TRABALHADOS DE ACORDO COM AS HORAS POR DIA
            #     hours = num_work_days * hours_per_day
            #     days = (hours / hours_per_day) if hours_per_day else 0
            #     if work_entry_type_id == biggest_work:
            #         days += add_days_rounding
            #     day_rounded = self._round_days(work_entry_type, days)
            #     add_days_rounding += (days - day_rounded)
            #     attendance_line = {
            #         'sequence': work_entry_type.sequence,
            #         'work_entry_type_id': work_entry_type_id,
            #         'number_of_days': day_rounded,
            #         'number_of_hours': hours,
            #     }
            #     res.append(attendance_line)
            work_entry_type = self.env.ref('hr_work_entry.work_entry_type_attendance')
            # CALCULAR OS DIAS TRABALHADOS DE ACORDO COM AS HORAS POR DIA
            hours = num_work_days * hours_per_day
            # days = (hours / hours_per_day) if hours_per_day else 0

            attendance_line = {
                'sequence': work_entry_type.sequence,
                'work_entry_type_id': work_entry_type.id,
                'number_of_days': num_work_days,
                'number_of_hours': hours,
            }
            res.append(attendance_line)

            return res
        else:
            return super(HRPayslip, self)._get_worked_day_lines_values()

    def get_num_work_days(self):
        # Pegar todos os dias de trabalho no calendario do funcionário
        dates = (self.date_from + timedelta(idx + 1)
                 for idx in range((self.date_to - self.date_from).days))
        # verificar o tipo de funcionario
        if self.employee_id.contract_type.code == 'NACIONAL' and not self.contract_id.calendar_days:
            first_day, last_day = self.get_first_and_last_day(self.date_from, self.date_to)
            if first_day == self.date_from.day and last_day == self.date_to.day:
                return int(self.env.company.working_days_moth_salary)
            else:
                # Verificar se o dia actual esta no entervalo de dias uteis
                num_work_days = sum(1 for day in dates if day.weekday() < 5)
                if num_work_days > int(self.env.company.working_days_moth_salary):
                    num_work_days = int(self.env.company.working_days_moth_salary)
                return num_work_days
        elif self.employee_id.contract_type.code in ['EXPATRIADO',
                                                     'EXPATRIADO_RESIDENTE'] or self.contract_id.calendar_days:
            first_day, last_day = self.get_first_and_last_day(self.date_from, self.date_to)
            if first_day == self.date_from.day and last_day == self.date_to.day:
                return int(self.env.company.calendar_days_moth_salary)
            else:
                # Verificar se o dia actual esta no entervalo de dias corridos(SEGUNDA A DOMINGO)
                num_work_days = sum(1 for day in dates if day.weekday() in [0, 1, 2, 3, 4, 5, 6])
                if num_work_days > int(self.env.company.calendar_days_moth_salary):
                    num_work_days = int(self.env.company.calendar_days_moth_salary)
                return num_work_days

    def get_num_work_days_base_salary(self):
        if self.contract_id.work_entry_source == 'calendar':
            diference = self.date_to - self.date_from
            num_work_days = diference.days + 1
            first_day, last_day = self.get_first_and_last_day(self.date_from, self.date_to)
            if first_day == self.date_from.day and last_day == self.date_to.day:
                return int(self.env.company.calendar_days_moth_salary)
            else:
                if num_work_days > int(self.env.company.calendar_days_moth_salary):
                    num_work_days = int(self.env.company.calendar_days_moth_salary)
                return num_work_days

    # def get_first_and_last_day(self, date_from):
    #     first_day = date_from.replace(day=1)
    #     last_day = calendar.monthrange(date_from.year, date_from.month)[1]
    #     return first_day.day, last_day

    def get_first_and_last_day(self, date_from, date_to):
        first_day = date_from.replace(day=1)
        last_day = calendar.monthrange(date_to.year, date_to.month)[1]
        return first_day.day, last_day

    def get_salary_rules_is_irt_compensation(self, rule_ids):
        return rule_ids.filtered(lambda r: r.is_irt_compensation)

    def verify_old_irt_compensation_rule(self, compensation_rules):
        # PESQUISAR TODOS AS FOLHAS SALÁRIAIS DO FUNCIONÁRIO DO CORRENTE ANO
        payslips_ids = self.get_all_current_payslip()
        if payslips_ids:
            # FILTAR AS LINHAS COM COMPESAÇÃO IRT NAS FOLHAS SÁRIAS
            salary_lines = payslips_ids[-1].line_ids.filtered(
                lambda r: r.salary_rule_id.id in compensation_rules.ids)
            if salary_lines:
                return salary_lines.salary_rule_id
        return False

    def get_all_current_payslip(self):
        current_date = datetime.now()
        current_year = current_date.year
        first_day_year = date(current_year, 1, 1)
        last_day_year = date(current_year, 12, 31)
        # PESQUISAR TODOS AS FOLHAS SALÁRIAIS DO FUNCIONÁRIO DO CORRENTE ANO
        payslips_ids = self.env['hr.payslip'].sudo().search(
            [('employee_id', '=', self.employee_id.id), ('state', 'in', ['done', 'paid']),
             ('date_from', '>=', first_day_year),
             ('date_to', '<', last_day_year)])
        return payslips_ids

    def calculate_christmas_amount(self, work_month=False):
        amount = self.wage
        data = self.get_scale_group_values()
        work_month = self.contract_id.get_employee_work_complete_month(self.date_from) if not work_month else work_month

        if self.contract_type_id.code in ['EXPATRIADO',
                                          'EXPATRIADO_RESIDENTE'] and self.process_automatically_exchange:
            if not self.salary_kz:
                if self.env.company.currency == 'USD' or self.env.company.currency == 'AOA':
                    amount = self.contract_id.get_kz_amount(self.contract_id.total_paid_usd)
                elif self.env.company.currency == 'EUR':
                    amount = self.contract_id.get_euro_kz_amount(
                        self.contract_id.total_paid_usd)
        elif self.contract_type_id.code in ['EXPATRIADO',
                                            'EXPATRIADO_RESIDENTE'] and not self.process_automatically_exchange:
            if not self.salary_kz:
                amount = (self.contract_id.total_paid_usd * self.exchange_rate)

        christmas_amount = ((amount * int(data.get('christmas_bonus'))) / 100)
        amount = (christmas_amount / 12) * work_month
        return amount

    def create_missed_hours(self, input_type_ids):
        input_line_values = []
        for record in self:
            if input_type_ids:
                input_type_falta_injustificada_id = self.env.ref(
                    'l10n_ao_hr.l10n_ao_hr_type_missed_hours_falta_injustificada').id
                input_type_falta_justificada_sem_remuneracao_id = self.env.ref(
                    'l10n_ao_hr.l10n_ao_hr_type_missed_hours_falta_just_nao_remunerada').id
                input_type_falta_justificada_remuneracao_id = self.env.ref(
                    'l10n_ao_hr.l10n_ao_hr_type_missed_hours_falta_just_remunerada').id

                input_type_unjustified_ids = input_type_ids.filtered(
                    lambda r: 'unjustified' == r.type_missed_hours and 'MISSING_HOUR' == r.input_type_id.code)
                input_type_justified_without_remuneration_ids = input_type_ids.filtered(
                    lambda
                        r: 'justified_without_remuneration' == r.type_missed_hours and 'MISSING_HOUR' == r.input_type_id.code)
                input_type_justified_remuneration_ids = input_type_ids.filtered(
                    lambda
                        r: 'justified_with_remuneration' == r.type_missed_hours and 'MISSING_HOUR' == r.input_type_id.code)

                hours_per_day = record.employee_id.resource_calendar_id.hours_per_day
                salary_hour = record.get_mount_hour_salary_employee()
                if input_type_unjustified_ids:
                    quantity_days = sum(input_type_unjustified_ids.mapped('quantity_days'))
                    hours = quantity_days * hours_per_day
                    amount_normal = (hours * salary_hour)
                    input_line_values.append((0, 0,
                                              {'payslip_id': record.id,
                                               'input_type_id': input_type_falta_injustificada_id,
                                               'amount': amount_normal,
                                               'type_missed_hours': 'unjustified',
                                               'hours': sum(input_type_unjustified_ids.mapped('hours')),
                                               'quantity_days': quantity_days,
                                               'date_start': fields.Date.today(),
                                               'date_end': fields.Date.today()
                                               }))

                if input_type_justified_without_remuneration_ids:
                    quantity_days = sum(input_type_justified_without_remuneration_ids.mapped('quantity_days'))
                    hours = quantity_days * hours_per_day
                    amount_weekend = (hours * salary_hour)
                    input_line_values.append((
                        0, 0,
                        {'payslip_id': record.id, 'input_type_id': input_type_falta_justificada_sem_remuneracao_id,
                         'amount': amount_weekend,
                         'type_missed_hours': 'justified_without_remuneration',
                         'hours': sum(input_type_justified_without_remuneration_ids.mapped('hours')),
                         'quantity_days': quantity_days,
                         'date_start': fields.Date.today(),
                         'date_end': fields.Date.today()
                         }))

                if input_type_justified_remuneration_ids:
                    quantity_days = sum(input_type_justified_remuneration_ids.mapped('quantity_days'))
                    hours = quantity_days * hours_per_day
                    amount_weekend = (hours * salary_hour)
                    input_line_values.append((
                        0, 0,
                        {'payslip_id': record.id, 'input_type_id': input_type_falta_justificada_remuneracao_id,
                         'amount': amount_weekend,
                         'type_missed_hours': 'justified_with_remuneration',
                         'hours': sum(input_type_justified_remuneration_ids.mapped('hours')),
                         'quantity_days': quantity_days,
                         'date_start': fields.Date.today(),
                         'date_end': fields.Date.today()
                         }))

        return input_line_values

    def create_extra_hours(self, input_type_ids):
        input_line_values = []
        for record in self:
            hour_execed = input_type_weekend_total_hours = 0
            input_type_normal_ids = input_type_ids.filtered(
                lambda r: r.type_of_overtime == 'normal' and r.input_type_id.code == 'HEXTRAS')
            input_type_weekend_ids = input_type_ids.filtered(
                lambda r: r.type_of_overtime == 'weekend' and r.input_type_id.code == 'HEXTRAS')
            if input_type_normal_ids:
                input_type_normal_total_hours = sum(input_type_normal_ids.mapped('hours'))
                if input_type_normal_total_hours > self.env.company.limit_hours:
                    hour_execed = input_type_normal_total_hours - self.env.company.limit_hours

                amount_normal = input_type_normal_ids[0].calculate_extra_hours('normal', record, {
                    'hours': input_type_normal_total_hours if hour_execed == 0 else self.env.company.limit_hours})
                input_line_values.append(
                    (0, 0, {'payslip_id': record.id,
                            'input_type_id': self.env.ref('l10n_ao_hr.l10n_ao_hr_horas_extras_50%').id,
                            'amount': amount_normal,
                            'type_of_overtime': 'normal',
                            'hours': input_type_normal_total_hours if hour_execed == 0 else self.env.company.limit_hours,
                            'date': fields.Date.today()
                            }
                     )
                )

            if input_type_weekend_ids or hour_execed != 0:
                if input_type_weekend_ids:
                    input_type_weekend_total_hours = sum(input_type_weekend_ids.mapped('hours'))

                input_type_weekend_total_hours += hour_execed
                input_type_weekend_id = input_type_weekend_ids[0] if input_type_weekend_ids else input_type_normal_ids[
                    0]
                amount_weekend = input_type_weekend_id.calculate_extra_hours('weekend', record,
                                                                             {'hours': input_type_weekend_total_hours})

                input_line_values.append(
                    (0, 0, {'payslip_id': record.id,
                            'input_type_id': self.env.ref('l10n_ao_hr.l10n_ao_hr_horas_extras_75%').id,
                            'amount': amount_weekend,
                            'type_of_overtime': 'weekend', 'hours': input_type_weekend_total_hours,
                            'date': fields.Date.today()
                            }
                     )
                )

        return input_line_values

    def calculate_missed_hours(self, type_missed_hours, values):
        extra_value = 0

        def get_hour_value(hours, salario_hora):
            return hours * salario_hora

        def get_minute_values(salario_hora):
            return salario_hora / 2

        if not values.get("hours"):
            return extra_value

        hour_salary = self.get_mount_hour_salary_employee()
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

            if type_missed_hours in ['unjustified', 'justified_without_remuneration']:
                if hours:
                    extra_value = get_hour_value(hours, hour_salary)

                if minutes:
                    total_minutes = get_minute_values(hour_salary)
                    extra_value += total_minutes

        return extra_value

    def get_mount_hour_salary_employee(self):
        venc = abs(self.contract_id.wage)
        hour_salary = (venc * 12) / (52 * self.contract_id.resource_calendar_id.hours_per_week)
        return hour_salary

    def get_hour_minutes(self, values):
        hours = int(values.get("hours"))
        minutes = int((values.get("hours") - hours) * 60)
        return hours, minutes

    def calculate_vocation_allowance(self, working_days=0):
        difference_months = 0
        vocation_bonus = self.get_scale_group_values()['vocation_bonus']
        working_days_moth_salary = self.get_scale_group_values()['working_days_moth_salary']
        contract_id = self.env['hr.contract'].sudo().search([('employee_id', '=', self.employee_id.id)])
        if working_days == 0:
            difference_months = self.employee_id.validate_employee_admission_date(self.date_from)
            if difference_months:
                if difference_months > 12:
                    difference_months = 12

        if working_days == 0:
            working_days = difference_months * 2 if difference_months < 12 else 22

        # CALCULAR GRÁTIFICAÇÃO DE FÉRIAS DO FUNCIONÁRIO
        employee_salary = contract_id[-1].wage * (vocation_bonus / 100)
        gratificacao_feria = (employee_salary / working_days_moth_salary) * working_days
        return gratificacao_feria

    def calculate_vocation_proportional(self, working_days):
        working_days_moth_salary = self.get_scale_group_values()['working_days_moth_salary']
        vacation_amount = (self.contract_id.wage / working_days_moth_salary) * working_days
        return vacation_amount

    def calculate_retroactive_amount(self, working_days, code):
        employee_salary = 0
        if self.employee_id.contract_type.code == 'NACIONAL' and not self.contract_id.calendar_days:
            working_days_moth_salary = self.get_scale_group_values()['working_days_moth_salary']
        else:
            working_days_moth_salary = self.get_scale_group_values()['calendar_days_moth_salary']

        contract_id = self.env['hr.contract'].sudo().search([('employee_id', '=', self.employee_id.id)])
        if code == 'R92':
            if contract_id[-1].remuneration_ids.filtered(lambda r: r.remuneration_code_id.code == 'R75'):
                employee_salary = contract_id[-1].remuneration_ids.filtered(
                    lambda r: r.remuneration_code_id.code == 'R75').mapped('amount')[0]
        elif code == 'R67':
            if contract_id[-1].remuneration_ids.filtered(lambda r: r.remuneration_code_id.code == 'SUB_TRANS'):
                employee_salary = contract_id[-1].remuneration_ids.filtered(
                    lambda r: r.remuneration_code_id.code == 'SUB_TRANS').mapped('amount')[0]
        elif code == 'R68':
            if contract_id[-1].remuneration_ids.filtered(lambda r: r.remuneration_code_id.code == 'SUB_ALI'):
                employee_salary = contract_id[-1].remuneration_ids.filtered(
                    lambda r: r.remuneration_code_id.code == 'SUB_ALI').mapped('amount')[0]

        vacation_amount = (employee_salary / working_days_moth_salary) * working_days
        return vacation_amount

    def verify_old_vocation_allowance(self):
        # PESQUISAR TODOS AS FOLHAS SALÁRIAIS DO FUNCIONÁRIO DO CORRENTE ANO
        payslips_ids = self.get_all_current_payslip()
        if payslips_ids:
            # FILTAR AS LINHAS DE SALARIO DE GRATIFICAÇÃO DE FÉRIAS NAS FOLHAS SÁRIAS
            gratification_salary_lines = payslips_ids[-1].input_line_ids.filtered(
                lambda r: r.input_type_id.id == self.env.ref('l10n_ao_hr.l10n_ao_hr_gratificacao_feria').id)
            if gratification_salary_lines:
                return True
        return False

    @api.onchange('employee_id')
    def on_change_employee_id(self):
        for payslip in self:
            if payslip.employee_id:
                contract_id = self.env["hr.contract"].sudo().search(
                    [('employee_id', '=', payslip.employee_id.id), ('date_start', '<=', payslip.date_to), '|',
                     ('date_end', '>=', payslip.date_from),
                     ('date_end', '=', False), ('state', '=', 'open')], limit=1)
                if contract_id:
                    payslip.contract_id = contract_id
            else:
                payslip.write({'contract_id': False, 'struct_id': False})

    @api.onchange('contract_id')
    def on_change_contract_id(self):
        for payslip in self:
            if payslip.contract_id:
                struct_id = self.env["hr.payroll.structure"].sudo().search(
                    [('type_id', '=', payslip.contract_id.structure_type_id.id)])
                if struct_id:
                    payslip.struct_id = struct_id[-1]

                    # start_day = self.env.company.holidays_processing_day_start
                    # end_day = self.env.company.holidays_processing_day_end
                    # # pegar o mes anterior ao mes selecionado no processamento
                    # before_month = payslip.date_from.month - 1
                    # if before_month > 0:
                    #     first_date = date(payslip.date_from.year, before_month, start_day)
                    #     end_date = date(payslip.date_from.year, payslip.date_from.month, end_day)
                    #     leave_ids = self.env['hr.leave'].get_validate_leave_ids([payslip.employee_id.id], first_date,
                    #                                                             end_date)
                    #     if leave_ids:
                    #         input_lines = payslip.check_leave_type(leave_ids, first_date, end_date)
                    #         self.input_line_ids = input_lines
            else:
                payslip.name = ""

    def get_dates_from_leaves(self, leave_date_start, leave_date_end, first_date, end_date):
        leave_intervale_dates = (leave_date_start + timedelta(days=idx)
                                 for idx in range((leave_date_end - leave_date_start).days + 1))
        intervale_dates = (first_date + timedelta(days=idx)
                           for idx in range((end_date - first_date).days + 1))
        days = [day for day in intervale_dates]
        # Para os Expatriados com a Politica Individual tem 40 dias corridos
        if self.employee_id.contract_type.code == "NACIONAL":
            """Filtra apenas os dias úteis dias da semana"""
            working_days = [day.date() for day in leave_intervale_dates if day.weekday() < 5]
            days_filtered = [day for day in working_days if day in days]
            num_work_days = len(days_filtered)
            if num_work_days > int(self.env.company.working_days_moth_salary):
                num_work_days = int(self.env.company.working_days_moth_salary)
            return num_work_days
        else:
            working_days = [day.date() for day in leave_intervale_dates]
            days_filtered = [day for day in working_days if day in days]
            """Filtra todos os dias corridos dias da semana"""
            num_work_days = len(days_filtered)
            if num_work_days > int(self.env.company.calendar_days_moth_salary):
                num_work_days = int(self.env.company.calendar_days_moth_salary)
            return num_work_days

    def input_type_values(self, input_type_id, date_from, date_to, working_days, amount=0, hour=0):
        return (0, 0,
                {
                    'input_type_id': input_type_id,
                    'date_start': date_from,
                    'date_end': date_to,
                    'quantity_days': working_days,
                    'hours': hour,
                    'amount': amount
                })

    @api.onchange('struct_id')
    def _onchange_structure(self):
        if self.env.company.country_id.code == "AO":
            structure = self.struct_id and self.struct_id.id or None
            input_records = self.env['hr.payslip.input.type'].search([])
            aa = input_records.mapped(lambda i: i.id)
            input_list = [x.id for x in input_records if
                          (len(x.struct_ids) == 0 or structure and structure in x.struct_ids.mapped(lambda i: i.id))]
            self.input_line_ids = [(5, 0, 0)]
            for input_record in input_list:
                self.input_line_ids = [(0, 0, {'input_type_id': input_record, 'amount': 0.0})]

    @api.onchange('date_to')
    def on_change_date_to(self):
        if self.env.company.country_id.code == "AO":
            for payslip in self:
                aoa_currency = self.env.ref('base.AOA').with_context(date=payslip.date_to)
                usd_currency = self.env.ref('base.USD').with_context(date=payslip.date_to)
                rate_date_at = self.env["res.company"].sudo().search([], limit=1)
                if rate_date_at:
                    if rate_date_at.rate_date_at == 'current_date':
                        payslip.currency_rate = self.env['res.currency']._get_conversion_rate(usd_currency,
                                                                                              aoa_currency,
                                                                                              payslip.company_id or self.env.user.company_id,
                                                                                              date.today())
                    elif rate_date_at.rate_date_at == 'payslip_close_date':
                        payslip.currency_rate = self.env['res.currency']._get_conversion_rate(usd_currency,
                                                                                              aoa_currency,
                                                                                              payslip.company_id or self.env.user.company_id,
                                                                                              payslip.date_to)

    def compute_remuneration(self):
        res = {}
        for slip in self:
            _sum = 0.0
            if self.env.company.country_id.code == "AO":
                for line in slip.line_ids:
                    if line.appears_on_payslip == False:
                        continue
                    if line.category_id.code == 'BAS':
                        _sum = _sum + line.total
            res[slip.id] = _sum
            slip.remuneration = _sum
        return res

    def compute_overtimes(self):
        res = {}
        for slip in self:
            _sum = 0.0
            if self.env.company.country_id.code == "AO":
                for line in slip.line_ids:
                    if line.appears_on_payslip == False:
                        continue
                    if line.category_id.code == 'HEXTRA':
                        _sum = _sum + line.total
            res[slip.id] = _sum
            slip.overtimes = _sum
        return res

    def compute_extra_remunerations(self):
        res = {}
        for slip in self:
            if self.env.company.country_id.code == "AO":
                slip.extra_remunerations = slip.total_remunerations - slip.remuneration - slip.overtimes
            else:
                slip.extra_remunerations = 0
        return res

    def compute_misses(self):
        res = {}
        for slip in self:
            _sum = 0.0
            if self.env.company.country_id.code == "AO":
                for line in slip.line_ids:
                    if line.appears_on_payslip == False:
                        continue
                    if line.category_id.code == 'FALTA':
                        _sum = _sum + line.total
            res[slip.id] = _sum
            slip.misses = _sum
        return res

    def compute_remuneration_inss_base(self):
        for slip in self:
            if self.env.company.country_id.code == "AO":
                rule_base = slip.line_ids.filtered(lambda r: r.code == 'BASE')
                slip.remuneration_inss_base = rule_base.amount
                # slip.remuneration_inss_base = slip.remuneration + slip.overtimes + slip.misses
            else:
                slip.remuneration_inss_base = 0

    def compute_remuneration_inss_extra(self):
        res = {}
        for slip in self:
            _sum = 0.0
            if self.env.company.country_id.code == "AO":
                for line in slip.line_ids:
                    if line.appears_on_payslip == False:
                        continue
                    if line.category_id.code in ('ABOINSS', 'ABOINSSIRT'):
                        _sum = _sum + line.total
            res[slip.id] = _sum
            slip.remuneration_inss_extra = _sum
        return res

    def compute_remuneration_inss_total(self):
        for slip in self:
            if self.env.company.country_id.code == "AO":
                slip.remuneration_inss_total = slip.collected_material_inss
            else:
                slip.remuneration_inss_total = 0

    def compute_amount_inss(self):
        res = {}
        for slip in self:
            _sum = 0.0
            if self.env.company.country_id.code == "AO":
                for line in slip.line_ids:
                    if line.appears_on_payslip == False:
                        continue
                    if line.category_id.code == 'INSS':
                        _sum = _sum + line.total
            res[slip.id] = _sum
            slip.amount_inss = _sum
        return res

        # inss 8% no processamento

    def compute_amount_inss8(self):
        res = {}
        for slip in self:
            _sum = 0.0
            if self.env.company.country_id.code == "AO":
                for line in slip.line_ids:
                    if line.appears_on_payslip == False:
                        continue
                    if line.category_id.code == 'INSS8':
                        _sum = _sum + line.total
            res[slip.id] = _sum
            slip.amount_inss8 = _sum
        return res

    def compute_amount_irt(self):
        res = {}
        for slip in self:
            _sum = 0.0
            if self.env.company.country_id.code == "AO":
                for line in slip.line_ids:
                    if line.appears_on_payslip == False:
                        continue
                    if line.category_id.code == 'IRT':
                        _sum = _sum + line.total
            res[slip.id] = _sum
            slip.amount_irt = _sum
        return res

    def compute_extra_deductions(self):
        for p in self:
            _sum = 0.0
            if self.env.company.country_id.code == "AO":
                for line in p.line_ids:
                    if line.category_id.code not in ('INSS', 'IRT') and line.deduction > 0:
                        _sum = _sum + line.deduction
            p.extra_deductions = -_sum

    def compute_amount_base_irt(self):
        res = {}
        for slip in self:
            _sum = 0.0
            if self.env.company.country_id.code == "AO":
                for line in slip.line_ids:
                    if line.appears_on_payslip == False:
                        continue
                    if line.category_id.code in ['BAS', 'HEXTRA_50', 'HEXTRA_75', 'FALTA', 'ABOIRT', 'ABOINSSIRT',
                                                 'DEDINSSIRT', 'INSS']:
                        _sum = _sum + line.total
            res[slip.id] = _sum
            slip.amount_base_irt = _sum
        return res

    def compute_payslip_period(self):
        for slip in self:
            date_obj = slip.date_to
            months = {
                1: _('Janeiro'),
                2: _('Fevereiro'),
                3: _('Março'),
                4: _('Abril'),
                5: _('Maio'),
                6: _('Junho'),
                7: _('Julho'),
                8: _('Agosto'),
                9: _('Setembro'),
                10: _('Outubro'),
                11: _('Novembro'),
                12: _('Dezembro'),
            }
            slip.payslip_period = months[int(date_obj.month)]

    def compute_total_remunerations(self):
        res = {}
        for slip in self:
            rem_total = 0.0
            if self.env.company.country_id.code == "AO":
                if slip.total_remunerations_exp == 0:
                    for slipline in slip.line_ids:
                        if not slipline.appears_on_payslip:
                            continue

                        if slipline.code in ['ATRA', 'FJNR', 'FJR', 'FI', 'R105', 'R1005', 'R1007', 'R1006',
                                             'gozo_ferias',
                                             'remote_work', 'LSV']:
                            continue

                        # if slip.contract_type_id.code in ['EXPATRIADO',',
                        #                                   'EXPATRIADO_RESIDENTE'] and not slip.contract_id.irt_exempt:
                        #
                        #     if slipline.code in ['R75', 'A_CUSTO', 'EAT']:
                        #         continue

                        rem_total += slipline.remuneration
                else:
                    rem_total = slip.total_remunerations_exp
            res[slip.id] = rem_total
            slip.total_remunerations = rem_total
        return res

    def compute_total_deductions(self):
        res = {}
        for slip in self:
            ded_total = 0.0
            if self.env.company.country_id.code == "AO":
                for slipline in slip.line_ids:
                    if not slipline.appears_on_payslip:
                        continue

                    if slipline.code in ['ATRA', 'FJNR', 'FJR', 'FI', 'R105', 'R1005', 'R1007', 'R1006', 'gozo_ferias',
                                         'remote_work', 'LSV']:
                        continue

                    ded_total += slipline.deduction

            res[slip.id] = ded_total
            slip.total_deductions = ded_total
        return res

    def compute_total_paid(self):
        res = {}
        for slip in self:
            if self.env.company.country_id.code == "AO":
                # if slip.contract_type_id.code == 'EXPATRIADO':
                #     if slip.dont_return_irt:
                #         # Filtrar a regra de IRT
                #         deduction_rule = slip.line_ids.filtered(
                #             lambda p: p.category_id == self.env.ref('l10n_ao_hr.hr_payroll_salary_rule_category_irt'))
                #         deduction_irt_amount = deduction_rule.total * -1 if deduction_rule else 0
                #         total_deductions = slip.total_deductions - deduction_irt_amount
                #         slip.total_paid = slip.total_remunerations - total_deductions
                #     else:
                #         slip.total_paid = slip.total_remunerations - slip.total_deductions
                # else:
                slip.total_paid = slip.total_remunerations - slip.total_deductions
                if slip.total_paid > 0:
                    currency_values = {"AOA": _("Kwanzas"), "EUR": _("Euros"), "USD": _("Dolares Americanos")}
                    if self.env.company.currency_id.symbol == "Kz":
                        currency_name = currency_values[self.env.company.currency_id.name]
                        slip.total_paid_words = amount_currency_translate_pt.amount_to_text(int(slip.total_paid),
                                                                                            currency_name)
                else:
                    slip.total_paid_words = 0
                    slip.total_paid = 0
            else:
                slip.total_paid_words = 0
                slip.total_paid = 0
        return res

    def compute_total_receipt_kz(self):
        for slip in self:
            if self.env.company.country_id.code == "AO" and slip.contract_type_id.code == 'EXPATRIADO':
                deduction_rules = slip.line_ids.filtered(lambda p: p.code in ['D44'])
                deduction_total = sum(rules.total for rules in deduction_rules) * -1 if deduction_rules else 0
                total_recept_kz_rules = slip.line_ids.filtered(lambda p: p.salary_rule_id.paid_in_kwanza_in_angola)
                total_recept_kz_rule_total = sum(rules.total for rules in total_recept_kz_rules) + slip.allowance_exp
                slip.total_recept_kz = total_recept_kz_rule_total - deduction_total if total_recept_kz_rule_total > 0 else 0
            else:
                slip.total_recept_kz = 0

    def compute_total_receipt_usd_kz(self):
        for slip in self:
            if self.env.company.country_id.code == "AO" and slip.contract_type_id.code == 'EXPATRIADO':
                deduction_irt_amount = 0
                deduction_rules = slip.line_ids.filtered(
                    lambda p: p.code in ['Desc_Seguro', 'D19', 'D32', 'D33', 'D34', 'D35',
                                         'D36', 'D37', 'D38', 'D39', 'D40'])
                deduction_total = sum(rules.total for rules in deduction_rules) * -1 if deduction_rules else 0
                total_recept_usd_kz_rules = slip.line_ids.filtered(
                    lambda p: p.salary_rule_id.paid_in_kwanza_foreign_currency)
                if slip.dont_fixed_remunerations:
                    deduction_rules = slip.line_ids.filtered(lambda p: p.code in ['D44'])
                    if not deduction_rules:
                        deduction_rule = slip.line_ids.filtered(
                            lambda p: p.category_id == self.env.ref('l10n_ao_hr.hr_payroll_salary_rule_category_irt'))
                        deduction_irt_amount = deduction_rule.total * -1 if deduction_rule else 0
                    else:
                        deduction_total = sum(rules.total for rules in deduction_rules) * -1 if deduction_rules else 0

                slip.total_recept_usd_kz = sum(rules.total for rules in total_recept_usd_kz_rules) - (
                        deduction_total + deduction_irt_amount)
            elif self.env.company.country_id.code == "AO" and slip.contract_type_id.code == 'EXPATRIADO_RESIDENTE':
                slip.total_recept_usd_kz = slip.total_paid
            else:
                slip.total_recept_usd_kz = 0

    @api.depends("total_recept_usd_kz")
    def compute_total_paid_usd(self):
        for slip in self:
            if self.env.company.country_id.code == "AO":
                total_recept_usd_kz = slip.total_recept_usd_kz
                if slip.process_automatically_exchange:
                    aoa_currency = self.env.ref('base.AOA')
                    usd_currency = self.env.ref('base.USD')
                    usd = aoa_currency._compute(aoa_currency, usd_currency, total_recept_usd_kz)
                    slip.total_paid_usd = usd
                else:
                    if slip.exchange_rate_id.name != 0:
                        slip.total_paid_usd = total_recept_usd_kz / slip.exchange_rate_id.name
                    else:
                        slip.total_paid_usd = 0
            else:
                slip.total_paid_usd = 0

    @api.depends("total_recept_usd_kz")
    def compute_total_paid_euro(self):
        aoa_currency = self.env.ref('base.AOA')
        euro_currency = self.env.ref('base.EUR')
        for slip in self:
            if self.env.company.country_id.code == "AO":
                usd = aoa_currency._compute(aoa_currency, euro_currency, slip.total_recept_usd_kz)
                slip.total_paid_euro = usd
            else:
                slip.total_paid_euro = ''

    def compute_hour_salary(self):
        for slip in self:
            if self.env.company.country_id.code == "AO":
                venc = abs(slip.contract_id.wage)
                slip.hour_salary = (venc * 12) / (52 * slip.contract_id.resource_calendar_id.hours_per_week)
            else:
                slip.hour_salary = 0

    def compute_worked_days(self):
        for slip in self:
            if self.env.company.country_id.code == "AO":
                if slip.line_ids:
                    hours_per_day = slip._get_worked_day_lines_hours_per_day()
                    num_work_days = slip.get_num_work_days()
                    # CALCULAR OS DIAS TRABALHADOS DE ACORDO COM AS HORAS POR DIA
                    hours = num_work_days * hours_per_day
                    slip.worked_days = (hours / hours_per_day) if hours_per_day else 0
                else:
                    slip.worked_days = 0
            else:
                slip.worked_days = 0

    def compute_payslip_line(self):
        for slip in self:
            if self.env.company.country_id.code == "AO":
                if slip.line_ids:
                    # PEGAR O VENCIMENTO BASE
                    slip.wage = (
                                        slip.contract_id.wage / self.env.company.calendar_days_moth_salary
                                ) * slip.get_num_work_days_base_salary()
                else:
                    slip.wage = slip.contract_id.wage
            else:
                slip.wage = slip.contract_id.wage

    def compute_period_working_days(self):
        for payslip in self:
            # Add code to consider public holidays
            schedule = payslip.contract_id.resource_calendar_id
            total_days = 0
            date_from = fields.Date.from_string(payslip.date_from)
            date_to = fields.Date.from_string(payslip.date_to)
            delta_days = (date_to - date_from).days
            for single_date in (date_from + timedelta(n) for n in range(delta_days + 1)):
                total_days += 1
            payslip.period_working_days = total_days

    @api.depends('date_to', 'company_id')
    def compute_currency_rate(self):
        for payslip in self:
            if self.env.company.country_id.code == "AO":
                aoa_currency = self.env.ref('base.AOA').with_context(date=payslip.date_to)
                usd_currency = self.env.ref('base.USD').with_context(date=payslip.date_to)
                rate_date_at = self.env["res.company"].sudo().search([('id', '=', payslip.company_id.id)], limit=1)
                if rate_date_at:
                    if rate_date_at.rate_date_at == 'current_date':
                        payslip.currency_rate = self.env['res.currency']._get_conversion_rate(usd_currency,
                                                                                              aoa_currency,
                                                                                              payslip.company_id or self.env.user.company_id,
                                                                                              date.today())
                    elif rate_date_at.rate_date_at == 'payslip_close_date':
                        payslip.currency_rate = self.env['res.currency']._get_conversion_rate(usd_currency,
                                                                                              aoa_currency,
                                                                                              payslip.company_id or self.env.user.company_id,
                                                                                              payslip.date_to)
            else:
                payslip.currency_rate = 0

    def compute_show_total_paid_usd(self):
        for slip in self:
            if self.env.company.country_id.code == "AO":
                if slip.env.user.company_id.show_paid_usd:
                    if slip.employee_id.contract_type.code in ['EXPATRIADO_RESIDENTE', 'EXPATRIADO']:
                        slip.show_total_paid_usd = True
                    else:
                        slip.show_total_paid_usd = False
                else:
                    slip.show_total_paid_usd = slip.env.user.company_id.show_paid_usd
            else:
                slip.show_total_paid_usd = False

    def _get_employee_partner(self):
        for payslip in self:
            partner_id = self.env['res.partner'].sudo().search([('name', '=', payslip.employee_id.name)], limit=1)
            return partner_id.id

    def create_extra_hours_report(self):
        # TPEGAR O EXTERNAR ID DAS Horas Extras
        extra_hour_normal_id = self.env.ref('l10n_ao_hr.l10n_ao_hr_horas_extras_50%').id
        extra_hour_weekend_id = self.env.ref('l10n_ao_hr.l10n_ao_hr_horas_extras_75%').id
        # PEGAR AS LINHAS DE HORAS EXTRAS NA FOLHA SALARIAL
        extra_hour_normal_line_id = self.input_line_ids.filtered(lambda r: r.input_type_id.id == extra_hour_normal_id)
        extra_hour_weekend_line_id = self.input_line_ids.filtered(lambda r: r.input_type_id.id == extra_hour_weekend_id)
        if extra_hour_normal_line_id or extra_hour_weekend_line_id:
            current_date = datetime.now()
            current_year = current_date.year
            # CONSTRUIR O DICIONÁRIO COM OS CAMPOS PARA A CRIAÇÃO DO RELÁTÓRIO DE HORAS EXTRAS
            extra_hours_values = {
                'company_id': self.env.company.id,
                'employee_id': self.employee_id.id,
                'department_id': self.employee_id.department_id.id if self.employee_id.department_id else False,
                'country_id': self.employee_id.country_id.id if self.employee_id.country_id else False,
                'job_id': self.employee_id.job_id.id if self.employee_id.job_id else False,
                'gender': self.employee_id.gender if self.employee_id.gender else False,
                'year': current_year,
            }
            # CRIAR RELATÓRIO DE LANÇAMENTO DE HORAS EXTRAS DO FUNCIONÁRIO
            if extra_hour_normal_line_id:
                self.create_extra_hours_model(extra_hours_values, extra_hour_normal_line_id, 'normal')

            if extra_hour_weekend_line_id:
                self.create_extra_hours_model(extra_hours_values, extra_hour_weekend_line_id, 'weekend')

        return {}

    def create_extra_hours_model(self, extra_hours_values, extra_hour_line_id, extra_hour_type):
        extra_hours_values['input_type_id'] = extra_hour_line_id[0].id
        extra_hours_values['type_of_overtime'] = extra_hour_type
        extra_hours_values['date'] = extra_hour_line_id[0].date
        extra_hours_values['hours'] = extra_hour_line_id[0].hours
        extra_hours_values['amount'] = extra_hour_line_id[0].amount
        return self.env['extra.hours.report'].create(extra_hours_values)

    def _prepare_adjust_line(self, line_ids, adjust_type, debit_sum, credit_sum, date):
        acc_id = self.sudo().journal_id.default_account_id.id if self.sudo().journal_id.default_account_id else self.sudo().journal_id.default_account_salary_id.id
        if not acc_id:
            raise UserError(
                _('The Expense Journal "%s" has not properly configured the default Account!') % (self.journal_id.name))
        existing_adjustment_line = (
            line_id for line_id in line_ids if line_id['name'] == _('Adjustment Entry')
        )
        adjust_credit = next(existing_adjustment_line, False)

        if not adjust_credit:
            adjust_credit = {
                'name': _('Adjustment Entry'),
                'partner_id': False,
                'account_id': acc_id,
                'journal_id': self.journal_id.id,
                'date': date,
                'debit': 0.0 if adjust_type == 'credit' else credit_sum - debit_sum,
                'credit': debit_sum - credit_sum if adjust_type == 'credit' else 0.0,
            }
            line_ids.append(adjust_credit)
        else:
            adjust_credit['credit'] = debit_sum - credit_sum

    def action_report_simple_payslip(self):
        return {
            'name': 'Simple Payslip',
            'type': 'ir.actions.act_url',
            'url': '/print/simple/payslips?list_ids=%(list_ids)s' % {'list_ids': ','.join(str(x) for x in self.ids)},
        }

    def action_report_double_payslip(self):
        return {
            'name': 'Double Payslip',
            'type': 'ir.actions.act_url',
            'url': '/print/double/payslips?list_ids=%(list_ids)s' % {'list_ids': ','.join(str(x) for x in self.ids)},
        }

    def action_send_email(self, cr=None, context=None):
        if self.env.company.country_id.code == "AO":
            '''
            This function opens a window to compose an email, with the edi sale template message loaded by default
            '''
            uid = self.env.user
            ids = [self.id]
            template_id = self.env.ref('l10n_ao_hr.l10n_ao_hr_email_template_payslip_send_email', False)
            compose_form_id = False
            ctx = dict()
            ctx.update({
                'default_model': 'hr.payslip',
                'default_res_id': self.id,
                'default_use_template': bool(template_id),
                'default_template_id': template_id and template_id.id or False,
                'default_composition_mode': 'comment',
            })
            return {
                'type': 'ir.actions.act_window',
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'mail.compose.message',
                'views': [(compose_form_id, 'form')],
                'view_id': compose_form_id,
                'target': 'new',
                'context': ctx,
            }
        else:
            return super(HRPayslip, self).action_send_email()

    def action_print_payslip(self):
        if self.env.company.country_id.code == "AO":
            return {
                'name': 'Payslip',
                'type': 'ir.actions.act_url',
                'url': 'print/double/payslips?list_ids=%(list_ids)s' % {'list_ids': ','.join(str(x) for x in self.ids)},
            }
        else:
            return super(HRPayslip, self).action_print_payslip()

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
            'working_days_moth_salary': self.env.company.working_days_moth_salary,
            'calendar_days_moth_salary': self.env.company.calendar_days_moth_salary,
            'vocation_bonus': self.env.company.vocation_bonus,
            'take_vacation_after_admission': self.env.company.take_vacation_after_admission,
            'christmas_bonus': self.env.company.christmas_bonus,
        }
        return data


class HRPayslipLine(models.Model):
    _inherit = 'hr.payslip.line'

    remuneration = fields.Float(compute='compute_remuneration', digits=(10, 2), string='Remuneration')
    deduction = fields.Float(compute='compute_deduction', digits=(10, 2), string='Deduction')
    quantity_days = fields.Float(string="Quantidade", defautl=1,
                                 help="Este campo vai servir para apresentar quantidade de dias, utilizado para debitar nas regras com base nas ausẽncias")
    amount_before_discount = fields.Float(string="Valor", help="Valor original do subsídio antes do Desconto")

    @api.depends('quantity', 'amount', 'rate')
    def _compute_total(self):
        for line in self:
            line.total = float(line.quantity) * line.amount * line.rate / 100

    def compute_remuneration(self):
        for slip_line in self:
            total = 0
            if slip_line.total >= 0:
                total = slip_line.total
            slip_line.remuneration = total
        return {}

    def compute_deduction(self):
        for slip_line in self:
            total = 0
            if slip_line.total < 0:
                total = abs(slip_line.total)
            slip_line.deduction = total
        return {}


class HRPayslipRun(models.Model):
    _inherit = 'hr.payslip.run'

    exchange_rate_id = fields.Many2one('hr.exchange.rate', string='Taxa de Câmbio')

    def action_open_add_extra_rules_wizard(self):
        return {
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': "hr.add.extra.salary.rules",
            'context': {'default_payslip_run_id': self.id},
            'target': 'new',
        }

    def action_send_email(self):
        for slip_run in self:
            if self.env.company.country_id.code == "AO":
                for slip in slip_run.slip_ids:
                    template = self.env.ref('l10n_ao_hr.l10n_ao_hr_email_template_payslip_send_email')
                    # template = self.env['mail.template'].browse(template.id)
                    template.sudo().send_mail(
                        slip.id, force_send=True,
                        email_layout_xmlid='mail.mail_notification_light')
            else:
                return True


class HrPayslipEmployees(models.TransientModel):
    _inherit = 'hr.payslip.employees'

    def compute_sheet(self):
        self.ensure_one()
        if self.env.company.country_id.code == "AO":
            if not self.structure_id:
                raise UserError(_("Deve Informar a Estrutura Salarial para avançar."))

            if not self.env.context.get('active_id'):
                from_date = fields.Date.to_date(self.env.context.get('default_date_start'))
                end_date = fields.Date.to_date(self.env.context.get('default_date_end'))
                today = fields.date.today()
                first_day = today + relativedelta(day=1)
                last_day = today + relativedelta(day=31)
                if from_date == first_day and end_date == last_day:
                    batch_name = from_date.strftime('%B %Y')
                else:
                    batch_name = _('From %s to %s', format_date(self.env, from_date), format_date(self.env, end_date))
                payslip_run = self.env['hr.payslip.run'].create({
                    'name': batch_name,
                    'date_start': from_date,
                    'date_end': end_date,
                })
            else:
                payslip_run = self.env['hr.payslip.run'].browse(self.env.context.get('active_id'))

            employees = self.with_context(active_test=False).employee_ids
            if not employees:
                raise UserError(_("Você deve selecionar o(s) funcionário(s) para gerar o(s) Recibos de Salário."))

            # Prevent a payslip_run from having multiple payslips for the same employee
            employees -= payslip_run.slip_ids.employee_id
            success_result = {
                'type': 'ir.actions.act_window',
                'res_model': 'hr.payslip.run',
                'views': [[False, 'form']],
                'res_id': payslip_run.id,
            }
            if not employees:
                return success_result

            # payslips = self.env['hr.payslip']
            Payslip = self.env['hr.payslip']

            contracts = employees._get_contracts(
                payslip_run.date_start, payslip_run.date_end, states=['open', 'close']
            ).filtered(lambda c: c.active)
            contracts.generate_work_entries(payslip_run.date_start, payslip_run.date_end)
            work_entries = self.env['hr.work.entry'].search([
                ('date_start', '<=', payslip_run.date_end),
                ('date_stop', '>=', payslip_run.date_start),
                ('employee_id', 'in', employees.ids),
            ])
            self._check_undefined_slots(work_entries, payslip_run)

            if (self.structure_id.type_id.default_struct_id == self.structure_id):
                work_entries = work_entries.filtered(lambda work_entry: work_entry.state != 'validated')
                if work_entries._check_if_error():
                    work_entries_by_contract = defaultdict(lambda: self.env['hr.work.entry'])

                    for work_entry in work_entries.filtered(lambda w: w.state == 'conflict'):
                        work_entries_by_contract[work_entry.contract_id] |= work_entry

                    for contract, work_entries in work_entries_by_contract.items():
                        conflicts = work_entries._to_intervals()
                        time_intervals_str = "\n - ".join(['', *["%s -> %s" % (s[0], s[1]) for s in conflicts._items]])
                    return {
                        'type': 'ir.actions.client',
                        'tag': 'display_notification',
                        'params': {
                            'title': _('Some work entries could not be validated.'),
                            'message': _('Time intervals to look for:%s', time_intervals_str),
                            'sticky': False,
                        }
                    }

            default_values = Payslip.default_get(Payslip.fields_get())
            payslips_vals = []
            for contract in self._filter_contracts(contracts):
                values = dict(default_values, **{
                    'name': _('New Payslip'),
                    'employee_id': contract.employee_id.id,
                    'payslip_run_id': payslip_run.id,
                    'date_from': payslip_run.date_start,
                    'date_to': payslip_run.date_end,
                    'contract_id': contract.id,
                    'struct_id': self.structure_id.id or contract.structure_type_id.default_struct_id.id,
                    'exchange_rate_id': payslip_run.exchange_rate_id.id if contract.employee_id.contract_type.id != self.env.ref(
                        'l10n_ao_hr.l10n_ao_hr_contract_type_nacional').id else False,
                    'exchange_rate': payslip_run.exchange_rate_id.name
                })
                payslips_vals.append(values)
            payslips = Payslip.with_context(tracking_disable=True).create(payslips_vals)
            payslips._compute_name()
            payslips.compute_sheet()
            payslip_run.state = 'verify'

            return success_result
        else:
            return super(HrPayslipEmployees, self).compute_sheet()
