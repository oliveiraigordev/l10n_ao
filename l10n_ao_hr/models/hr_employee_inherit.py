from odoo import fields, models, api, _
from datetime import datetime, timedelta, date
import logging

_logger = logging.getLogger(__name__)


class HRDirection(models.Model):
    _name = 'hr.direction'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Employee Direction'
    _order = 'name'

    name = fields.Char('Direcção', required=True)
    manager_id = fields.Many2one('hr.employee', 'Gestor')


class HRDepartment(models.Model):
    _inherit = 'hr.department'

    direction_id = fields.Many2one('hr.direction', 'Direcção', )


class HRHierarchicalLevel(models.Model):
    _name = 'hr.hierarchical.level'
    _description = 'Employee Hierarchical level'
    _order = 'name'

    name = fields.Char('Nível hierárquico', required=True)
    sector_id = fields.Many2one('hr.sector', string='Sector', required=True)
    department_id = fields.Many2one('hr.department', 'Departamento', required=True)


class HRSector(models.Model):
    _name = 'hr.sector'
    _description = 'Employee Sector'
    _order = 'name'

    name = fields.Char('Sector', required=True)
    department_id = fields.Many2one('hr.department', 'Departamento')


class HREmployeeDependents(models.Model):
    _name = 'hr.employee.dependents'
    _description = 'Employee Dependents'
    _order = 'name'

    name = fields.Char('Nome')
    degree_of_kinship = fields.Selection(
        [('pai', 'PAI'), ('mae', 'Mãe'), ('filho(a)', 'Filho(a)'), ('conjuge', 'CÔNJUGE'),
         ('tio(a)', 'Tio(a)'), ('sobrinho(a)', 'Sobrinho(a)')], 'Degree of Kinship', required=True)
    gender = fields.Selection([('male', 'Male'), ('female', 'Female')], 'Gender', required=True)
    date_of_birth = fields.Date('Data de Nascimento', required=True)
    employee_id = fields.Many2one('hr.employee', 'Employee')
    has_document = fields.Boolean('Tem documento?')
    has_insurance = fields.Boolean('Tem seguro?')
    date_of_inclusion = fields.Date('Data de inclusão')
    quarterly_value = fields.Float('Valor Trimestral')
    annual_value = fields.Float('Valor Anual', compute='_compute_annual_value')
    date_expiration = fields.Date('Data de expiração')
    notes = fields.Text('Notas')

    @api.depends('quarterly_value')
    def _compute_annual_value(self):
        for record in self:
            if record.quarterly_value != 0:
                record.annual_value = record.quarterly_value * 4
            else:
                record.annual_value = 0


class HREmployee(models.Model):
    _inherit = 'hr.employee'

    employee_number = fields.Char(related="registration_number", help="Inserir aqui o número do empregado")
    social_security = fields.Char('Número Segurança Social (INSS)', size=64,
                                  help="Inserir aqui o número de segurança social do trabalhador")
    fiscal_number = fields.Char('Número Fiscal (NIF)', size=64,
                                help="Inserir aqui o número de Fiscal do trabalhador", )
    admission_date = fields.Date('Data de Admissão',
                                 help='Defina esta data como o primeiro dia de trabalho, isso será necessário para o processamento parcial do salário e subsídios')
    last_work_date = fields.Date('Último dia de trabalho',
                                 help='Defina este dia como o último dia de trabalho antes de processar sua folha salarial. Isso é necessário para o processamento parcial de salários e subsídios')
    address_province = fields.Selection([('BEG', 'Bengo'),
                                         ('BEN', 'Benguela'),
                                         ('BIE', 'Bie'),
                                         ('CAB', 'Cabinda'),
                                         ('KUA', 'Cuando-Cubango'),
                                         ('KWN', 'Cuanza-Norte'),
                                         ('KWS', 'Cuanza-Sul'),
                                         ('CUN', 'Cunene'),
                                         ('HUA', 'Huambo'),
                                         ('HUI', 'Huila'),
                                         ('LDA', 'Luanda'),
                                         ('LDN', 'Lunda-Norte'),
                                         ('LDS', 'Lunda-Sul'),
                                         ('MAL', 'Malange'),
                                         ('MOX', 'Moxico'),
                                         ('NAM', 'Namibe'),
                                         ('UIG', 'Uige'),
                                         ('ZAI', 'Zaire'), ], 'Province',
                                        help='Inserir aqui a província do Funcionário')
    address_county = fields.Char('Município', size=20, help="Insira aqui o município Funcionário")
    address_address = fields.Char('Endereço', size=600, help="Insirir aqui o endereço do Funcionários")
    personal_mobile = fields.Char('Telefone Pessoal', size=20, help="Inserir aqui o telemóvel pessoal")
    personal_email = fields.Char('Email Pessoal', size=100, help="Inserir aqui o email pessoal do funcionário")
    payment_method = fields.Selection([('bank', 'Transferência bancária'), ('cash', 'Dinheiro'), ('check', 'Check')],
                                      'Método de Pagamento', default='check')
    bank_bank = fields.Many2one('res.bank', string='Banco', help='Selecione o banco do funcionário')
    bank_account = fields.Char('Número de Conta', size=100, help="Inserir aqui o número de conta do funcionário")
    bank_iban_account = fields.Char('IBAN', size=100, help="Inserir aqui o IBAN de conta do funcionário")
    bank_nib_account = fields.Char('NIB', size=100, help="Inserir aqui o NIB de conta do funcionário")
    is_foreign = fields.Boolean('Is Foreign',
                                help='Se este funcionário for estrangeiro, marque esta caixa. O empregado estrangeiro está sujeito a regras diferentes na folha de pagamento.')
    contract_type = fields.Many2one('hr.contract.type', string='Tipo de Funcionário')
    sector_id = fields.Many2one('hr.sector', string='Sector')
    hierarchical_level_id = fields.Many2one('hr.hierarchical.level', string='Nível hierárquico')
    hr_job = fields.Many2one('hr.job', string='Função/Cargo')
    first_job = fields.Boolean('Primeiro Trabalho?', default=True)
    employee_situation = fields.Selection(
        [('active', 'Activo'), ('fired', 'Demitido'), ('termination', 'Rescisão'),
         ('unpaid_leave', 'Ausência não remunerada'),
         ('maternity_leave', 'Licença de maternidade'), ('pre_maternity_leave', 'Licença Pré-Maternidade'),
         ('service_commission', 'Comissão de Serviço')], 'Situação', default='active', tracking=True)
    job_title = fields.Char(compute='compute_job_title', tracking=True)
    salary_scale_id = fields.Many2one('hr.salary.scale', string='Escala Salarial')
    steps_ids = fields.Many2one('hr.salary.scale.steps', string='Nível')
    dependents_ids = fields.One2many('hr.employee.dependents', 'employee_id', string='Dependentes')
    children = fields.Integer(compute='_compute_children_number')
    holiday_pay_date = fields.Date(string='Data do pagamento das férias',
                                   help='Save the employee"s salary payment date and vacation bonus in a calendar year')
    hour_salary = fields.Float(digits=(10, 2), string='Salário Hora', default=0)
    direction_id = fields.Many2one(related="department_id.direction_id", store=True, compute_sudo=True, help="Direcção",
                                   tracking=True)
    employee_type = fields.Selection(selection_add=[('service_provider', 'Prestador de Serviço'), ('student',)],
                                     ondelete={"service_provider": "set default"}, tracking=True)
    service_provider_wage = fields.Float(digits=(10, 2), string='Salário', default=0, tracking=True)
    currency_type = fields.Selection([('USD', 'USD'), ('EURO', 'EURO'), ('KWANZA', 'KWANZA')],
                                     'Moeda', default='KWANZA')
    departure_raison = fields.Char('Motivo de Saída', tracking=True)
    type_of_agreement = fields.Selection(
        [('mutual_agreement', 'Mutuo Acordo'),
         ('work_request', 'A Pedido do Trabalhador'), ('just_cause_dis', 'Justa Causa (Disciplinar)'),
         ('just_cause_ob_c', 'Justa Causa (Causas Objectivas)'), ('resignation', 'Demissão'),
         ('work_abandonment', 'Abandono de Trabalho')], string='Tipo de Acordo', tracking=True)
    departure_reason_description = fields.Html('Detalhes de Saída', tracking=True)
    identification_emission_date = fields.Date(string='Data de Emissão', tracking=True)
    identification_expiration_date = fields.Date(string='Data de Validade', tracking=True)
    certificate = fields.Selection(
        selection_add=[('bacharelato', 'Bacharelato'), ('frequencia_universitaria', 'Frequência Universitária'),
                       ('pos_graduado', 'Pós Graduado'),
                       ('graduate',)], tracking=True)

    def write(self, vals):
        if self.env.company.country_id.code == "AO":
            if 'active' not in vals or vals['active'] != False:
                pass
            else:
                vals['last_work_date'] = fields.Date.today()
        return super(HREmployee, self).write(vals)

    @api.onchange('steps_ids')
    def on_change_employee_id(self):
        for record in self:
            if self.env.company.country_id.code == "AO":
                if record.steps_ids:
                    salary_hour = record.get_mount_hour_salary_employee(record)
                    if 'hourly_cost' in record._fields:
                        record.hourly_cost = salary_hour
                    record.hour_salary = salary_hour
                else:
                    if 'hourly_cost' in record._fields:
                        record.hourly_cost = 0

    @api.onchange('payment_method')
    def on_change_payment_method(self):
        for record in self:
            if self.env.company.country_id.code == "AO":
                if record.payment_method != 'bank':
                    record.write(
                        {'bank_bank': False, 'bank_account': False, 'bank_iban_account': False,
                         'bank_nib_account': False})

    def get_mount_hour_salary_employee(self, record):
        venc = abs(record.steps_ids.amount_in_kwanza)
        salary_hour = round((venc * 12) / (52 * record.resource_calendar_id.hours_per_week), 2)
        return salary_hour

    def _compute_children_number(self):
        for employee in self:
            employee.children = len(employee.dependents_ids.filtered(
                lambda r: r.degree_of_kinship == self.env.company.type_of_dependents and r.has_document))

    @api.depends('hr_job')
    def compute_job_title(self):
        if self.hr_job:
            self.job_title = self.hr_job.name
            self.job_id = self.hr_job.id
        else:
            self.job_title = ""
            self.job_id = False

    def calculate_family_allowance(self, dependents, contract_wage):

        family_allowance = 0
        # VERIFICAR SE O NUMERO DE DEPENDENTES É IGUAL AO QUE FOI ESTABELECIDO NO TIPO DE EMPRESA SE NÃO PEGAR APENAS O LIMITE ESTABELEICI
        number_dependents = len(dependents)
        dependents_limit = self.env.company.dependent_limit
        if number_dependents > dependents_limit:
            number_limit = dependents_limit
        else:
            number_limit = number_dependents

        # CALCULAR O VALOR A RECEBER DE ACORDO AO LIMITE DE DEPENDENTES E O SALARIO DO FUNCIONÁRIO
        venc = abs(contract_wage)
        national_minimum_wage = self.env.company.national_minimum_wage
        national_minimum_wage_5 = national_minimum_wage * 5
        national_minimum_wage_10 = national_minimum_wage * 10
        first_allowance_amount = {1: _(800), 2: _(1600), 3: _(2400), 4: _(3200), 5: _(4000)}
        second_allowance_amount = {1: _(500), 2: _(1000), 3: _(1500), 4: _(2000), 5: _(2000)}
        tree_allowance_amount = {1: _(300), 2: _(600), 3: _(900), 4: _(1200), 5: _(1500)}
        # REMUNERAÇÃO ATÉ 5 SALARIOS MINIMO NACIONAL
        if venc <= national_minimum_wage_5:
            family_allowance = first_allowance_amount[number_limit]
        # REMUNERAÇÃO > 5 < 10 SALARIOS MINIMOS NACIONAL
        elif national_minimum_wage_5 < venc < national_minimum_wage_10:
            family_allowance = second_allowance_amount[number_limit]
        # REMUNERAÇÃO > 10 SALARIOS MINIMOS NACIONAL
        elif venc > national_minimum_wage_10:
            family_allowance = tree_allowance_amount[number_limit]

        return family_allowance

    def validate_employee_admission_date(self, date_from):
        # Data de admissão do funcionário
        current_date = date_from
        admission_date = self.first_contract_date
        if not admission_date:
            return False

        # verificar o dia do mes de início do contrato se for maior que o dia 1, então conta mes seguinte do contrato
        if admission_date.day > 1:
            contract_month = admission_date.month + 1
        else:
            contract_month = admission_date.month

        if admission_date.year == current_date.year:
            complete_months = 12 - contract_month + 1
        else:
            complete_months = (12 - contract_month) + 12  # Até o final do ano

        return min(complete_months, 12)


class HrEmployeePublic(models.Model):
    _inherit = "hr.employee.public"

    employee_number = fields.Char(related="employee_id.registration_number", help="Insert here the Employee Number",
                                  compute_sudo=True)
    social_security = fields.Char('Security Number', related='employee_id.social_security', compute_sudo=True)
    fiscal_number = fields.Char('Fiscal Number', related='employee_id.fiscal_number', compute_sudo=True)
    admission_date = fields.Date('Admission Date', related='employee_id.admission_date', compute_sudo=True)
    last_work_date = fields.Date('Last Work Day', related='employee_id.last_work_date', compute_sudo=True)
    address_province = fields.Selection(related='employee_id.address_province', compute_sudo=True)
    address_county = fields.Char('County', related='employee_id.address_county', compute_sudo=True)
    address_address = fields.Char('Address', related='employee_id.address_address', compute_sudo=True)
    personal_mobile = fields.Char('Personal Mobile', related='employee_id.personal_mobile', compute_sudo=True)
    personal_email = fields.Char('Personal Email', related='employee_id.personal_email', compute_sudo=True)
    payment_method = fields.Selection(related='employee_id.payment_method', compute_sudo=True)
    bank_bank = fields.Many2one(related='employee_id.bank_bank', compute_sudo=True)
    bank_account = fields.Char('Bank Account', related='employee_id.bank_account', compute_sudo=True)
    bank_iban_account = fields.Char('IBAN', related='employee_id.bank_iban_account', compute_sudo=True)
    bank_nib_account = fields.Char('NIB', related='employee_id.bank_nib_account', compute_sudo=True)
    is_foreign = fields.Boolean('Is Foreign', related='employee_id.is_foreign', compute_sudo=True)
    contract_type = fields.Many2one(related='employee_id.contract_type', compute_sudo=True)
    sector_id = fields.Many2one(related='employee_id.sector_id', compute_sudo=True)
    hierarchical_level_id = fields.Many2one(related='employee_id.hierarchical_level_id', compute_sudo=True)
    hr_job = fields.Many2one(related='employee_id.hr_job', compute_sudo=True)
    first_job = fields.Boolean(related='employee_id.first_job', compute_sudo=True)
    employee_situation = fields.Selection(related='employee_id.employee_situation', compute_sudo=True)
    job_title = fields.Char(related='employee_id.job_title', compute_sudo=True)
    salary_scale_id = fields.Many2one(related='employee_id.salary_scale_id', compute_sudo=True)
    steps_ids = fields.Many2one(related='employee_id.steps_ids', compute_sudo=True)
    dependents_ids = fields.One2many(related='employee_id.dependents_ids', compute_sudo=True)
    children = fields.Integer(related='employee_id.children', compute_sudo=True)
    holiday_pay_date = fields.Date(related='employee_id.holiday_pay_date', compute_sudo=True)
    hour_salary = fields.Float(related='employee_id.hour_salary', compute_sudo=True)
    direction_id = fields.Many2one(related="employee_id.direction_id", compute_sudo=True)
    employee_type = fields.Selection(related='employee_id.employee_type', compute_sudo=True)
    service_provider_wage = fields.Float(related='employee_id.service_provider_wage', compute_sudo=True)
    departure_raison = fields.Char(related='employee_id.departure_raison', compute_sudo=True)
    type_of_agreement = fields.Selection(related='employee_id.type_of_agreement', compute_sudo=True)
    departure_reason_description = fields.Html(related='employee_id.departure_reason_description', compute_sudo=True)
    identification_emission_date = fields.Date(related='employee_id.identification_emission_date', compute_sudo=True)
    identification_expiration_date = fields.Date(related='employee_id.identification_emission_date', compute_sudo=True)
