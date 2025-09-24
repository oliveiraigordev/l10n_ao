from odoo import fields, models, api, _
from odoo.exceptions import UserError, ValidationError

class AccountPaymentSalary(models.Model):
    _name = 'account.payment.salary'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = "Salary Payment Angola"

    name            = fields.Char(string="Name", required=False)
    ref             = fields.Char(string="Reference")
    communication   = fields.Char(string="Description")
    date            = fields.Date(string="Date", default=fields.Date.today)
    journal_id      = fields.Many2one('account.journal', string='Journal', required=True)
    currency_id     = fields.Many2one('res.currency', default=lambda s: s.env.company.currency_id)
    company_id      = fields.Many2one('res.company', default=lambda s: s.env.company)

    hr_payment      = fields.Many2one('hr.payment', string='Salary Payment Order', required=True)
    amount_paid     = fields.Float(string="Total Bruto (Remunerações)",compute='_compute_totals',store=True,readonly=True,)
    total_deductions = fields.Float(string="Total Descontos",compute='_compute_totals',store=True,readonly=True,)

    amount          = fields.Monetary(string='Amount to Pay', required=True)
    slip_amount     = fields.Monetary(string='Salary Total', compute="_compute_slip_amount", store=False)
    hr_irt_amount   = fields.Monetary(string='IRT Total',    compute="_compute_irt_amount", store=True)
    hr_ss_amount    = fields.Monetary(string='SS Total',     compute="_compute_irt_amount", store=True)
    hr_ss_amount8   = fields.Monetary(string='SS 8% Total', compute="_compute_irt_amount", store=True)

    payslip_run_id = fields.Many2one('hr.payslip.run', string="Lote de Salário")

    show_details = fields.Boolean(
        string='Mostrar Detalhes',
        help='Marque para exibir campos adicionais nas linhas de pagamento.'
    )
    include_foreing_employee = fields.Boolean(
        string='Mostrar Detalhes',
        help='Marque para exibir campos adicionais nas linhas de pagamento.'
    )

    partial_paid_total = fields.Monetary(
        string="Total Pago Parcial",
        compute='_compute_partial_paid_total',
        store=True,
    )
    remaining_amount = fields.Monetary(
        string="Restante a Pagar",
        compute='_compute_remaining_amount',
        store=True,
    )

    counter_currency_id = fields.Many2one(
        'res.currency',
        string="Counter Currency",
        help="Escolha a moeda para ver o contra-valor deste pagamento.",
    )
    # 2) Taxa de câmbio: quantos AOA = 1 Counter Currency
    exchange_rate = fields.Float(
        string="Taxa de Câmbio",
        help="Quantos da moeda da empresa (AOA) equivalem a 1 unidade da Counter Currency.",
    )

    amount_counter = fields.Monetary(
        string="Contra-valor",
        help="Valor total convertido para a moeda selecionada.",
        compute='_compute_amount_counter',
        store=True,
        currency_field='counter_currency_id',
    )

    lines           = fields.One2many('account.payment.hr', 'salary_payment', string='Payment Line')
    payment_split   = fields.Selection([('automated', 'Automatic'), ('manual', 'Manual')], string="Division", default="automated")
    state           = fields.Selection([('draft','Draft'), ('posted','Posted')], default='draft')
    payment_type    = fields.Selection([('outbound','Out'),('inbound','In')], default='outbound')
    payment_method  = fields.Selection([('transfer','Transfer'),('deposit','Deposit'),('cash','Cash')],
                                       default='transfer')
    partner_type    = fields.Selection([('employee','Employee'),('customer','Customer'),('supplier','Vendor')],default='employee')
    move_id         = fields.Many2one('account.move', string="Move")
    pay_tax         = fields.Boolean(string="Incluir Impostos", default=True)


    pay_irt = fields.Boolean(string="Pagar IRT", default=True)
    pay_ss = fields.Boolean(string="Pagar INSS", default=True)
    pay_ss8 = fields.Boolean(string="Pagar INSS 8%", default=True)
    irt_paid = fields.Boolean(string="IRT Pago", default=False)
    ss_paid = fields.Boolean(string="INSS Pago", default=False)
    ss8_paid = fields.Boolean(string="INSS 8%  Pago", default=False)
    tax_paid = fields.Boolean(string="Todos os Impostos Pagos", compute="_compute_tax_paid", store=True)

    tax_move_ids = fields.One2many(
        'account.move',
        'salary_tax_payment_id',
        string="Lançamentos de Impostos",
        readonly=True
    )

    # tax_move_id     = fields.Many2one('account.move', string="Tax Move", readonly=True)
    other_earnings = fields.Monetary(string="Outros Ganhos", compute="_compute_other_amount", store=True)

    # Outros descontos (não INSS/IRT)
    other_deductions = fields.Monetary(string="Outros Descontos", compute="_compute_other_amount", store=True)
    total_gross = fields.Float(string="Total Bruto")

    # para expatriado

    include_expatriates = fields.Boolean(
        string="Incluir Expatriados",
        help="Quando marcado, inclui funcionários expatriados em Kz no lote nacional."
    )
    # payment_exp = fields.Boolean(string="valor em kz do expatriado")

    total_kz = fields.Float(
        string="Total Líquido (Kz)",
        compute='_compute_totals_recept',
        store=True,
        readonly=True,
    )
    total_usd = fields.Float(
        string="Total Conversão (USD)",
        compute='_compute_totals_recept',
        store=True,
        readonly=True,
    )
    rate = fields.Float(
        string="Câmbio",
        compute='_compute_exchange_rate',
        store=True,
        readonly=True,
    )

    counter_currency = fields.Float(
        string="Total Pago em Moeda Estrangeira",
        compute='_compute_amount_counter_full',
        store=False,
        readonly=True,
    )
    expatriate_only = fields.Boolean(
        string="Só Expatriados",
        related='payslip_run_id.is_expatriate_batch',
        store=True,
    )

    @api.depends('hr_payment.lines.payslip_id.total_recept_kz',
                 'hr_payment.lines.payslip_id.total_paid_usd','hr_payment.lines.payslip_id.exchange_rate')
    def _compute_totals_recept(self):
        for rec in self:
            kz = usd = ca = 0.0
            for line in rec.hr_payment.lines:
                slip = line.payslip_id
                if slip:
                    kz += getattr(slip, 'total_recept_kz', 0.0)
                    usd += getattr(slip, 'total_paid_usd', 0.0)
                    ca += getattr(slip, 'exchange_rate',0.0)
            rec.total_kz = kz
            rec.total_usd = usd
            rec.rate = ca

    @api.depends('hr_payment.lines.payslip_id.exchange_rate')
    def _compute_exchange_rate(self):
        for rec in self:
            total_rate = 0.0
            count = 0
            for line in rec.hr_payment_ids:
                rate = line.exchange_rate
                if rate:
                    total_rate += rate
                    count += 1
            rec.exchange_rate = total_rate / count if count else 0.0

    @api.depends('lines.contract_type_id.code')
    def _compute_expat_only(self):
        print("esta funcionando ")
        for rec in self:
            exps = rec.lines.filtered(lambda l: l.contract_type_id and l.contract_type_id.code == 'expatriado')
            rec.expatriate_only = bool(exps) and len(exps) == len(rec.lines)


    ali = fields.Float(string="Subsídio Alimentação (ALI)")
    trans = fields.Float(string="Subsídio Transporte (TRANS)")
    fami = fields.Float(string="Subsídio Familiar (FAMI)")
    renc = fields.Float(string="RENÇ")
    eat = fields.Float(string="EAT")
    comu = fields.Float(string="COMU")
    falha = fields.Float(string="FALHA")
    bon = fields.Float(string="BON")
    r92 = fields.Float(string="R92")
    atra = fields.Float(string="ATRA")
    famexc = fields.Float(string="FAMEXC")
    comission = fields.Float(string="COMISSION")
    chef = fields.Float(string="CHEF")
    cfng = fields.Float(string="CFNG")
    thirteen = fields.Float(string="13º")
    fjr = fields.Float(string="FJR")
    fi = fields.Float(string="FI")
    r75 = fields.Float(string="R75")
    gozo_ferias = fields.Float(string="Gozo Férias")
    ata = fields.Float(string="ATA")
    adi = fields.Float(string="ADI")
    hextra_50 = fields.Float(string="H.Extra 50%")
    hextra_75 = fields.Float(string="H.Extra 75%")
    adi_alimentacao = fields.Float(string="Adi Alimentação")
    isen_hora = fields.Float(string="Insenção de Horário")
    partial_move_ids = fields.One2many(
        'account.move', 'partial_payment_salary_id',
        string='Pagamentos Parciais Registrados'
    )

    penalty_move_ids = fields.One2many(
        'account.move', 'salary_penalty_id',
        string='Lançamentos de Multas/Juros', readonly=True)
    penalty_count = fields.Integer(
        string='Qtd. Multas/Juros',
        compute='_compute_penalty_count')
    total_penalties = fields.Monetary(
        string='Total Multas/Juros',
        compute='_compute_total_penalties',
        currency_field='currency_id')

    # @api.depends('penalty_move_ids', 'penalty_move_ids.line_ids.debit')
    # def _compute_total_penalties(self):
    #     for rec in self:
    #         # soma o débito apenas das linhas de multa/juros (código 76...)
    #         rec.total_penalties = sum(
    #             rec.penalty_move_ids.mapped('line_ids')
    #             .filtered(lambda l: l.account_id.code.startswith('76'))
    #             .mapped('debit')
    #         )


    @api.depends('penalty_move_ids.line_ids.debit')
    def _compute_total_penalties(self):
        for rec in self:
            lines = rec.penalty_move_ids.mapped('line_ids') \
                .filtered(lambda l: l.debit > 0)
            rec.total_penalties = sum(lines.mapped('debit'))

    @api.depends('penalty_move_ids')
    def _compute_penalty_count(self):
        for rec in self:
            rec.penalty_count = len(rec.penalty_move_ids)

    # Abre o wizard para criar multa/juros
    def action_open_penalty_wizard(self):
        self.ensure_one()
        journal = self.journal_id or self.env['account.journal'].search(
            [('type', 'in', ('bank', 'cash')), ('company_id', '=', self.company_id.id)],
            limit=1
        )
        return {
            'type': 'ir.actions.act_window',
            'name': _('Registrar Multas/Juros'),
            'res_model': 'salary.penalty.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_salary_payment_id': self.id,
                'default_journal_id': journal.id if journal else False,
                'default_company_id': self.company_id.id,
            },
        }

    # Abre a lista de account.move já criados
    def action_view_penalties(self):
        self.ensure_one()
        return {
            'name': _('Lançamentos de Multas/Juros'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'tree,form',
            'domain': [('salary_penalty_id', '=', self.id)],
            'context': {
                'create': False,
                'default_company_id': self.company_id.id,
            },
        }

    @api.depends('lines')
    def _compute_other_amount(self):
        for rec in self:
            rec.hr_irt_amount = sum(line.irt_amount for line in rec.lines)
            rec.hr_ss_amount = sum(line.ss_amount for line in rec.lines)
            rec.amount = sum(line.amount for line in rec.lines)

            total_slip = 0.0
            outros_ganhos = 0.0
            outros_descontos = 0.0

            for line in rec.lines:
                slip = line.payslip_id
                if not slip:
                    continue

                for l in slip.line_ids:
                    cat_code = l.salary_rule_id.category_id.code
                    total_slip += l.total

                    if cat_code not in ['INSS', 'IRT', 'Básico']:
                        if l.total > 0:
                            outros_ganhos += l.total
                        elif l.total < 0:
                            outros_descontos += abs(l.total)

            # rec.slip_amount = total_slip
            rec.other_earnings = outros_ganhos
            rec.other_deductions = outros_descontos


    @api.depends('lines.slip_amount')
    def _compute_total_slip_lines(self):
        for rec in self:
            rec.total_slip_lines = sum(rec.lines.mapped('slip_amount'))

    @api.depends('lines.slip_amount')
    def _compute_slip_amount(self):
        for rec in self:
            rec.slip_amount = sum(rec.lines.mapped('slip_amount') or [0.0])


    # @api.depends('hr_payment.lines', 'pay_irt', 'pay_ss', 'hr_payment.payslip_id')
    # def _compute_irt_amount(self):
    #     for rec in self:
    #         rec.hr_irt_amount = 0.0
    #         rec.hr_ss_amount = 0.0
    #
    #         if rec.hr_payment.lines:
    #             rec.hr_irt_amount = sum(l.irt_amount for l in rec.hr_payment.lines) if rec.pay_irt else 0.0
    #             rec.hr_ss_amount = sum(l.ss_amount for l in rec.hr_payment.lines) if rec.pay_ss else 0.0
    #         elif rec.hr_payment.payslip_id:
    #             slip = rec.hr_payment.payslip_id
    #             rec.hr_irt_amount = getattr(slip, 'amount_irt', 0.0) if rec.pay_irt else 0.0
    #             rec.hr_ss_amount = getattr(slip, 'amount_ss', 0.0) if rec.pay_ss else 0.0

    @api.depends('hr_payment.lines', 'pay_irt', 'pay_ss', 'pay_ss8', 'hr_payment.payslip_id')
    def _compute_irt_amount(self):
        for rec in self:
            rec.hr_irt_amount = 0.0
            rec.hr_ss_amount = 0.0
            rec.hr_ss_amount8 = 0.0

            if rec.hr_payment.lines:
                rec.hr_irt_amount = sum(l.irt_amount for l in rec.hr_payment.lines) if rec.pay_irt else 0.0
                rec.hr_ss_amount = sum(l.ss_amount for l in rec.hr_payment.lines) if rec.pay_ss else 0.0
                rec.hr_ss_amount8 = sum(l.ss8_amount for l in rec.hr_payment.lines) if rec.pay_ss8 else 0.0
            elif rec.hr_payment.payslip_id:
                slip = rec.hr_payment.payslip_id
                rec.hr_irt_amount = getattr(slip, 'amount_irt', 0.0) if rec.pay_irt else 0.0
                rec.hr_ss_amount = getattr(slip, 'amount_ss', 0.0) if rec.pay_ss else 0.0
                rec.hr_ss_amount8 = getattr(slip, 'amount_ss8', 0.0) if rec.pay_ss8 else 0.0
                rec.hr_ss_amount8 = getattr(slip, 'amount_ss8', 0.0) if rec.pay_ss8 else 0.0

    @api.depends('irt_paid', 'ss_paid', 'ss8_paid')
    def _compute_tax_paid(self):
        for rec in self:
            rec.tax_paid = rec.irt_paid and rec.ss_paid and rec.ss8_paid

    def toggle_pay_tax(self):
        for rec in self:
            rec.pay_tax = not rec.pay_tax

    @api.depends(
        'hr_payment.payslip_id.total_remunerations',
        'hr_payment.payslip_id.total_deductions',
        'hr_payment.lines.payslip_id.total_remunerations',
        'hr_payment.lines.irt_amount',
        'hr_payment.lines.ss_amount',
    )
    def _compute_totals(self):
        for rec in self:
            gross = 0.0
            ded = 0.0
            # individual
            if rec.hr_payment.payslip_id:
                gross = rec.hr_payment.payslip_id.total_remunerations or 0.0
                ded = rec.hr_payment.payslip_id.total_deductions or 0.0
            # batch
            elif rec.hr_payment.lines:
                for line in rec.hr_payment.lines:
                    if line.payslip_id:
                        gross += line.payslip_id.total_remunerations or 0.0
                    ded += (line.irt_amount or 0.0) + (line.ss_amount or 0.0)
            rec.amount_paid = gross
            rec.total_deductions = ded
            rec.total_gross = gross

    #O valor Remanescente
    @api.depends('partial_move_ids.line_ids.credit')
    def _compute_partial_paid_total(self):
        for rec in self:
            # soma todos os créditos das linhas dos movimentos parciais
            lines = rec.partial_move_ids.mapped('line_ids')
            rec.partial_paid_total = sum(lines.mapped('credit'))

    @api.depends('slip_amount', 'partial_paid_total')
    def _compute_remaining_amount(self):
        for rec in self:
            rec.remaining_amount = rec.slip_amount - rec.partial_paid_total

    @api.onchange('hr_payment')
    def _onchange_hr_payment(self):
        lines = [(5, 0, 0)]
        # Se batch
        if self.hr_payment.lines:
            for l in self.hr_payment.lines:
                lines.append((0, 0, {
                    'employee_id': l.employee_id.id,
                    'amount': l.amount,
                    'irt_amount': l.irt_amount,
                    'ss_amount': l.ss_amount,
                    'ss8_amount': l.ss8_amount,
                    'payslip_id': l.payslip_id.id,
                }))
        # Se individual
        elif self.hr_payment.payslip_id:
            slip = self.hr_payment.payslip_id
            lines.append((0, 0, {
                'employee_id': slip.employee_id.id,
                'amount': slip.total_paid,
                'irt_amount': getattr(slip, 'amount_irt', 0.0),
                'ss_amount': getattr(slip, 'amount_ss', 0.0),
                'ss8_amount': getattr(slip, 'amount_ss8', 0.0),
                'payslip_id': slip.id,
            }))
        self.lines = lines

    def hr_payment_post(self):
        for rec in self:
            # Validar diário
            if rec.journal_id.type not in ['bank','cash']:
                raise ValidationError(_("Diário deve ser tipo Banco ou Numerário"))
            # Validar valor
            # if rec.amount > rec.slip_amount:
            #     raise ValidationError(_("Pagamento não pode exceder total da folha"))
            if rec.payment_split == 'automated':
                if rec.amount == rec.slip_amount:
                    for ln in rec.lines:
                        ln.amount_paid = ln.amount
                else:
                    rate = rec.amount / rec.slip_amount
                    for ln in rec.lines:
                        ln.amount_paid = ln.amount * rate
            else:
                pass

            # Marca hr_payment como pago
            rec.hr_payment.amount_paid = rec.amount
            rec.hr_payment.state = 'paid'
            # Se for batch
            if rec.hr_payment.payslip_run_id:
                rec.hr_payment.payslip_run_id.payment_state = 'paid'
            # Se individual
            if rec.hr_payment.payslip_id:
                rec.hr_payment.payslip_id.payment_state = 'paid'

            # Cria e posta o journal entry
            move = self.env['account.move'].create(rec._prepare_account_move())
            move._post()
            rec.move_id = move.id
            rec.state   = 'posted'

    # Lançamento dos Impostos

    def action_pay_tax(self):
        for res in self:
            move_lines = []
            amt_irt = float(res.hr_irt_amount or 0.0)
            amt_ss = float(res.hr_ss_amount or 0.0)
            amt_ss8 = float(res.hr_ss_amount8 or 0.0)

            if not any([
                res.pay_irt and amt_irt > 0,
                res.pay_ss and amt_ss > 0,
                res.pay_ss8 and amt_ss8 > 0,
            ]):
                raise ValidationError(_("Selecione pelo menos um imposto (IRT, INSS ou INSS 8%) com valor maior de  0."))

            if res.pay_irt and res.irt_paid:
                raise ValidationError(_("O IRT já foi pago."))
            if res.pay_ss and res.ss_paid:
                raise ValidationError(_("O INSS já foi pago."))
            if res.pay_ss8 and res.ss8_paid:
                raise ValidationError(_("O INSS 8% já foi pago."))

            pending_account = (
                res.journal_id.outbound_payment_method_line_ids
                .mapped('payment_account_id')
                .filtered(lambda acc: acc)[:1]
            )
            if pending_account:
                account_journal = pending_account.id
            elif res.journal_id.default_account_id:
                account_journal = res.journal_id.default_account_id.id
            else:
                account_journal = self._check_account('43101001', res.company_id).id

            irt_rule = self.env['hr.salary.rule'].search([('category_id.code', '=', 'IRT')], limit=1)
            account_irt = irt_rule.account_credit.id if irt_rule and irt_rule.account_credit else self._check_account(
                '3431', res.company_id).id

            inss_rule = self.env['hr.salary.rule'].search([('category_id.code', '=', 'INSS')], limit=1)
            account_inss = inss_rule.account_credit.id if inss_rule and inss_rule.account_credit else self._check_account(
                '34951', res.company_id).id

            inss8_rule = self.env['hr.salary.rule'].search([('category_id.code', '=', 'INSS8')], limit=1)
            account_inss8 = inss8_rule.account_credit.id if inss8_rule and inss8_rule.account_credit else self._check_account(
                '34951', res.company_id).id

            if res.pay_irt and not res.irt_paid and res.hr_irt_amount > 0:
                move_lines += [
                    (0, 0, {'name': 'Pagamento de IRT', 'account_id': account_journal, 'journal_id': res.journal_id.id,
                            'date': res.date, 'debit': 0.0, 'credit': res.hr_irt_amount}),
                    (0, 0, {'name': 'Liquidação de IRT', 'account_id': account_irt, 'journal_id': res.journal_id.id,
                            'date': res.date, 'debit': res.hr_irt_amount, 'credit': 0.0}),
                ]
                res.irt_paid = True

            if res.pay_ss and not res.ss_paid and res.hr_ss_amount > 0:
                move_lines += [
                    (0, 0, {'name': 'Pagamento de INSS', 'account_id': account_journal, 'journal_id': res.journal_id.id,
                            'date': res.date, 'debit': 0.0, 'credit': res.hr_ss_amount}),
                    (0, 0, {'name': 'Liquidação de INSS', 'account_id': account_inss, 'journal_id': res.journal_id.id,
                            'date': res.date, 'debit': res.hr_ss_amount, 'credit': 0.0}),
                ]
                res.ss_paid = True

            if res.pay_ss8 and not res.ss8_paid and res.hr_ss_amount8 > 0:
                move_lines += [
                    (0, 0, {'name': 'Pagamento de INSS 8% ', 'account_id': account_journal, 'journal_id': res.journal_id.id,
                            'date': res.date, 'debit': 0.0, 'credit': res.hr_ss_amount8}),
                    (0, 0, {'name': 'Liquidação de INSS 8%', 'account_id': account_inss8, 'journal_id': res.journal_id.id,
                            'date': res.date, 'debit': res.hr_ss_amount8, 'credit': 0.0}),
                ]
                res.ss8_paid = True

            if not move_lines:
                raise ValidationError(_("Nenhuma linha contábil foi gerada. Ative IRT ou INSS para continuar."))

            move_vals = {
                'move_type': 'entry',
                'journal_id': res.journal_id.id,
                'date': res.date,
                'ref': f'Lançamento de Pagamento de Impostos - {res.name}',
                'line_ids': move_lines,
            }
            move = self.env['account.move'].with_context(default_payment_id=False).create(move_vals)
            move._post()
            move.salary_tax_payment_id = res.id


    def _prepare_account_move(self):
        self.ensure_one()
        lines = self._prepare_move_lines()
        if not lines:
            raise ValidationError(_("Nenhuma linha contábil gerada"))
        return {
            'ref':        self.ref or self.name,
            'date':       self.date,
            'journal_id': self.journal_id.id,
            'narration':  self.communication or self.name,
            'line_ids':   lines,
        }


    def _prepare_move_lines(self):
        self.ensure_one()
        # bruto = self.amount + (self.hr_irt_amount + self.hr_ss_amount if self.pay_tax else 0.0)
        # bruto = self.amount_paid
        # liquido = self.amount
        liquido = self.slip_amount
        lines = []
        # As Contas
        # 1) Conta de IRT (débito)
        irt_rule = self.env['hr.salary.rule'].search(
            [('category_id.code', '=', 'IRT')], limit=1
        )
        account_irt = (
            irt_rule.account_credit.id
            if irt_rule and irt_rule.account_credit
            else self._check_account('3431', self.company_id).id
        )
        # Conta de INSS (débito)
        inss_rule = self.env['hr.salary.rule'].search(
            [('category_id.code', '=', 'INSS')], limit=1
        )
        account_inss8 = (
            inss_rule.account_credit.id
            if inss_rule and inss_rule.account_credit
            else self._check_account('34951', self.company_id).id
        )

        # Conta de INSS (débito)
        inss8_rule = self.env['hr.salary.rule'].search(
            [('category_id.code', '=', 'INSS8')], limit=1
        )
        account_inss = (
            inss8_rule.account_credit.id
            if inss8_rule and inss8_rule.account_credit
            else self._check_account('34951', self.company_id).id
        )
        #  Conta do líquido  (débito)
        inss_rule = self.env['hr.salary.rule'].search(
            [('category_id.code', '=', 'Básico')], limit=1
        )
        account_base = (
            inss_rule.account_credit.id
            if inss_rule and inss_rule.account_credit
            else self._check_account('36211', self.company_id).id
        )


        #  Contas de Subsídios — para cada código de subsídio, tenta a regra salarial,
        #    senão usa o código de conta padrão indicado no seu dict de subsidios_contas
        subsidiary_accounts = {}
        subsidios_contas = {
            'ali': '3791',
            'trans': '3792',
            'fami': '3791',
            'renc': '3791',
            'eat': '3791',
            'comu': '3791',
            'falha': '3791',
            'bon': '3791',
            'r92': '3791',
            'atra': '3791',
            'famexc': '3791',
            'comission': '3791',
            'chef': '3791',
            'cfng': '3791',
            'thirteen': '3791',
            'fjr': '3791',
            'fi': '3791',
            'r75': '3791',
            'gozo_ferias': '3791',
            'ata': '3791',
            'adi': '3791',
            'hextra_50': '3791',
            'hextra_75': '3791',
            'adi_alimentacao': '3791',
            'isen_hora': '3791',
        }

        for code, fallback_acc in subsidios_contas.items():
            rule = self.env['hr.salary.rule'].search([('code', '=', code.upper())], limit=1)
            subsidiary_accounts[code] = (
                rule.account_debit.id
                if rule and rule.account_debit
                else self._check_account(fallback_acc, self.company_id).id
            )

        # Créditos de impostos
        if self.pay_tax and self.hr_irt_amount:
            # acct_irt = self._check_account('3431', self.company_id)
            lines.append((0, 0, {
                'name': 'IRT a Pagar',
                'account_id': account_irt,
                'debit': self.hr_irt_amount,
                'credit': 0.0,
            }))
        if self.pay_tax and self.hr_ss_amount:
            # acct_ss = self._check_account('34951', self.company_id)
            lines.append((0, 0, {
                'name': 'INSS a Pagar',
                'account_id': account_inss,
                'debit': self.hr_ss_amount,
                'credit': 0.0,
            }))

        if self.pay_tax and self.hr_ss_amount8:
            # acct_ss = self._check_account('34951', self.company_id)
            lines.append((0, 0, {
                'name': 'INSS 8% a Pagar',
                'account_id': account_inss8,
                'debit': self.hr_ss_amount8,
                'credit': 0.0,
            }))

        # Crédito: salário líquido
        # acct_liq = self._check_account('36211', self.company_id)
        lines.append((0, 0, {
            'name': 'Salário Líquido',
            'account_id': account_base,
            'debit': liquido,
            'credit': 0.0,
        }))

        # Subsídios com contas específicas
        subsidios_contas = {
            'ali': ('Subsídio de Alimentação', '3791'),
            'trans': ('Subsídio de Transporte', '3792'),
            'fami': ('Subsídio Familiar', '3791'),
            'renc': ('RENÇ', '3791'),
            'eat': ('EAT', '3791'),
            'comu': ('COMU', '3791'),
            'falha': ('FALHA', '3791'),
            'bon': ('Bónus', '3791'),
            'r92': ('R92', '3791'),
            'atra': ('Atrasos', '3791'),
            'famexc': ('Excesso Abono de Família', '3791'),
            'comission': ('Comissões', '3791'),
            'chef': ('Subsídio de Chefia', '3791'),
            'cfng': ('Compensação Férias Não Gozadas', '3791'),
            'thirteen': ('13º Salário', '3791'),
            'fjr': ('Falta Justificada Remunerada', '3791'),
            'fi': ('Falta Injustificada', '3791'),
            'r75': ('Adiantamento Ajuda Custo R75', '3791'),
            'gozo_ferias': ('Gozo de Férias', '3791'),
            'ata': ('Subsídio Atavio', '3791'),
            'adi': ('Adiantamento Salarial', '3791'),
            'hextra_50': ('Horas Extra 50%', '3791'),
            'hextra_75': ('Horas Extra 75%', '3791'),
            'adi_alimentacao': ('Adiantamento Alimentação', '3791'),
            'isen_hora': ('Insenção de Horário', '3791'),
        }

        # for field_name, (descricao, fallback_code) in subsidios_contas.items():
        #     valor = sum(self.lines.mapped(field_name))
        #     if valor <= 0:
        #         continue
        #
        #     # tenta buscar conta na regra salarial pelo código da regra igual ao nome do campo em maiúsculas
        #     rule = self.env['hr.salary.rule'].search([('code', '=', field_name.upper())], limit=1)
        #     if rule and rule.account_debit:
        #         acct_id = rule.account_debit.id
        #     else:
        #         acct_id = self._check_account(fallback_code, self.company_id).id
        #
        #     lines.append((0, 0, {
        #         'name': descricao,
        #         'account_id': acct_id,
        #         'debit': valor,
        #         'credit': 0.0,
        #     }))

        for field_name, (descricao, fallback_code) in subsidios_contas.items():
            valor = sum(self.lines.mapped(field_name))
            if valor <= 0:
                continue

            rule = self.env['hr.salary.rule'].search([('code', '=', field_name.upper())], limit=1)
            if rule and rule.account_debit:
                acct_id = rule.account_debit.id
                acct_code = rule.account_debit.code
            else:
                acct = self._check_account(fallback_code, self.company_id)
                acct_id = acct.id
                acct_code = acct.code

            # Se a conta começa com '7', ignora este subsídio na linha contábil
            if acct_code.startswith('7'):
                continue

            lines.append((0, 0, {
                'name': descricao,
                'account_id': acct_id,
                'debit': valor,
                'credit': 0.0,
            }))
        total_debit = sum(line_vals['debit'] for _, _, line_vals in lines)

        # if self.journal_id.default_account_id:
        #     debit_account_salary = self.journal_id.default_account_id.id
        #     print("a conta do salrio =======",debit_account_salary)
        # else:
        #     debit_account_salary = self._check_account('7221', self.company_id).id
        pending_account = (
            self.journal_id.outbound_payment_method_line_ids
            .mapped('payment_account_id')
            .filtered(lambda acc: acc)[:1]
        )

        if pending_account:
            debit_account_salary = pending_account.id
        elif self.journal_id.default_account_id:
            debit_account_salary = self.journal_id.default_account_id.id
        else:
            debit_account_salary = self._check_account('7221', self.company_id).id
        lines.insert(0, (0, 0, {
            'name': 'Despesa de Salário',
            'account_id': debit_account_salary,
            'debit': 0.0,
            'credit': total_debit,
        }))

        return lines


    # def _prepare_move_lines(self):
    #     self.ensure_one()
    #
    #     liquido = self.slip_amount
    #     lines = []
    #     #As Contas
    #     # 1) Conta de IRT (débito)
    #     irt_rule = self.env['hr.salary.rule'].search(
    #         [('category_id.code', '=', 'IRT')], limit=1
    #     )
    #     account_irt = (
    #         irt_rule.account_credit.id
    #         if irt_rule and irt_rule.account_credit
    #         else self._check_account('3431', self.company_id).id
    #     )
    #     # 2) Conta de INSS (débito)
    #     inss_rule = self.env['hr.salary.rule'].search(
    #         [('category_id.code', '=', 'INSS')], limit=1
    #     )
    #     account_inss = (
    #         inss_rule.account_credit.id
    #         if inss_rule and inss_rule.account_credit
    #         else self._check_account('34951', self.company_id).id
    #     )
    #     # 3) Conta do líquido  (débito)
    #     inss_rule = self.env['hr.salary.rule'].search(
    #         [('category_id.code', '=', 'Básico')], limit=1
    #     )
    #     account_base = (
    #         inss_rule.account_credit.id
    #         if inss_rule and inss_rule.account_credit
    #         else self._check_account('36211', self.company_id).id
    #     )
    #
    #     # 3) Contas de Subsídios — para cada código de subsídio, tenta a regra salarial,
    #     #    senão usa o código de conta padrão indicado no seu dict de subsidios_contas
    #     subsidiary_accounts = {}
    #     subsidios_contas = {
    #         'ali': '3791',
    #         'trans': '3792',
    #         'fami': '3791',
    #         'renc': '3791',
    #         'eat': '3791',
    #         'comu': '3791',
    #         'falha': '3791',
    #         'bon': '3791',
    #         'r92': '3791',
    #         'atra': '3791',
    #         'famexc': '3791',
    #         'comission': '3791',
    #         'chef': '3791',
    #         'cfng': '3791',
    #         'thirteen': '3791',
    #         'fjr': '3791',
    #         'fi': '3791',
    #         'r75': '3791',
    #         'gozo_ferias': '3791',
    #         'ata': '3791',
    #         'adi': '3791',
    #         'hextra_50': '3791',
    #         'hextra_75': '3791',
    #         'adi_alimentacao': '3791',
    #         'isen_hora': '3791',
    #     }
    #
    #     for code, fallback_acc in subsidios_contas.items():
    #         rule = self.env['hr.salary.rule'].search([('code', '=', code.upper())], limit=1)
    #         subsidiary_accounts[code] = (
    #             rule.account_debit.id
    #             if rule and rule.account_debit
    #             else self._check_account(fallback_acc, self.company_id).id
    #         )
    #
    #     # Créditos de impostos
    #     if self.pay_tax and self.hr_irt_amount:
    #         #acct_irt = self._check_account('3431', self.company_id)
    #         lines.append((0, 0, {
    #             'name': 'IRT a Pagar',
    #             'account_id': account_irt,
    #             'debit': self.hr_irt_amount,
    #             'credit': 0.0,
    #         }))
    #     if self.pay_tax and self.hr_ss_amount:
    #         #acct_ss = self._check_account('34951', self.company_id)
    #         lines.append((0, 0, {
    #             'name': 'INSS a Pagar',
    #             'account_id': account_inss,
    #             'debit': self.hr_ss_amount,
    #             'credit': 0.0,
    #         }))
    #
    #     # Crédito: salário líquido
    #     #acct_liq = self._check_account('36211', self.company_id)
    #     lines.append((0, 0, {
    #         'name': 'Salário Líquido',
    #         'account_id': account_base,
    #         'debit': liquido,
    #         'credit': 0.0,
    #     }))
    #
    #     # Subsídios com contas específicas
    #     subsidios_contas = {
    #         'ali': ('Subsídio de Alimentação', '3791'),
    #         'trans': ('Subsídio de Transporte', '3792'),
    #         'fami': ('Subsídio Familiar', '3791'),
    #         'renc': ('RENÇ', '3791'),
    #         'eat': ('EAT', '3791'),
    #         'comu': ('COMU', '3791'),
    #         'falha': ('FALHA', '3791'),
    #         'bon': ('Bónus', '3791'),
    #         'r92': ('R92', '3791'),
    #         'atra': ('Atrasos', '3791'),
    #         'famexc': ('Excesso Abono de Família', '3791'),
    #         'comission': ('Comissões', '3791'),
    #         'chef': ('Subsídio de Chefia', '3791'),
    #         'cfng': ('Compensação Férias Não Gozadas', '3791'),
    #         'thirteen': ('13º Salário', '3791'),
    #         'fjr': ('Falta Justificada Remunerada', '3791'),
    #         'fi': ('Falta Injustificada', '3791'),
    #         'r75': ('Adiantamento Ajuda Custo R75', '3791'),
    #         'gozo_ferias': ('Gozo de Férias', '3791'),
    #         'ata': ('Subsídio Atavio', '3791'),
    #         'adi': ('Adiantamento Salarial', '3791'),
    #         'hextra_50': ('Horas Extra 50%', '3791'),
    #         'hextra_75': ('Horas Extra 75%', '3791'),
    #         'adi_alimentacao': ('Adiantamento Alimentação', '3791'),
    #         'isen_hora': ('Insenção de Horário', '3791'),
    #     }
    #
    #
    #     for field_name, (descricao, fallback_code) in subsidios_contas.items():
    #         valor = sum(self.lines.mapped(field_name))
    #         if valor <= 0:
    #             continue
    #
    #         rule = self.env['hr.salary.rule'].search([('code', '=', field_name.upper())], limit=1)
    #         if rule and rule.account_debit:
    #             acct_id = rule.account_debit.id
    #             acct_code = rule.account_debit.code
    #         else:
    #             acct = self._check_account(fallback_code, self.company_id)
    #             acct_id = acct.id
    #             acct_code = acct.code
    #
    #         # Se a conta começa com '7', ignora este subsídio na linha contábil
    #         if acct_code.startswith('7'):
    #             continue
    #
    #         lines.append((0, 0, {
    #             'name': descricao,
    #             'account_id': acct_id,
    #             'debit': valor,
    #             'credit': 0.0,
    #         }))
    #     total_debit = sum(line_vals['debit'] for _, _, line_vals in lines)
    #
    #     pending_account = (
    #         self.journal_id.outbound_payment_method_line_ids
    #         .mapped('payment_account_id')
    #         .filtered(lambda acc: acc)[:1]
    #     )
    #
    #     if pending_account:
    #         debit_account_salary = pending_account.id
    #     elif self.journal_id.default_account_id:
    #         debit_account_salary = self.journal_id.default_account_id.id
    #     else:
    #         debit_account_salary = self._check_account('7221', self.company_id).id
    #     lines.insert(0, (0, 0, {
    #         'name': 'Despesa de Salário',
    #         'account_id': debit_account_salary,
    #         'debit': 0.0,
    #         'credit': total_debit,
    #     }))
    #
    #     return lines

    def _check_account(self, code, company):
        acct = self.env['account.account'].search([
            ('code','=',code),
            ('company_id','=',company.id),
        ], limit=1)
        if not acct:
            raise ValidationError(_("Conta %s não encontrada no plano") % code)
        return acct

    def hr_entry_journal_payment(self, res):
        lines = []
        account_move_dict = {
            'narration': res.communication,
            'ref': res.name,
            'journal_id': res.journal_id.id,
            'date': res.date,
        }

        # 1) Escolhe o payslip certo:
        payslip = False
        if res.hr_payment.payslip_id:
            # pagamento individual
            payslip = res.hr_payment.payslip_id
        elif res.hr_payment.payslip_run_id and res.hr_payment.payslip_run_id.slip_ids:
            # pagamento em lote
            payslip = res.hr_payment.payslip_run_id.slip_ids[0]

        if payslip and payslip.struct_id and payslip.struct_id.type_id.name == 'Funcionário':
            lines.extend(self.move_line_salary())
        else:
            pass

        if not lines:
            raise ValidationError(_("É necessário adicionar ao menos uma linha contábil."))

        account_move_dict['line_ids'] = lines
        return account_move_dict

    def employee_salary(self):
        return sum([line.amount for line in self.lines if line.employee_type == 'funcionário'])

    def action_draft(self):
        for rec in self:
            #  Reverte e apaga lançamentos de impostos (como antes)
            for move in rec.tax_move_ids:
                if move.state == 'posted':
                    move.button_draft()
                move.unlink()
            #  Reverte e apaga o lançamento total padrão
            if rec.move_id and rec.move_id.state == 'posted':
                rec.move_id.button_draft()
                rec.move_id.unlink()
            #  Reverte e apaga TODOS os lançamentos parciais
            for partial in rec.partial_move_ids:
                if partial.state == 'posted':
                    partial.button_draft()
                partial.unlink()
            #  Limpa as relações Many2one/One2many
            rec.write({
                'state': 'draft',
                'move_id': False,
                'tax_move_ids': [(5, 0, 0)],
                'partial_move_ids': [(5, 0, 0)],
                'irt_paid': False,
                'ss_paid': False,
                'ss8_paid': False,
                'tax_paid': False,
            })


    # def action_draft(self):
    #     """Versão simplificada - reverte para rascunho"""
    #     for rec in self:
    #         if rec.state not in ['posted', 'partial']:
    #             continue
    #
    #         # Lista todos os moves para deletar
    #         moves_to_delete = []
    #
    #         for move in rec.tax_move_ids:
    #             if move.state == 'posted':
    #                 move.button_draft()
    #             moves_to_delete.append(move)
    #
    #         if rec.move_id:
    #             if rec.move_id.state == 'posted':
    #                 rec.move_id.button_draft()
    #             moves_to_delete.append(rec.move_id)
    #
    #         for move in rec.partial_move_ids:
    #             if move.state == 'posted':
    #                 move.button_draft()
    #             moves_to_delete.append(move)
    #
    #         for move in rec.penalty_move_ids:
    #             if move.state == 'posted':
    #                 move.button_draft()
    #             moves_to_delete.append(move)
    #
    #         # Limpa as referências ANTES de deletar
    #         rec.write({
    #             'move_id': False,
    #             'tax_move_ids': [(5, 0, 0)],
    #             'partial_move_ids': [(5, 0, 0)],
    #             'penalty_move_ids': [(5, 0, 0)],
    #             'state': 'draft',
    #             'irt_paid': False,
    #             'ss_paid': False,
    #             'tax_paid': False,
    #         })
    #
    #         if moves_to_delete:
    #             self.env['account.move'].concat(*moves_to_delete).unlink()



    # def action_draft(self):
    #     for rec in self:
    #         # 1) Reverte e apaga lançamentos de impostos (como antes)
    #         for move in rec.tax_move_ids:
    #             if move.state == 'posted':
    #                 move.button_draft()
    #             move.unlink()
    #         # 2) Reverte e apaga o lançamento total padrão
    #         if rec.move_id and rec.move_id.state == 'posted':
    #             rec.move_id.button_draft()
    #             rec.move_id.unlink()
    #         # 3) Reverte e apaga TODOS os lançamentos parciais
    #         for partial in rec.partial_move_ids:
    #             if partial.state == 'posted':
    #                 partial.button_draft()
    #             partial.unlink()
    #         # 4) Limpa as relações Many2one/One2many
    #         rec.write({
    #             'state': 'draft',
    #             'move_id': False,
    #             'tax_move_ids': [(5, 0, 0)],
    #             'partial_move_ids': [(5, 0, 0)],
    #             'irt_paid': False,
    #             'ss_paid': False,
    #             'tax_paid': False,
    #         })

    def action_open_partial_payment_wizard(self):
        self.ensure_one()
        if self.remaining_amount <= 0 or self.partial_paid_total >= self.slip_amount:
            raise UserError(_("Não é possível registrar pagamento: já foi pago o total da folha."))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Registrar Pagamento'),
            'res_model': 'partial.salary.payment.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_salary_payment_id': self.id,
            }
        }

    def action_open_tax_penalty_wizard(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Pagar Impostos / Multas & Juros'),
            'res_model': 'hr.tax.pay.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'active_id': self.id,  # usado no default_get do wizard
            }
        }

    #******************************************************
    #                  Pagamento para outra moeda
    # ******************************************************

    @api.onchange('counter_currency_id', 'date')
    def _onchange_counter_currency(self):
        """ Sugere uma taxa de câmbio inicial sempre que mudar moeda ou data. """
        for pay in self:
            if not (pay.counter_currency_id and pay.date):
                pay.exchange_rate = 0.0
                continue
            # pega o inverse_rate para sugerir
            rate = pay.counter_currency_id.with_context(date=pay.date).inverse_rate or 0.0
            pay.exchange_rate = rate

    @api.depends('slip_amount', 'exchange_rate', 'counter_currency_id')
    def _compute_amount_counter(self):
        """ Converte slip_amount pela exchange_rate manual. """
        for pay in self:
            pay.amount_counter = 0.0
            if pay.exchange_rate and pay.slip_amount and pay.counter_currency_id:
                # slip_amount está em moeda da empresa (AOA)
                pay.amount_counter = pay.slip_amount / pay.exchange_rate

    def unlink(self):
        """Versão simplificada do unlink"""
        # Coleta hr_payments antes da exclusão
        hr_payments = self.mapped('hr_payment').filtered(lambda x: x.exists())

        # Reverte registros posted para draft primeiro
        posted_records = self.filtered(lambda r: r.state == 'posted')
        if posted_records:
            posted_records.action_draft()

        # Executa unlink normal
        result = super().unlink()

        # Remove hr_payments órfãos
        if hr_payments.exists():
            hr_payments.unlink()

        return result
    # def unlink(self):
    #     hr_payments = self.mapped('hr_payment')
    #     result = super().unlink()
    #     hr_payments.unlink()
    #     return result


class AccountPaymentHr(models.Model):
    _name = 'account.payment.hr'
    _description = 'Hr Payment'

    salary_payment = fields.Many2one(comodel_name="account.payment.salary")
    name = fields.Char(string="Name", required=0)
    employee_type = fields.Char(strin="Employee Type")
    external_id = fields.Integer(string="Ext Id")
    amount = fields.Float(string="Processed Amount")
    # Substitua o amount_paid atual por um related:
    amount_debt = fields.Float(string="Difference", compute='_amount_balance')
    irt_amount = fields.Float(string="IRT Amount")
    ss_amount = fields.Float(string="SS Amount")
    ss8_amount = fields.Float(string="INSS 8% (Patronal)")
    payment_split = fields.Selection([
        ('automated', 'Automatic'), ('manual', 'Manual'),
    ], string="Division", related='salary_payment.payment_split')
    balance = fields.Float(string="Balance", compute='_amount_balance')
    obs = fields.Char(string='obs')
    employee_id = fields.Many2one('hr.employee', string="Employee")
    payslip_id = fields.Many2one('hr.payslip', string="Payslip")
    payslip_batch = fields.Many2one('hr.payslip.run', string="Payslip batch")
    currency_id     = fields.Many2one('res.currency', default=lambda s: s.env.company.currency_id)


    amount_paid = fields.Float(
        string="Total Bruto (Remunerações)",
        related='payslip_id.total_remunerations',
        store=True,
        readonly=True,
    )
    # Novo campo para total de descontos:
    total_deductions = fields.Float(
        string="Total Descontos",
        related='payslip_id.total_deductions',
        store=True,
        readonly=True,
    )
    slip_amount = fields.Float(
        string="Total Líquido",
        related='payslip_id.total_paid',
        store=True,
        readonly=True,
    )
    show_details = fields.Boolean(
        related='salary_payment.show_details',
        string='Mostrar Detalhes',
        store=False,
    )
    other_earnings = fields.Float(string="Outros Ganhos")
    other_deductions = fields.Float(string="Outros Descontos")
    total_gross = fields.Float(string="Total Bruto")
    ali = fields.Float(string="Subsídio Alimentação (ALI)")
    trans = fields.Float(string="Subsídio Transporte (TRANS)")
    fami = fields.Float(string="Subsídio Familiar (FAMI)")
    renc = fields.Float(string="RENÇ")
    eat = fields.Float(string="EAT")
    comu = fields.Float(string="COMU")
    falha = fields.Float(string="FALHA")
    bon = fields.Float(string="BON")
    r92 = fields.Float(string="R92")
    atra = fields.Float(string="ATRA")
    famexc = fields.Float(string="FAMEXC")
    comission = fields.Float(string="COMISSION")
    chef = fields.Float(string="CHEF")
    cfng = fields.Float(string="CFNG")
    thirteen = fields.Float(string="13º")
    fjr = fields.Float(string="FJR")
    fi = fields.Float(string="FI")
    r75 = fields.Float(string="R75")
    gozo_ferias = fields.Float(string="Gozo Férias")
    ata = fields.Float(string="ATA")
    adi = fields.Float(string="ADI")
    hextra_50 = fields.Float(string="H.Extra 50%")
    hextra_75 = fields.Float(string="H.Extra 75%")
    adi_alimentacao = fields.Float(string="Adi Alimentação")
    isen_hora = fields.Float(string="Insenção de Horário")

    #para expatriado

    total_kz = fields.Float(
        string="Total Líquido (Kz)",
        related='payslip_id.total_recept_kz',
        store=True,
        readonly=True,
    )
    total_usd = fields.Float(
        string="Total Líquido (USD)",
        related='payslip_id.total_paid_usd',
        store=True,
        readonly=True,
    )

    contract_type_id = fields.Many2one(
        'hr.contract.type',
        string="Tipo de Contrato",
        related='payslip_id.contract_id.contract_type_id',
        store=True,
        readonly=True,
    )
    exchange_rate = fields.Float(
        string="Câmbio",
        related='payslip_id.exchange_rate_id.name'
    )
    expatriate_only = fields.Boolean(
        string="Só Expatriados",
        related='salary_payment.expatriate_only',
        store=True,
        readonly=True,
    )

    @api.depends('amount', 'amount_paid')
    def _amount_balance(self):
        for rec in self:
            rec.balance = rec.amount_paid - rec.amount if rec.amount_paid >= rec.amount else 0.0
            rec.amount_debt = rec.amount - rec.amount_paid if rec.amount_paid <= rec.amount else 0.0


class AccountPaymentInd(models.Model):
    _name = 'hr.individual.payment'
    _description = 'Hr Payment'

class AccountMove(models.Model):
    _inherit = 'account.move'

    salary_tax_payment_id = fields.Many2one(
        'account.payment.salary',
        string="Pagamento de Impostos"
    )

    partial_payment_salary_id = fields.Many2one(
        'account.payment.salary',
        string='Pagamento Salarial Parcial'
    )
    salary_penalty_id = fields.Many2one('account.payment.salary', string='Pagamento Multas/Juros')


