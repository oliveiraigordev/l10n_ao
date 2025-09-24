# -*- coding: utf-8 -*-
import logging

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class AccountJournal(models.Model):
    _inherit = 'account.journal'

    force_same_account_on_reconcile = fields.Boolean(
        string="Usar Conta Principal na Reconciliação",
        help="Se habilitado, sistema reconciliará lançamentos da conta suspensa, na conta principal"
    )
    
    def _get_journal_inbound_outstanding_payment_accounts(self):
        account_ids = super()._get_journal_inbound_outstanding_payment_accounts()
        if self.force_same_account_on_reconcile:
            inbound_payment_account_ids = self.inbound_payment_method_line_ids.mapped('payment_account_id')
            if inbound_payment_account_ids not in account_ids:
                account_ids = account_ids | inbound_payment_account_ids
        return account_ids
    
    def _get_journal_outbound_outstanding_payment_accounts(self):
        account_ids = super(AccountJournal, self)._get_journal_outbound_outstanding_payment_accounts()
        if self.force_same_account_on_reconcile:
            outbound_payment_account_ids = self.outbound_payment_method_line_ids.mapped('payment_account_id')
            if outbound_payment_account_ids not in account_ids:
                account_ids = account_ids | outbound_payment_account_ids
        return account_ids

    def update_dashboard_data(self):
        self._kanban_dashboard()
        self._kanban_dashboard_graph()
    
    def _fill_bank_cash_dashboard_data(self, dashboard_data):
        super(AccountJournal, self)._fill_bank_cash_dashboard_data(dashboard_data)