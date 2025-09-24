from odoo import models, fields
from odoo.exceptions import ValidationError


class AccountMove(models.Model):
    _inherit = 'account.move'

    def _get_new_hash(self, secure_seq_number):
        """ Returns the hash to write on journal entries when they get posted"""
        self.ensure_one()
        # get the only one exact previous move in the securisation sequence
        prev_move = self.sudo().search([
            ('state', '=', 'posted'),
            ('company_id', '=', self.company_id.id),
            ('journal_id', '=', self.journal_id.id),
            ('secure_sequence_number', '!=', 0),
            ('secure_sequence_number', '=', int(secure_seq_number) - 1)
        ], order="id desc", limit=1)
        # build and return the hash
        return self._compute_hash(prev_move.inalterable_hash if prev_move else u'')
