from odoo import fields, models, _, api
from odoo.exceptions import ValidationError


class AccountBudgetGroup(models.Model):
    _name = "account.budget.group"
    _order = "name"
    _description = "Posição Orçamental"

    name = fields.Char('Nome', required=True)
    account_ids = fields.Many2many('account.account', column1='budget_id', column2='account_id', string='Contas',
        domain="[('deprecated', '=', False), ('company_id', '=', company_id)]")

    company_id = fields.Many2one('res.company', 'Empresa', required=True,
        default=lambda self: self.env.company)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._check_account_ids(vals)
        return super().create(vals_list)

    def _check_account_ids(self, vals):
        if 'account_ids' in vals:
            account_ids = self.new({'account_ids': vals['account_ids']}, origin=self).account_ids
        else:
            account_ids = self.account_ids
        if not account_ids:
            raise ValidationError(_('Adiciona pelo menos uma conta'))
