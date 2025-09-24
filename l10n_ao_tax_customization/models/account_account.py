from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class AccountAccount(models.Model):
    _inherit = 'account.account'

    nature_account = fields.Selection([
        ('reason', 'Razão'),
        ('integrator', 'Integradora'),
        ('moviment', 'Movimento')
    ], 
    string='Natureza da Conta',
    compute='_compute_nature_account', 
    store=True,
    default='moviment'
    )

    @api.depends('code')
    def _compute_nature_account(self):
        for record in self:
            record.nature_account = 'moviment'
            
            if record.code:
                clean_code = ''.join(filter(str.isdigit, record.code))
                digits_count = len(clean_code)
                
                if digits_count == 2:
                    record.nature_account = 'reason'
                elif digits_count == 3:
                    record.nature_account = 'integrator'
                elif digits_count >= 4:
                    try:
                        search_domain = [
                            ('code', '=like', record.code + '%'),
                            ('code', '!=', record.code)
                        ]
                        if record._origin.id:
                            search_domain.append(('id', '!=', record.id))
                        
                        child_accounts = self.search(search_domain)
                        
                        if child_accounts:
                            record.nature_account = 'integrator'
                        else:
                            record.nature_account = 'moviment'
                    except Exception:
                        record.nature_account = 'moviment'

    @api.constrains('nature_account', 'code')
    def _check_nature_account_required(self):
        """Ensure nature_account is always set"""
        for record in self:
            if not record.nature_account:
                raise ValidationError(_(
                    'A natureza da conta é obrigatória para a conta "%s".'
                ) % (record.name or record.code or 'Nova Conta'))

    # @api.constrains('nature_account')
    # def _check_account_nature_for_moves(self):
    #     """Valida se existem movimentos contábeis em contas que não permitem lançamentos"""
    #     for record in self:
    #         if record.nature_account in ['reason', 'integrator']:
    #             move_lines = self.env['account.move.line'].search([
    #                 ('account_id', '=', record.id)
    #             ], limit=1)
                
    #             if move_lines:
    #                 raise ValidationError(_(
    #                     'Não é possível alterar a natureza da conta "%s" para "%s" '
    #                     'pois existem lançamentos contábeis associados a ela. '
    #                     'Apenas contas de movimento podem ter lançamentos.'
    #                 ) % (record.name, dict(record._fields['nature_account'].selection)[record.nature_account]))

    @api.model
    def create(self, vals):
        """Override para validar criação de novas contas"""
        if 'nature_account' not in vals:
            vals['nature_account'] = 'moviment'
            
        account = super().create(vals)
        
        account._compute_nature_account()
        
        if account.code and len(''.join(filter(str.isdigit, account.code))) >= 4:
            parent_codes = []
            clean_code = ''.join(filter(str.isdigit, account.code))
            
            for i in range(2, len(clean_code)):
                parent_code_digits = clean_code[:i]
                parent_codes.append(parent_code_digits)
            
            for parent_code_digits in parent_codes:
                parent_accounts = self.search([
                    ('code', 'ilike', parent_code_digits),
                    ('id', '!=', account.id)
                ])
                
                for parent in parent_accounts:
                    parent_clean = ''.join(filter(str.isdigit, parent.code))
                    if parent_clean == parent_code_digits and len(parent_clean) >= 4:
                        parent._compute_nature_account()
        
        return account

    def write(self, vals):
        """Override para revalidar quando o código da conta for alterado"""
        result = super().write(vals)
        
        if 'code' in vals:
            all_accounts = self.search([])
            all_accounts._compute_nature_account()
        
        return result