from odoo import api, fields, models, _
from odoo.exceptions import UserError

class AccountMove(models.Model):
    _inherit = 'account.move'

    is_debit_note    = fields.Boolean(string="É Nota de Débito", default=False, store=True)
    debit_note = fields.Char(string="Nota de Débito", readonly=True, copy=False)

    @api.onchange('move_type', 'is_debit_note', 'company_id', 'journal_id')
    def _onchange_move_type_debit_note(self):
        # Se não é nota de débito, mantém o domínio padrão da view
        if not self.is_debit_note:
            return

        out_types = ('out_invoice', 'out_refund', 'out_receipt')
        in_types = ('in_invoice', 'in_refund', 'in_receipt')

        base = [('company_id', '=', self.company_id.id or self.env.company.id)]
        dom = list(base)

        if self.move_type in out_types:
            dom += [('type', '=', 'sale')]
            # se o diário atual não for 'sale', limpa
            if self.journal_id and self.journal_id.type != 'sale':
                self.journal_id = False

        elif self.move_type in in_types:
            dom += [('type', '=', 'purchase')]
            # se o diário atual não for 'purchase', limpa
            if self.journal_id and self.journal_id.type != 'purchase':
                self.journal_id = False

        else:
            self.journal_id = False

        return {'domain': {'journal_id': dom}}

    def action_post(self):
        res = super().action_post()
        for move in self:
            if move.is_debit_note:
                if move.move_type == 'out_invoice':
                    seq_code = 'report.debit.note.accounting'
                elif move.move_type == 'in_invoice':
                    seq_code = 'report.debit.note.vendor'
                else:
                    continue

                seq = self.env['ir.sequence'].with_company(move.company_id).next_by_code(seq_code)
                if not seq:
                    raise UserError(_("Sequência não encontrada para o código: %s", seq_code))
                move.write({'debit_note': seq})
        return res



