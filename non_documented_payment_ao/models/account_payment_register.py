# -*- coding: utf-8 -*-
# © 2024 NOSI.

from odoo import models, api, _, fields
from odoo.exceptions import ValidationError, UserError

class AccountPaymentRegister(models.TransientModel):
    _inherit = 'account.payment.register'

    def _get_total_amount_using_same_currency(self, batch_result, early_payment_discount=True):
        self.ensure_one()
        amount = 0.0
        mode = False
        for aml in batch_result['lines']:
            if early_payment_discount and aml._is_eligible_for_early_payment_discount(aml.currency_id, self.payment_date):
                amount += aml.discount_amount_currency
                mode = 'early_payment'
            else:
                amount += aml.amount_residual_currency

        if aml.move_id.amount_tax_captive:
            amount = aml.move_id.amount_residual

        return abs(amount), mode
    
    def action_create_payments(self):
        move = self.env['account.move'].search([('id', '=', self._context.get('active_ids'))])

        if move.amount_tax_captive:
            residual = move.amount_residual - self.amount
            
        super(AccountPaymentRegister, self).action_create_payments()

        if move.amount_tax_captive:
            move.update(
                {"amount_residual": residual}
            )

        if move.amount_residual == 0 or residual == 0:
            move.update(
                {"payment_state": 'paid'}
            )