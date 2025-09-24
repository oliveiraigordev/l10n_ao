from odoo import models, api

class AccountBankStatementLine(models.Model):
    _inherit = 'account.bank.statement.line'

    # @api.model_create_multi
    # def create(self, vals):
    #     for val in vals:
    #         if val.get('journal_id'):
    #             journal = self.env['account.journal'].browse(val.get('journal_id'))
    #             if journal.force_same_account_on_reconcile and val.get('payment_ref'):
    #                 val['payment_ref'] = val.get('payment_ref')
    #     result = super(AccountBankStatementLine, self).create(vals)
    #     return result

    def get_account_move_id(self, val):
        account_move_id = self.env['account.move']
        domain = []
        if 'partner_id' in val:
            domain.append(('partner_id', '=', val.get('partner_id')))
        if 'journal_id' in val:
            domain.append(('journal_id', '=', val.get('journal_id')))
        if 'payment_ref' in val:
            domain.append(('ref', '=', val.get('payment_ref')))
        if 'date' in val:
            domain.append(('date', '=', val.get('date')))
        if domain:
            account_move_id = account_move_id.search(domain, limit=1)
        return account_move_id
    
    def get_st_line_id(self, account_move_id):
        st_line_id = self.env['account.bank.statement.line']
        domain = []
        if account_move_id.ref:
            domain.append(('payment_ref', '=', account_move_id.ref))
        if domain:
            st_line_id = st_line_id.search(domain, limit=1)
        return st_line_id