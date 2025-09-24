from odoo import models, fields, api
from odoo.tools import float_is_zero
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = "account.move"

    def action_change_account_and_revalidate(self):
        self.ensure_one()  

        return {
            'name': 'Alterar Conta Contábil',
            'type': 'ir.actions.act_window',
            'res_model': 'account.move.edit.account.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_move_id': self.id},
        }