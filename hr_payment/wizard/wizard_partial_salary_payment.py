from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools.float_utils import float_compare

class PartialSalaryPaymentWizard(models.TransientModel):
    _name = 'partial.salary.payment.wizard'
    _description = 'Pagamento Parcial de Salário'

    salary_payment_id = fields.Many2one('account.payment.salary', required=True, ondelete='cascade')
    amount_to_pay = fields.Monetary(string='Valor a Pagar', required=True)
    currency_id = fields.Many2one('res.currency', default=lambda s: s.env.company.currency_id)
    total_amount = fields.Monetary(string="Total a Pagar", related='salary_payment_id.slip_amount', readonly=True)
    partial_paid_total = fields.Monetary(string="Total Pago (Parcial)", related='salary_payment_id.partial_paid_total', readonly=True)
    remaining_amount = fields.Monetary(string="Restante a Pagar", related='salary_payment_id.remaining_amount', readonly=True)

    @api.constrains('amount_to_pay')
    def _check_amount_to_pay(self):
        for w in self:
            if float_compare(w.amount_to_pay, 0.0, precision_rounding=w.currency_id.rounding) <= 0:
                raise UserError(_("O valor deve ser maior que zero."))
            if float_compare(w.amount_to_pay, w.remaining_amount, precision_rounding=w.currency_id.rounding) > 0:
                raise UserError(_("O valor (%s) excede o saldo remanescente a pagar (%s).") % (w.amount_to_pay, w.remaining_amount))

    def confirm_partial_payment(self):
        self.ensure_one()
        payment = self.salary_payment_id

        if float_compare(payment.remaining_amount, 0.0, precision_rounding=payment.currency_id.rounding) <= 0:
            raise UserError(_("Não há saldo remanescente para pagamento parcial."))

        value = payment.currency_id.round(self.amount_to_pay)

        pending_account_id = (
            payment.journal_id.outbound_payment_method_line_ids
            .filtered(lambda m: m.payment_method_id.code == 'manual')
            .mapped('payment_account_id')[:1].id
        ) or (payment.journal_id.default_account_id.id if payment.journal_id.default_account_id else False)

        if not pending_account_id:
            raise UserError(_("Configure uma conta no método de pagamento manual ou defina a conta padrão no diário %s.") % payment.journal_id.display_name)

        # 4) Conta de débito (líquido 36211) por empresa
        salary_account = self.env['account.account'].search([
            ('code', '=', '36211'),
            ('company_id', '=', payment.company_id.id),
        ], limit=1)
        if not salary_account:
            raise UserError(_("Conta contábil '36211' não encontrada para a empresa %s.") % payment.company_id.display_name)

        # 5) Monta o move
        move_vals = {
            'move_type': 'entry',
            'journal_id': payment.journal_id.id,
            'date': payment.date or fields.Date.today(),
            'ref': _('Pagamento parcial - %s') % (payment.name or ''),
            'partial_payment_salary_id': payment.id,
            'payment_id': False,  # evita FK nativa com account.payment
            'line_ids': [
                (0, 0, {
                    'name': _('Pagamento Parcial de Salário'),
                    'account_id': pending_account_id,
                    'credit': value,
                    'debit': 0.0,
                }),
                (0, 0, {
                    'name': _('Pagamento Parcial de Salário'),
                    'account_id': salary_account.id,
                    'debit': value,
                    'credit': 0.0,
                }),
            ],
        }

        # contexto limpo
        Move = self.env['account.move'].with_context(default_payment_id=False)
        move = Move.create(move_vals)
        move._post()

        payment.message_post(body=_("Pagamento parcial de %s %s registrado.") % (value, payment.currency_id.symbol))

        # marca como posted e referência o último move
        if float_compare(payment.remaining_amount, 0.0, precision_rounding=payment.currency_id.rounding) <= 0:
            payment.write({'state': 'posted', 'move_id': move.id})

        return {'type': 'ir.actions.act_window_close'}
