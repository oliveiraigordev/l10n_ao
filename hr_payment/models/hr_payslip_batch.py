from odoo import fields, models, api,_
from odoo.exceptions import UserError,ValidationError



class HrPayslipBatch(models.Model):
    _inherit = 'hr.payslip.run'

    payment_state = fields.Selection([
        ('not_paid', 'Not Paid'),
        ('in_payment', 'In Payment'),
        ('partial', 'Partially Paid'),
        ('paid', 'Paid'),
    ], string="Payment State", default='not_paid')

    slip_move_count = fields.Integer(string="Contagem de Moves", compute="_compute_slip_move_count")
    payment_salary_count = fields.Integer(string="Pagamentos Salário", compute="_compute_payment_salary_count")

    is_expatriate_batch = fields.Boolean(
        string="Lote Expatriado",
        compute="_compute_is_expatriate_batch",
        store=True,
    )

    @api.depends('slip_ids.contract_id.contract_type_id')
    def _compute_is_expatriate_batch(self):
        for rec in self:
            slips = rec.slip_ids.filtered(lambda s: s.contract_id and s.contract_id.contract_type_id)
            rec.is_expatriate_batch = all(
                slip.contract_id.contract_type_id.code.lower() == 'expatriado'
                for slip in slips
            ) if slips else False

    def _compute_slip_move_count(self):
        for run in self:
            payslips = self.env['hr.payslip'].search([('payslip_run_id', '=', run.id)])
            run.slip_move_count = self.env['account.move'].search_count([('id', 'in', payslips.mapped('move_id').ids)])

    def action_open_related_moves(self):
        self.ensure_one()
        payslips = self.env['hr.payslip'].search([('payslip_run_id', '=', self.id)])
        move_ids = payslips.mapped('move_id').ids

        return {
            'type': 'ir.actions.act_window',
            'name': 'Related Journal Entries',
            'res_model': 'account.move',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', move_ids)],
            'context': {'create': False},
        }

    def _compute_payment_salary_count(self):
        for run in self:
            payments = self.env['account.payment.salary'].search([
                ('hr_payment.payslip_run_id', '=', run.id)
            ])
            run.payment_salary_count = len(payments)

    def action_view_salary_payments(self):
        self.ensure_one()
        payments = self.env['account.payment.salary'].search([
            ('hr_payment.payslip_run_id', '=', self.id)
        ])
        return {
            'type': 'ir.actions.act_window',
            'name': 'Pagamentos Contábeis de Salário',
            'res_model': 'account.payment.salary',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', payments.ids)],
            'context': {'default_hr_payment': self.id},
        }

    def post_treasury(self):
        """
        Processa o pagamento de salários em lote.
        Cria o registro em hr.payment com cálculo correto de líquido, bruto, IRT, INSS,
        ganhos e descontos adicionais, e remunerações específicas.
        """
        for res in self:
            if res.payment_state != 'not_paid':
                continue

            if not res.slip_ids:
                raise ValidationError(_("Nenhum slip associado ao pagamento %s. Verifique os dados." % res.name))

            vals = {
                'name': res.name,
                'payslip_run_id': res.id,
                'state': 'treasury',
            }

            slip_lines = [(5, 0, 0)]

            for slip in res.slip_ids:
                if not slip.employee_id:
                    raise ValidationError(_("Slip associado ao pagamento %s não possui funcionário." % res.name))

                total_gross = sum(l.total for l in slip.line_ids)
                irt = self._get_rule_total_by_category(slip, 'IRT')
                ss = self._get_rule_total_by_category(slip, 'INSS')
                ss8 = self._get_rule_total_by_category(slip, 'INSS8')

                other_earnings = sum(
                    l.total for l in slip.line_ids
                    if l.salary_rule_id.category_id.code not in ['IRT', 'INSS', 'Básico'] and l.total > 0
                )
                other_deductions = sum(
                    abs(l.total) for l in slip.line_ids
                    if l.salary_rule_id.category_id.code not in ['IRT', 'INSS'] and l.total < 0
                )

                valor_liquido = total_gross - irt - ss - other_deductions

                if valor_liquido <= 0:
                    raise ValidationError(_("Valor líquido inválido para pagamento: %s." % slip.employee_id.name))

                slip_lines.append((0, 0, {
                    'employee_id': slip.employee_id.id,
                    'amount': valor_liquido,
                    'irt_amount': irt,
                    'ss_amount': ss,
                    'ss8_amount': ss8,
                    'other_earnings': other_earnings,
                    'other_deductions': other_deductions,
                    'total_gross': total_gross,
                    'ali': sum(l.total for l in slip.line_ids if l.salary_rule_id.code == 'ALI'),
                    'trans': sum(l.total for l in slip.line_ids if l.salary_rule_id.code == 'TRANS'),
                    'fami': sum(l.total for l in slip.line_ids if l.salary_rule_id.code == 'FAMI'),
                    'renc': sum(l.total for l in slip.line_ids if l.salary_rule_id.code == 'RENC'),
                    'eat': sum(l.total for l in slip.line_ids if l.salary_rule_id.code == 'EAT'),
                    'comu': sum(l.total for l in slip.line_ids if l.salary_rule_id.code == 'COMU'),
                    'falha': sum(l.total for l in slip.line_ids if l.salary_rule_id.code == 'FALHA'),
                    'bon': sum(l.total for l in slip.line_ids if l.salary_rule_id.code == 'BON'),
                    'r92': sum(l.total for l in slip.line_ids if l.salary_rule_id.code == 'R92'),
                    'atra': sum(l.total for l in slip.line_ids if l.salary_rule_id.code == 'ATRA'),
                    'famexc': sum(l.total for l in slip.line_ids if l.salary_rule_id.code == 'FAMEXC'),
                    'comission': sum(l.total for l in slip.line_ids if l.salary_rule_id.code == 'COMISSION'),
                    'chef': sum(l.total for l in slip.line_ids if l.salary_rule_id.code == 'CHEF'),
                    'cfng': sum(l.total for l in slip.line_ids if l.salary_rule_id.code == 'CFNG'),
                    'thirteen': sum(l.total for l in slip.line_ids if l.salary_rule_id.code == '13'),
                    'fjr': sum(l.total for l in slip.line_ids if l.salary_rule_id.code == 'FJr'),
                    'fi': sum(l.total for l in slip.line_ids if l.salary_rule_id.code == 'FI'),
                    'r75': sum(l.total for l in slip.line_ids if l.salary_rule_id.code == 'R75'),
                    'gozo_ferias': sum(l.total for l in slip.line_ids if l.salary_rule_id.code == 'GOZO_FERIAS'),
                    'ata': sum(l.total for l in slip.line_ids if l.salary_rule_id.code == 'ATA'),
                    'adi': sum(l.total for l in slip.line_ids if l.salary_rule_id.code == 'ADI'),
                    'hextra_50': sum(l.total for l in slip.line_ids if l.salary_rule_id.code == 'HEXTRA_50'),
                    'hextra_75': sum(l.total for l in slip.line_ids if l.salary_rule_id.code == 'HEXTRA_75'),
                    'adi_alimentacao': sum(l.total for l in slip.line_ids if l.salary_rule_id.code == 'ADI_ALI'),
                    'isen_hora': sum(l.total for l in slip.line_ids if l.salary_rule_id.code == 'ISEN-HORA'),
                    'payslip_id': slip.id,
                }))

            vals['lines'] = slip_lines

            try:
                hr_payment = self.env['hr.payment'].create(vals)
            except Exception as e:
                raise ValidationError(_("Erro ao criar o registro de tesouraria: %s") % str(e))

            try:
                res._prepare_account_payment(hr_payment)
            except Exception as e:
                raise ValidationError(_("Erro ao preparar o pagamento contábil: %s") % str(e))

            res.payment_state = 'in_payment'

            # # 7) Dispara o e-mail para o grupo DAF
            # template = self.env.ref('hr_payment.email_template_payslip_batch_daf', raise_if_not_found=False)
            # if not template:
            #     # Se não encontrar, levanta ValidationError para facilitar o debug
            #     raise ValidationError(
            #         _("Template de e‐mail hr_payment.email_template_payslip_batch_daf não encontrado."))
            #
            # # Aqui usamos run.id (ID do lote), que já existe no banco
            # template.send_mail(res.id, force_send=True)
            #
            # # 8) Registra na chatter que o e‐mail foi disparado
            # res.message_post(body=_("Notificação enviada ao grupo DAF via e‐mail."))
        return True

    def _compute_irt(self, slip):
        """
        Cálculo seguro do IRT (Imposto de Rendimento do Trabalho).
        """
        return abs(getattr(slip, 'amount_irt', 0.0))

    def _compute_ss(self, slip):
        """
        Retorna o valor do INSS já calculado no slip, se existir.
        Se não, tenta calcular com base nas regras sujeitas ao INSS.
        """
        ss_amount = getattr(slip, 'amount_ss', 0.0)
        if ss_amount:
            return abs(ss_amount)

        # Alternativa: somar regras com categoria INSS (mais preciso)
        if hasattr(slip, 'line_ids'):
            ss_lines = slip.line_ids.filtered(lambda l: l.salary_rule_id.category_id.code == 'INSS')
            return abs(sum(ss_lines.mapped('total')))

        return 0.0

    def _prepare_account_payment(self, hr_payment):
        """
        Prepara o pagamento contábil para o registro de pagamento de salário,
        agora mapeando por código de regra em vez de categoria, com detalhamento completo.
        """
        for res in self:
            total_payment = 0.0
            hr_payment_lines = [(5, 0, 0)]

            for line in hr_payment.lines:
                slip = line.payslip_id
                if not slip:
                    continue

                # Valores principais
                total_gross = self._get_rule_total_by_code(slip, 'BASE')
                irt = self._get_rule_total_by_category(slip, 'IRT')
                ss = self._get_rule_total_by_category(slip, 'INSS')
                ss8 = self._get_rule_total_by_category(slip, 'INSS8')

                # Outros proventos e descontos genéricos
                other_earnings = sum(
                    l.total for l in slip.line_ids
                    if l.salary_rule_id.code not in ('BASE', 'IRT18', 'INSS') and l.total > 0
                )
                other_deductions = sum(
                    abs(l.total) for l in slip.line_ids
                    if l.salary_rule_id.code not in ('BASE', 'IRT18', 'INSS') and l.total < 0
                )

                # Rubricas específicas por código
                code_map = {
                    'ali': 'ALI',
                    'trans': 'TRANS',
                    'fami': 'FAMI',
                    'renc': 'RENC',
                    'eat': 'EAT',
                    'comu': 'COMU',
                    'falha': 'FALHA',
                    'bon': 'BON',
                    'r92': 'R92',
                    'atra': 'ATRA',
                    'famexc': 'FAMEXC',
                    'comission': 'COMISSION',
                    'chef': 'CHEF',
                    'cfng': 'CFNG',
                    'thirteen': '13',
                    'fjr': 'FJr',
                    'fi': 'FI',
                    'r75': 'R75',
                    'gozo_ferias': 'GOZO_FERIAS',
                    'ata': 'ATA',
                    'adi': 'ADI',
                    'hextra_50': 'HEXTRA_50',
                    'hextra_75': 'HEXTRA_75',
                    'adi_alimentacao': 'ADI_ALI',
                    'isen_hora': 'ISEN-HORA',
                }

                extra_vals = {
                    key: sum(l.total for l in slip.line_ids if l.salary_rule_id.code == rule_code)
                    for key, rule_code in code_map.items()
                }
                liquido = total_gross
                if liquido <= 0:
                    raise ValidationError(_(
                        "Valor líquido inválido para pagamento: %s."
                    ) % slip.employee_id.name)

                total_payment += liquido

                payment_line_vals = {
                    'name': line.employee_id.name,
                    'employee_type': line.employee_id.employee_type,
                    'amount': liquido,
                    'irt_amount': irt,
                    'ss_amount': ss,
                    'ss8_amount': ss8,
                    'other_earnings': other_earnings,
                    'other_deductions': other_deductions,
                    'total_gross': total_gross,
                    'payslip_id': slip.id,
                }
                payment_line_vals.update(extra_vals)

                hr_payment_lines.append((0, 0, payment_line_vals))

            journal = hr_payment.journal_id or self.env['account.journal'].search([
                ('company_id', '=', hr_payment.company_id.id),
                ('type', 'in', ['bank', 'cash'])
            ], limit=1)
            if not journal:
                raise ValidationError(_(
                    "Nenhum diário de tipo Banco ou Numerário foi encontrado "
                    "para gerar o pagamento contábil em lote."
                ))

            # 2) monta o dict incluindo journal_id e date
            vals = {
                'name': hr_payment.name,
                'journal_id': journal.id,
                'date': hr_payment.date or fields.Date.today(),
                'payment_type': 'outbound',
                'partner_type': 'employee',
                'hr_payment': hr_payment.id,
                'payment_method': 'transfer',
                'amount': total_payment,
                'lines': hr_payment_lines,
                'payslip_run_id': res.id,
            }
            self.env['account.payment.salary'].create(vals)
            if len(self) == 1:
                action_id = 'hr_payment.action_salary_payment_usd' if self.is_expatriate_batch else 'hr_payment.action_salary_payment_aoa'
                return self.env.ref(action_id).read()[0]

    def _get_rule_total_by_category(self, slip, category_code, absolute=True):
        """
        Soma os valores de regras salariais por categoria.
        Se absolute=True, retorna valor absoluto (útil para descontos como IRT, INSS).
        """
        if not slip or not slip.line_ids:
            return 0.0

        total = sum(
            l.total for l in slip.line_ids
            if l.salary_rule_id.category_id.code == category_code
        )
        return abs(total) if absolute else total

    def _get_rule_total_by_code(self, slip, code):
        if not slip or not slip.line_ids:
            return 0.0
        line = slip.line_ids.filtered(lambda l: l.salary_rule_id.code == code)
        return line.total if line else 0.0

    def action_draft(self):
        """
        Antes de voltar o lote ao estado 'draft', verifica se existe ao menos UM
        lançamento contábil (account.move) postado vinculado a um dos hr.payslip desse lote.
        Se encontrar, dispara UserError e bloqueia a ação.
        """
        for run in self:
            # Busca todos os payslips associados a este lote
            payslips = self.env['hr.payslip'].search([
                ('payslip_run_id', '=', run.id)
            ])
            # Coleta todos os move_id desses payslips (se existirem)
            move_ids = payslips.mapped('move_id').filtered(lambda m: m.state == 'posted').ids
            if move_ids:
                # Se houver ao menos um account.move em 'posted', bloquear
                raise UserError(_(
                    "Os recibos deste lote já possuem lançamentos contábeis postados. "
                    "Por favor, altere o(s) lançamento(s) para rascunho antes de voltar o lote para rascunho."
                ))
        # Se não encontrou nenhum move posted, segue o fluxo normal
        return super(HrPayslipBatch, self).action_draft()
