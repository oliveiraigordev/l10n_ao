from odoo import models, fields


class AssetNature(models.Model):
    _name = "asset.nature"
    _description = "Natureza de Ativos"

    name = fields.Char(string="Name", required=True)
    account_ids = fields.Many2many(
        comodel_name="account.account",
        string="Contas Associadas",
        help="Contas associadas a esta natureza de ativo",
    )
    code = fields.Char(
        string="Code",
        help="Código único para identificar a natureza do ativo",
    )
    active = fields.Boolean(string="Active", default=True)
