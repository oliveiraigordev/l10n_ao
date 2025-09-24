from odoo import models, api, _
from odoo.exceptions import ValidationError

class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if 'account_id' in vals:
                account = self.env['account.account'].browse(vals['account_id'])
                if account.nature_account in ['reason', 'integrator']:
                    raise ValidationError(_(
                        'Não é possível fazer lançamentos na conta "%s" (%s). '
                        'Lançamentos só são permitidos em contas de movimento.'
                    ) % (account.name, account.code))
        
        return super().create(vals_list)

    def write(self, vals):
        if 'account_id' in vals:
            account = self.env['account.account'].browse(vals['account_id'])
            if account.nature_account in ['reason', 'integrator']:
                raise ValidationError(_(
                    'Não é possível fazer lançamentos na conta "%s" (%s). '
                    'Lançamentos só são permitidos em contas de movimento.'
                ) % (account.name, account.code))
        
        return super().write(vals)
