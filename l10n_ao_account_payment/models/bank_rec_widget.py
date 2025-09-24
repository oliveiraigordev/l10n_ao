from odoo import models, fields, api, _

class BankRecWidget(models.Model):
    _inherit = 'bank.rec.widget'
    
    def button_validate(self):
        try:
            journal_id = self.move_id.journal_id
            move_id = self.env['account.move'].search([
                ('name', '=', self.move_id.line_ids[0].name)
            ], limit=1, order='id desc')
            
            payment_id = self.env['account.payment'].search([
                ('ref', '=', self.move_id.line_ids[0].name)
            ], limit=1, order='id desc')
            
            if not payment_id:
                today = fields.Date.today()
                payments = self.env['account.payment'].search([
                    ('journal_id', '=', self.move_id.journal_id.id)])
                quantity = len(
                    payments.filtered(
                        lambda p: p.date.month == today.month and p.date.year == today.year))
                quantity += 1
                name = f"{self.move_id.journal_id.code}/{today.year}/{today.month}/{quantity:04d}"
                
                payment_id = self.env['account.payment'].create({
                    'payment_type': 'inbound',
                    'partner_type': 'customer',
                    'partner_id': self.move_id.partner_id.id,
                    'amount': self.move_id.amount_total,
                    'date': fields.Date.today(),
                    'journal_id': self.move_id.journal_id.id,
                    'ref': self.move_id.line_ids[0].name,
                    'company_id': self.move_id.company_id.id,
                })
            
                payment_id.name = name
                payment_id.display_name = name
            
            payment_id.cash_flow_in_payment = False
            payment_id.register_cashflow = False
            
            payment_id.is_reconciled = True
            payment_id.is_matched = True
            payment_id.to_check = True
            
            line_ids = payment_id.move_id.line_ids
            line_ids.filtered(lambda l: l.account_id == move_id.journal_id.default_account_id).update({
                'reconciled': True,
            })
            
            if not move_id.payment_id:
                move_id.payment_id = payment_id
            if move_id.payment_id.state != 'posted':
                move_id.payment_id.state = 'posted'
            if journal_id.force_same_account_on_reconcile:
                self.move_id.payment_state = 'paid'
                move_id.payment_state = 'paid'
            super(BankRecWidget, self).button_validate()
        except Exception as e:
            raise Exception(e)

    @api.depends('st_line_id')
    def _compute_amls_widget(self):
        super(BankRecWidget, self)._compute_amls_widget()
        for wizard in self:
            journal = wizard.st_line_id.journal_id
            if journal.force_same_account_on_reconcile:
                account_ids = set()
                inbound_accounts = journal._get_journal_inbound_outstanding_payment_accounts() + journal.default_account_id
                outbound_accounts = journal._get_journal_outbound_outstanding_payment_accounts() + journal.default_account_id
                for account in inbound_accounts:
                    account_ids.add(account.id)

                # Matching on credit account.
                for account in outbound_accounts:
                    account_ids.add(account.id)
                domain = [
                    '&',
                    ('account_id', 'in', tuple(account_ids)),  # Contas permitidas
                    '|',
                    # Linhas de faturas (sem pagamento associado)
                    '&',
                    ('payment_id', '=', False),
                    ('account_id.account_type', 'in', ['asset_receivable', 'liability_payable']),
                    # Linhas de pagamento (já associadas)
                    '&',
                    ('payment_id', '!=', False),
                    ('account_id.account_type', '=', 'asset_cash'),
                ]
                wizard.amls_widget['dynamic_filters'][0]['domain'] = str(domain)
                for domain_line in wizard.amls_widget['domain']:
                    if 'statement_line_id' in domain_line:
                        wizard.amls_widget['domain'].remove(domain_line)