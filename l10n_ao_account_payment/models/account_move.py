# -*- coding: utf-8 -*-
import logging

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

class AccounMove(models.Model):
    _inherit = 'account.move'

    @api.model_create_multi
    def create(self, vals):
        for move in vals:
            if move.get('journal_id'):
                journal = self.env['account.journal'].browse(move.get('journal_id'))
                if journal.force_same_account_on_reconcile:
                    account_move_id = self.get_account_move_id(move)
                    if account_move_id:
                        account_move_id.write(move)
                        return account_move_id
        return super(AccounMove, self).create(vals)
    
    def get_account_move_id(self, move):
        account_move_id = self.env['account.move']
        domain = []
        if move.get('ref'):
            domain.append(('ref', '=', move.get('ref')))
        if move.get('date'):
            domain.append(('date', '=', move.get('date')))
        if move.get('journal_id'):
            domain.append(('journal_id', '=', move.get('journal_id')))
        if domain and move.get('ref'):
            account_move_id = account_move_id.search(domain, limit=1)
        return account_move_id

class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'
    
    @api.model_create_multi
    def create(self, vals):
        move_id = self.env['account.move']
        for val in vals:
            if val.get('move_id'):
                move_id = move_id.browse(val.get('move_id'))
            if move_id and move_id.journal_id.force_same_account_on_reconcile and move_id.line_ids:
                for move_line in move_id.line_ids:
                        move_line.reconciled = False
        if move_id and move_id.journal_id.force_same_account_on_reconcile and move_id.line_ids and move_id.state == 'draft':
            return move_id.line_ids
        else:
            return super(AccountMoveLine, self).create(vals)