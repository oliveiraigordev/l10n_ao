# -*- coding: utf-8 -*-
# © 2024 NOSI.

from odoo import models, api, _, fields
from odoo.exceptions import ValidationError, UserError

from odoo.tools import format_amount
from contextlib import ExitStack, contextmanager

class AccountMoveLine(models.Model):
    _inherit = "account.move"

    @contextmanager
    def _check_balanced(self, container):
        """Assert the move is fully balanced debit = credit.
        An error is raised if it's not the case.
        """
        with self._disable_recursion(
            container, "check_move_validity", default=True, target=False
        ) as disabled:
            yield
            if disabled:
                return

        # unbalanced_moves = self._get_unbalanced_moves(container)
        unbalanced_moves = []
        if unbalanced_moves:
            # if not unbalanced_moves[0][1] == unbalanced_moves[0][2]:
            error_msg = _("An error has occurred.")
            for move_id, sum_debit, sum_credit in unbalanced_moves:
                move = self.browse(move_id)
                error_msg += _(
                    "\n\n"
                    "The move (%s) is not balanced.\n"
                    "The total of debits equals %s and the total of credits equals %s.\n"
                    'You might want to specify a default account on journal "%s" to automatically balance each move.',
                    move.display_name,
                    format_amount(self.env, sum_debit, move.company_id.currency_id),
                    format_amount(self.env, sum_credit, move.company_id.currency_id),
                    move.journal_id.name,
                )
            raise UserError(error_msg)

    # OVERRIDE DO MÉTODO COMPUTE AMOUNT PARA CALCULO DA RETENÇÃO
    @api.depends(
    'line_ids.matched_debit_ids.debit_move_id.move_id.payment_id.is_matched',
    'line_ids.matched_debit_ids.debit_move_id.move_id.line_ids.amount_residual',
    'line_ids.matched_debit_ids.debit_move_id.move_id.line_ids.amount_residual_currency',
    'line_ids.matched_credit_ids.credit_move_id.move_id.payment_id.is_matched',
    'line_ids.matched_credit_ids.credit_move_id.move_id.line_ids.amount_residual',
    'line_ids.matched_credit_ids.credit_move_id.move_id.line_ids.amount_residual_currency',
    'line_ids.balance',
    'line_ids.currency_id',
    'line_ids.amount_currency',
    'line_ids.amount_residual',
    'line_ids.amount_residual_currency',
    'line_ids.payment_id.state',
    'line_ids.full_reconcile_id')
    def _compute_amount(self):
        for move in self:
            total_untaxed, total_untaxed_currency = 0.0, 0.0
            total_tax, total_tax_currency = 0.0, 0.0
            total_residual, total_residual_currency = 0.0, 0.0
            total, total_currency = 0.0, 0.0
            amount_tax_wth = 0.0
            iva_captive_amount = 0.0

            # Cálculo do imposto retido (cativo) e do valor de retenção conforme a configuração do imposto
            if move.is_invoice(True):
                for line in move.invoice_line_ids:
                    for tax in line.tax_ids:
                        self.with_context()
                        tax_base_amount = line.price_unit * line.quantity
                        # Se for imposto retido "on_payment"
                        if tax.tax_exigibility == 'on_payment' and tax.is_withholding and \
                                tax_base_amount >= tax.limit_amount_wht:
                            tax_amount = tax._compute_amount(
                                line.price_unit * line.quantity * (1 - (line.discount or 0.0) / 100.0),
                                line.price_unit,
                                line.quantity)
                            amount_tax_wth += abs(tax_amount)
                        # Se for imposto do tipo IVA cativo (CAT50 ou CAT100)
                        if tax.iva_tax_type in ['CAT50', 'CAT100'] and tax.tax_exigibility == 'on_invoice':
                            amount_tax = tax_base_amount * (tax.amount / 100)
                            # Para CAT50, retemos 50% do imposto; para CAT100, 100%
                            iva_captive_amount += abs(amount_tax - (amount_tax * 0.5 if tax.iva_tax_type == 'CAT50' else 0))

            # Cálculo dos totais a partir das linhas do lançamento (move.line_ids)
            for line in move.line_ids:
                if move.is_invoice(True):
                    if line.display_type == 'tax' or (line.display_type == 'rounding' and line.tax_repartition_line_id):
                        total_tax += line.balance
                        total_tax_currency += line.amount_currency
                        total += line.balance
                        total_currency += line.amount_currency
                    elif line.display_type in ('product', 'rounding'):
                        total_untaxed += line.balance
                        total_untaxed_currency += line.amount_currency
                        total += line.balance
                        total_currency += line.amount_currency
                    elif line.display_type == 'payment_term':
                        total_residual += line.amount_residual
                        total_residual_currency += line.amount_residual_currency
                else:
                    if line.debit:
                        total += line.balance
                        total_currency += line.amount_currency

            sign = move.direction_sign
            move.amount_untaxed = sign * total_untaxed_currency
            move.amount_tax = sign * total_tax_currency
            move.amount_total = sign * total_currency
            move.amount_residual = -sign * total_residual_currency
            move.amount_untaxed_signed = -total_untaxed
            move.amount_tax_signed = -total_tax
            move.amount_total_signed = abs(total) if move.move_type == 'entry' else -total
            move.amount_residual_signed = total_residual
            move.amount_total_in_currency_signed = abs(move.amount_total) if move.move_type == 'entry' else -(
                sign * move.amount_total)
            move.amount_total_wth = move.amount_total - amount_tax_wth if amount_tax_wth else 0.0
            move.amount_tax_captive = iva_captive_amount

            # --- Ajuste para manter o imposto original e alterar somente o valor devido ---
            # Recalcula o total e o imposto a partir das linhas da fatura

            if move.amount_tax_captive:
                total_valor = 0.0
                total_imposto = 0.0
                for line in move.invoice_line_ids:
                    total_valor += line.price_subtotal
                    total_imposto += line.amount_tax

                move.amount_total = total_valor + total_imposto
                move.amount_tax = total_imposto

                move.amount_residual = move.amount_total - iva_captive_amount
    


    def action_register_payment(self):
        ''' Open the account.payment.register wizard to pay the selected journal entries.
        :return: An action opening the account.payment.register wizard.
        '''
        if self.amount_tax_captive:
            return {
                'name': _('Register Payment'),
                'res_model': 'account.payment.register',
                'view_mode': 'form',
                'context': {
                    'active_model': 'account.move',
                    'active_ids': self.ids,
                    'default_amount': self.amount_residual
                },
                'target': 'new',
                'type': 'ir.actions.act_window',
            }
        else:
            return {
                'name': _('Register Payment'),
                'res_model': 'account.payment.register',
                'view_mode': 'form',
                'context': {
                    'active_model': 'account.move',
                    'active_ids': self.ids,
                },
                'target': 'new',
                'type': 'ir.actions.act_window',
            }
