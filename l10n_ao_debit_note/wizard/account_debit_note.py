# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.tools.translate import _
from odoo.exceptions import UserError


class AccountDebitNote(models.TransientModel):
    _inherit = 'account.debit.note'

    def _prepare_default_values(self, move):
        if move.move_type in ('in_refund', 'out_refund'):
            type = 'in_invoice' if move.move_type == 'in_refund' else 'out_invoice'
        else:
            type = move.move_type
        default_values = {
                'ref': '%s, %s' % (move.name, self.reason) if self.reason else move.name,
                'date': self.date or move.date,
                'invoice_date': move.is_invoice(include_receipts=True) and (self.date or move.date) or False,
                'journal_id': self.journal_id and self.journal_id.id or move.journal_id.id,
                'invoice_payment_term_id': None,
                'debit_origin_id': move.id,
                'move_type': type,
                'is_debit_note': True,
            }
        if not self.copy_lines or move.move_type in [('in_refund', 'out_refund')]:
            default_values['line_ids'] = [(5, 0, 0)]
        return default_values

    def create_debit(self):
        self.ensure_one()
        new_moves = self.env['account.move']
        for move in self.move_ids.with_context(include_business_fields=True):
            default_values = self._prepare_default_values(move)

            # Força marcação de nota de débito para habilitar sequência
            default_values['is_debit_note'] = True

            new_move = move.copy(default=default_values)

            # Gerar sequência manualmente (porque ainda não foi postado)
            # if new_move.is_debit_note and not new_move.debit_note:
            #     seq = self.env['ir.sequence'].next_by_code('report.debit.note.accounting')
            #     if not seq:
            #         raise UserError(_('Sequência "report.debit.note.accounting" não encontrada.'))
            #     new_move.debit_note = seq

            move_msg = _(
                "This debit note was created from: %s",
                move._get_html_link(),
            )
            new_move.message_post(body=move_msg)
            new_moves |= new_move

        action = {
            'name': _('Debit Notes'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'context': {'default_move_type': default_values['move_type']},
        }
        if len(new_moves) == 1:
            action.update({
                'view_mode': 'form',
                'res_id': new_moves.id,
            })
        else:
            action.update({
                'view_mode': 'tree,form',
                'domain': [('id', 'in', new_moves.ids)],
            })
        return action