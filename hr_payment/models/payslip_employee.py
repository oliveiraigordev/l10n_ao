from odoo import fields, models, api, _
from odoo.exceptions import ValidationError

class HrPayslipIndividualPayment(models.Model):
    _inherit = 'hr.payslip'

    payment_state = fields.Selection([
        ('not_paid', 'Não Pago'),
        ('in_payment', 'Em Pagamento'),
        ('paid', 'Pago'),
    ], string="Estado de Pagamento", default='not_paid', tracking=True)

    # Contadores para exibir na vista
    salary_move_count = fields.Integer(string="Lançamentos Contábeis", compute="_compute_salary_move_count")
    payment_salary_count = fields.Integer(string="Pagamentos Salário", compute="_compute_payment_salary_count")

    def _compute_salary_move_count(self):
        for slip in self:
            # se o próprio payslip tiver um move_id
            slip.salary_move_count = 1 if slip.move_id else 0

    def action_open_related_moves(self):
        """Abre o journal entry vinculado a este payslip."""
        self.ensure_one()
        if not self.move_id:
            raise ValidationError(_("Nenhum lançamento contábil encontrado para este Payslip."))
        return {
            'type': 'ir.actions.act_window',
            'name': 'Lançamento Contábil',
            'res_model': 'account.move',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', [self.move_id.id])],
            'context': {'create': False},
        }

    def _compute_payment_salary_count(self):
        for slip in self:
            payments = self.env['account.payment.salary'].search([
                ('hr_payment.payslip_id', '=', slip.id),
            ])
            slip.payment_salary_count = len(payments)

    def action_view_salary_payments(self):
        """Abre os registros de account.payment.salary gerados para este payslip."""
        self.ensure_one()
        payments = self.env['account.payment.salary'].search([
            ('hr_payment.payslip_id', '=', self.id),
        ])
        return {
            'type': 'ir.actions.act_window',
            'name': 'Pagamentos Salário',
            'res_model': 'account.payment.salary',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', payments.ids)],
            'context': {'create': False},
        }

    def action_post_treasury_single(self):
        """
        Processa o pagamento contábil de um único payslip, incluindo todos os subsídios.
        """
        for slip in self:
            # Validações
            if slip.state != 'done':
                raise ValidationError(_("O slip precisa estar validado (estado 'done') para ser pago."))
            if slip.payment_state != 'not_paid':
                raise ValidationError(_("Este funcionário já possui pagamento em curso ou concluído."))
            if not slip.employee_id:
                raise ValidationError(_("Slip não possui funcionário associado."))
            if slip.total_paid <= 0:
                raise ValidationError(_("Valor inválido para pagamento: %s.") % slip.employee_id.name)

            existing = self.env['hr.payment'].search([
                ('lines.payslip_id', '=', slip.id),
                ('payslip_run_id', '=', False),
                ('state', '!=', 'cancel'),
            ], limit=1)

            # if existing:
            #     raise ValidationError(_(
            #         "Já existe um pagamento individual em aberto "
            #         "para este Payslip (%s)." % slip.number or slip.name
            #     ))

            journal = getattr(slip, 'journal_id', False) or self.env['account.journal'].search([
                ('company_id', '=', slip.company_id.id),
                ('type', 'in', ['bank', 'cash'])
            ], limit=1)
            if not journal:
                raise ValidationError(_(
                    "Nenhum diário de tipo Banco ou Numerário encontrado "
                    "no payslip ou na companhia."
                ))

            # Calcula IRT e SS
            irt = self.env['hr.payslip.run']._compute_irt(slip)
            ss  = self.env['hr.payslip.run']._compute_ss(slip)
            ss8  = self.env['hr.payslip.run']._compute_ss8(slip)

            # Mapeia subsídios
            code_map = {
                'ali': 'ALI', 'trans': 'TRANS', 'fami': 'FAMI', 'renc': 'RENC',
                'eat': 'EAT', 'comu': 'COMU', 'falha': 'FALHA', 'bon': 'BON',
                'r92': 'R92', 'atra': 'ATRA', 'famexc': 'FAMEXC', 'comission': 'COMISSION',
                'chef': 'CHEF', 'cfng': 'CFNG', 'thirteen': '13', 'fjr': 'FJR',
                'fi': 'FI', 'r75': 'R75', 'gozo_ferias': 'GOZO_FERIAS',
                'ata': 'ATA', 'adi': 'ADI', 'hextra_50': 'HEXTRA_50', 'hextra_75': 'HEXTRA_75',
                'adi_alimentacao': 'ADI_ALI',
                'isen_hora': 'ISEN-HORA',
            }
            subsidies = {
                key: sum(l.total for l in slip.line_ids if l.salary_rule_id.code == rule)
                for key, rule in code_map.items()
            }

            # Prepara valores para criação de hr.payment
            line_vals = {
                'employee_id':      slip.employee_id.id,
                'payslip_id':       slip.id,
                'amount':           slip.total_paid,
                'irt_amount':       irt,
                'ss_amount':        ss,
                'ss8_amount':        ss8,
                **subsidies,
            }
            payment_vals = {
                'name':            f'Pagamento Individual - {slip.number or slip.name}',
                'state':           'treasury',
                'lines':           [(0, 0, line_vals)],
            }
            hr_payment = self.env['hr.payment'].create(payment_vals)

            # Cria registro contábil via account.payment.salary
            self._prepare_account_payment_single(hr_payment, slip)

            # Atualiza estado e notifica
            slip.payment_state = 'paid'
            slip.message_post(body=_("Pagamento individual realizado com sucesso."))

    def _prepare_account_payment_single(self, hr_payment, slip):
        """
        Cria registro em account.payment.salary com todas as rubricas.
        """
      # 1) Escolhe o diário: slip.journal_id > hr_payment.journal_id > fallback
        journal = getattr(slip, 'journal_id', False) or hr_payment.journal_id or self.env['account.journal'].search(
            [
                ('company_id', '=', hr_payment.company_id.id),
                ('type', 'in', ['bank', 'cash'])
            ], limit=1)
        if not journal:
            raise ValidationError(_("Nenhum diário de Caixa/Numerário disponível para lançamento contábil."))

        total_amount = sum(line.amount for line in hr_payment.lines)
        vals = {
            'name':           hr_payment.name,
            'payment_type':   'outbound',
            'journal_id': journal.id,
            'date': hr_payment.date or fields.Date.today(),
            'partner_type':   'employee',
            'hr_payment':     hr_payment.id,
            'payment_method': 'transfer',
            'amount':         total_amount,
            'lines': [
                (0, 0, {
                    'name':              line.employee_id.name,
                    'employee_id':       line.employee_id.id,
                    'payslip_id':        line.payslip_id.id if line.payslip_id else False,
                    'amount':            line.amount,
                    'irt_amount':        line.irt_amount,
                    'ss_amount':         line.ss_amount,
                    'ss8_amount':        line.ss8_amount,
                    'other_earnings':    getattr(line, 'other_earnings', 0.0),
                    'other_deductions':  getattr(line, 'other_deductions', 0.0),
                    'total_gross':       getattr(line, 'total_gross', 0.0),
                    # Subsídios
                    'ali':               line.ali,
                    'trans':             line.trans,
                    'fami':              line.fami,
                    'renc':              line.renc,
                    'eat':               line.eat,
                    'comu':              line.comu,
                    'falha':             line.falha,
                    'bon':               line.bon,
                    'r92':               line.r92,
                    'atra':              line.atra,
                    'famexc':            line.famexc,
                    'comission':         line.comission,
                    'chef':              line.chef,
                    'cfng':              line.cfng,
                    'thirteen':          line.thirteen,
                    'fjr':               line.fjr,
                    'fi':                line.fi,
                    'r75':               line.r75,
                    'gozo_ferias':       line.gozo_ferias,
                    'ata':               line.ata,
                    'adi':               line.adi,
                    'hextra_50':         line.hextra_50,
                    'hextra_75':         line.hextra_75,
                    'adi_alimentacao':   line.adi_alimentacao,
                    'isen_hora':          line.isen_hora,
                }) for line in hr_payment.lines
            ],
        }
        self.env['account.payment.salary'].create(vals)
