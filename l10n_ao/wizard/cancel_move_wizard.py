from odoo import api, fields, models, _,exceptions
import logging

class CancelMoveWizard(models.TransientModel):
    _name = 'cancel.move.wizard'
    _description = 'Cancel Move Wizard'

    motive = fields.Selection(string='Motivo',selection=[('A','Anulação'),('R','Retificação')], required=True)
    description = fields.Char("Descrição")
    def action_confirm_motive(self):
        active_id = self.env.context.get('active_id')
        if active_id:
            record = self.env['account.move'].browse(active_id)
            if self.motive == 'A':
                motive = "Anulação"
            else:
                motive = "Retificação"
            record.write({'state':'cancel','ref':motive,'auto_post': 'no'})