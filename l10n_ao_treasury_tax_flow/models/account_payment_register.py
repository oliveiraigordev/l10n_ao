# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class AccountPaymentRegister(models.TransientModel):
    _inherit = 'account.payment.register'

    def _init_payments(self, to_process, edit_mode=False):
        """ Create the payments.

        :param to_process:  A list of python dictionary, one for each payment to create, containing:
                            * create_vals:  The values used for the 'create' method.
                            * to_reconcile: The journal items to perform the reconciliation.
                            * batch:        A python dict containing everything you want about the source journal items
                                            to which a payment will be created (see '_get_batches').
        :param edit_mode:   Is the wizard in edition mode.
        """
        has_post_retention = any(
            tax.post_retention_payment
            for move in self.line_ids.mapped('move_id')
            for line in move.invoice_line_ids
            for tax in line.tax_ids
        )
        if not has_post_retention:
            return super(AccountPaymentRegister, self)._init_payments(to_process, edit_mode=False)
        # L10N_AO FOI ADICIONADO NO CONTEXTO O VALOR PARA SABER SE LANÇA OU NÃO IMPOSTOS
        payments = self.env['account.payment'] \
            .with_context(skip_invoice_sync=True, payment_with_withholding=self.payment_with_withholding, payment_difference_handling=self.payment_difference_handling) \
            .create([x['create_vals'] for x in to_process])

        for payment, vals in zip(payments, to_process):
            vals['payment'] = payment

            # If payments are made using a currency different than the source one, ensure the balance match exactly in
            # order to fully paid the source journal items.
            # For example, suppose a new currency B having a rate 100:1 regarding the company currency A.
            # If you try to pay 12.15A using 0.12B, the computed balance will be 12.00A for the payment instead of 12.15A.
            if edit_mode:
                lines = vals['to_reconcile']

                # Batches are made using the same currency so making 'lines.currency_id' is ok.
                if payment.currency_id != lines.currency_id:
                    liquidity_lines, counterpart_lines, writeoff_lines = payment._seek_for_lines()
                    source_balance = abs(sum(lines.mapped('amount_residual')))
                    if liquidity_lines[0].balance:
                        payment_rate = liquidity_lines[0].amount_currency / liquidity_lines[0].balance
                    else:
                        payment_rate = 0.0
                    source_balance_converted = abs(source_balance) * payment_rate

                    # Translate the balance into the payment currency is order to be able to compare them.
                    # In case in both have the same value (12.15 * 0.01 ~= 0.12 in our example), it means the user
                    # attempt to fully paid the source lines and then, we need to manually fix them to get a perfect
                    # match.
                    payment_balance = abs(sum(counterpart_lines.mapped('balance')))
                    payment_amount_currency = abs(sum(counterpart_lines.mapped('amount_currency')))
                    if not payment.currency_id.is_zero(source_balance_converted - payment_amount_currency):
                        continue

                    delta_balance = source_balance - payment_balance

                    # Balance are already the same.
                    if self.company_currency_id.is_zero(delta_balance):
                        continue

                    # Fix the balance but make sure to peek the liquidity and counterpart lines first.
                    debit_lines = (liquidity_lines + counterpart_lines).filtered('debit')
                    credit_lines = (liquidity_lines + counterpart_lines).filtered('credit')

                    if debit_lines and credit_lines:
                        payment.move_id.write({'line_ids': [
                            (1, debit_lines[0].id, {'debit': debit_lines[0].debit + delta_balance}),
                            (1, credit_lines[0].id, {'credit': credit_lines[0].credit + delta_balance}),
                        ]})
        return payments      