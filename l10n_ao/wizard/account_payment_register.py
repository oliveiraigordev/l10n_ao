# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class AccountPaymentRegisterAng(models.TransientModel):
    _inherit = 'account.payment.register'

    amount_wth_total = fields.Monetary(_("Amount w/ Withhold"), currency_field='currency_id',
                                 compute="_compute_amount_withholding",
                                 store=True)
    wth_amount = fields.Monetary(_("Withhold Amount"),
                                 compute="_compute_amount_withholding",
                                 currency_field='currency_id',
                                 readonly=True, store=True)
    current_wth = fields.Monetary(_("Applied Withhold"), currency_field='currency_id',
                                  compute="_compute_amount_withholding",
                                  store=True)

    payment_with_withholding = fields.Selection(
        string="Payment with Withholding",
        selection=[('with', 'Com Retenção'), ('not_with', 'Sem Retenção')],
        readonly=False,
    )

    amount = fields.Monetary(string="mount", currency_field='currency_id',
                             readonly=False,compute="_compute_total_wth",store=True)


    is_withholding = fields.Boolean(string="É Retenção?")

    # Sobrescrever o campo 'amount' para que seja atualizado
    #dinamicamente com o valor da do total com  Retenção

    @api.depends('amount_wth_total', 'payment_with_withholding', 'current_wth')
    def _compute_total_wth(self):
        for record in self:
            if record.payment_with_withholding == 'with':
                record.amount = record.amount_wth_total
            elif record.payment_with_withholding == 'not_with':
                record.amount = record.amount_wth_total + record.current_wth
            else:
                invoice_moves = self.env['account.move'].browse(self._context.get('active_ids', []))
                record.amount = sum(invoice_moves.mapped("amount_residual"))

    @api.depends("amount")
    def _compute_amount_withholding(self):
        amount_tax_wth = 0.0
        residual_rate = 1.0
        amount_wth_total = 0.0
        invoice_moves = self.env['account.move'].browse(self._context.get('active_ids', []))
        total_amount_residual = sum(invoice_moves.mapped("amount_residual"))
        for invoice in invoice_moves:
            residual_rate = 1 - (invoice.amount_total - invoice.amount_residual) / (invoice.amount_total or 1)
            invoice_amount_tax_wth = 0.0
            for line in invoice.invoice_line_ids:
                for tax in line.tax_ids:
                    for invoice in invoice_moves:
                        tax_base_amount = sum(
                            l.price_unit * l.quantity
                            for l in invoice.invoice_line_ids
                        )
                    # tax_base_amount = line.price_unit * line.quantity
                    if tax.tax_exigibility == 'on_payment' and tax.is_withholding and tax.limit_amount_wht < tax_base_amount:
                        tax_amount = tax._compute_amount(
                            line.price_unit * line.quantity * (1 - (line.discount or 0.0) / 100.0), line.price_unit,
                            line.quantity)
                        amount_tax_wth += abs(tax_amount) * residual_rate
                        invoice_amount_tax_wth += abs(tax_amount) * residual_rate
            amount_wth_total += invoice.amount_residual - invoice_amount_tax_wth
        payment_rate = self.amount == 0.0 and 0.0 or (self.amount / (total_amount_residual - amount_tax_wth or 1))
        if amount_tax_wth == total_amount_residual:
            payment_rate = 0
        if payment_rate > 1:
            payment_rate = 1

        self.wth_amount = amount_tax_wth
        self.current_wth = amount_tax_wth * payment_rate
        self.amount_wth_total = amount_wth_total

    @api.depends('amount')
    def _compute_taxes_on_payment(self):
        for wizard in self:
            invoice_moves = self.env['account.move'].browse(self._context.get('active_ids', []))
            # calcular a razão do pagamento com base no valor em dívida.

            if wizard.source_currency_id == wizard.currency_id:
                # Same currency.
                amount_wth_total = wizard.source_amount_currency - wizard.amount
            elif wizard.currency_id == wizard.company_id.currency_id:
                # Payment expressed on the company's currency.
                wizard.amount_wth_total = wizard.source_amount - wizard.amount
            else:
                # Foreign currency on payment different than the one set on the journal entries.
                amount_payment_currency = wizard.company_id.currency_id._convert(wizard.source_amount,
                                                                                 wizard.currency_id, wizard.company_id,
                                                                                 wizard.payment_date)
                # wizard.amount_wth_total = amount_payment_currency - wizard.amount

    @api.depends('amount','payment_with_withholding')
    def _compute_payment_difference(self):
        for wizard in self:
            if wizard.source_currency_id == wizard.currency_id:
                # Same currency.
                # TIS: Adicionado a retencao a diferenca de pagamento
                wizard.payment_difference = wizard.source_amount_currency - wizard.amount if wizard.payment_with_withholding == 'with' else wizard.source_amount_currency - wizard.amount
            elif wizard.currency_id == wizard.company_id.currency_id:
                # Payment expressed on the company's currency.
                wizard.payment_difference = wizard.source_amount - wizard.amount - wizard.wth_amount
            else:
                # Foreign currency on payment different than the one set on the journal entries.
                amount_payment_currency = wizard.company_id.currency_id._convert(wizard.source_amount,
                                                                                 wizard.currency_id, wizard.company_id,
                                                                                 wizard.payment_date)
                wizard.payment_difference = amount_payment_currency - wizard.amount - wizard.wth_amount

    def default_get(self, fields_list):
        # OVERRIDE
        res = super().default_get(fields_list)
        amount_wth_total = 0.0

        if 'line_ids' in fields_list and 'line_ids' not in res:

            # Retrieve moves to pay from the context.
            if self._context.get('active_model') == 'account.move':
                lines = self.env['account.move'].browse(self._context.get('active_ids', [])).line_ids
            elif self._context.get('active_model') == 'account.move.line':
                lines = self.env['account.move.line'].browse(self._context.get('active_ids', []))
            else:
                raise UserError(_(
                    "The register payment wizard should only be called on account.move or account.move.line records."
                ))

            # Keep lines having a residual amount to pay.
            available_lines = self.env['account.move.line']
            for line in lines:
                if line.move_id.state != 'posted':
                    raise UserError(_("You can only register payment for posted journal entries."))

                if line.account_type not in ('asset_receivable', 'liability_payable'):
                    continue
                if line.currency_id:
                    if line.currency_id.is_zero(line.amount_residual_currency):
                        continue
                else:
                    if line.company_currency_id.is_zero(line.amount_residual):
                        continue
                available_lines |= line

            # Check.
            if not available_lines:
                raise UserError(_(
                    "You can't register a payment because there is nothing left to pay on the selected journal items."))
            if len(lines.company_id) > 1:
                raise UserError(_("You can't create payments for entries belonging to different companies."))
            if len(set(available_lines.mapped('account_internal_type'))) > 1:
                raise UserError(
                    _("You can't register payments for journal items being either all inbound, either all outbound."))

            res['line_ids'] = [(6, 0, available_lines.ids)]

        moves = self.env['account.move'].browse(self._context.get('active_ids', []))
        for move in moves:
            amount_wth_total += move.amount_total_wth
        res['amount_wth_total'] = amount_wth_total
        return res

    def _init_payments(self, to_process, edit_mode=False):
        """ Create the payments.

        :param to_process:  A list of python dictionary, one for each payment to create, containing:
                            * create_vals:  The values used for the 'create' method.
                            * to_reconcile: The journal items to perform the reconciliation.
                            * batch:        A python dict containing everything you want about the source journal items
                                            to which a payment will be created (see '_get_batches').
        :param edit_mode:   Is the wizard in edition mode.
        """
        # L10N_AO FOI ADICIONADO NO CONTEXTO O VALOR PARA SABER SE LANÇA OU NÃO IMPOSTOS
        payments = self.env['account.payment'] \
            .with_context(skip_invoice_sync=True, payment_with_withholding=self.payment_with_withholding) \
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

    def action_create_payments(self):
        res = super(AccountPaymentRegisterAng, self).action_create_payments()
        if self._context.get('active_model') == 'account.move':
            move_id = self.env['account.move'].browse(self._context.get('active_ids', []))
            if len(move_id) == 1 and self.is_withholding and move_id.move_type == 'out_invoice' and self.payment_difference > 0:
                if any(tax.is_withholding for tax in move_id.line_ids.tax_ids):
                    raise UserError("Já existe um imposto de retenção nesta fatura!")
                move_id.write({'late_wth_amount': self.payment_difference})
        return res

