from odoo import models, fields


class AccountAssetInProgress(models.Model):
    _name = 'account.asset.in_progress'
    _description = 'Imobilizado em Curso'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Asset Name', required=True)
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Company',
        default=lambda self: self.env.company
    )
    # state = fields.Selection(
    #     selection=[('model', 'Modelo'),
    #         ('draft', 'Rascunho'),
    #         ('open', 'Em Execução'),
    #         ('paused', 'Em Espera'),
    #         ('close', 'Encerrado'),
    #         ('cancelled', 'Cancelado')],
    #     string='Status',
    #     copy=False,
    #     default='draft',
    # )
    active = fields.Boolean(default=True)
    asset_condition = fields.Selection(
        selection=[
            ('without_use', 'Ativo adquirido sem amortização'),
            ('in_use', 'Bens em estado de uso')
        ],
        default=False,
        string="Condição do Ativo"
    )
    date_of_use = fields.Date(string="Data de Utilização")
    acquisition_date = fields.Date(string='Data de Aquisição', required=True)
    is_imported = fields.Boolean(string='Importado?', default=False)
    asset_value = fields.Monetary(string='Valor de Aquisção', required=True)
    annual_rate = fields.Float(string='Taxa Anual')
    corrected_rate = fields.Float(string='Taxa Corrigida')
    currency_id = fields.Many2one(
        comodel_name='res.currency',
        string='Moeda',
        default=lambda self: self.env.company.currency_id,
    )
    account_asset_id = fields.Many2one(
        comodel_name='account.account',
        string='Conta de Ativo Fixo',
        help="Conta utilizada para registar a compra do ativo pelo seu preço original.",
        domain="[('company_id', '=', company_id), ('is_off_balance', '=', False)]")
    account_depreciation_id = fields.Many2one(
        comodel_name='account.account',
        string='Conta de Depreciação',
        domain="[('account_type', 'not in', ('asset_receivable', 'liability_payable', 'asset_cash', 'liability_credit_card', 'off_balance')), ('deprecated', '=', False), ('company_id', '=', company_id)]",
        help="Conta utilizada nas entradas de depreciação, para diminuir o valor do ativo.",
    )
    account_depreciation_expense_id = fields.Many2one(
        comodel_name='account.account',
        string='Conta de Despesa',
        domain="[('account_type', 'not in', ('asset_receivable', 'liability_payable', 'asset_cash', 'liability_credit_card', 'off_balance')), ('deprecated', '=', False), ('company_id', '=', company_id)]",
        help="Conta utilizada nas entradas de depreciação, para diminuir o valor do ativo.",
    )
    journal_id = fields.Many2one(
        comodel_name='account.journal',
        string='Diário',
        domain="[('type', '=', 'general'), ('company_id', '=', company_id)]",
    )