from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    is_ip_payment = fields.Boolean(string="Pagamento de IP", default=False)
    is_company = fields.Boolean(related="partner_id.is_company", readonly=True)
    is_industrial_tax = fields.Boolean(string="Imposto Industrial", default=False)
    tax_line_id = fields.Many2one("account.tax", string="Imposto", ondelete="restrict", compute="_compute_tax_line_id")
    partner_accounting_account_id = fields.Many2one("account.account", string="Conta contábil do parceiro", ondelete="restrict", compute="_compute_partner_accounting_account_id", readonly=False)
    post_retention_payment = fields.Boolean(compute="_compute_post_retention_payment")
    retention_payment_ref = fields.Char(string="Ref. Pagamento Retenção", readonly=True, copy=False)
    tax_account_id = fields.Many2one(
        "account.account",
        string="Conta Contábil do Imposto",
        compute="_compute_tax_account_id",
        store=False,
    )
    invoice_id = fields.Many2one(
        'account.move',
        string="Fatura",
    )
    available_invoice_ids = fields.Many2many('account.move', compute="_compute_available_invoices", readonly=True, invisible=True)
    retention_tax_id = fields.Many2one(
        'account.tax',
        string="Retenção aplicada",
        compute='_compute_retention_tax_id',
        store=False
    )
    confirm_retention = fields.Boolean(string="Marcar retenção a pagar")
    attachment = fields.Binary(string='Anexo', copy=False, tracking=True)
    attachment_ids = fields.One2many(
        'ir.attachment', 'res_id',
        domain=[('res_model', '=', 'account.payment')],
        string='Anexo'
    )
    retention_tax_ids = fields.Many2many(
        'account.tax',
        compute='_compute_client_retentions',
        string="Retenções do Cliente"
    )

    @api.depends('invoice_id')
    def _compute_tax_line_id(self):
        for pay in self:
            tax_account_id = pay.invoice_id.line_ids.tax_ids.filtered(lambda t: 'Ret' in t.name).id
            pay.tax_line_id =  tax_account_id

    @api.depends('available_payment_method_line_ids')
    def _compute_payment_method_line_id(self):
        ''' Compute the 'payment_method_line_id' field.
        This field is not computed in '_compute_payment_method_line_fields' because it's a stored editable one.
        '''
        for pay in self:
            if pay.journal_id.type == 'general':
                method_line = self.env['account.payment.method.line'].search([
                    ('payment_type', '=', self.payment_type)
                ], limit=1)
                pay.payment_method_line_id = method_line
            else:
                super()._compute_payment_method_line_id()

    @api.onchange('partner_id')
    def _onchange_partner_id_journal_domain(self):
        domain = [('company_id', '=', self.company_id.id)]
        if self.is_industrial_tax:
            domain += [('type', 'in', ['bank', 'cash', 'general'])]
        else:
            domain += [('type', 'in', ['bank', 'cash'])]

        return {'domain': {'journal_id': domain}}
    
    @api.constrains('payment_method_line_id')
    def _check_payment_method_line_id(self):
        for pay in self:
            if pay.journal_id and pay.journal_id.type == 'general':
                continue

            if not pay.payment_method_line_id:
                raise ValidationError(_("Please define a payment method line on your payment."))

            if (
                pay.payment_method_line_id.journal_id
                and pay.payment_method_line_id.journal_id != pay.journal_id
            ):
                raise ValidationError(_("The selected payment method is not available for this payment, please select the payment method again."))

    @api.depends('retention_tax_id')
    def _compute_post_retention_payment(self):
        for payment in self:
            payment.post_retention_payment = False
            if payment.retention_tax_id:
                payment.post_retention_payment = True

    @api.depends('partner_id')
    def _compute_partner_accounting_account_id(self):
        for payment in self:
            payment.partner_accounting_account_id = payment.partner_id.property_account_receivable_id
            
    @api.depends('amount_total_signed', 'payment_type')
    def _compute_amount_company_currency_signed(self):
        for payment in self:
            liquidity_lines = payment._seek_for_lines()[0]
            payment.amount_company_currency_signed
            
    @api.depends('partner_id')
    def _compute_available_invoices(self):
        for rec in self:
            rec.available_invoice_ids = False
            if not rec.partner_id:
                continue
            invoices = self.env['account.move'].search([
                ('partner_id', '=', rec.partner_id.id),
                ('move_type', 'in', ['out_invoice', 'in_invoice']),
                ('state', '=', 'posted'),
                ('payment_state', 'in', ('partial', 'in_payment')),
                ('retention_paid', '=', False),
            ])
            rec.available_invoice_ids = invoices.filtered(lambda inv: any(
                t for l in inv.invoice_line_ids for t in l.tax_ids if 'Ret' in t.name
            ))

    @api.depends('partner_id')
    def _compute_client_retentions(self):
        for rec in self:
            if rec.partner_id:
                lines = self.env['account.move.line'].search([
                    ('partner_id', '=', rec.partner_id.id),
                    ('tax_ids.name', 'ilike', 'Ret')
                ])
                taxes = self.env['account.tax']
                for line in lines:
                    taxes |= line.tax_ids.filtered(lambda t: 'Ret' in t.name)
                rec.retention_tax_ids = taxes
            else:
                rec.retention_tax_ids = False

    @api.depends('invoice_id')
    def _compute_retention_tax_id(self):
        for rec in self:
            retention = False
            if rec.invoice_id:
                for line in rec.invoice_id.invoice_line_ids:
                    tax = line.tax_ids.filtered(lambda t: 'Ret' in t.name)
                    if tax:
                        retention = tax[0]
                        break
            rec.retention_tax_id = retention

    @api.onchange('invoice_id')
    def _onchange_invoice_data(self):
        self.retention_tax_id = False
        self.amount = 0.0
        if self.invoice_id:
            total = 0.0
            for line in self.invoice_id.invoice_line_ids:
                taxes = line.tax_ids.filtered(lambda t: 'Ret' in t.name)
                if taxes:
                    if not self.retention_tax_id:
                        self.retention_tax_id = taxes[0]
                    total += line.price_subtotal * (taxes[0].amount / 100)
            self.amount = total

    @api.depends('tax_line_id')
    def _compute_tax_account_id(self):
        for rec in self:
            repartitions = rec.tax_line_id.invoice_repartition_line_ids
            account = repartitions.filtered(lambda r: r.account_id).mapped('account_id')[:1]
            rec.tax_account_id = account.id if account else False

    @api.depends('confirm_retention')
    def _onchange_confirm_retention_set_tax(self):
        for rec in self:
            if rec.confirm_retention and rec.retention_tax_id:
                if not rec.tax_line_id.post_retention_payment:
                    repartition = rec.retention_tax_id.invoice_repartition_line_ids.filtered(lambda r: r.account_id)
                    rec.tax_line_id = rec.retention_tax_id if repartition else False
                    rec.tax_account_id = repartition[0].account_id.id if repartition else False
                else:
                    rec.tax_account_id = rec.partner_id.property_account_receivable_id.id
            else:
                rec.tax_line_id = False
                rec.tax_account_id = False

    def action_post(self):
        for payment in self:
            if payment.is_ip_payment:
                payment._post_ip_payment()
            elif payment.is_industrial_tax:
                sequence_code = self.env['ir.sequence'].next_by_code('rdar.tax')
                payment.retention_payment_ref = sequence_code
                payment._post_industrial_tax_payment()
                payment.write({'name': sequence_code})
                payment.write({'payment_number': sequence_code})
            else:
                super().action_post()
        
    def _post_ip_payment(self):
        self.ensure_one()
        account_id = self.journal_id.outbound_payment_method_line_ids.payment_account_id.id
        if not account_id:
            raise ValidationError(_('O diário %s não possui uma conta de Pagamento de saída.') % self.journal_id.name)
        move = self.env['account.move'].create({
            'ref': self.ref or 'Pagamento IP',
            'move_type': 'entry',
            'journal_id': self.journal_id.id,
            'line_ids': [
                (0, 0, {
                    'name': self.ref or 'Imposto Predial',
                    'account_id': self.tax_account_id.id,
                    'debit': self.amount,
                    'partner_id': self.partner_id.id,
                }),
                (0, 0, {
                    'name': self.ref or 'Imposto Predial',
                    'account_id': account_id,
                    'credit': self.amount,
                    'partner_id': self.partner_id.id,
                }),
            ],
        })
        move.action_post()
        self.move_id = move
        self.state = 'posted'

    def _post_industrial_tax_payment(self):
        self.ensure_one()
        # Determina tipo de fatura e contas envolvidas
        move_type = self.invoice_id.move_type if self.invoice_id else None
        if move_type == 'out_invoice':
            main_account = self.partner_id.property_account_receivable_id
            receivable_account = self.partner_id.property_account_receivable_id
            payment_type = 'inbound'
        elif move_type == 'in_invoice':
            main_account = self.partner_id.property_account_payable_id
            receivable_account = self.journal_id.outbound_payment_method_line_ids.payment_account_id
            payment_type = 'outbound'
        else:
            raise ValidationError("Tipo de fatura desconhecido ou não suportado.")
        # Garante conta contábil do método se existir
        # payment_method_account = self.journal_id.outbound_payment_method_line_ids.payment_account_id or main_account

        move = self.env['account.move'].create({
            'ref': '%s Imposto Industrial'% self.retention_payment_ref,
            'move_type': 'entry',
            'partner_id': self.partner_id.id,
            'journal_id': self.journal_id.id,
            'line_ids': [
                (0, 0, {
                    'name': self.retention_payment_ref,
                    'account_id': self.tax_account_id.id,
                    'debit': self.amount,
                    'partner_id': self.partner_id.id,
                }),
                (0, 0, {
                    'name': self.retention_payment_ref,
                    'account_id': receivable_account.id,
                    'credit': self.amount,
                    'partner_id': self.partner_id.id,
                }),
            ],
        })
        move.action_post()

        if self.confirm_retention and self.invoice_id:
            invoice_lines = self.invoice_id.line_ids.filtered(
                lambda l: l.account_id == main_account and not l.reconciled
            )
            retention_line = move.line_ids.filtered(
                lambda l: l.account_id == main_account and l.credit > 0
            )
            if invoice_lines and retention_line:
                (invoice_lines + retention_line).reconcile()

            self.invoice_id.retention_paid = True

        # Registrar vínculo ao movimento contábil
        self.move_id = move

    def _synchronize_from_moves(self, changed_fields):
        ''' Update the account.payment regarding its related account.move.
        Also, check both models are still consistent.
        :param changed_fields: A set containing all modified fields on account.move.
        '''
        if self._context.get('skip_account_move_synchronization'):
            return

        for pay in self.with_context(skip_account_move_synchronization=True):

            # After the migration to 14.0, the journal entry could be shared between the account.payment and the
            # account.bank.statement.line. In that case, the synchronization will only be made with the statement line.
            if pay.move_id.statement_line_id:
                continue

            move = pay.move_id
            move_vals_to_write = {}
            payment_vals_to_write = {}

            if 'journal_id' in changed_fields:
                if pay.journal_id.type not in ('bank', 'cash') and pay.journal_id.type != 'general':
                    raise UserError(_("A payment must always belongs to a bank or cash journal."))

            if 'line_ids' in changed_fields:
                all_lines = move.line_ids
                liquidity_lines, counterpart_lines, writeoff_lines = pay._seek_for_lines()

                if len(liquidity_lines) != 1:
                    raise UserError(_(
                        "Journal Entry %s is not valid. In order to proceed, the journal items must "
                        "include one and only one outstanding payments/receipts account.",
                        move.display_name,
                    ))

                if len(counterpart_lines) != 1:
                    raise UserError(_(
                        "Journal Entry %s is not valid. In order to proceed, the journal items must "
                        "include one and only one receivable/payable account (with an exception of "
                        "internal transfers).",
                        move.display_name,
                    ))

                if any(line.currency_id != all_lines[0].currency_id for line in all_lines):
                    raise UserError(_(
                        "Journal Entry %s is not valid. In order to proceed, the journal items must "
                        "share the same currency.",
                        move.display_name,
                    ))

                if any(line.partner_id != all_lines[0].partner_id for line in all_lines):
                    raise UserError(_(
                        "Journal Entry %s is not valid. In order to proceed, the journal items must "
                        "share the same partner.",
                        move.display_name,
                    ))

                if counterpart_lines.account_id.account_type == 'asset_receivable':
                    partner_type = 'customer'
                else:
                    partner_type = 'supplier'

                liquidity_amount = liquidity_lines.amount_currency

                move_vals_to_write.update({
                    'currency_id': liquidity_lines.currency_id.id,
                    'partner_id': liquidity_lines.partner_id.id,
                })
                payment_vals_to_write.update({
                    'amount': abs(liquidity_amount),
                    'partner_type': partner_type,
                    'currency_id': liquidity_lines.currency_id.id,
                    'destination_account_id': counterpart_lines.account_id.id,
                    'partner_id': liquidity_lines.partner_id.id,
                })
                if liquidity_amount > 0.0:
                    payment_vals_to_write.update({'payment_type': 'inbound'})
                elif liquidity_amount < 0.0:
                    payment_vals_to_write.update({'payment_type': 'outbound'})

            move.write(move._cleanup_write_orm_values(move, move_vals_to_write))
            pay.write(move._cleanup_write_orm_values(pay, payment_vals_to_write))

