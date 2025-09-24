from odoo import models

class AccountMove(models.Model):
    _inherit = 'account.move'

    def action_post(self):
        for move in self:
            if move.move_type != 'in_invoice':
                continue

            lines_to_create = []

            for tax_line in move.line_ids.filtered(lambda l: l.tax_line_id):
                tax = tax_line.tax_line_id
                
                if tax.amount == 0:
                    continue
                
                if tax.iva_balance_debit_account_id:
                    tax_amount = abs(tax_line.balance)

                    lines_to_create.append((0, 0, {
                        'name': f'Saldar IVA: {tax.name}',
                        'account_id': tax_line.account_id.id,
                        'debit': 0.0,
                        'credit': tax_amount,
                        'display_type': 'tax',
                    }))
                    lines_to_create.append((0, 0, {
                        'name': f'Saldar IVA: {tax.name}',
                        'account_id': tax.iva_balance_debit_account_id.id,
                        'debit': tax_amount,
                        'credit': 0.0,
                        'display_type': 'tax',
                    }))

            if lines_to_create:
                move.write({
                    'line_ids': lines_to_create,
                })

        res = super().action_post()
        return res