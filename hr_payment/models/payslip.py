from odoo import fields, models, api,_
from odoo.exceptions import ValidationError



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
            slips = rec.slip_ids
            expatriados = slips.filtered(
                lambda s: s.contract_id.contract_type_id and s.contract_id.contract_type_id.code == 'expatriado'
            )
            rec.is_expatriate_batch = len(expatriados) == len(slips) if slips else False

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

    # def post_treasury(self):
    #     for res in self:
    #         if res.payment_state in ['not_paid']:
    #             vals = {
    #                 'name': res.name,
    #                 'payslip_run_id': res.id,
    #                 'state': 'treasury',
    #             }
    #             slip_lines = [(5, 0, 0)]
    #             for slip in res.slip_ids:
    #                 slip_lines.append((0, 0, {
    #                     'employee_id': slip.employee_id.id,
    #                     'amount': slip.total_paid,
    #                     'irt_amount': slip.amount_irt * -1 if slip.amount_irt < 0 else 0.0,
    #                     'ss_amount': ((slip.total_remunerations * 0.08) + (slip.amount_inss * -1)) if res.structure_type_id.type == 'funcionário' else 0.0
    #                 }))
    #             vals['lines'] = slip_lines
    #             print("aqui ..........",vals['lines'])
    #             hr_payment = self.env['hr.payment'].create(vals)
    #             res._prepare_account_payment(hr_payment)
    #             res.payment_state = 'in_payment'


    def post_treasury(self):
        """
        Função para processar o pagamento de salário.
        Atualiza o estado de pagamento e cria o registro na Conttabilidade.
        """
        for res in self:
            # Validação do estado inicial de pagamento
            if res.payment_state not in ['not_paid']:
                continue

            # Validação de slips
            if not res.slip_ids:
                raise ValidationError(_("Nenhum slip associado ao pagamento %s. Verifique os dados.") % res.name)

            vals = {
                'name': res.name,
                'payslip_run_id': res.id,
                'state': 'treasury',
            }

            # Construção das linhas associadas aos slips
            slip_lines = [(5, 0, 0)]
            for slip in res.slip_ids:
                if not slip.employee_id:
                    raise ValidationError(_("Slip associado ao pagamento %s não possui funcionário.") % res.name)

                if getattr(slip, 'total_paid', 0.0) <= 0:
                    raise ValidationError(_("Slip com valor inválido para pagamento: %s.") % slip.employee_id.name)

                # Adiciona a linha com os cálculos robustos
                slip_lines.append((0, 0, {
                    'employee_id': slip.employee_id.id,
                    'amount': getattr(slip, 'total_paid', 0.0),
                    'irt_amount': self._compute_irt(slip),
                    'ss_amount': self._compute_ss(slip),
                }))

            vals['lines'] = slip_lines
            vals['lines'] = slip_lines

            # Criação do registro de pagamento de salário
            try:
                hr_payment = self.env['hr.payment'].create(vals)
            except Exception as e:
                raise ValidationError(_("Erro ao criar o registro de tesouraria: %s") % str(e))

            # Preparar estrutura de pagamento
            try:
                res._prepare_account_payment(hr_payment)
            except Exception as e:
                raise ValidationError(_("Erro ao preparar o pagamento contábil: %s") % str(e))

            # Atualiza o estado do processamento da folha
            res.payment_state = 'in_payment'

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
        Prepara o pagamento contábil para o registro de pagamento de salário.

        :param hr_payment: Registro de pagamento contendo informações de funcionários e valores.
        """
        for res in self:
            # Montagem do dicionário principal com informações do pagamento
            vals = {
                'name': hr_payment.name,
                # 'journal_id': res.journal_id.id,
                'payment_type': 'outbound',
                'partner_type': 'employee',
                'hr_payment': hr_payment.id,
                'payment_method': 'transfer',
                'amount': sum(line.amount for line in hr_payment.lines),
            }

            # Inicialização das linhas do pagamento
            hr_payment_lines = [(5, 0, 0)]
            hr_payment_lines += [
                (0, 0, {
                    'name': line.employee_id.name,
                    'employee_type': line.employee_id.employee_type,
                    'amount': line.amount,
                    'irt_amount': line.irt_amount,
                    'ss_amount': line.ss_amount,
                })
                for line in hr_payment.lines
            ]

            # Adicionar as linhas processadas ao dicionário principal
            vals['lines'] = hr_payment_lines
            self.env['account.payment.salary'].create(vals)

