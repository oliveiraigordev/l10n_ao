from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from datetime import datetime, timedelta, date, time
from dateutil.relativedelta import relativedelta
import calendar
from collections import defaultdict
import pytz


def calc_age(birthday):
    today = fields.Date.today()
    return (today.year - birthday.year) - (
            (today.month, today.day) < (birthday.month, birthday.day)
    )


class ContractTypePayroll(models.Model):
    _inherit = 'hr.contract.type'

    code = fields.Char('Código')
    # is_exchange_adjustment = fields.Boolean('Exchange Adjustment')
    is_irt_compensation = fields.Boolean('Compensação IRT')
    is_inss_compensation = fields.Boolean('Compensação INSS')
    is_exempt_irt = fields.Boolean('Isento IRT')
    is_exempt_inss = fields.Boolean('Isento INSS')

    def write(self, values):
        if self.env.company.country_id.code == "AO":
            if values.get('name') and self.code in ['NACIONAL', 'EXPATRIADO', 'EXPATRIADO_RESIDENTE']:
                return {}
        return super(ContractTypePayroll, self).write(values)

    def unlink(self):
        to_unlink = self.env[self._name]
        for record in self:
            if self.env.company.country_id.code == "AO":
                if record.code in ['NACIONAL', 'EXPATRIADO', 'EXPATRIADO_RESIDENTE']:
                    continue
                else:
                    to_unlink |= record
        return super(ContractTypePayroll, to_unlink).unlink()


class HREmployeeDisciplinarySituation(models.Model):
    _name = 'employee.disciplinary.situation'
    _description = 'Employee Disciplinary Situation'

    contract_id = fields.Many2one('hr.contract', 'Contract')
    currency_id = fields.Many2one('res.currency', string='Currency', related='contract_id.currency_id')
    disciplinary_situation = fields.Boolean(string="Active", tracking=True,
                                            help="Indicates whether the employee is subject to discipline.")
    disciplinary_wage = fields.Monetary(string="Disciplinary Wage", tracking=True,
                                        help="Wage to be paid to the employee.")
    disciplinary_date_start = fields.Date(string="Date Start", tracking=True, help="Start date of disciplinary action.",
                                          required=True)
    disciplinary_date_end = fields.Date(string="Date End", tracking=True, help="End date of disciplinary action.",
                                        required=True)
    note = fields.Text(string="Note", tracking=True, help="Note")

    @api.constrains('disciplinary_date_start', 'disciplinary_date_end')
    def _check_dates(self):
        if self.disciplinary_date_start > self.disciplinary_date_end:
            raise ValidationError(_("The start date of disciplinary action must be earlier than the end date."))

    def active_disciplinary_situation(self):
        active_records = self.search([('disciplinary_situation', '=', True), ('contract_id', '=', self.contract_id.id)])
        if active_records:
            active_records.disciplinary_situation = False

        self.disciplinary_situation = True
        self.contract_id.write({'disciplinary_situation': True})

    def remove_disciplinary_situation(self):
        self.disciplinary_situation = False
        self.contract_id.write({'disciplinary_situation': False})

    @api.model_create_multi
    def create(self, vals):

        result = super(HREmployeeDisciplinarySituation, self).create(vals)
        for record in result:
            if record.disciplinary_wage <= 0:
                raise ValidationError(_("Disciplinary amount must be greater than zero."))

        return result

    def write(self, vals):

        res = super(HREmployeeDisciplinarySituation, self).write(vals)
        for record in self:
            if record.disciplinary_wage <= 0:
                raise ValidationError(_("Disciplinary amount must be greater than zero."))

        return res


class HREmployeeSalaryHistory(models.Model):
    _name = 'employee.salary.history'
    _description = 'Employee Salary History'

    contract_id = fields.Many2one('hr.contract', 'Contract')
    job_id = fields.Many2one('hr.job', 'Job Title', related='contract_id.job_id')
    currency_id = fields.Many2one('res.currency', string='Currency', related='contract_id.currency_id')
    amount = fields.Monetary(string='Amount', currency_field='currency_id')
    date = fields.Date(string='Date')
    set_active = fields.Boolean(string='Active', default=False)
    note = fields.Text(string="Note", tracking=True, help="Note")

    @api.model_create_multi
    def create(self, vals):

        result = super(HREmployeeSalaryHistory, self).create(vals)
        for record in result:
            if record.amount <= 0:
                raise ValidationError(_("Salary amount must be greater than zero."))

        return result

    def write(self, vals):

        res = super(HREmployeeSalaryHistory, self).write(vals)
        for record in self:
            if record.amount <= 0:
                raise ValidationError(_("Salary amount must be greater than zero."))

        return res

    def update_contract_salary(self):
        # filtrar as employee_salary_history_ids que tem o set_active = True
        active_records = self.search([('set_active', '=', True), ('contract_id', '=', self.contract_id.id)])
        if active_records:
            active_records.set_active = False

        self.set_active = True
        if self.contract_id.employee_id.contract_type.code == 'NACIONAL':
            self.contract_id.write({'wage': self.amount})
        else:
            self.contract_id.write({'total_paid_usd': self.amount})


class ContractPayroll(models.Model):
    _inherit = 'hr.contract'

    wage_final = fields.Float(string='Salário Base', compute='compute_wage_final', digits=(10, 2),
                              help="This is the real wage for this employee. You can define wage in contract or in job (for all employees), if you define wage in contract and job, the wage in contract will be considered.")
    week_hours = fields.Float(string='Horas Semanais', compute='compute_week_hours',
                              help="This is the amount of week hours defined in working schedule for this contract.")
    wage_hour = fields.Float(string='Salário Hora', compute='compute_wage_hour',
                             help="This is the hour wage for this employee. This is computed from the working schedule using (wage * 12)/(week_hours * 52)")
    wage_day = fields.Float(string="Salário Dia", compute="_compute_wage_day")
    remuneration_ids = fields.One2many('hr.extra.remuneration', 'contract_id',
                                       string='Remunerações do presente contrato')
    state = fields.Selection(selection_add=[('termination', 'Rescisão'), ('close',)])
    type_of_agreement = fields.Selection(
        [('mutual_agreement', 'Mutuo Acordo'),
         ('work_request', 'A Pedido do Trabalhador'), ('just_cause_dis', 'Justa Causa (Disciplinar)'),
         ('just_cause_ob_c', 'Justa Causa (Causas Objectivas)'), ('resignation', 'Demissão'),
         ('work_abandonment', 'Abandono de Trabalho'), ('expiry_of_cotract', 'Caducidade de Contracto')])
    causes = fields.Selection(
        [('economical', 'Económicas'), ('individual_or_collective_dismissal', 'Despedimento Individual ou Colectivo')])
    is_seniority_allowance = fields.Boolean('Subsídio de Antiguidade')
    early_warning = fields.Selection(
        [('working', 'Trabalho'), ('discounted', 'Com desconto'), ('indemnified', 'Indemnizado'),
         ('trial', 'Trial Order')])
    early_warning_date = fields.Date('Data de alerta')
    type_of_notice_days = fields.Selection(
        [('working_days', 'Dias Úteis'), ('calendar_days', 'Dias Corridos')], 'Tipo de aviso/Dias')
    notice_days = fields.Integer('Dias de pré-aviso')
    termination_date = fields.Date('Data de Rescisão')
    date_of_medical_examination = fields.Date('Data do exame médico')
    attach_medical_exam = fields.Binary('Anexar exame médico')
    attach_medical_exam_file_name = fields.Char(string="Anexo do exame médico")
    contract_type_id = fields.Many2one(compute="compute_employee_id")
    contract_situation = fields.Selection(
        [('active', 'Activo'), ('fired', 'Demitido'),
         ('termination', 'Rescisão'), ('unpaid_leave', 'Férias não Remuneradas'),
         ('maternity_leave', 'Licença Maternidade'), ('pre_maternity_leave', 'Licença Pré-Maternidade'),
         ('service_commission', 'Comissão de Serviço'), ], 'Situação', default='active')
    fired_date = fields.Date('Data de Despedimento')
    leave_period_start_date = fields.Date('Data de Início')
    leave_period_end_date = fields.Date('Data Final')
    termination_confirm = fields.Boolean()
    termination_payslip_id = fields.Integer()
    total_paid_words = fields.Char(compute='compute_total_paid_words', string="Total Pago em extenso")
    contract_period = fields.Selection(
        [('quarterly', 'Trimestral'), ('semi-annually', 'Semestral'), ('annually', 'Anual')], 'Período de Contrato')
    self_renewable = fields.Boolean(string='Auto-renovável?')
    total_paid_usd = fields.Float(digits=(10, 2), string='Salário')
    show_total_paid_usd = fields.Boolean(string='Mostrar Total Líquido (USD)', default=False)
    show_total_paid_euro = fields.Boolean(string='Mostrar Total Líquido (Euro)', default=False)
    admission_date = fields.Date(string="Data de Admissão", tracking=True)
    contract_end_date_automatically = fields.Boolean('Calcular automaticamente a data de fim do contrato')
    direction_id = fields.Many2one(related="department_id.direction_id", help="Direcção")
    exchange_rate_id = fields.Many2one('hr.exchange.rate', string='Taxa de Câmbio')
    salary_manual_processing = fields.Boolean('Adicionar Salário Manualmente')
    process_automatically_exchange = fields.Boolean(related='company_id.process_automatically_exchange')
    salary_kz = fields.Boolean('Adicionar valor em Kwanza')
    calendar_days = fields.Boolean("Calcular dias corridos para cálculo de subsídios")
    irt_exempt = fields.Boolean("Isento a IRT")
    contract_type = fields.Selection(
        [('determinado', ' Determinado'), ('indeterminado', 'Indeterminada'),
         ('independente', 'Independente'), ('autonomo', 'Autonomo'), ('estagio', 'Estágio'),
         ('especial', 'Contrato de Trabalho Especial')], string='Tipo de Contrato', default='indeterminado')
    employee_salary_history_ids = fields.One2many('employee.salary.history', 'contract_id', tracking=True,
                                                  string='Employee Salary History')
    employee_disc_situation_history_ids = fields.One2many('employee.disciplinary.situation', 'contract_id',
                                                          string='Employee Disciplinary Situation')
    disciplinary_situation = fields.Boolean(string="Disciplinary Situation", tracking=True,
                                            help="Indicates whether the employee is subject to discipline.")
    contract_res = fields.Date(string="Data efectiva da rescisão de contrato", tracking=True)
    contract_res_from = fields.Date(string="Data de processamento da rescisão", tracking=True)
    contract_res_to = fields.Date(string="Data de processamento da rescisão", tracking=True)
    dont_include_base_rule = fields.Boolean(string="Não incluir Salário Base na Rescisão")

    def write(self, vals):
        if self.env.company.country_id.code == "AO":
            if 'state' in vals:
                for record in self:
                    if record.state == 'termination' and record.termination_confirm:
                        raise UserError(
                            f"Não é permitido mudar o estado do contracto que se encontra em estado de Rescisão.")

            # today = date.today()
            # # Alterar o valor do salário do contrato para o valor adicionado na situação disciplinar
            # if 'disciplinary_situation' in vals and vals['disciplinary_situation']:
            #     # Verificar se a data de inicio da situação disciplinar é igual a data de hoje
            #     date_start = date(
            #         int(vals['disciplinary_date_start'].split('-')[0]),
            #         int(vals['disciplinary_date_start'].split('-')[1]),
            #         int(vals['disciplinary_date_start'].split('-')[2]),
            #     )
            #     if date_start == today:
            #         vals['wage'] = vals[
            #             'disciplinary_wage'] if 'disciplinary_wage' in vals else self.disciplinary_wage
            #
            # if 'disciplinary_situation' in vals and not vals['disciplinary_situation']:
            #     # filtrar as employee_salary_history_ids que tem o set_active = True
            #     active_records = self.employee_salary_history_ids.filtered(lambda x: x.set_active)
            #     if active_records:
            #         vals['wage'] = active_records.amount

        return super(ContractPayroll, self).write(vals)

    def action_view_employee_salary_history(self):
        self.ensure_one()
        if not self.employee_salary_history_ids:
            self.env['employee.salary.history'].create(
                {'contract_id': self.id, 'amount': self.wage, 'date': self.date_start, 'set_active': True})

        return {
            'type': 'ir.actions.act_window',
            'name': f'Salary History',
            'view_mode': 'tree',
            'res_model': "employee.salary.history",
            "domain": f"[('id', 'in', {self.employee_salary_history_ids.ids})]",
            'context': {'default_contract_id': self.id},
            'target': 'current',
        }

    def action_view_disciplinary_situation(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Disciplinary Situation History',
            'view_mode': 'tree',
            'res_model': "employee.disciplinary.situation",
            "domain": f"[('id', 'in', {self.employee_disc_situation_history_ids.ids})]",
            'context': {'default_contract_id': self.id},
            'target': 'current',
        }

    def action_print_declaration(self):
        return self.env.ref('l10n_ao_hr.action_report_work_declaration').report_action(self)

    def action_report_mock_receipt(self):
        if self.env.company.country_id.code == "AO":
            if self.state != 'termination':
                return

            if not self.admission_date and self.is_seniority_allowance:
                raise UserError(
                    f"Deve fornecer a data de admissão do colaborador para avançar com Rescisão.")

            self.delete_payslip()
            result = self.create_termination_contract_salary()
            if result:
                self.termination_payslip_id = result.id

            return {
                'name': 'Mock Receipt Termination Payslip',
                'type': 'ir.actions.act_url',
                'url': '/print/termination/mock/receipt?list_ids=%(list_ids)s' % {
                    'list_ids': ','.join(str(x) for x in [self.termination_payslip_id])},
            }

    def action_report_termination_confirmation(self):
        if self.env.company.country_id.code == "AO":
            if self.state != 'termination' or not self.termination_payslip_id:
                return

            payslip_id = self.env['hr.payslip'].sudo().search([('id', '=', self.termination_payslip_id)])
            if payslip_id.state in ['draft', 'verify']:
                payslip_id.action_payslip_done()

            if not self.termination_confirm:
                if self.type_of_agreement != 'resignation':
                    self.write(
                        {'termination_confirm': True, 'contract_situation': 'termination',
                         'fired_date': self.termination_date, 'date_end': self.termination_date})
                else:
                    self.write(
                        {'termination_confirm': True, 'contract_situation': 'fired',
                         'fired_date': self.termination_date, 'date_end': self.termination_dat})
                # Actualizar o estado da situação e o ultimo dia de trabalho do funcionário na ficha
                self.employee_id.write(
                    {'employee_situation': self.contract_situation, 'last_work_date': self.termination_date})

            return {
                'name': 'Termination Confirmation Payslip',
                'type': 'ir.actions.act_url',
                'url': '/print/double/payslips?list_ids=%(list_ids)s' % {
                    'list_ids': ','.join(str(x) for x in [self.termination_payslip_id])},
            }

    def create_termination_contract_salary(self):
        if self.env.company.country_id.code == "AO":
            # PEGAR O EXTERNAR ID DAS input line
            input_type_antiguidade = self.env.ref('l10n_ao_hr.l10n_ao_hr_antiguidade').id
            input_type_aviso_previo_compensacao = self.env.ref('l10n_ao_hr.l10n_ao_hr_aviso_previo_compensacao').id
            input_type_aviso_previo_descontado = self.env.ref('l10n_ao_hr.l10n_ao_hr_aviso_previo_descontado').id
            input_type_abono_natal_id = self.env.ref('l10n_ao_hr.l10n_ao_hr_horas_abono_natal').id
            input_type_gratificacao_ferias = self.env.ref('l10n_ao_hr.l10n_ao_hr_gratificacao_feria').id
            input_type_grati_propor_ferias = self.env.ref('l10n_ao_hr.l10n_ao_hr_ferias_proporcional_before_9').id
            input_type_proporc_abono_natal_id = self.env.ref('l10n_ao_hr.l10n_ao_hr_natal_proporcional').id
            input_type_proporc_ferias_before_id = self.env.ref('l10n_ao_hr.l10n_ao_hr_ferias_proporcional_before').id
            input_type_proporc_ferias_id = self.env.ref('l10n_ao_hr.l10n_ao_hr_ferias_proporcional_after').id
            payslip_id = False
            input_type_lines = []
            num_work_days = 0
            # RESCISÃO POR MUTUO ACORDO
            if self.type_of_agreement in ['mutual_agreement', 'work_request', 'expiry_of_cotract']:
                payslip_id = self.create_employee_payslip()
                num_work_days = payslip_id.get_num_work_days_base_salary()
                #  INDEMNIZADO
                if self.early_warning == 'indemnified':
                    compensation_amount = self.calculate_compensation_deduction(self.type_of_notice_days, num_work_days)
                    input_type_lines.append(
                        payslip_id.get_input_type_values(input_type_aviso_previo_compensacao, compensation_amount))
                # Trabalhado
                elif self.early_warning == 'working':
                    input_type_lines.append(
                        payslip_id.get_input_type_values(input_type_aviso_previo_descontado, 0, num_work_days))
                #  Descontado
                elif self.early_warning == 'discounted':
                    deduction_amount = self.calculate_compensation_deduction(self.type_of_notice_days, num_work_days)
                    input_type_lines.append(
                        payslip_id.get_input_type_values(input_type_aviso_previo_descontado, deduction_amount))
            #  RESCISÃO POR Justa Causa (Disciplinary) ou (objective causes) e Abandono do trabalho
            elif self.type_of_agreement in ['just_cause_dis', 'just_cause_ob_c', 'work_abandonment']:
                payslip_id = self.create_employee_payslip()
            #  RESCISÃO POR Caducidade ou renúncia
            elif self.type_of_agreement == 'resignation':
                payslip_id = self.create_employee_payslip()
                num_work_days = payslip_id.get_num_work_days_base_salary()
                compensation_amount = self.calculate_compensation_deduction(self.type_of_notice_days, num_work_days)
                input_type_lines.append(
                    payslip_id.get_input_type_values(input_type_aviso_previo_compensacao, compensation_amount))

            #  CALCULAR ABONO DE ANTIFUIDADE
            if self.is_seniority_allowance:
                seniority_allowance_amount = self.calculate_seniority_allowance()
                if seniority_allowance_amount != 0:
                    input_type_lines.append(
                        payslip_id.get_input_type_values(input_type_antiguidade, seniority_allowance_amount))

            #  Create abono de Natal
            work_month = self.get_employee_work_complete_month(self.date_start)
            christmas_amount = payslip_id.calculate_christmas_amount(work_month)
            input_type_lines.append(payslip_id.get_input_type_values(input_type_abono_natal_id, christmas_amount))

            #  Create Proporcional abono de Natal
            christmas_prop_amount = ((self.wage / 12) * self.contract_res_from.month) * (
                    int(self.env.company.christmas_bonus) / 100)
            input_type_lines.append(
                payslip_id.get_input_type_values(input_type_proporc_abono_natal_id, christmas_prop_amount))

            # VERIFICAR SE A OPÇÃO PROCESSAMENTO AUTOMATIVCO DE GRATIFICAÇÃO FÉRIAS ESTA MARCADO NO TIPO DE EMPRESA
            if self.env.company.process_automatically_vacation:
                working_days = work_month * 2 if work_month < 12 else 22
                # VERIFICAR SE JÁ FOI PAGO O SALARIO DE FÉRIAS E GRATIFICAÇÃO DE FERIAS AO FUNCIONÁRIO
                verify_old_vocation_allowance = payslip_id.verify_old_vocation_allowance()
                if not verify_old_vocation_allowance:
                    # Calcular Gratificação de férias do ano anterior
                    gratificacao_ferias_amount = payslip_id.calculate_vocation_allowance(working_days)
                    input_salario_feria_values = [payslip_id.get_input_type_values(input_type_grati_propor_ferias,
                                                                                   gratificacao_ferias_amount)]

                    # Calcular Ferias proporcional de férias do ano anterior
                    vacation_before_prop_amount = payslip_id.calculate_vocation_proportional(working_days)
                    input_salario_feria_values.append(
                        payslip_id.get_input_type_values(input_type_proporc_ferias_before_id,
                                                         vacation_before_prop_amount)
                    )

                    if input_salario_feria_values:
                        input_type_lines.extend(input_salario_feria_values)
                else:
                    # Calcular Ferias proporcional de férias do ano anterior
                    vacation_before_prop_amount = payslip_id.calculate_vocation_proportional(working_days)
                    input_type_lines.append(
                        payslip_id.get_input_type_values(input_type_proporc_ferias_before_id,
                                                         vacation_before_prop_amount))
            else:
                working_days = work_month * 2 if work_month < 12 else 22
                gratificacao_ferias_amount = payslip_id.calculate_vocation_allowance(working_days)
                input_type_lines.append(
                    payslip_id.get_input_type_values(input_type_gratificacao_ferias, gratificacao_ferias_amount))

            # Proporcional Ferias
            working_vacation_days = self.contract_res_from.month * 2 if self.contract_res_from.month < 12 else 22
            vacation_prop_amount = payslip_id.calculate_vocation_proportional(working_vacation_days)
            input_type_lines.append(
                payslip_id.get_input_type_values(input_type_proporc_ferias_id, vacation_prop_amount))

            # Gratificação Ferias
            input_type_lines.append(
                payslip_id.get_input_type_values(input_type_gratificacao_ferias, (vacation_prop_amount / 2)))

            if payslip_id:
                payslip_id.write({'input_line_ids': input_type_lines})
                payslip_id.compute_sheet()
                return payslip_id

        return {}

    def calculate_compensation_deduction(self, type_of_notice_days, num_work_days=0):
        value = 0
        if self.env.company.country_id.code == "AO":
            if type_of_notice_days == 'calendar_days':
                value = (self.wage / int(self.env.company.calendar_days_moth_salary)) * num_work_days
            elif type_of_notice_days == 'working_days':
                value = (self.wage / int(self.env.company.working_days_moth_salary)) * num_work_days

        return value

    def create_employee_payslip(self):
        current_date = datetime.now()
        date_from = self.contract_res_from if self.contract_res_from else fields.Date.today()
        date_end = self.contract_res_to if self.contract_res_to else fields.Date.today()
        payslip_data = {
            'name': f'TERM OF TERMINATION:{current_date.year}/{current_date.month}',
            'company_id': self.env.company.id,
            'employee_id': self.employee_id.id,
            'contract_id': self.id,
            'date_from': date_from,
            'date_to': date_end,
            'dont_include_base_rule': self.dont_include_base_rule,
        }
        payslip_id = self.env['hr.payslip'].sudo().create(payslip_data)
        payslip_id.on_change_contract_id()
        return payslip_id

    def delete_payslip(self):
        payslip_id = self.env['hr.payslip'].search([('id', '=', self.termination_payslip_id)])
        payslip_id.action_payslip_cancel()
        return payslip_id.unlink()

    def calculate_seniority_allowance(self, years=False):

        def seniority_allowance_amount(work_year_limit, work_year_exced):
            amount_exed = 0
            base_salary = self.wage
            seniority_percentage = self.env.company.seniority_percentage
            amount = base_salary * work_year_limit
            if work_year_exced:
                amount_exed = (base_salary * work_year_exced) * (seniority_percentage / 100)

            amount += amount_exed
            return amount

        # Calcular os anos trabalhados pelo trabalhador
        seniority_limit = self.env.company.seniority_limit
        current_date = fields.Date.today()
        work_year_exced, work_year = 0, 0
        if not years:
            # Calcular a diferença de meses do trabalhador
            difference_months = current_date - self.admission_date
            work_year = difference_months.days // 365
            work_month = (difference_months.days % 365) // 30
            if work_month >= 3:
                work_year += 1
        else:
            work_year = years

        # VERIFICAR SE OS ANOS TRABALHADOS EXEDEM O LIMITE DEFINIDO NO TIPO DE EMPRESA
        if work_year > seniority_limit:
            work_year_exced = work_year - seniority_limit
            work_year = seniority_limit

        # VERIFICAR SE ESTA MARCADO A OPÇÃO NÃO INFLENCIAR OS ANOS TRANBALHADOS
        # if not_influence_number_of_years:
        #     work_year = 0
        # VERIFICAR O TIPO DE EMPRESA E CALCULAR O SUBSÍDIO DE ANTIGUIDADE
        seniority_amount = seniority_allowance_amount(work_year, work_year_exced)
        return seniority_amount

    def cron_check_disciplinary_situations_contract(self):
        today = date.today()
        # Pesquisar contractos com estado disciplinar activo
        contracts = self.search([('disciplinary_situation', '=', True), ('state', '=', 'open')])
        for contract in contracts:
            # Verificar se a data de fim do situacao disciplinar é maior ou igual a data de hoje
            if contract.disciplinary_date_end >= today:
                active_records = contract.employee_salary_history_ids.filtered(lambda x: x.set_active)
                if active_records:
                    contract.wage = active_records.amount
                    contracts.disciplinary_situation = False

            if contract.disciplinary_date_start == date.today():
                contract.wage = contract.disciplinary_wage

    def cron_end_contract_notification(self):
        email_templates = []
        if self.env.company.country_id.code == "AO":
            country_ao_id = self.env.ref('base.ao')
            # PESQUISAR OS CONTRATOS EM ESTADO EXECUÇÃO E QUE TEM PRAZO DE TERMINO DEFINIDO e não são Auto-Renovável
            contract_ids = self.search(
                [('state', '=', 'open'), ('date_end', '!=', False), ('self_renewable', '=', False),
                 ('company_country_id', '=', country_ao_id.id)])
            for contract in contract_ids:
                current_date = datetime.now()
                year = contract.date_end.year
                # PEGAR OPENULTIMO MẼS ANTES DO TERMINO DO CONTRACTO
                month = contract.date_end.month - 1
                if month == current_date.month and year == current_date.year:
                    email_template = self.env.ref(
                        'l10n_ao_hr.l10n_ao_hr_email_template_notify_end_contract_employee')
                    body = email_template._render_template(email_template.body_html, 'hr.contract', contract.ids,
                                                           post_process=True)
                    base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
                    key = next(iter(body))
                    body_new1 = body.get(key)
                    body_new1 = body_new1.split('href="/"')
                    body_new2 = body_new1[1].split('ABRIR O CONTRATO')
                    body_new2.pop(0)
                    href = f'"{base_url}/web#id={contract.id}&model=hr.contract&view_type=form">ABRIR O CONTRATO'
                    body_new2 = f"href={href}{''.join(l for l in body_new2)}"
                    body = f"{body_new1[0]}{''.join(l for l in body_new2)}"
                    mail_values = {
                        'name': email_template.name,
                        'model_id': self.env.ref('hr_payroll.model_hr_contract').id,
                        'email_from': self.env.company.email,
                        'lang': contract.activity_user_id.lang,
                        'email_to': contract.hr_responsible_id.partner_id.email,
                        'description': email_template.description,
                        'subject': email_template.subject,
                        'body_html': body,
                        'auto_delete': True,
                    }
                    # CRIAR UM NOVO TEMPLATE DE EMAIL
                    email_template = self.env['mail.template'].sudo().create(mail_values)
                    email_template.send_mail(contract.id, force_send=True)
                    email_templates.append(email_template.id)

            if email_templates:
                # ELIMINAR OS TEMPLATES DE EMAILS CRIADOS
                templates = self.env['mail.template'].search([('id', 'in', email_templates)])
                templates.unlink()

        return {}

    def cron_self_renewable_contract(self):
        if self.env.company.country_id.code == "AO":
            country_ao_id = self.env.ref('base.ao')
            contract_ids = self.search(
                [('state', '=', 'open'), ('self_renewable', '=', True), ('company_country_id', '=', country_ao_id.id)])
            for contract in contract_ids:
                current_date = datetime.now()
                if contract.date_end.month <= current_date.month and contract.date_end.year == current_date.year:
                    date_end = contract.get_self_renewable_date(contract.date_end)
                    contract.date_end = date_end
                    contract.message_post(
                        body=f'Foi Renovado a duração do contrato para <strong>{contract.date_end}</strong> automaticamente, Utilizador: <strong>{self.env.user.name}</strong>',
                        message_type='notification')

    def get_self_renewable_date(self, date_start):
        date_end = False
        if self.env.company.country_id.code == "AO":
            # Verificar o ano do inicio do contrato esta no passado
            current_date = datetime.now()
            if date_start.year < current_date.year:
                date_start = date(current_date.year, date_start.month, date_start.day)

            if self.contract_period:
                if self.contract_period == 'quarterly':
                    date_end = date_start + relativedelta(months=3)
                elif self.contract_period == 'semi-annually':
                    date_end = date_start + relativedelta(months=6)
                elif self.contract_period == 'annually':
                    date_end = date_start + relativedelta(months=12)
                day_end = calendar.monthrange(date_end.year, date_end.month)[1]
                date_end = date(date_end.year, date_end.month, day_end)
        return date_end

    @api.onchange('contract_end_date_automatically')
    def _onchange_contract_end_date_automatically(self):
        if self.contract_end_date_automatically and self.env.company.country_id.code == "AO":
            date_end = self.get_self_renewable_date(self.date_start)
            self.date_end = date_end

    @api.onchange('contract_period')
    def _onchange_contract_period(self):
        if self.contract_period and self.contract_end_date_automatically and self.env.company.country_id.code == "AO":
            date_end = self.get_self_renewable_date(self.date_start)
            self.date_end = date_end

    @api.onchange('date_start')
    def _onchange_date_start(self):
        if self.date_start and self.contract_end_date_automatically and self.env.company.country_id.code == "AO":
            date_end = self.get_self_renewable_date(self.date_start)
            self.date_end = date_end

    @api.onchange('contract_situation')
    def _onchange_contract_situation(self):
        if self.contract_situation and self.env.company.country_id.code == "AO":
            self.employee_id.employee_situation = self.contract_situation

    @api.onchange('employee_id')
    def _onchange_employee_id(self):
        if self.env.company.country_id.code == "AO":
            self.salary_manual_processing = False
            self.admission_date = self.employee_id.admission_date if not self.admission_date else self.employee_id.admission_date
        else:
            self.salary_manual_processing = True

    @api.depends('employee_id')
    def compute_employee_id(self):
        if self.env.company.country_id.code == "AO":
            for contract_id in self:
                if contract_id.employee_id:
                    contract_id.contract_type_id = contract_id.employee_id.contract_type if contract_id.employee_id.contract_type else False
                    contract_id.job_id = contract_id.employee_id.hr_job if contract_id.employee_id.hr_job else False
                    if contract_id.employee_id.contract_type.code == 'NACIONAL':
                        wage_kz = contract_id.wage if contract_id.salary_manual_processing else contract_id.employee_id.steps_ids.amount_in_kwanza
                        contract_id.write({'wage': wage_kz, 'show_total_paid_usd': False})
                    elif contract_id.employee_id.contract_type.code in ['EXPATRIADO', 'EXPATRIADO_RESIDENTE']:
                        # Verificar se esta marcado a opção de calculo de cambio automatico na configuração da companhia
                        if contract_id.process_automatically_exchange:
                            amount_in_kwanza, amount_in_dollar = 0, 0
                            if not contract_id.salary_kz:
                                amount_in_dollar = contract_id.total_paid_usd if contract_id.salary_manual_processing else \
                                    contract_id.employee_id.steps_ids.amount_in_dollar
                                amount_in_kwanza = contract_id.get_kz_amount(amount_in_dollar) if \
                                    contract_id.process_automatically_exchange else (
                                        contract_id.env.company.exchange_rate * amount_in_dollar)
                            else:
                                amount_in_kwanza = contract_id.wage
                            contract_id.write({'wage': amount_in_kwanza, 'total_paid_usd': amount_in_dollar,
                                               'show_total_paid_usd': True})
                        else:
                            if self.env.company.currency == 'USD':
                                amount_in_kwanza, amount_in_dollar = 0, 0
                                if not contract_id.salary_kz:
                                    amount_in_dollar = contract_id.total_paid_usd if contract_id.salary_manual_processing else \
                                        contract_id.employee_id.steps_ids.amount_in_dollar
                                    amount_in_kwanza = contract_id.get_kz_amount(amount_in_dollar) if \
                                        contract_id.process_automatically_exchange else (
                                            contract_id.env.company.exchange_rate * amount_in_dollar)
                                else:
                                    amount_in_kwanza = contract_id.wage

                                contract_id.write(
                                    {'wage': amount_in_kwanza, 'total_paid_usd': amount_in_dollar,
                                     'show_total_paid_usd': True,
                                     'show_total_paid_euro': False})
                            elif self.env.company.currency == 'EUR':
                                amount_in_kwanza, amount_in_euro = 0, 0
                                if not contract_id.salary_kz:
                                    amount_in_euro = contract_id.total_paid_usd if contract_id.salary_manual_processing else \
                                        contract_id.employee_id.steps_ids.amount_in_euro
                                    amount_in_kwanza = contract_id.get_euro_kz_amount(amount_in_euro) if \
                                        contract_id.process_automatically_exchange else (
                                            contract_id.env.company.exchange_rate * amount_in_euro)
                                else:
                                    amount_in_kwanza = contract_id.wage

                                contract_id.write(
                                    {'wage': amount_in_kwanza, 'total_paid_usd': amount_in_euro,
                                     'show_total_paid_usd': False,
                                     'show_total_paid_euro': True})
                else:
                    contract_id.contract_type_id = False
                    contract_id.job_id = False
        else:
            self.contract_type_id = False
            self.job_id = False

    def cron_calculate_amount_usd_to_kz(self):
        if self.env.company.country_id.code == "AO":
            contract_ids = self.search([('state', '=', 'open')])
            contract_ids = contract_ids.filtered(
                lambda r: r.employee_id.contract_type.code in ['EXPATRIADO_RESIDENTE',
                                                               'EXPATRIADO'])
            for record in contract_ids:
                # Verificar se esta marcado a opção de calculo de cambio automatico na configuração da companhia
                if record.process_automatically_exchange:
                    amount_in_dollar = record.total_paid_usd if record.salary_manual_processing else \
                        record.employee_id.steps_ids.amount_in_dollar
                    amount_in_kwanza = record.get_kz_amount(amount_in_dollar)
                    record.write(
                        {'wage': amount_in_kwanza, 'total_paid_usd': amount_in_dollar, 'show_total_paid_usd': True,
                         'show_total_paid_euro': False})
                else:
                    if self.env.company.currency == 'USD':
                        amount_in_dollar = record.total_paid_usd if record.salary_manual_processing else \
                            record.employee_id.steps_ids.amount_in_dollar
                        amount_in_kwanza = (record.get_kz_amount(amount_in_dollar)) if \
                            record.process_automatically_exchange else (
                                self.env.company.exchange_rate * amount_in_dollar)
                        record.write(
                            {'wage': amount_in_kwanza, 'total_paid_usd': amount_in_dollar, 'show_total_paid_usd': True,
                             'show_total_paid_euro': False})
                    else:
                        amount_in_euro = record.total_paid_usd if record.salary_manual_processing else \
                            record.employee_id.steps_ids.amount_in_euro
                        amount_in_kwanza = (record.get_euro_kz_amount(amount_in_euro)) if \
                            record.process_automatically_exchange else (
                                self.env.company.exchange_rate * amount_in_euro)
                        record.write(
                            {'wage': amount_in_kwanza, 'total_paid_usd': amount_in_euro, 'show_total_paid_usd': False,
                             'show_total_paid_euro': True})

    def get_kz_amount(self, wage_usd):
        current_date = datetime.today()
        usd_currency = self.env.ref('base.USD')
        inverse_rate = usd_currency.with_context(date=current_date.date()).inverse_rate
        wage_kz = inverse_rate * wage_usd
        return wage_kz

    def get_euro_kz_amount(self, wage_euro):
        current_date = datetime.today()
        euro_currency = self.env.ref('base.EUR')
        inverse_rate = euro_currency.with_context(date=current_date.date()).inverse_rate
        wage_kz = inverse_rate * wage_euro
        return wage_kz

    @api.onchange('type_of_notice_days')
    def _onchange_type_of_notice_days(self):
        if self.type_of_notice_days and self.env.company.country_id.code == "AO":
            self.write({'notice_days': 0, 'termination_date': False})

    @api.onchange('notice_days')
    def _onchange_notice_days(self):
        if self.notice_days and self.early_warning_date and self.env.company.country_id.code == "AO":
            if self.type_of_notice_days == 'working_days':
                self.termination_date = self.get_working_days(self.early_warning_date, self.notice_days)
            elif self.type_of_notice_days == 'calendar_days':
                self.termination_date = self.get_calendar_days(self.early_warning_date, self.notice_days)
        else:
            self.termination_date = False

    def get_working_days(self, start_date, num_days):
        days_added = 0
        current_date = start_date
        while days_added < num_days:
            current_date += timedelta(days=1)
            if current_date.weekday() >= 5:  # Check if the day is a weekday (0 = Monday, 6 = Sunday)
                continue
            days_added += 1
        return current_date

    def get_calendar_days(self, early_warning_date, notice_days):
        return datetime.combine(early_warning_date, time.min) + timedelta(
            days=notice_days)

    def compute_week_hours(self):
        res = {}
        for contract in self:
            _total_hours = 40
            if contract.resource_calendar_id and contract.resource_calendar_id.week_hours_final > 0:
                _total_hours = contract.resource_calendar_id.week_hours_final
            contract.week_hours = _total_hours
        return res

    def compute_wage_final(self):
        res = {}
        for contract in self:
            contract.wage_final = contract.wage
        return res

    def compute_wage_hour(self):
        res = {}
        for contract in self:
            week_hours = contract.week_hours
            contract.wage_hour = round((contract.wage_final * 12) / (week_hours * 52), 2)
        return res

    @api.depends('resource_calendar_id')
    def _compute_wage_day(self):
        for res in self:
            _wage_day = res.wage_hour * res.resource_calendar_id.hours_per_day
            res.wage_day = _wage_day

    def compute_total_paid_words(self):
        res = {}
        for contract in self:
            if contract.termination_payslip_id:
                payslip_id = self.env['hr.payslip'].sudo().search([('id', '=', contract.termination_payslip_id)])
                contract.total_paid_words = payslip_id.total_paid_words
            else:
                contract.total_paid_words = ''
        return res

    def get_employee_work_complete_month(self, date_from):
        current_date = date_from
        if self.date_start > current_date:
            return 0  # Se o contrato é futuro, não conta meses

        # verificar o dia do mes de início do contrato se for maior que o dia 15, então conta mes seguinte do contrato
        if self.date_start.day > 1:
            contract_month = self.date_start.month + 1
        else:
            contract_month = self.date_start.month

        if self.date_start.year == current_date.year:
            complete_months = 12 - contract_month + 1
        else:
            complete_months = (12 - contract_month) + 12  # Até o final do ano

        return min(complete_months, 12)
