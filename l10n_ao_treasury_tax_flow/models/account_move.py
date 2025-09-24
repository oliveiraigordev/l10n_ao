from contextlib import contextmanager
from odoo import models, api, _, fields
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = "account.move"

    is_iac_payment = fields.Boolean(string="Pagamento IAC", default=False)
    journal_id = fields.Many2one(
        'account.journal',
        string='Journal',
        compute='_compute_journal_id', inverse='_inverse_journal_id', store=True, readonly=False, precompute=True,
        required=True,
        states={'draft': [('readonly', False)]},
        check_company=True,
        domain="[('type', '=', 'bank')]",
    )
    retention_paid = fields.Boolean(string="Retenção Paga", default=False, copy=False)
    
    @api.onchange('line_ids')
    def _onchange_line_ids_add_account(self):
        if not self.is_iac_payment or not self.journal_id:
            return

        lines = self.line_ids
        if not self.line_ids :
            return 
        count_lines = len(lines)

        # Se número de linhas for ímpar, adiciona linha contrapartida
        if count_lines % 2 == 1:
            transit_account = self.journal_id.outbound_payment_method_line_ids.payment_account_id

            if transit_account:
                # Evita duplicar a linha contrapartida
                has_account = any(l.account_id == transit_account for l in lines)
                if not has_account:
                    self.line_ids = [(0, 0, {
                        'account_id': transit_account.id,
                        'debit': 0,
                        'credit': 0,
                        'name': 'Automatic Balancing Line',
                    })]


    @contextmanager
    def _sync_unbalanced_lines(self, container):
        yield

        for invoice in (x for x in container['records'] if x.state != 'posted'):
            if not invoice.is_iac_payment:
                return super()._sync_unbalanced_lines(container)

            balance_name = ('Automatic Balancing Line')
            existing_line = invoice.line_ids.filtered(lambda l: l.name == balance_name)

            if not invoice.line_ids.tax_ids and invoice.line_ids.filtered('tax_line_id'):
                invoice.line_ids.filtered('tax_line_id').unlink()

            if existing_line:
                existing_line.balance = existing_line.amount_currency = 0.0

            unbalanced = self._get_unbalanced_moves({'records': invoice})
            if isinstance(unbalanced, list) and len(unbalanced) == 1:
                _, debit, credit = unbalanced[0]
                vals = {'balance': credit - debit}

                if existing_line:
                    existing_line.write(vals)
                else:
                    transit_account = invoice.journal_id.outbound_payment_method_line_ids.payment_account_id.id  # conta do diário

                    vals.update({
                        'name': balance_name,
                        'move_id': invoice.id,
                        'account_id': transit_account,
                        'currency_id': invoice.currency_id.id,
                    })
                    self.env['account.move.line'].create(vals)


    def action_get_invoice(self):
        value = True
        if self.invoice_id:
            form_view = self.env.ref('account.view_move_form')
            tree_view = self.env.ref('account.view_invoice_tree')
            value = {
                'domain': str([('id', '=', self.invoice_id.id)]),
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'account.move',
                'view_id': False,
                'views': [(form_view and form_view.id or False, 'form'),
                          (tree_view and tree_view.id or False, 'list')],
                'type': 'ir.actions.act_window',
                'res_id': self.invoice_id.id,
                'target': 'current',
                'nodestroy': True
            }
        return value
    
    def button_apply_captive_100(self):
        result = super().button_apply_captive_100()
        if self.move_type == 'out_invoice':
            captive_recovery = self.line_ids.filtered(lambda l: l.display_type == 'tax' and l.debit and not l.credit)
            recovery_value = sum(captive_recovery.mapped('debit'))
            customer_line = self.line_ids.filtered(lambda l: l.account_id == self.partner_id.property_account_receivable_id)
            if customer_line:
                customer_line.with_context(check_move_validity=False).write({
                    'debit': customer_line.debit + recovery_value,
                })
            self.line_ids.with_context(check_move_validity=False).create({
                'move_id': self.id,
                'account_id': self.partner_id.property_account_receivable_id.id,
                'partner_id': self.partner_id.id,
                'credit': recovery_value,
                'debit': 0.0,
                'name': _('À recuperar Cativo 100'),
            })
        elif self.move_type == 'in_invoice':
            captive_recovery = self.line_ids.filtered(lambda l: l.display_type == 'tax' and l.credit and not l.debit)
            recovery_value = sum(captive_recovery.mapped('credit'))
            supplier_line = self.line_ids.filtered(lambda l: l.account_id == self.partner_id.property_account_payable_id)
            if supplier_line:
                supplier_line.with_context(check_move_validity=False).write({
                    'credit': supplier_line.credit + recovery_value,
                })
            self.line_ids.with_context(check_move_validity=False).create({
                'move_id': self.id,
                'account_id': self.partner_id.property_account_payable_id.id,
                'partner_id': self.partner_id.id,
                'debit': recovery_value,
                'credit': 0.0,
                'name': _('À recuperar Cativo 100'),
            })
        return result
    
    def button_apply_captive_50(self):
        result = super().button_apply_captive_50()
        if self.move_type == 'out_invoice':
            captive_recovery = self.line_ids.filtered(lambda l: l.display_type == 'tax' and l.debit and not l.credit)
            recovery_value = sum(captive_recovery.mapped('debit'))
            customer_line = self.line_ids.filtered(lambda l: l.account_id == self.partner_id.property_account_receivable_id)
            if customer_line:
                customer_line.with_context(check_move_validity=False).write({
                    'debit': customer_line.debit + recovery_value,
                })
            self.line_ids.with_context(check_move_validity=False).create({
                'move_id': self.id,
                'account_id': self.partner_id.property_account_receivable_id.id,
                'partner_id': self.partner_id.id,
                'credit': recovery_value,
                'debit': 0.0,
                'name': _('À recuperar Cativo 50'),
            })
        elif self.move_type == 'in_invoice':
            captive_recovery = self.line_ids.filtered(lambda l: l.display_type == 'tax' and l.credit and not l.debit)
            recovery_value = sum(captive_recovery.mapped('credit'))
            supplier_line = self.line_ids.filtered(lambda l: l.account_id == self.partner_id.property_account_payable_id)
            if supplier_line:
                supplier_line.with_context(check_move_validity=False).write({
                    'credit': supplier_line.credit + recovery_value,
                })
            self.line_ids.with_context(check_move_validity=False).create({
                'move_id': self.id,
                'account_id': self.partner_id.property_account_payable_id.id,
                'partner_id': self.partner_id.id,
                'debit': recovery_value,
                'credit': 0.0,
                'name': _('À recuperar Cativo 50'),
            })
        return result