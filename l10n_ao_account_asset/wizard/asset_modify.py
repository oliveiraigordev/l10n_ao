from odoo import models, api, _


class AssetModify(models.TransientModel):
    _inherit = 'asset.modify'

    @api.depends('asset_id')
    def _get_selection_modify_options(self):
        if self.env.context.get('resume_after_pause'):
            return [('resume', _('Resume'))]
        return [
            ('dispose', "Abater"),
            ('sell', "Vender"),
            ('modify', "Reavaliar"),
            ('pause', "Pausar"),
        ]
