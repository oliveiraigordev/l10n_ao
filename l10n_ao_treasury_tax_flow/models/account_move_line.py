from odoo import models, fields, api


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)

        for line in lines:
            move = line.move_id
            if (
                move.is_iac_payment
                and move.journal_id
                and move.journal_id.default_account_id
                and len(move.line_ids) % 2 == 1
            ):
                outbound_account_id = self.journal_id.outbound_payment_method_line_ids.payment_account_id.id
                self.create({
                    'move_id': move.id,
                    'account_id': outbound_account_id,
                    'name': 'Contrapartida Automática',
                    'debit': line.credit,
                    'credit': line.debit,
                    'partner_id': line.partner_id.id,
                    'company_id': move.company_id.id,
                    'currency_id': move.currency_id.id,
                    'journal_id': move.journal_id.id,
                })

        return lines

