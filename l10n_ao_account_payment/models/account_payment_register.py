# -*- coding: utf-8 -*-
import logging

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class AccountPaymentRegister(models.TransientModel):
    _inherit = 'account.payment.register'

    def _reconcile_payments(self, to_process, edit_mode=False):
        try:
            result = super(AccountPaymentRegister, self)._reconcile_payments(to_process, edit_mode)
            move_id = self.env['account.move'].browse(self._context.get('active_ids', []))
            if move_id and move_id.payment_state != 'in_payment':
                payment_ids = self.env['account.payment']
                
                if to_process and to_process[0].get('payment'):
                    payment_ids = to_process[0]['payment']
                else:
                    payment_ids = payment_ids.search([('move_id', '=', move_id.id)])
                
                if not move_id.payment_id and payment_ids:
                    move_id.payment_id = payment_ids[0]
                
                if self.journal_id.force_same_account_on_reconcile:
                    move_id.payment_state = 'in_payment'
                    move_id.to_check = True
                
                for payment in payment_ids:
                    payment.is_reconciled = False
                    payment.to_check = False
                    payment.is_matched = False
                    for line in payment.move_id.line_ids:
                        line.reconciled = False

            self.journal_id.update_dashboard_data()
            return result
        except Exception as e:
            raise Exception(e)
        # objetivo permitir criar a reconciliação, porém mante-la em aberto, em pagamento na fatura