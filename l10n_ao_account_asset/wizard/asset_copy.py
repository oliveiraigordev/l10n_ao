from odoo import models, fields, api

class CopyAssetWizard(models.TransientModel):
    _name = 'copy.asset.wizard'
    _description = 'Wizard to Copy Assets'

    number_of_copies = fields.Integer(
        string='Número de Cópias do Ativo',
        required=True,
        
    )

    def action_copy_asset(self):
        self.ensure_one()
        active_model = self.env.context.get('active_model')
        active_ids = self.env.context.get('active_ids') 

        if not active_model or not active_ids:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'message': 'No active records found in context.',
                    'type': 'warning',
                    'sticky': False,
                }
            }

        records_to_copy = self.env[active_model].browse(active_ids)

        if not records_to_copy.exists():
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'message': f'No records found for IDs {active_ids} in model {active_model}.',
                    'type': 'warning',
                    'sticky': False,
                }
            }

        for record_to_copy in records_to_copy:
            for _ in range(self.number_of_copies):
                record_to_copy.copy()

        return {'type': 'ir.actions.act_window_close'}
