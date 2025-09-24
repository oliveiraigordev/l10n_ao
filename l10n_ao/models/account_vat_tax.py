from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from dateutil.parser import parse
from dateutil.relativedelta import relativedelta
from datetime import date


class AccountVATTax(models.Model):
    _name = "account.vat.tax"
    _inherit = ['mail.thread']
    _description = "Object for VAT management and processing"
    _order = "create_date desc, name desc"

    def pay_tax(self):
        wizard = self.env["l10n_ao.journal.selection.wizard"].create({"withholding": self.id})
        action = self.env.ref('l10n_ao.l10n_ao_journal_selection_wizard_action').read()[0]
        action['views'] = [(self.env.ref('l10n_ao.l10n_ao_journal_selection_wizard_view').id, 'form')]
        action["res_id"] = wizard.id
        return action

    def _get_double_move_line_vals(self, debit_account_id, credit_account_id, amount_currency, move_id):
        """ Returns values common to both move lines (except for debit, credit and amount_currency which are reversed)
        """
        return [{
            'account_id': debit_account_id.id,
            'move_id': move_id.id,
            'debit': amount_currency,
            'credit': 0.0,
            'amount_currency': False,
        },
            {
                'account_id': credit_account_id.id,
                'move_id': move_id.id,
                'debit': 0.0,
                'credit': amount_currency,
                'amount_currency': False,
            }
        ]

    def _get_counterpart_move_line_vals(self):
        if self.type == 'pay':
            name = _("DU {} Paid").format(self.dar_number)
        else:
            name = _("DU {} Received").format(self.dar_number)
        return {
            'name': name,
            'account_id': self.tax_id.account_id.id,
            'journal_id': self.journal_id.id,
            'currency_id': self.currency_id != self.company_id.currency_id and self.currency_id.id or False,
        }

    def _get_move_vals(self):
        """ Return dict to create the payment move
        """
        journal = self.journal_id
        # if not journal.sequence_id:
        #     raise UserError(_('Configuration Error !'),
        #                     _('The journal %s does not have a sequence, please specify one.') % journal.name)
        # if not journal.sequence_id.active:
        #     raise UserError(_('Configuration Error !'), _('The sequence of journal %s is deactivated.') % journal.name)
        # name = journal.with_context().sequence_id.next_by_id()
        return {
            'name': "/",
            'date': fields.Date.today(),
            'ref': self.communication or '',
            'company_id': self.company_id.id,
            'journal_id': journal.id,
        }

    name = fields.Char(_('Document Ref'), default='New')
    state = fields.Selection(
        [('draft', 'Draft'), ('payment', 'For Payment'), ('refund', 'Refund Requested'),
         ('move', 'Move to next period'), ('accepted', 'Refund Accepted'), ('rejected', 'Refund Rejected'),
         ('complain', 'Refund Complain'), ('expense', 'Register as Expense'),
         ('complain_rejected', 'Complain Rejected'),
         ('complain_accepted', 'Complain Accepted'), ('refund_payment', 'Awaiting Refund Payment'),
         ('posted', 'Posted'), ('done', 'Done'), ('cancel', 'Canceled')], "State",
        default='draft',
    )
    date = fields.Date("Date", default=fields.Date.today())
    fiscal_year = fields.Integer("Fiscal Year", default=fields.Date.today().year)
    journal_id = fields.Many2one("account.journal", "Journal", required=True)
    close_move_id = fields.Many2one("account.move", "Move")
    move_id = fields.Many2one("account.move", string="VAT Settlement Move", readonly="1")
    move_lines = fields.One2many(related="move_id.line_ids", )
    move_state = fields.Selection(related="move_id.state", readonly="1")
    type = fields.Selection([("refund", "Refund"), ("pay", "To Pay")], "Type", readonly="1")
    refund_move_id = fields.Many2one("account.move", string="VAT Refund Request", readonly="1")
    refund_move_lines = fields.One2many(related="refund_move_id.line_ids", )
    refund_move_state = fields.Selection(related="refund_move_id.state", readonly="1")

    refund_acceptance_move_id = fields.Many2one("account.move", string="VAT Refund Acceptance", readonly="1")
    refund_acceptance_move_lines = fields.One2many(related="refund_acceptance_move_id.line_ids", )
    refund_acceptance_move_state = fields.Selection(related="refund_acceptance_move_id.state", readonly="1")
    refund_acceptance_percentage = fields.Float("Refunded %")
    refund_acceptance_payment = fields.Selection([("bank_cash", "Bank or Cash"),
                                                  ("certificate", "Fiscal Certificate")],
                                                 "Refund Payment")
    payment_move_id = fields.Many2one("account.move", string="VAT Payment", readonly="1")
    payment_move_lines = fields.One2many(related="payment_move_id.line_ids", )
    payment_move_state = fields.Selection(related="payment_move_id.state", readonly="1")
    journal_payment_id = fields.Many2one("account.journal", "Payment Journal",
                                         domain=[("type", "in", ["cash", "bank"])], )

    refund_complain_move_id = fields.Many2one("account.move", string="VAT Refund Complain", readonly="1")
    refund_complain_move_lines = fields.One2many(related="refund_complain_move_id.line_ids")
    refund_complain_move_state = fields.Selection(related="refund_complain_move_id.state", readonly="1")

    complain_acceptance_move_id = fields.Many2one("account.move", string="VAT Complain Acceptance", readonly="1")
    complain_acceptance_move_lines = fields.One2many(related="complain_acceptance_move_id.line_ids")
    complain_acceptance_move_state = fields.Selection(related="complain_acceptance_move_id.state", readonly="1")

    start_period = fields.Selection([('1', "Jan"), ('2', "Feb"), ('3', "Mar"), ('4', "Apr"), ('5', "May"),
                                     ('6', "Jun"), ('7', "Jul"), ('8', "Aug"), ('9', "Sep"),
                                     ('10', "Oct"), ('11', "Nov"), ('12', "Dec")], string="Start Period")
    end_period = fields.Selection([('1', "Jan"), ('2', "Feb"), ('3', "Mar"), ('4', "Apr"), ('5', "May"),
                                   ('6', "Jun"), ('7', "Jul"), ('8', "Aug"), ('9', "Sep"),
                                   ('10', "Oct"), ('11', "Nov"), ('12', "Dec")], string="End Period")
    amount_pay = fields.Monetary(default=0.0, currency_field='currency_id', string="Amount to Pay")
    amount_receive = fields.Monetary(default=0.0, currency_field='currency_id', string="Amount to Receive")
    amount_min = fields.Monetary(currency_field='currency_id', string="Minimum Amount for Refund", default=300000)
    company_id = fields.Many2one('res.company', _('Company'), default=lambda self: self.env.company.id)
    currency_id = fields.Many2one(related='company_id.currency_id')
    communication = fields.Char(_('Communication'))
    refund_requested = fields.Boolean("Refund Requested")
    refund_next_period = fields.Boolean("Move to next period")
    refund_accepted = fields.Boolean("Refund Request Accepted")
    refund_rejected = fields.Boolean("Refund Request Rejected")
    refund_complain = fields.Boolean("Refund Complain")
    complain_accepted = fields.Boolean("Refund Complain Accepted")
    complain_rejected = fields.Boolean("Refund Complain Rejected")
    refund_expense = fields.Boolean("Refund Expense")
    enable_post = fields.Boolean("Enable post")

    @api.constrains("start_period", "end_period", "fiscal_year", "move_state")
    def check_settlement(self):
        result = self.search([("start_period", "<=", self.start_period), ("end_period", ">=", self.end_period),
                              ("move_state", "=", "posted"), ('company_id', '=', self.company_id.id)])
        if result:
            raise ValidationError("Cannot create VAT settlement for periods that already were settled!")

    def unlink(self):
        for line in self:
            if line.state == "done" and (
                    self.move_state == "posted" or self.payment_move_state == "posted" or self.refund_move_state == "posted"):
                raise ValidationError("You cannot delete a posted VAT Settlement!")

        return super(AccountVATTax, self).unlink()

    def action_cancel(self):
        if self.payment_move_state == "posted":
            raise ValidationError("This VAT Settlement it's already paid. You need to unreconcile the payment first!")
        if self.complain_acceptance_move_state == "posted":
            self.complain_acceptance_move_id.button_cancel()
            self.complain_acceptance_move_id.unlink()
        if self.refund_complain_move_state == "posted":
            self.refund_complain_move_id.button_cancel()
            self.refund_complain_move_id.unlink()
        if self.refund_acceptance_move_state == "posted":
            self.refund_acceptance_move_id.button_cancel()
            self.refund_acceptance_move_id.unlink()
        if self.refund_move_state == "posted":
            self.refund_move_id.button_cancel()
            self.refund_move_id.unlink()
        if self.move_state == "posted":
            self.move_id.button_cancel()
            self.move_id.unlink()
        self.state = "cancel"

    def compute_settlement(self):

        if self.move_id:
            self.move_id.unlink()
            self.enable_post = False

        start_date = date(year=int(self.fiscal_year), month=int(self.start_period), day=1)
        end_date = date(year=int(self.fiscal_year), month=int(self.end_period), day=1)
        end_date = fields.Date.end_of(end_date, "month")

        move_vals = self._get_move_vals()
        move_vals['ref'] = _("Apuramento Period  %s-%s") % (self.start_period, self.end_period)
        move_id = self.env['account.move'].create(move_vals)

        deductible_lines = self.env["account.move.line"].search([("date", ">=", start_date), ("date", "<=", end_date),
                                                                 ("account_id.code", "ilike", "3452%"),
                                                                 ("parent_state", "=", "posted"),
                                                                 ('company_id', '=', self.company_id.id)])
        settlement_ml = []
        tax_groups = deductible_lines.mapped("tax_line_id")
        for tax_id in tax_groups:
            deductible_balance = sum([line.debit - line.credit for line in
                                      deductible_lines.filtered(lambda r: r.tax_line_id.id == tax_id.id)])
            if deductible_balance > 0:
                # Create move from 3452 Dedutivel -> 3455 Apuramento creditando 3451 e debitando 3452
                debit_account_id = self.env["account.account"].search([("code", "ilike", "34551%"),
                                                                       ('company_id', '=', self.company_id.id)])[0]
                if not debit_account_id:
                    raise ValidationError("No account with code 34551 was found!")
                for tax_account_id in tax_id.invoice_repartition_line_ids.filtered(lambda c: c.account_id.code):
                    credit_account_id = tax_account_id.account_id

                    if self.company_id.tax_exigibility:
                        debit_account_id = self.env["account.account"].search([("code", "ilike", "34552%"),
                                                                               (
                                                                               'company_id', '=', self.company_id.id)])[
                            0]
                        if not debit_account_id:
                            raise ValidationError("No account with code 34552 was found!")
                    dedu_ml = self._get_double_move_line_vals(debit_account_id, credit_account_id,
                                                              abs(deductible_balance),
                                                              move_id)
                    settlement_ml.extend(dedu_ml)

        regularization_lines = self.env["account.move.line"].search([("date", ">=", start_date),
                                                                     ("date", "<=", end_date),
                                                                     '|', ("account_id.code", "ilike", "34541%"),
                                                                     ("account_id.code", "ilike", "34542%"),
                                                                     ("parent_state", "=", "posted"),
                                                                     ('company_id', '=', self.company_id.id)])
        tax_groups = regularization_lines.mapped("tax_line_id")
        for tax_id in tax_groups:
            regularization_balance = sum(
                [ml.debit - ml.credit for ml in
                 regularization_lines.filtered(
                     lambda r: r.account_id.id == tax_id.refund_repartition_line_ids.mapped("account_id").id)])

            if regularization_balance > 0:  # Saldo Devedor
                # Create move from 34541 Regularizacoes -> 3455 Apuramento creditando 3451 e debitando 3452
                debit_account_id = self.env["account.account"].search([("code", "ilike", "34551%"),
                                                                       ('company_id', '=', self.company_id.id)])[0]
                if not debit_account_id:
                    raise ValidationError("No account with code 34551 was found!")

                credit_account_id = tax_id.refund_repartition_line_ids.mapped("account_id")

                if self.company_id.tax_exigibility:
                    debit_account_id = self.env["account.account"].search([("code", "ilike", "34552%"),
                                                                           ('company_id', '=', self.company_id.id)])[0]
                    if not debit_account_id:
                        raise ValidationError(_("No account with code 34552 was found!"))
                reg_p_ml = self._get_double_move_line_vals(debit_account_id, credit_account_id,
                                                           abs(regularization_balance), move_id)
                settlement_ml.extend(reg_p_ml)

            if regularization_balance < 0:  # Saldo Credor
                # Create move from 34542 Regularizacoes -> 3455 Apuramento creditando 3451 e debitando 3452
                debit_account_id = tax_id.refund_repartition_line_ids.mapped("account_id")

                credit_account_id = self.env["account.account"].search([("code", "ilike", "34551%"),
                                                                        ('company_id', '=', self.company_id.id)])[0]
                if not credit_account_id:
                    raise ValidationError(_("No account with code 34551 was found!"))

                if self.company_id.tax_exigibility:
                    credit_account_id = self.env["account.account"].search([("code", "ilike", "34552%"),
                                                                            ('company_id', '=', self.company_id.id)])[0]
                    if not credit_account_id:
                        raise ValidationError(_("No account with code 34552 was found!"))
                reg_e_ml = self._get_double_move_line_vals(debit_account_id, credit_account_id,
                                                           abs(regularization_balance), move_id)
                settlement_ml.extend(reg_e_ml)

        recover_lines = self.env["account.move.line"].search([("date", ">=", start_date), ("date", "<=", end_date),
                                                              ("account_id.code", "ilike", "34571&"),
                                                              ("parent_state", "=", "posted"),
                                                              ('company_id', '=', self.company_id.id)])

        # tax_groups = recover_lines.mapped("tax_line_id")
        # for tax_id in tax_groups:
        recover_balance = sum([ml.debit - ml.credit for ml in recover_lines])
        if recover_balance > 0:
            # Create move from 3452 Dedutivel -> 3455 Apuramento creditando 3451 e debitando 3452
            debit_account_id = self.env["account.account"].search([("code", "ilike", "34571"),
                                                                   ('company_id', '=', self.company_id.id)])[0]
            if not debit_account_id:
                raise ValidationError(_("No account with code 34571 was found!"))

            credit_account_id = self.env["account.account"].search([("code", "ilike", "34551%"),
                                                                    ('company_id', '=', self.company_id.id)])[0]
            if not credit_account_id:
                raise ValidationError(_("No account with code 34523 was found!"))

            if self.company_id.tax_exigibility:
                credit_account_id = self.env["account.account"].search([("code", "ilike", "34552%"),
                                                                        ('company_id', '=', self.company_id.id)])[0]
                if not debit_account_id:
                    raise ValidationError(_("No account with code 34552 was found!"))
            recover_ml = self._get_double_move_line_vals(debit_account_id, credit_account_id, abs(recover_balance),
                                                         move_id)
            settlement_ml.extend(recover_ml)

        captive_lines = self.env["account.move.line"].search([("date", ">=", start_date), ("date", "<=", end_date),
                                                              ("account_id.code", "ilike", "34572%"),
                                                              ("parent_state", "=", "posted"),
                                                              ('company_id', '=', self.company_id.id)])
        tax_groups = captive_lines.mapped("tax_line_id")
        for tax_id in tax_groups:
            captive_balance = sum([line.debit - line.credit for line in
                                   captive_lines.filtered(lambda r: r.tax_line_id.id == tax_id.id)])
            if captive_balance > 0:
                # Create move from 3452 Dedutivel -> 3455 Apuramento creditando 3451 e debitando 3452
                debit_account_id = self.env["account.account"].search([("code", "ilike", "34551%"),
                                                                       ('company_id', '=', self.company_id.id)])[0]
                if not debit_account_id:
                    raise ValidationError(_("No account with code 34551 was found!"))

                credit_account_id = tax_id.account_id

                if self.company_id.tax_exigibility:
                    debit_account_id = self.env["account.account"].search([("code", "ilike", "34552%"),
                                                                           ('company_id', '=', self.company_id.id)])[0]
                    if not debit_account_id:
                        raise ValidationError(_("No account with code 34552 was found!"))
                captive_ml = self._get_double_move_line_vals(debit_account_id, credit_account_id, abs(captive_balance),
                                                             move_id)
                settlement_ml.extend(captive_ml)

        paid_lines = self.env["account.move.line"].search([("date", ">=", start_date), ("date", "<=", end_date),
                                                           ("account_id.code", "ilike", "3453%"),
                                                           ("parent_state", "=", "posted"),
                                                           ('company_id', '=', self.company_id.id)])

        tax_groups = paid_lines.mapped("tax_line_id")

        for tax_id in tax_groups:
            tax_account_ids = tax_id.mapped("invoice_repartition_line_ids.account_id.id")
            paid_balance = sum([ml.debit - ml.credit for ml in paid_lines.filtered(
                lambda r: r.account_id.id in tax_account_ids)])
            # TODO: Tratar do caso de regime de caixa
            if paid_balance < 0:
                for tax_account_id in tax_id.invoice_repartition_line_ids.filtered(
                        lambda c: c.account_id.code == '345311'):
                    # Create move from 3453 Liquidado -> 3455 Apuramento creditando 3451 e debitando 3452
                    debit_account_id = tax_account_id.account_id

                    credit_account_id = self.env["account.account"].search([("code", "ilike", "34551%"),
                                                                            ('company_id', '=', self.company_id.id)])[0]
                    if not credit_account_id:
                        raise ValidationError("No account with code 34551 was found!")

                    if self.company_id.tax_exigibility:
                        debit_account_id = tax_id.cash_basis_account_id
                        credit_account_id = self.env["account.account"].search([("code", "ilike", "34552%"),
                                                                                ('company_id', '=',
                                                                                 self.company_id.id)])[0]
                        if not credit_account_id:
                            raise ValidationError("No account with code 34552 was found!")

                    paid_ml = self._get_double_move_line_vals(debit_account_id, credit_account_id, abs(paid_balance),
                                                              move_id)
                    settlement_ml.extend(paid_ml)

        settlement_accounts = self.env["account.account"].search([('company_id', '=', self.company_id.id),
                                                                  '|', ("code", "ilike", "34551%"),
                                                                  ("code", "ilike", "34552%"),
                                                                  ])
        settlement_account_ids = settlement_accounts.mapped("id")
        settlement_balance = sum(
            [ml['debit'] - ml['credit'] for ml in settlement_ml if ml["account_id"] in settlement_account_ids])
        if settlement_balance < 0:  # SAldo credor
            self.amount_pay = abs(settlement_balance)
            self.amount_receive = 0
            # Create move from 34551/2 Apurameento -> 34561 IVA a Pagar
            debit_account_id = self.env["account.account"].search([("code", "ilike", "34551%"),
                                                                   ('company_id', '=', self.company_id.id)])[0]
            if not debit_account_id:
                raise ValidationError("No account with code 34551 was found!")

            credit_account_id = self.env["account.account"].search([("code", "ilike", "34561%"),
                                                                    ('company_id', '=', self.company_id.id)])[0]
            if not credit_account_id:
                raise ValidationError("No credit account defined in Journal!")

            if self.company_id.tax_exigibility:
                debit_account_id = self.env["account.account"].search([("code", "ilike", "34552%"),
                                                                       ('company_id', '=', self.company_id.id)])[0]
                if not debit_account_id:
                    raise ValidationError("No account with code 34552 was found!")
            pay_ml = self._get_double_move_line_vals(debit_account_id, credit_account_id,
                                                     abs(settlement_balance), move_id)
            settlement_ml.extend(pay_ml)

        elif settlement_balance > 0:
            self.amount_receive = settlement_balance
            self.amount_pay = 0
            # Create move from 3453 Liquidado -> 3455 Apuramento creditando 3451 e debitando 3452
            debit_account_id = self.env["account.account"].search([("code", "ilike", "3453%"),
                                                                   ('company_id', '=', self.company_id.id)])[0]
            if not debit_account_id:
                raise ValidationError("No debit account defined in Journal!")

            credit_account_id = self.env["account.account"].search([("code", "ilike", "34551%"),
                                                                    ('company_id', '=', self.company_id.id)])[0]
            if not credit_account_id:
                raise ValidationError("No account with code 34551 was found!")

            if self.company_id.tax_exigibility:
                credit_account_id = self.env["account.account"].search([("code", "ilike", "34552%"),
                                                                        ('company_id', '=', self.company_id.id)])[0]
                if not credit_account_id:
                    raise ValidationError("No account with code 34552 was found!")
            receive_ml = self._get_double_move_line_vals(debit_account_id, credit_account_id, settlement_balance,
                                                         move_id)
            settlement_ml.extend(receive_ml)

        move_lines = []
        for ml in settlement_ml:
            ml_id = self.env["account.move.line"].with_context(check_move_validity=False).create(ml)
            move_lines.append((4, ml_id.id, 0))

        move_id.line_ids = move_lines
        self.move_id = move_id
        self.name = _("IVA Settlement: %s Period %s - %s") % (self.fiscal_year, self.start_period, self.end_period)
        self.enable_post = True

    def compute_refund(self):
        if self.refund_move_id:
            self.refund_move_id.unlink()
        # Requets refund to the state
        move_vals = self._get_move_vals()
        refund_ml = []
        self.refund_requested = False
        self.refund_next_period = False
        self.enable_post = False

        if self.amount_receive > 0 and not self._context.get("move_to_next_period", False):
            move_vals['ref'] = _("Refund request period %s-%s") % (self.start_period, self.end_period)
            move_id = self.env['account.move'].create(move_vals)
            # Create move from Cr 34571 IVA a Recuperar -> Db 34581 Reembolsos pedidos
            debit_account_id = self.env["account.account"].search([("code", "ilike", "34581%"),
                                                                   ('company_id', '=', self.company_id.id)])[0]
            if not debit_account_id:
                raise ValidationError(_("No account with code 34581 was found!"))

            credit_account_id = self.env["account.account"].search([("code", "ilike", "34571%"),
                                                                    ('company_id', '=', self.company_id.id)])[0]
            refund_ml = self._get_double_move_line_vals(debit_account_id, credit_account_id, abs(self.amount_receive),
                                                        move_id)
            self.refund_move_id = move_id
            self.refund_requested = True
            self.enable_post = True
            self.state = "refund"
        elif self.amount_receive > 0 and self._context.get("move_to_next_period"):
            move_vals['ref'] = _("Move to next period %s-%s") % (self.start_period, self.end_period)
            move_id = self.env['account.move'].create(move_vals)
            # Create move from Cr 34571 IVA a Recuperar -> Db IVA de 34551/2 apuramento IVA a Pagar
            debit_account_id = self.env["account.account"].search([("code", "ilike", "34551%"),
                                                                   ('company_id', '=', self.company_id.id)])[0]
            if not debit_account_id:
                raise ValidationError(_("No account with code 34551 was found!"))

            credit_account_id = self.env["account.account"].search([("code", "ilike", "34571%"),
                                                                    ('company_id', '=', self.company_id.id)])[0]

            if self.company_id.tax_exigibility:
                debit_account_id = self.env["account.account"].search([("code", "ilike", "34552%"),
                                                                       ('company_id', '=', self.company_id.id)])[0]
                if not debit_account_id:
                    raise ValidationError(_("No account with code 34552 was found!"))
            refund_ml = self._get_double_move_line_vals(debit_account_id, credit_account_id,
                                                        abs(self.amount_receive), move_id)
            self.refund_move_id = move_id
            self.refund_next_period = True
            self.enable_post = True
            self.state = "move"
        move_lines = []
        for ml in refund_ml:
            ml_id = self.env["account.move.line"].with_context(check_move_validity=False).create(ml)
            move_lines.append((4, ml_id.id, 0))
        self.refund_move_id.line_ids = move_lines

    def refund_acceptance(self):
        if self.refund_acceptance_move_id:
            self.refund_acceptance_move_id.unlink()
        # Accept refund to the state
        move_vals = self._get_move_vals()
        acceptance_ml = []
        self.refund_accepted = False
        self.refund_rejected = False
        self.enable_post = False

        # Reembolso Deferido
        if self.amount_receive > 0 and self._context.get("refund_approved"):
            move_vals['ref'] = _("Refund request accepted period %s-%s") % (self.start_period, self.end_period)
            move_id = self.env['account.move'].create(move_vals)
            # Create move from Cr 34581 IVA reembolsos pedidos -> Db 34582 Rembolsos deferidos
            debit_account_id = self.env["account.account"].search([("code", "ilike", "34582%"),
                                                                   ('company_id', '=', self.company_id.id)])[0]
            if not debit_account_id:
                raise ValidationError(_("No account with code 34582 was found!"))

            credit_account_id = self.env["account.account"].search([("code", "ilike", "34581%"),
                                                                    ('company_id', '=', self.company_id.id)])[0]
            if not credit_account_id:
                raise ValidationError(_("No account with code 34581 was found!"))
            acceptance_ml = self._get_double_move_line_vals(debit_account_id, credit_account_id,
                                                            abs(self.amount_receive),
                                                            move_id)
            self.refund_acceptance_move_id = move_id
            self.refund_accepted = True
            self.enable_post = True
            self.state = 'accepted'
        elif self.amount_receive > 0 and not self._context.get("refund_approved"):
            move_vals['ref'] = _("Refund request rejected %s-%s") % (self.start_period, self.end_period)
            move_id = self.env['account.move'].create(move_vals)
            # Create move from Cr 34581 IVA reembolsos pedidos -> Db 34583 Rembolsos indeferidos
            debit_account_id = self.env["account.account"].search([("code", "ilike", "34583%"),
                                                                   ('company_id', '=', self.company_id.id)])[0]
            if not debit_account_id:
                raise ValidationError(_("No account with code 34583 was found!"))

            credit_account_id = self.env["account.account"].search([("code", "ilike", "34581%"),
                                                                    ('company_id', '=', self.company_id.id)])[0]
            if not credit_account_id:
                raise ValidationError(_("No account with code 34581 was found!"))
            acceptance_ml = self._get_double_move_line_vals(debit_account_id, credit_account_id,
                                                            abs(self.amount_receive), move_id)
            self.refund_acceptance_move_id = move_id
            self.refund_rejected = True
            self.enable_post = True
            self.state = 'rejected'

        move_lines = []
        for ml in acceptance_ml:
            ml_id = self.env["account.move.line"].with_context(check_move_validity=False).create(ml)
            move_lines.append((4, ml_id.id, 0))
        self.refund_acceptance_move_id.line_ids = move_lines

    def refund_complaining(self):
        if self.refund_complain_move_id:
            self.refund_complain_move_id.unlink()
        # Accept refund to the state
        move_vals = self._get_move_vals()
        refund_complain_ml = []
        self.refund_complain = False
        self.refund_expense = False
        self.enable_post = False

        # Reembolso Deferido
        if self.amount_receive > 0 and self._context.get("complain"):
            move_vals['ref'] = _("Refund complain period %s-%s") % (self.start_period, self.end_period)
            move_id = self.env['account.move'].create(move_vals)
            # Create move from Cr 34583 IVA Reembolsos i -> Db 34584 Rembolsos Reclamados
            debit_account_id = self.env["account.account"].search([("code", "ilike", "34584%"),
                                                                   ('company_id', '=', self.company_id.id)])[0]
            if not debit_account_id:
                raise ValidationError(_("No account with code 34584 was found!"))

            credit_account_id = self.env["account.account"].search([("code", "ilike", "34583%"),
                                                                    ('company_id', '=', self.company_id.id)])[0]
            if not credit_account_id:
                raise ValidationError(_("No account with code 34583 was found!"))
            refund_complain_ml = self._get_double_move_line_vals(debit_account_id, credit_account_id,
                                                                 abs(self.amount_receive),
                                                                 move_id)
            self.refund_complain_move_id = move_id
            self.refund_complain = True
            self.enable_post = True
            self.state = "complain"
        elif self.amount_receive > 0 and self._context.get("expense"):
            move_vals['ref'] = _("Move refund rejected to expense rejected %s-%s") % (
                self.start_period, self.end_period)
            move_id = self.env['account.move'].create(move_vals)
            # Create move from Cr 34583 IVA Reembolsos indeferidos -> Db 75312 IVA
            debit_account_id = self.env["account.account"].search([("code", "ilike", "75312%"),
                                                                   ('company_id', '=', self.company_id.id)])[0]
            if not debit_account_id:
                raise ValidationError(_("No account with code 75312 was found!"))

            credit_account_id = self.env["account.account"].search([("code", "ilike", "34583%"),
                                                                    ('company_id', '=', self.company_id.id)])[0]
            if not credit_account_id:
                raise ValidationError(_("No account with code 34583 was found!"))
            refund_complain_ml = self._get_double_move_line_vals(debit_account_id, credit_account_id,
                                                                 abs(self.amount_receive), move_id)
            self.refund_complain_move_id = move_id
            self.refund_expense = True
            self.enable_post = True
            self.state = "expense"
        move_lines = []
        for ml in refund_complain_ml:
            ml_id = self.env["account.move.line"].with_context(check_move_validity=False).create(ml)
            move_lines.append((4, ml_id.id, 0))
        self.refund_complain_move_id.line_ids = move_lines

    def complain_acceptance(self):
        if self.complain_acceptance_move_id:
            self.complain_acceptance_move_id.unlink()
        # Accept refund to the state
        move_vals = self._get_move_vals()
        refund_complain_ml = []
        self.complain_accepted = False
        self.complain_rejected = False
        self.enable_post = False

        # Reembolso Deferido
        if self.amount_receive > 0 and self._context.get("complain_approved"):
            move_vals['ref'] = _("Complain accepted period %s-%s") % (self.start_period, self.end_period)
            move_id = self.env['account.move'].create(move_vals)
            # Create move from Cr 34581 IVA reembolsos pedidos -> Db 34582 Rembolsos deferidos
            debit_account_id = self.env["account.account"].search([("code", "ilike", "34582%"),
                                                                   ('company_id', '=', self.company_id.id)])[0]
            if not debit_account_id:
                raise ValidationError(_("No account with code 34582 was found!"))

            credit_account_id = self.env["account.account"].search([("code", "ilike", "34584%"),
                                                                    ('company_id', '=', self.company_id.id)])[0]
            if not credit_account_id:
                raise ValidationError(_("No account with code 34584 was found!"))
            refund_complain_ml = self._get_double_move_line_vals(debit_account_id, credit_account_id,
                                                                 abs(self.amount_receive),
                                                                 move_id)
            self.complain_acceptance_move_id = move_id
            self.complain_accepted = True
            self.enable_post = True
            self.state = "complain_accepted"
        elif self.amount_receive > 0 and not self._context.get("complain_approved"):
            move_vals['ref'] = _("Complain rejected %s-%s") % (self.start_period, self.end_period)
            move_id = self.env['account.move'].create(move_vals)
            # Create move from Cr 34581 IVA reembolsos pedidos -> Db 34583 Rembolsos indeferidos
            debit_account_id = self.env["account.account"].search([("code", "ilike", "75312%"),
                                                                   ('company_id', '=', self.company_id.id)])[0]
            if not debit_account_id:
                raise ValidationError(_("No account with code 75312 was found!"))

            credit_account_id = self.env["account.account"].search([("code", "ilike", "34584%"),
                                                                    ('company_id', '=', self.company_id.id)])[0]
            if not credit_account_id:
                raise ValidationError(_("No account with code 34584 was found!"))
            refund_complain_ml = self._get_double_move_line_vals(debit_account_id, credit_account_id,
                                                                 abs(self.amount_receive), move_id)
            self.complain_acceptance_move_id = move_id
            self.complain_rejected = True
            self.enable_post = True
            self.state = "complain_rejected"
        move_lines = []
        for ml in refund_complain_ml:
            ml_id = self.env["account.move.line"].with_context(check_move_validity=False).create(ml)
            move_lines.append((4, ml_id.id, 0))
        self.complain_acceptance_move_id.line_ids = move_lines

    def vat_payment(self):
        if self.payment_move_id:
            self.payment_move_id.unlink()
        # Accept refund to the state
        move_vals = self._get_move_vals()
        payment_ml = []
        self.enable_post = False

        # Refund payment
        if self.amount_receive > 0 and self._context.get("refund_payment"):

            move_vals['ref'] = _("VAT Refund payment for period %s-%s") % (self.start_period, self.end_period)
            move_id = self.env['account.move'].create(move_vals)
            # Create move from Cr 34582 IVA reembolsos pedidos -> Db 43/45/346 Rembolsos deferidos
            if self.refund_acceptance_payment == "certificate":
                debit_account_id = self.env["account.account"].search([("code", "ilike", "346%"),
                                                                       ('company_id', '=', self.company_id.id)])[0]
                if not debit_account_id:
                    raise ValidationError(_("No account with code 346 was found!"))
            else:
                debit_account_id = self.env["account.account"].search([("code", "ilike", "34582%"),
                                                                       ('company_id', '=', self.company_id.id)])[0]

            credit_account_id = self.env["account.account"].search([("code", "ilike", "34582%"),
                                                                    ('company_id', '=', self.company_id.id)])[0]
            if not credit_account_id:
                raise ValidationError(_("No account with code 34582 was found!"))
            payment_ml = self._get_double_move_line_vals(debit_account_id, credit_account_id,
                                                         abs(self.amount_receive),
                                                         move_id)
            self.payment_move_id = move_id
            self.enable_post = True
        # Pay VAT to government
        elif self.amount_pay > 0 and self._context.get("vat_payment"):
            move_vals['ref'] = _("Payment VAT for %s-%s") % (self.start_period, self.end_period)
            move_id = self.env['account.move'].create(move_vals)
            # Create move from Cr Bank or cash -> Db 34561 Iva a pagar de apuramento
            debit_account_id = self.env["account.account"].search([("code", "ilike", "34561%"),
                                                                   ('company_id', '=', self.company_id.id)])[0]
            credit_account_id = self.journal_payment_id.default_account_id

            payment_ml = self._get_double_move_line_vals(debit_account_id, credit_account_id,
                                                         abs(self.amount_pay), move_id)
            self.payment_move_id = move_id
            self.enable_post = True

        move_lines = []
        for ml in payment_ml:
            ml_id = self.env["account.move.line"].with_context(check_move_validity=False).create(ml)
            move_lines.append((4, ml_id.id, 0))
        self.payment_move_id.line_ids = move_lines

    def post(self):
        if self.move_id.state == "draft":
            self.move_id.post()
            self.state = "posted"
            if self.amount_receive > 0:
                self.type = "refund"
                self.state = "refund_payment"
            elif self.amount_pay > 0:
                self.state = "payment"
                self.type = "pay"

        elif self.state in ['refund', 'move'] and self.refund_move_id:
            self.refund_move_id.post()
            # self.type = "refund"
            # if self.refund_requested:
            #    self.state = "refund"
            if self.refund_next_period:
                self.state = "done"
        elif self.refund_move_id.state == "posted" and self.refund_acceptance_move_id \
                and self.refund_acceptance_move_state != 'posted':
            self.refund_acceptance_move_id.post()
            # if self.refund_accepted:
            #    self.state = "refund_payment"
        elif self.refund_move_id.state == "posted" and self.refund_complain_move_id \
                and self.refund_complain_move_state != 'posted':
            self.refund_complain_move_id.post()
            # if self.refund_rejected:
            ##self.state = "complain"
            #   self.refund_complain = True
        elif self.state in ["complain_rejected", "complain_accepted"] and self.complain_acceptance_move_id \
                and self.complain_acceptance_move_id.state != "posted":
            self.complain_acceptance_move_id.post()
            if self.complain_accepted:
                self.state = "refund_payment"
            elif self.complain_rejected:
                self.state = "done"

        elif self.state in ["refund_payment", "payment"] and self.payment_move_id:
            self.payment_move_id.post()
            self.state = "done"

        self.enable_post = False