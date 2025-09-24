from odoo import models


class AccountMove(models.Model):
    _inherit = "account.move"

    def action_register_payment(self):
        action = super(AccountMove, self).action_register_payment()

        action["context"]["invoice_line_ids"] = self.invoice_line_ids.ids
        return action
