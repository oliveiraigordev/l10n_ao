from odoo import models, api, fields, _, Command
from odoo.tools.misc import formatLang, format_date, get_lang
from odoo.exceptions import RedirectWarning, UserError, ValidationError
from . import amount_currency_translate_pt
from odoo.addons.l10n_ao.sign import sign


class AccountPaymentAO(models.Model):
    _inherit = "account.payment"

    # TODO: é necessário validar se vamos ter outra opção para além de RC
    # saft_payment_type = fields.Selection(string="Payment Type", help="Tipo de recibo",
    #                                 selection=[('RC', 'Recibo emitido'), ('AR', 'Aviso de cobrança'),
    #                                            ('RG', 'Outros recibos emitidos')], default='RC' , required=True)

    payment_mechanism = fields.Selection(string="Payment Mechanism",
                                         selection=[('CC', 'Cartão crédito'), ('CD', 'Cartão débito'),
                                                    ('CI', 'Crédito documentário internacional'),
                                                    ('CO', 'Cheque ou cartão oferta'),
                                                    ('CS', 'Compensação de saldos em conta corrente'),
                                                    ('DE',
                                                     'Dinheiro electrónico,por exemplo residente em cartões de fidelidade ou de pontos'),
                                                    ('MB', 'Referências de pagamento para Multicaixa'),
                                                    ('NU', 'Numerário'),
                                                    ('OU', 'Outros meios aqui não assilados'),
                                                    ('PR', 'Permuta de bens'),
                                                    ('TB', 'Transferência bancária')])

    amount_wth = fields.Monetary(_("Amount w/ Withhold"), currency_field='currency_id',
                                 compute="_compute_amount_withhold",
                                 store=True)
    wth_amount = fields.Monetary(_("Withhold Amount"),
                                 compute="_compute_amount_withhold",
                                 currency_field='currency_id',
                                 readonly=True, store=True)
    current_wth = fields.Monetary(_("Applied Withhold"), currency_field='currency_id',
                                  compute="_compute_amount_withhold",
                                  store=True)
    sequence_number = fields.Integer("Sequence Number", copy=False, readonly=True)
    amount_text = fields.Char(_("Amount in Words"), compute="_get_amount_in_words", store=True)
    print_counter = fields.Integer("Control Number of printing", default=0)
    approved = fields.Boolean("approved", default=False)
    payment_number = fields.Char(string='Number', copy=False, readonly=False)
    partner_name = fields.Char("Name", compute='set_customer_data', store=True)
    partner_street = fields.Char("Street", compute='set_customer_data', store=True)
    partner_street2 = fields.Char("Street2", compute='set_customer_data', store=True)
    partner_city = fields.Char("City", compute='set_customer_data', store=True)
    partner_state = fields.Char("State", compute='set_customer_data', store=True)
    partner_vat = fields.Char("NIF", compute='set_customer_data', store=True)
    iva_regime = fields.Char("IVA Regime", compute='set_customer_data', store=True)
    hash = fields.Char(string="Hash", copy=False, readonly=True)
    hash_control = fields.Char(string="Hash Control", default="0", copy=False)
    hash_to_sign = fields.Char(string="Hash to sign", copy=False)
    saft_status_date = fields.Datetime("SAFT Status Date", copy=False)
    system_entry_date = fields.Datetime("Signature Datetime", copy=False)

    def write(self, vals):
        for payment in self:
            if payment.state == 'posted' and not payment.approved and payment.payment_type == 'outbound':
                vals['payment_number'] = payment.env['ir.sequence'].with_company(payment.company_id.id).next_by_code(
                    'account.payment.supplier', payment.date)
                vals['approved'] = True
                vals['sequence_number'] = vals['payment_number'].split("/")[1]
                payments = super().write(vals)
                vals['hash_to_sign'] = payment.get_new_content_to_sign()
                content_signed = payment.sign_document(vals['hash_to_sign']).split(";")
                if vals['hash_to_sign'] != content_signed:
                    vals[
                        'hash_control'] = 0  # content_signed[1] if len(content_signed) >= 1 else "0" TODO: QUANDO OBTER A VALIDAÇÃO DEVO DESCOMENTAR ISTO E PASSAR O HAS_CONTROL  A 1
                    vals['hash'] = content_signed[0]

            elif payment.state == 'posted' and not payment.approved and payment.payment_type == 'inbound':
                vals['payment_number'] = payment.env['ir.sequence'].with_company(payment.company_id.id).next_by_code(
                    'account.payment', payment.date)
                vals['approved'] = True
                vals['sequence_number'] = vals['payment_number'].split("/")[1]
                payments = super().write(vals)
                vals['hash_to_sign'] = payment.get_new_content_to_sign()
                content_signed = payment.sign_document(vals['hash_to_sign']).split(";")
                if vals['hash_to_sign'] != content_signed:
                    vals[
                        'hash_control'] = 0  # content_signed[1] if len(content_signed) >= 1 else "0" TODO: QUANDO OBTER A VALIDAÇÃO DEVO DESCOMENTAR ISTO E PASSAR O HAS_CONTROL  A 1
                    vals['hash'] = content_signed[0]
            return super().write(vals)

    def sign_document(self, content_data):
        response = ''
        if content_data:
            response = sign.sign_content(content_data)
        if response:
            return response
        return content_data

    def get_new_content_to_sign(self):
        content_to_sign = ""
        if self.sequence_number - 1 >= 1:
            preview_last_payment = self.sudo().search([('state', 'in', ['posted']),
                                                       ('id', "!=", self.id),
                                                       ('company_id', '=', self.company_id.id),
                                                       ('date', '<=', self.date),
                                                       ('payment_type', '=', self.payment_type),
                                                       ('system_entry_date', '<=', self.system_entry_date),
                                                       ('sequence_number', '=', self.sequence_number - 1)],
                                                      order="system_entry_date desc", limit=1)
            if preview_last_payment:
                get_last_order_hash = preview_last_payment.hash if preview_last_payment.hash else ""
                system_entry_date = self.system_entry_date.isoformat(sep='T',
                                                                     timespec='auto') if self.system_entry_date else fields.Datetime.now().isoformat(
                    sep='T', timespec='auto')
                content_to_sign = ";".join((fields.Date.to_string(self.date), system_entry_date,
                                            self.payment_number, str(format(self.amount, '.2f')),
                                            get_last_order_hash))
        elif self.sequence_number - 1 == 0:
            system_entry_date = self.system_entry_date.isoformat(sep='T',
                                                                 timespec='auto') if self.system_entry_date else fields.Datetime.now().isoformat(
                sep='T', timespec='auto')
            content_to_sign = ";".join((fields.Date.to_string(self.date), system_entry_date,
                                        self.payment_number, str(format(self.amount, '.2f')), ""))
        return content_to_sign

    @api.depends('amount', 'move_id')
    def _get_amount_in_words(self):
        for pay in self:
            currency_name = "AOA"
            if pay.amount > 0 and pay.currency_id:
                if pay.currency_id.name == "AOA":
                    currency_name = "Kwanzas"
                if pay.currency_id.name == "EUR":
                    currency_name = "Euros"
                if pay.currency_id.name == "USD":
                    currency_name = "Dolares Americanos"
                pay.amount_text = amount_currency_translate_pt.amount_to_text(pay.amount, currency_name)

    @api.constrains('partner_id', 'partner_type', 'state')
    def set_customer_data(self):
        for pt in self:
            if pt.state == "draft":
                pt.write({
                    'partner_name': pt.partner_id.display_name,
                    'partner_street': pt.partner_id.street,
                    'partner_street2': pt.partner_id.street2,
                    'partner_state': pt.partner_id.state_id.name,
                    'partner_city': pt.partner_id.city,
                    'partner_vat': pt.partner_id.vat,
                    'iva_regime': pt.company_id.tax_regime_id.name
                })

    @api.depends("amount")
    def _compute_amount_withhold(self):
        amount_tax_wth = 0.0
        residual_rate = 1.0
        invoice_moves = self.env['account.move'].browse(self._context.get('active_ids', []))
        total_amount_residual = sum(invoice_moves.mapped("amount_residual"))
        for inv in self:
            for invoice in invoice_moves:
                residual_rate = 1 - (invoice.amount_total - invoice.amount_residual) / (invoice.amount_total or 1)
                for line in invoice.invoice_line_ids:
                    for tax in line.tax_ids:
                        tax_base_amount = line.price_unit * line.quantity
                        if tax.tax_exigibility == 'on_payment' and tax.is_withholding and \
                                tax_base_amount >= tax.limit_amount_wth:
                            # Tax amount.
                            tax_amount = tax._compute_amount(line.price_unit * line.quantity, line.price_unit,
                                                             line.quantity)
                            amount_tax_wth += abs(tax_amount) * residual_rate

            payment_rate = inv.amount == 0.0 and 0.0 or (inv.amount / (total_amount_residual - amount_tax_wth or 1))
            if amount_tax_wth == total_amount_residual:
                payment_rate = 0
            if payment_rate > 1:
                payment_rate = 1

            inv.wth_amount = amount_tax_wth
            inv.current_wth = amount_tax_wth * payment_rate

    def get_saft_data(self):

        result = {
            'Payments': {
                "NumberOfEntries": 0,
                "TotalDebit": 0,
                "TotalCredit": 0,
                "Payment": [],
            }
        }

        payments = self.filtered(lambda r: r.state in ['posted', 'cancel'] and r.payment_type == 'inbound')
        for payment in payments:
            payment_status = 'N'
            if payment.state == 'cancelled':
                payment_status = 'A'
            line = payment.reconciled_invoice_ids.mapped("invoice_line_ids")

            payment_saft = {

                "PaymentRefNo": payment.payment_reference,
                "Period": int(fields.Date.to_string(payment.date)[5:7]),
                "TransactionID": payment.id,
                "TransactionDate": fields.Date.to_string(payment.date),
                "PaymentType": 'RC',
                # "Description": payment.payment_reference,
                # "SystemID": payment.name,
                "DocumentStatus": {
                    "PaymentStatus": payment_status,
                    "PaymentStatusDate": fields.Date.to_string(payment.date),
                    "Reason": "",
                    "SourceID": payment.create_uid.id,
                    "SourcePayment": 'P',

                },
                "PaymentMethod": {
                    "PaymentMechanism": payment.payment_mechanism if payment.payment_mechanism else "MB",
                    "PaymentAmount": payment.amount,
                    "PaymentDate": fields.Date.to_string(payment.date),
                },
                "SourceID": payment.create_uid.id,
                "SystemEntryDate": fields.Date.to_string(payment.system_entry_date),
                "CustomerID": payment.partner_id.id,
                "Line": [
                    {
                        "LineNumber": inv.id,
                        "SourceDocumentID": {
                            "OriginatingON": inv.name,
                            "InvoiceDate": fields.Date.to_string(inv.invoice_date),
                            "Description": inv.reference,
                        },
                        "SettlementAmount": "",
                        "DebitAmount": line.price_subtotal if inv.type == "out_refund" else 0,
                        "CreditAmount": line.price_subtotal if inv.type == "out_invoice" else 0,
                        "Tax": [{
                            "TaxType": tax.tax_id.saft_tax_type,
                            "TaxCountryRegion": "AO",
                            "TaxCode": tax.tax_id.saft_tax_code,
                            "TaxPercentage": tax.tax_id.amount if tax.tax_id.amount_type in ["percent",
                                                                                             "division"] else "",
                            "TaxAmount": tax.tax_id.amount,

                        } for tax in inv.tax_line_ids],
                        "TaxExemptionReason": inv.invoice_line_ids.tax_ids.filtered(
                            lambda r: r.amount == 0)[0].reason if inv.tax_line_ids.filtered(
                            lambda r: r.amount == 0) else "",
                        "TaxExemptionCode": inv.tax_line_ids.filtered(
                            lambda r: r.amount == 0)[0].saft_tax_code if inv.tax_line_ids.filtered(
                            lambda r: r.amount == 0) else "",

                    } for inv in payment.reconciled_invoice_ids],
                "DocumentTotals": [{

                    "TaxPayable": inv.amount_tax,
                    "NetTotal": inv.amount_untaxed,
                    "GrossTotal": inv.amount_total,
                    "Settlement": {

                        "SettlementAmount": "",

                    },
                    "Currency": {

                        "CurrencyCode": inv.currency_id.name,
                        "CurrencyAmount": inv.amount_total,
                        "ExchangeRate": inv.currency_id.rate
                    } if inv.currency_id != inv.company_id.currency_id else {}
                } for inv in payment.reconciled_invoice_ids],
                #
                #     "WithholdingTax": [{
                #
                #         "WithholdingTaxType": tax.tax_id.saft_wth_type,
                #         "WithholdingTaxDescription": tax.tax_id.name,
                #         "WithholdingTaxAmount": tax.amount,
                #
                #     } for inv in payment.reconciled_invoice_ids for tax in
                #         inv.tax_line_ids.filtered(lambda r: r.tax_id.tax_on == "withholding")],
                #
            }
            for inv in payment.reconciled_invoice_ids:
                result["Payments"]["TotalDebit"] += inv.amount_total if inv.type == "out_refund" and inv.state in [
                    "open", "paid"] else 0
                result["Payments"]["TotalCredit"] += inv.amount_total if inv.type == "out_invoice" and inv.state in [
                    "open", "paid"] else 0
            result['Payments']['Payment'].append(payment_saft)
        result['Payments']['NumberOfEntries'] = len(payments)

        return result

    # AG: The override of this method it's need to avoid that because of the extra lines, odoo will understand that
    # those lines represents write_off instead of a normal tax move line. We need to do this for the taxes on payment

    def _prepare_move_line_default_vals_old_method(self, write_off_line_vals=None):
        ''' Prepare the dictionary to create the default account.move.lines for the current payment.
        :param write_off_line_vals: Optional dictionary to create a write-off account.move.line easily containing:
            * amount:       The amount to be added to the counterpart amount.
            * name:         The label to set on the line.
            * account_id:   The account on which create the write-off.
        :return: A list of python dictionary to be passed to the account.move.line's 'create' method.
        '''
        self.ensure_one()
        write_off_line_vals = write_off_line_vals or {}

        if not self.journal_id.payment_debit_account_id or not self.journal_id.payment_credit_account_id:
            raise UserError(_(
                "You can't create a new payment without an outstanding payments/receipts account set on the %s journal.",
                self.journal_id.display_name))

        # Compute amounts.
        write_off_amount_currency = write_off_line_vals.get('amount', 0.0)

        if self.payment_type == 'inbound':
            # Receive money.
            liquidity_amount_currency = self.amount
        elif self.payment_type == 'outbound':
            # Send money.
            liquidity_amount_currency = -self.amount
            write_off_amount_currency *= -1
        else:
            liquidity_amount_currency = write_off_amount_currency = 0.0

        write_off_balance = self.currency_id._convert(
            write_off_amount_currency,
            self.company_id.currency_id,
            self.company_id,
            self.date,
        )
        liquidity_balance = self.currency_id._convert(
            liquidity_amount_currency,
            self.company_id.currency_id,
            self.company_id,
            self.date,
        )
        counterpart_amount_currency = -liquidity_amount_currency - write_off_amount_currency
        counterpart_balance = -liquidity_balance - write_off_balance
        currency_id = self.currency_id.id

        if self.is_internal_transfer:
            if self.payment_type == 'inbound':
                liquidity_line_name = _('Transfer to %s', self.journal_id.name)
            else:  # payment.payment_type == 'outbound':
                liquidity_line_name = _('Transfer from %s', self.journal_id.name)
        else:
            liquidity_line_name = self.payment_reference

        # Compute a default label to set on the journal items.

        payment_display_name = {
            'outbound-customer': _("Customer Reimbursement"),
            'inbound-customer': _("Customer Payment"),
            'outbound-supplier': _("Vendor Payment"),
            'inbound-supplier': _("Vendor Reimbursement"),
        }

        default_line_name = self.env['account.move.line']._get_default_line_name(
            _("Internal Transfer") if self.is_internal_transfer else payment_display_name[
                '%s-%s' % (self.payment_type, self.partner_type)],
            self.amount,
            self.currency_id,
            self.date,
            partner=self.partner_id,
        )

        # AG: Customization to allow add the processing of withholding tax
        retention_balance = 0
        tax_payment_lines = {}
        if not self.is_internal_transfer:
            tax_payment_lines = self._prepare_invoice_payment_taxes_vals()
            retention_debit = sum([tax["debit"] for tax in tax_payment_lines])
            retention_credit = sum([tax["credit"] for tax in tax_payment_lines])
            retention_balance = retention_debit - retention_credit

        line_vals_list = [
            # Liquidity line.
            {
                'name': liquidity_line_name or default_line_name,
                'date_maturity': self.date,
                'amount_currency': liquidity_amount_currency,
                'currency_id': currency_id,
                'debit': liquidity_balance if liquidity_balance > 0.0 else 0.0,
                'credit': -liquidity_balance if liquidity_balance < 0.0 else 0.0,
                'partner_id': self.partner_id.id,
                'account_id': self.journal_id.payment_credit_account_id.id if liquidity_balance < 0.0 else self.journal_id.payment_debit_account_id.id,
            },
            # Receivable / Payable.
            {
                'name': self.payment_reference or default_line_name,
                'date_maturity': self.date,
                'amount_currency': counterpart_amount_currency - retention_balance + write_off_amount_currency if currency_id else 0.0,
                'currency_id': currency_id,
                'debit': counterpart_balance - retention_balance if counterpart_balance > 0.0 else 0.0,
                'credit': -counterpart_balance + retention_balance if counterpart_balance < 0.0 else 0.0,
                'partner_id': self.partner_id.id,
                'account_id': self.destination_account_id.id,
            },
        ]

        # AG Add withholding taxes move lines to the list of moves
        if not self.is_internal_transfer and tax_payment_lines:
            line_vals_list.extend(tax_payment_lines)

        if not self.currency_id.is_zero(write_off_amount_currency):
            # Write-off line.
            line_vals_list.append({
                'name': write_off_line_vals.get('name') or default_line_name,
                'amount_currency': write_off_amount_currency,
                'currency_id': currency_id,
                'debit': write_off_balance if write_off_balance > 0.0 else 0.0,
                'credit': -write_off_balance if write_off_balance < 0.0 else 0.0,
                'partner_id': self.partner_id.id,
                'account_id': write_off_line_vals.get('account_id'),
            })
        return line_vals_list

    def _prepare_move_line_default_vals(self, write_off_line_vals=None):
        ''' Prepare the dictionary to create the default account.move.lines for the current payment.
        :param write_off_line_vals: Optional list of dictionaries to create a write-off account.move.line easily containing:
            * amount:       The amount to be added to the counterpart amount.
            * name:         The label to set on the line.
            * account_id:   The account on which create the write-off.
        :return: A list of python dictionary to be passed to the account.move.line's 'create' method.
        '''
        self.ensure_one()
        write_off_line_vals = write_off_line_vals or {}

        if not self.outstanding_account_id:
            raise UserError(_(
                "You can't create a new payment without an outstanding payments/receipts account set either on the company or the %s payment method in the %s journal.",
                self.payment_method_line_id.name, self.journal_id.display_name))

        # Compute amounts.
        write_off_line_vals_list = write_off_line_vals or []
        write_off_amount_currency = sum(x['amount_currency'] for x in write_off_line_vals_list)
        write_off_balance = sum(x['balance'] for x in write_off_line_vals_list)

        if self.payment_type == 'inbound':
            # Receive money.
            liquidity_amount_currency = self.amount
        elif self.payment_type == 'outbound':
            # Send money.
            liquidity_amount_currency = -self.amount
        else:
            liquidity_amount_currency = 0.0

        liquidity_balance = self.currency_id._convert(
            liquidity_amount_currency,
            self.company_id.currency_id,
            self.company_id,
            self.date,
        )
        counterpart_amount_currency = -liquidity_amount_currency - write_off_amount_currency
        counterpart_balance = -liquidity_balance - write_off_balance
        currency_id = self.currency_id.id

        # Compute a default label to set on the journal items.
        liquidity_line_name = ''.join(x[1] for x in self._get_liquidity_aml_display_name_list())
        counterpart_line_name = ''.join(x[1] for x in self._get_counterpart_aml_display_name_list())

        # AG: Customization to allow add the processing of withholding tax
        retention_balance = 0
        tax_payment_lines = {}
        if not self.is_internal_transfer:
            tax_payment_lines = self._prepare_invoice_payment_taxes_vals()
            retention_debit = sum([tax["debit"] for tax in tax_payment_lines])
            retention_credit = sum([tax["credit"] for tax in tax_payment_lines])
            retention_balance = retention_debit - retention_credit

        line_vals_list = [
            # Liquidity line.
            {
                'name': liquidity_line_name,
                'date_maturity': self.date,
                'amount_currency': liquidity_amount_currency,
                'currency_id': currency_id,
                'debit': liquidity_balance if liquidity_balance > 0.0 else 0.0,
                'credit': -liquidity_balance if liquidity_balance < 0.0 else 0.0,
                'partner_id': self.partner_id.id,
                'account_id': self.outstanding_account_id.id,
            },
            # Receivable / Payable.
            # AG: To add withholding amount
            {
                'name': counterpart_line_name,
                'date_maturity': self.date,
                'amount_currency': counterpart_amount_currency - retention_balance if currency_id else 0.0,
                'currency_id': currency_id,
                'debit': counterpart_balance - retention_balance if counterpart_balance > 0.0 else 0.0,
                'credit': -counterpart_balance + retention_balance if counterpart_balance < 0.0 else 0.0,
                'partner_id': self.partner_id.id,
                'account_id': self.destination_account_id.id,
            },
        ]

        # AG Add withholding taxes move lines to the list of moves
        if not self.is_internal_transfer and tax_payment_lines:
            line_vals_list.extend(tax_payment_lines)

        return line_vals_list + write_off_line_vals_list

    def _compute_invoice_payment_taxes(self):
        ''' This method will create the tax groups to show on the receipt
        '''

        invoice_moves = self.env['account.move'].browse(self._context.get('active_ids', []))
        res = {}
        amount_tax_wth = 0.0
        tax_payment_vals = {}
        for invoice in invoice_moves:
            lang_env = invoice.with_context(lang=invoice.partner_id.lang).env
            tax_balance_multiplicator = -1 if invoice.is_inbound(True) else 1
            residual_rate = 1 - (invoice.amount_total - invoice.amount_residual) / (invoice.amount_total or 1)
            done_taxes = set()
            for line in invoice.invoice_line_ids:
                for tax in line.tax_ids:
                    res.setdefault(tax.tax_group_id, {'base': 0.0, 'amount': 0.0})
                    # res[tax.tax_group_id]["amount"] += tax_balance_multiplicator * (line.amount_currency if line.currency_id else line.balance)
                    tax_key_add_base = tuple([tax.id])
                    tax_base_amount = line.price_unit * line.quantity
                    if tax.tax_exigibility == 'on_payment' and tax.is_withholding and \
                            tax_base_amount >= tax.threshold_wht:
                        # Tax amount.
                        tax_amount = tax._compute_amount(line.price_unit * line.quantity, line.price_unit,
                                                         line.quantity)
                        amount_tax_wth += tax_amount * residual_rate

                        if tax_key_add_base not in done_taxes:
                            if line.currency_id and line.company_currency_id and line.currency_id != line.company_currency_id:
                                amount = line.company_currency_id._convert(line.tax_base_amount, line.currency_id,
                                                                           line.company_id,
                                                                           line.date or fields.Date.context_today(self))
                            else:
                                amount = line.price_unit * line.quantity
                            res[(invoice.id, tax.tax_group_id)]['base'] += amount
                            res[(invoice.id, tax.tax_group_id)]['amount'] += amount_tax_wth
                            # The base should be added ONCE
                            done_taxes.add(tax_key_add_base)

        res = sorted(res.items(), key=lambda l: l[0][1].sequence)

        self.amount_by_group = [(
            group.name, amounts['amount'],
            amounts['base'],
            formatLang(lang_env, amounts['amount'], currency_obj=invoice.currency_id),
            formatLang(lang_env, amounts['base'], currency_obj=invoice.currency_id),
            len(res),
            group.id
        ) for group, amounts in res]

    def _prepare_invoice_payment_taxes_vals(self):
        in_draft_mode = self != self._origin

        @api.model
        def _get_base_amount_to_display(base_amount, tax_rep_ln, parent_tax_group=None):
            """ The base amount returned for taxes by compute_all has is the balance
            of the base line. For inbound operations, positive sign is on credit, so
            we need to invert the sign of this amount before displaying it.
            """
            source_tax = parent_tax_group or tax_rep_ln.invoice_tax_id or tax_rep_ln.refund_tax_id
            if (tax_rep_ln.invoice_tax_id and source_tax.type_tax_use == 'sale') \
                    or (tax_rep_ln.refund_tax_id and source_tax.type_tax_use == 'purchase'):
                return -base_amount
            return base_amount

        def _serialize_tax_grouping_key(grouping_dict):
            ''' Serialize the dictionary values to be used in the taxes_map.
            :param grouping_dict: The values returned by '_get_tax_grouping_key_from_tax_line' or '_get_tax_grouping_key_from_base_line'.
            :return: A string representing the values.
            '''
            return '-'.join(str(v) for v in grouping_dict.values())

        def _compute_base_line_taxes(base_line, handle_price_include=True, include_caba_tags=False,
                                     early_pay_discount_computation=None, early_pay_discount_percentage=None):
            orig_price_unit_after_discount = base_line['price_unit'] * (1 - (base_line['discount'] / 100.0))
            price_unit_after_discount = orig_price_unit_after_discount
            taxes = base_line['taxes']._origin
            currency = base_line['currency'] or self.env.company.currency_id
            rate = base_line['rate']

            if early_pay_discount_computation in ('included', 'excluded'):
                remaining_part_to_consider = (100 - early_pay_discount_percentage) / 100.0
                price_unit_after_discount = remaining_part_to_consider * price_unit_after_discount

            if taxes:

                if handle_price_include is None:
                    manage_price_include = bool(base_line['handle_price_include'])
                else:
                    manage_price_include = handle_price_include

                taxes_res = taxes.with_context(**base_line['extra_context'], on_payment=True,
                                               caba_no_transition_account=True).compute_all(
                    price_unit_after_discount,
                    currency=currency,
                    quantity=base_line['quantity'],
                    product=base_line['product'],
                    partner=base_line['partner'],
                    is_refund=base_line['is_refund'],
                    handle_price_include=manage_price_include,
                    include_caba_tags=include_caba_tags,
                )

                to_update_vals = {
                    'tax_tag_ids': [Command.set(taxes_res['base_tags'])],
                    'price_subtotal': taxes_res['total_excluded'],
                    'price_total': taxes_res['total_included'],
                }

                if early_pay_discount_computation == 'excluded':
                    new_taxes_res = taxes.with_context(**base_line['extra_context']).compute_all(
                        orig_price_unit_after_discount,
                        currency=currency,
                        quantity=base_line['quantity'],
                        product=base_line['product'],
                        partner=base_line['partner'],
                        is_refund=base_line['is_refund'],
                        handle_price_include=manage_price_include,
                        include_caba_tags=include_caba_tags,
                    )
                    for tax_res, new_taxes_res in zip(taxes_res['taxes'], new_taxes_res['taxes']):
                        delta_tax = new_taxes_res['amount'] - tax_res['amount']
                        tax_res['amount'] += delta_tax
                        to_update_vals['price_total'] += delta_tax

                tax_values_list = []
                for tax_res in taxes_res['taxes']:
                    # FIXME: Look to this to see if will not affect other moves.
                    if tax_res['tax_exigibility'] == 'on_payment':
                        tax_amount = tax_res['amount'] / rate
                        if self.company_id.tax_calculation_rounding_method == 'round_per_line':
                            tax_amount = currency.round(tax_amount)
                        tax_rep = self.env['account.tax.repartition.line'].browse(tax_res['tax_repartition_line_id'])

                        tax_values_list.append({
                            **tax_res,
                            'tax_repartition_line': tax_rep,
                            'base_amount_currency': tax_res['base'],
                            'base_amount': currency.round(tax_res['base'] / rate),
                            'tax_amount_currency': tax_res['amount'],
                            'tax_amount': tax_amount,
                        })

            else:
                price_subtotal = currency.round(price_unit_after_discount * base_line['quantity'])
                to_update_vals = {
                    'tax_tag_ids': [Command.clear()],
                    'price_subtotal': price_subtotal,
                    'price_total': price_subtotal,
                }
                tax_values_list = []

            return to_update_vals, tax_values_list

        invoice_moves = self.env['account.move'].browse(
            self._context.get('active_ids', [])) if not self.is_internal_transfer else self.env['account.move']
        total_amount_residual = sum(invoice_moves.mapped("amount_residual"))
        taxes_map = {}
        for invoice in invoice_moves:
            lang_env = invoice.with_context(lang=invoice.partner_id.lang).env
            tax_balance_multiplicator = -1 if invoice.is_inbound(True) else 1
            residual_rate = 1 - (invoice.amount_total - invoice.amount_residual) / (invoice.amount_total or 1)
            done_taxes = set()
            amount_tax_wth = 0.0

            to_remove = self.env['account.move.line']
            amount_tax_wth = (invoice.amount_total - invoice.amount_total_wth) * residual_rate
            payment_rate = self.amount == 0.0 and 0.0 or (self.amount / (invoice.amount_residual - amount_tax_wth or 1))
            if amount_tax_wth == invoice.amount_residual:
                payment_rate = 1
            if payment_rate > 1:
                payment_rate = 1
            sign = 1
            if invoice.move_type in ["in_invoice", "out_refund"]:
                sign = -1
            for line in invoice.invoice_line_ids:
                # Don't call compute_all if there is no tax.
                if not line.tax_ids.filtered(lambda t: t.tax_exigibility == "on_payment"):
                    line.tax_tag_ids = [(5, 0, 0)]
                    continue
                base_line = line._convert_to_tax_base_line_dict()
                to_update_vals, tax_values_list = _compute_base_line_taxes(base_line)
                # compute_all_vals = _compute_base_line_taxes(line)

                # Assign tags on base line
                # line.tax_tag_ids = compute_all_vals['base_tags'] or [(5, 0, 0)]

                for tax_vals in tax_values_list:
                    tax = self.env["account.tax"].browse(tax_vals['id'])[0]
                    if tax.tax_exigibility == 'on_invoice':
                        continue
                    tax_repartition_line = self.env['account.tax.repartition.line'].browse(
                        tax_vals['tax_repartition_line_id'])

                    grouping_dict = {
                        'tax_repartition_line_id': tax_vals['tax_repartition_line_id'],
                        'account_id': tax_repartition_line.account_id.id,
                        'currency_id': line.currency_id.id,
                        # 'analytic_tag_ids': [(6, 0, tax_vals['analytic'] and line.analytic_tag_ids.ids or [])],
                        # 'analytic_account_id': tax_vals['analytic'] and line.analytic_account_id.id,
                        # 'tax_ids': [(6, 0, tax_vals['tax_ids'])],
                        # 'tax_tag_ids': [(6, 0, tax_vals['tag_ids'])],
                        'partner_id': line.partner_id.id,
                    }
                    grouping_key = _serialize_tax_grouping_key(grouping_dict)

                    tax = tax_repartition_line.invoice_tax_id or tax_repartition_line.refund_tax_id

                    if tax.tax_exigibility == 'on_payment':
                        tax_exigible = False

                    taxes_map_entry = taxes_map.setdefault(grouping_key, {
                        'tax_line': None,
                        'amount': 0.0,
                        'tax_base_amount': 0.0,
                        'grouping_dict': False,
                    })
                    taxes_map_entry['amount'] += sign * tax_vals['amount'] * payment_rate * residual_rate
                    taxes_map_entry['tax_base_amount'] += _get_base_amount_to_display(tax_vals['base'],
                                                                                      tax_repartition_line,
                                                                                      tax_vals['group'])
                    taxes_map_entry['grouping_dict'] = grouping_dict

        # ==== Process taxes_map ====
        tax_lines_vals = []
        for taxes_map_entry in taxes_map.values():
            # The tax line is no longer used in any base lines, drop it.
            if taxes_map_entry['tax_line'] and not taxes_map_entry['grouping_dict']:
                self.line_ids -= taxes_map_entry['tax_line']
                continue

            currency = self.env['res.currency'].browse(taxes_map_entry['grouping_dict']['currency_id'])

            # Don't create tax lines with zero balance.
            if currency.is_zero(taxes_map_entry['amount']):
                if taxes_map_entry['tax_line']:
                    self.line_ids -= taxes_map_entry['tax_line']
                continue

            # tax_base_amount field is expressed using the company currency.
            tax_base_amount = currency._convert(taxes_map_entry['tax_base_amount'], self.company_currency_id,
                                                self.company_id, self.date or fields.Date.context_today(self))

            # Recompute only the tax_base_amount.
            if taxes_map_entry['tax_line']:
                taxes_map_entry['tax_line'].tax_base_amount = tax_base_amount
                continue

            balance = currency._convert(
                taxes_map_entry['amount'],
                self.journal_id.company_id.currency_id,
                self.journal_id.company_id,
                self.date or fields.Date.context_today(self),
            )
            to_write_on_line = {
                'amount_currency': taxes_map_entry['amount'],
                'currency_id': taxes_map_entry['grouping_dict']['currency_id'],
                'debit': balance > 0.0 and balance or 0.0,
                'credit': balance < 0.0 and -balance or 0.0,
                'tax_base_amount': tax_base_amount,
            }

            tax_repartition_line_id = taxes_map_entry['grouping_dict']['tax_repartition_line_id']
            tax_repartition_line = self.env['account.tax.repartition.line'].browse(tax_repartition_line_id)
            tax = tax_repartition_line.invoice_tax_id or tax_repartition_line.refund_tax_id
            tax_line = {
                **to_write_on_line,
                'name': tax.name,
                # 'move_id': self.id,
                'partner_id': line.partner_id.id,
                'company_id': line.company_id.id,
                'company_currency_id': line.company_currency_id.id,
                'tax_base_amount': tax_base_amount,
                # 'exclude_from_invoice_tab': True,
                # 'tax_exigible': tax.tax_exigibility == 'on_payment',
                **taxes_map_entry['grouping_dict'],
            }
            tax_lines_vals.append(tax_line)
        return tax_lines_vals

    def action_payment_receipt_sent(self):
        """ Open a window to compose an email, with the edi receipt template
            message loaded by default
        """
        self.ensure_one()
        template = self.env.ref('l10n_ao.mail_template_payment_receipt', False)
        compose_form = self.env.ref('mail.email_compose_message_wizard_form', False)
        ctx = dict(
            default_model='account.payment',
            default_res_id=self.id,
            default_use_template=bool(template),
            default_template_id=template.id,
            default_composition_mode='comment',
            mark_payment_as_sent=True,
        )
        return {
            'name': _('Compose Email'),
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'mail.compose.message',
            'views': [(compose_form.id, 'form')],
            'view_id': compose_form.id,
            'target': 'new',
            'context': ctx,
        }
