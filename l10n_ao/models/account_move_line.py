# -*- coding: utf-8 -*-
from functools import partial
from odoo import models, fields, api, _
from contextlib import ExitStack, contextmanager
from odoo.tools.misc import formatLang
from odoo.exceptions import ValidationError, UserError
from odoo.tools import float_is_zero, float_compare, date_utils, DEFAULT_SERVER_DATE_FORMAT
from collections import defaultdict
# from .saft import dict_clean_up
# from odoo.addons.l10n_ao.sign import sign
from odoo.tools import frozendict, formatLang, format_date, float_compare, Query
from datetime import date, timedelta


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    margin_value = fields.Float(string="Margin (%)", compute='_compute_margin', store=True, digits='Margin',
                                readonly=False, precompute=True)
    amount_margin = fields.Float(string="Amount Margin")
    journal_ao_id = fields.Many2one("account.journal.ao", copy=False)

    @api.ondelete(at_uninstall=False)
    def _prevent_automatic_line_deletion(self):
        if self.env.user.company_id.country_id.code == "AO":
            if not self.env.context.get('dynamic_unlink'):
                for line in self:
                    if line.move_id.move_type in ['out_invoice', 'out_refund']:
                        if line.display_type == 'tax' and line.move_id.line_ids.tax_ids:
                            raise ValidationError(_(
                                "You cannot delete a tax line as it would impact the tax report"
                            ))
                        elif line.display_type == 'payment_term':
                            raise ValidationError(_(
                                "You cannot delete a payable/receivable line as it would not be consistent "
                                "with the payment terms"
                            ))
        else:
            return super(AccountMoveLine, self)._prevent_automatic_line_deletion()

    @api.depends('product_id')
    def _compute_margin(self):
        for line in self:
            if not line.product_id or line.display_type:
                line.margin_value = 0.0
            # line.margin_value = 0.0

    @api.onchange('discount', 'price_unit', 'quantity')
    def _check_discount(self):
        if self.env.user.company_id.country_id.code == "AO":
            for dic in self:
                if dic.discount < 0 or dic.discount > 100:
                    raise ValidationError(_("o valor do desconto na linha da factura deve estar entre 0 and 100 %."))
                if dic.price_unit < 0:
                    raise ValidationError(_("O valor do preço unitário tem que ser maior que zero"))
                if dic.quantity < 0:
                    raise ValidationError(_("the quantity value must not be negative"))

    @api.depends('quantity', 'discount', 'price_unit', 'tax_ids', 'currency_id', 'margin_value')
    def _compute_totals(self):
        for line in self:
            if line.display_type != 'product':
                line.price_total = line.price_subtotal = False
            # Compute 'price_subtotal'.
            margin_value = 0
            if line.margin_value > 0:
                amount = line.tax_ids.filtered(
                    lambda r: not r.tax_exigibility == 'on_payment' and r.margin_affect).amount
                margin_value = line.price_unit * (line.margin_value / 100)
                margin_value = margin_value + (margin_value * (amount / 100 if amount else 0))
            line_discount_price_unit = (line.price_unit * (1 - (line.discount / 100.0))) + margin_value
            subtotal = line.quantity * line_discount_price_unit

            # Compute 'price_total'.
            if line.tax_ids:
                taxes_res = line.tax_ids.compute_all(
                    line_discount_price_unit,
                    quantity=line.quantity,
                    currency=line.currency_id,
                    product=line.product_id,
                    partner=line.partner_id,
                    is_refund=line.is_refund,
                )
                line.price_subtotal = taxes_res['total_excluded']
                line.price_total = taxes_res['total_included']
            else:
                line.price_total = line.price_subtotal = subtotal

    @api.depends('tax_ids', 'currency_id', 'partner_id', 'analytic_distribution', 'balance', 'partner_id',
                 'move_id.partner_id', 'price_unit', 'quantity')
    def _compute_all_tax(self):
        for line in self:
            sign = line.move_id.direction_sign
            if line.display_type == 'tax':
                line.compute_all_tax = {}
                line.compute_all_tax_dirty = False
                continue
            if line.display_type == 'product' and line.move_id.is_invoice(True):
                # L10N_AO CALCULO DE TOTAL DE IMPOSTO E INCLUI O VALOR DA MARGEM E DO IMPOSTO INDUSTRIAL SOBRE A MARGEM SE EXISTIR
                margin = line.price_unit * (line.margin_value / 100)
                amount = line.tax_ids.filtered(
                    lambda r: r.tax_exigibility == 'on_invoice' and r.margin_affect).amount or 0
                margin = margin + (margin * (amount / 100))
                amount_currency = (sign * (line.price_unit + margin)) * (1 - line.discount / 100)
                handle_price_include = True
                quantity = line.quantity
            else:
                amount_currency = line.amount_currency
                handle_price_include = False
                quantity = 1
            compute_all_currency = line.tax_ids.compute_all(
                amount_currency,
                currency=line.currency_id,
                quantity=quantity,
                product=line.product_id,
                partner=line.move_id.partner_id or line.partner_id,
                is_refund=line.is_refund,
                handle_price_include=handle_price_include,
                include_caba_tags=line.move_id.always_tax_exigible,
                fixed_multiplicator=sign,
            )
            rate = line.amount_currency / line.balance if line.balance else 1
            line.compute_all_tax_dirty = True
            line.compute_all_tax = {
                frozendict({
                    'tax_repartition_line_id': tax['tax_repartition_line_id'],
                    'group_tax_id': tax['group'] and tax['group'].id or False,
                    'account_id': tax['account_id'] or line.account_id.id,
                    'currency_id': line.currency_id.id,
                    'analytic_distribution': (tax['analytic'] or not tax[
                        'use_in_tax_closing']) and line.analytic_distribution,
                    'tax_ids': [(6, 0, tax['tax_ids'])],
                    'tax_tag_ids': [(6, 0, tax['tag_ids'])],
                    'partner_id': line.move_id.partner_id.id or line.partner_id.id,
                    'move_id': line.move_id.id,
                    'display_type': line.display_type,
                }): {
                    'name': tax['name'] + (' ' + _('(Discount)') if line.display_type == 'epd' else ''),
                    'balance': tax['amount'] / rate,
                    'amount_currency': tax['amount'],
                    'tax_base_amount': tax['base'] / rate * (-1 if line.tax_tag_invert else 1),
                }
                for tax in compute_all_currency['taxes']
                if tax['amount']
            }
            if not line.tax_repartition_line_id:
                line.compute_all_tax[frozendict({'id': line.id})] = {
                    'tax_tag_ids': [(6, 0, compute_all_currency['base_tags'])],
                }

    @api.model
    def _get_default_tax_account(self, repartition_line):
        '''AG Override of this method to make the payment account to use the repartition line account_id'''
        tax = repartition_line.invoice_tax_id or repartition_line.refund_tax_id
        if tax.tax_exigibility == 'on_payment' and not self.company_id.country_id.code == "AO":
            account = tax.cash_basis_transition_account_id
        else:
            account = repartition_line.account_id
        return account

    def reconcile(self):
        ''' Reconcile the current move lines all together.
        :return: A dictionary representing a summary of what has been done during the reconciliation:
                * partials:             A recorset of all account.partial.reconcile created during the reconciliation.
                * exchange_partials:    A recorset of all account.partial.reconcile created during the reconciliation
                                        with the exchange difference journal entries.
                * full_reconcile:       An account.full.reconcile record created when there is nothing left to reconcile
                                        in the involved lines.
                * tax_cash_basis_moves: An account.move recordset representing the tax cash basis journal entries.
        '''
        results = {'exchange_partials': self.env['account.partial.reconcile']}

        if not self:
            return results

        not_paid_invoices = self.move_id.filtered(lambda move:
                                                  move.is_invoice(include_receipts=True)
                                                  and move.payment_state not in ('paid', 'in_payment')
                                                  )

        # ==== Check the lines can be reconciled together ====
        company = None
        account = None
        for line in self:
            if line.reconciled:
                raise UserError(_("You are trying to reconcile some entries that are already reconciled."))
            if not line.account_id.reconcile and line.account_id.account_type not in (
                    'asset_cash', 'liability_credit_card'):
                raise UserError(
                    _("Account %s does not allow reconciliation. First change the configuration of this account to allow it.")
                    % line.account_id.display_name)
            if line.move_id.state != 'posted':
                raise UserError(_('You can only reconcile posted entries.'))
            if company is None:
                company = line.company_id
            elif line.company_id != company:
                raise UserError(_("Entries doesn't belong to the same company: %s != %s")
                                % (company.display_name, line.company_id.display_name))
            if account is None:
                account = line.account_id
            elif line.account_id != account:
                raise UserError(_("Entries are not from the same account: %s != %s")
                                % (account.display_name, line.account_id.display_name))

        sorted_lines = self.sorted(
            key=lambda line: (line.date_maturity or line.date, line.currency_id, line.amount_currency))

        # ==== Collect all involved lines through the existing reconciliation ====

        involved_lines = sorted_lines._all_reconciled_lines()
        involved_partials = involved_lines.matched_credit_ids | involved_lines.matched_debit_ids

        # ==== Create partials ====

        partial_no_exch_diff = bool(
            self.env['ir.config_parameter'].sudo().get_param('account.disable_partial_exchange_diff'))
        sorted_lines_ctx = sorted_lines.with_context(
            no_exchange_difference=self._context.get('no_exchange_difference') or partial_no_exch_diff)
        partials = sorted_lines_ctx._create_reconciliation_partials()
        results['partials'] = partials
        involved_partials += partials
        exchange_move_lines = partials.exchange_move_id.line_ids.filtered(lambda line: line.account_id == account)
        involved_lines += exchange_move_lines
        exchange_diff_partials = exchange_move_lines.matched_debit_ids + exchange_move_lines.matched_credit_ids
        involved_partials += exchange_diff_partials
        results['exchange_partials'] += exchange_diff_partials

        # ==== Create entries for cash basis taxes ====
        # AG: Alteração pare não aplicar o cash basis.
        is_cash_basis_needed = account.company_id.tax_exigibility and account.account_type in (
            'asset_receivable', 'liability_payable')
        if self.company_id.country_id.code != "AO":
            if is_cash_basis_needed and not self._context.get('move_reverse_cancel'):
                tax_cash_basis_moves = partials._create_tax_cash_basis_moves()
                results['tax_cash_basis_moves'] = tax_cash_basis_moves

        # ==== Check if a full reconcile is needed ====

        def is_line_reconciled(line, has_multiple_currencies):
            # Check if the journal item passed as parameter is now fully reconciled.
            return line.reconciled \
                or (line.company_currency_id.is_zero(line.amount_residual)
                    if has_multiple_currencies
                    else line.currency_id.is_zero(line.amount_residual_currency)
                    )

        has_multiple_currencies = len(involved_lines.currency_id) > 1
        if all(is_line_reconciled(line, has_multiple_currencies) for line in involved_lines):
            # ==== Create the exchange difference move ====
            # This part could be bypassed using the 'no_exchange_difference' key inside the context. This is useful
            # when importing a full accounting including the reconciliation like Winbooks.

            exchange_move = self.env['account.move']
            caba_lines_to_reconcile = None
            if not self._context.get('no_exchange_difference'):
                # In normal cases, the exchange differences are already generated by the partial at this point meaning
                # there is no journal item left with a zero amount residual in one currency but not in the other.
                # However, after a migration coming from an older version with an older partial reconciliation or due to
                # some rounding issues (when dealing with different decimal places for example), we could need an extra
                # exchange difference journal entry to handle them.
                exchange_lines_to_fix = self.env['account.move.line']
                amounts_list = []
                exchange_max_date = date.min
                for line in involved_lines:
                    if not line.company_currency_id.is_zero(line.amount_residual):
                        exchange_lines_to_fix += line
                        amounts_list.append({'amount_residual': line.amount_residual})
                    elif not line.currency_id.is_zero(line.amount_residual_currency):
                        exchange_lines_to_fix += line
                        amounts_list.append({'amount_residual_currency': line.amount_residual_currency})
                    exchange_max_date = max(exchange_max_date, line.date)
                exchange_diff_vals = exchange_lines_to_fix._prepare_exchange_difference_move_vals(
                    amounts_list,
                    company=involved_lines[0].company_id,
                    exchange_date=exchange_max_date,
                )

                # Exchange difference for cash basis entries.
                if is_cash_basis_needed:
                    caba_lines_to_reconcile = involved_lines._add_exchange_difference_cash_basis_vals(
                        exchange_diff_vals)

                # Create the exchange difference.
                if exchange_diff_vals['move_vals']['line_ids']:
                    exchange_move = involved_lines._create_exchange_difference_move(exchange_diff_vals)
                    if exchange_move:
                        exchange_move_lines = exchange_move.line_ids.filtered(lambda line: line.account_id == account)

                        # Track newly created lines.
                        involved_lines += exchange_move_lines

                        # Track newly created partials.
                        exchange_diff_partials = exchange_move_lines.matched_debit_ids \
                                                 + exchange_move_lines.matched_credit_ids
                        involved_partials += exchange_diff_partials
                        results['exchange_partials'] += exchange_diff_partials

            # ==== Create the full reconcile ====
            results['full_reconcile'] = self.env['account.full.reconcile'].create({
                'exchange_move_id': exchange_move and exchange_move.id,
                'partial_reconcile_ids': [(6, 0, involved_partials.ids)],
                'reconciled_line_ids': [(6, 0, involved_lines.ids)],
            })

            # === Cash basis rounding autoreconciliation ===
            # In case a cash basis rounding difference line got created for the transition account, we reconcile it with the corresponding lines
            # on the cash basis moves (so that it reaches full reconciliation and creates an exchange difference entry for this account as well)

            if caba_lines_to_reconcile:
                for (dummy, account, repartition_line), amls_to_reconcile in caba_lines_to_reconcile.items():
                    if not account.reconcile:
                        continue

                    exchange_line = exchange_move.line_ids.filtered(
                        lambda l: l.account_id == account and l.tax_repartition_line_id == repartition_line
                    )

                    (exchange_line + amls_to_reconcile).filtered(lambda l: not l.reconciled).reconcile()

        not_paid_invoices.filtered(lambda move:
                                   move.payment_state in ('paid', 'in_payment')
                                   )._invoice_paid_hook()

        return results

    @api.model
    def _get_price_total_and_subtotal_model(self, price_unit, quantity, discount, currency, product, partner, taxes,
                                            move_type):
        ''' This method is used to compute 'price_total' & 'price_subtotal'.

        :param price_unit:  The current price unit.
        :param quantity:    The current quantity.
        :param discount:    The current discount.
        :param currency:    The line's currency.
        :param product:     The line's product.
        :param partner:     The line's partner.
        :param taxes:       The applied taxes.
        :param move_type:   The type of the move.
        :return:            A dictionary containing 'price_subtotal' & 'price_total'.
        '''
        res = {}

        # Compute 'price_subtotal'.
        line_discount_price_unit = price_unit * (1 - (discount / 100.0))
        subtotal = quantity * line_discount_price_unit

        # Compute 'price_total'.
        if taxes:
            force_sign = -1 if move_type in ('out_invoice', 'in_refund', 'out_receipt') else 1
            taxes = taxes.filtered(lambda t: not t.invoice_not_affected)
            taxes_res = taxes._origin.with_context(force_sign=force_sign).compute_all(line_discount_price_unit,
                                                                                      quantity=quantity,
                                                                                      currency=currency,
                                                                                      product=product, partner=partner,
                                                                                      is_refund=move_type in (
                                                                                          'out_refund', 'in_refund'))
            res['price_subtotal'] = taxes_res['total_excluded']
            res['price_total'] = taxes_res['total_included']
        else:
            res['price_total'] = res['price_subtotal'] = subtotal
        # In case of multi currency, round before it's use for computing debit credit
        if currency:
            res = {k: currency.round(v) for k, v in res.items()}
        return res

    def write(self, vals):
        result = super().write(vals)
        for line in self:
            vals['journal_ao_id'] = line.journal_id.journal_ao_id.id
        return super().write(vals)

    def _is_vendor_bill_line(self):
        vendor_types = {'in_invoice', 'in_refund'}
        return self and all(line.move_id and line.move_id.move_type in vendor_types for line in self)

    #função para remoção de campos protegidos ao criar fatura de fornecedor
    def _get_integrity_hash_fields(self):
        """
        Remove 'account_id' (Conta) e 'name' (Descrição) e (product_id) do conjunto de
        campos protegidos para linhas de fatura de fornecedor.
        """
        fields_list = super()._get_integrity_hash_fields()

        if self._is_vendor_bill_line():
            drop = {'account_id', 'name','partner_id'}
            fields_list = [f for f in fields_list if f not in drop]
        return fields_list
