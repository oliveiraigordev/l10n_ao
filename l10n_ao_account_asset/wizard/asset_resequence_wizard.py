from odoo import models, fields, api

class AssetResequenceWizard(models.TransientModel):
    _name = 'asset.resequence.wizard'
    _description = 'Wizard to Resequence Assets'

    next_number = fields.Integer(string="Novo número inicial", required=True)
    has_prefix = fields.Boolean(string="Usar prefixo", default=False)  
    prefix = fields.Char(string="Prefixo")
    padding = fields.Integer(string="Número de dígitos", default=1)

    sequence_example = fields.Char(string="Próxima sequência", compute="_compute_sequence_example")

    @api.depends('has_prefix', 'prefix', 'padding', 'next_number')
    def _compute_sequence_example(self):
        for rec in self:
            if rec.has_prefix:
                number = str(rec.next_number).rjust(rec.padding or 0, '0')
                rec.sequence_example = f"{rec.prefix or ''}{number}"
            else:
                rec.sequence_example = str(rec.next_number).rjust(rec.padding or 0, '0')

    @api.model
    def default_get(self, fields):
        res = super().default_get(fields)
        sequence = self.env.ref('l10n_ao_account_asset.seq_account_asset')
        res['next_number'] = sequence.number_next
        res['padding'] = sequence.padding
        res['prefix'] = sequence.prefix
        return res

    def action_update_sequence(self):
        sequence = self.env.ref('l10n_ao_account_asset.seq_account_asset')
        sequence.sudo().write({
            'number_next': self.next_number,
            'prefix': self.prefix if self.has_prefix else '',
            'padding': self.padding,
        })
