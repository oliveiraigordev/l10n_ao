from datetime import timedelta, date

from odoo import models, fields, api,_
from odoo.osv import expression
from odoo.exceptions import UserError



class AccountAssetExtends(models.Model):
    _inherit = "account.asset"
    _description = "Gestão de Ativos"

    # asset_usable_condition = fields.Boolean(string="Bens em estados de uso?")
    asset_condition = fields.Selection(
        selection=[
            ('without_use', 'Ativo adquirido sem amortização'),
            ('in_use', 'Bens em estado de uso')
        ],
        default=False,
        string="Condição do Ativo"
    )
    date_of_use = fields.Date(string="Data de Utilização")
    atividade_economica = fields.Char(string="Atividade Econômica")
    enquadramento = fields.Char(string="Enquadramento")
    len_count = fields.Integer(default=0, string="Vida Útil")
    codigo_resumido = fields.Char(string="Código Resumido")
    seq1 = fields.Char(string="Enquadramento")
    seq = fields.Char(string="Enquadramento")
    codigo_resumido = fields.Char(string="Código Resumido")
    vida_util = fields.Integer(default=0, string="Vida Útil")
    taxa_anual = fields.Float("Taxa Anual", default=0.0)

    num_serie = fields.Integer(default=0, string="Número de Série")
    num_ficha = fields.Integer(default=0, string="Número da Ficha")
    codigo_de_barra = fields.Integer(default=0, string="Código de Barra")
    numero_patrimonio = fields.Char(string="Número de Patrimonio", copy=False)

    atividade_economica_related = fields.Char(
        string="Atividade Econômica", related="model_id.atividade_economica"
    )
    name_related = fields.Char(string="Name", related="model_id.name")
    enquadramento_related = fields.Char(
        string="Enquadramento", related="model_id.enquadramento"
    )
    codigo_resumido_related = fields.Char(
        string="Código Resumido", related="model_id.codigo_resumido"
    )
    vida_util_related = fields.Integer(
        default=0, string="Vida Útil", related="model_id.vida_util"
    )
    taxa_anual_related = fields.Float(
        "Taxa Anual", default=0.0, related="model_id.taxa_anual"
    )
    asset_id = fields.Many2one(comodel_name="account.asset", string="Asset")
    asset_ids = fields.One2many(
        comodel_name="account.asset", inverse_name="asset_id", string="Asset"
    )

    valor_amortizacao_acululada = fields.Monetary(
        string="Valor Amortização Acumulada", compute="_compute_asset_values"
    )
    valor_contabilistico_residual = fields.Monetary(
        string="Valor Contabilístico Residual", compute="_compute_asset_values"
    )

    valor_valia = fields.Monetary(string = "Valor Maisvalia/Menosvalia", compute ="_compute_asset_values")

    valor_abate = fields.Monetary(string = "Valor Abate", compute ="_compute_asset_values")

    prorata_date = fields.Date(  # the starting date of the depreciations
        string='Prorata Date',
    )

    corrected_rate = fields.Float(
        string="Taxa Corrigida",
        digits=(3, 2)
    )
    corrected_life_use = fields.Float(
        string="Vida Útil Corrigida (anos)",
        digits=(3, 2)
    )
    in_use_description = fields.Char(
        string="Descrição",
    )

    @api.onchange('corrected_life_use') 
    def _onchange_corrected_life_use(self):
        if self.asset_condition == 'in_use':
            if not self.model_id:
                raise UserError(_("Por favor, selecione um modelo de ativo antes de definir a vida útil corrigida."))
            corrected_rate = (100 / self.corrected_life_use) if self.corrected_life_use else 0
            
            self.update({
                'corrected_rate': corrected_rate,
                'method_number': self.corrected_life_use * 12,
                'method_period': '1',
            })

    def _compute_asset_values(self):
        for asset_id in self:
            depreciation_move_ids = self.env["account.move"].search(
                [("asset_id", "=", asset_id.id)],
                order="date asc, id asc",
            )
            if self.disposal_date and len(depreciation_move_ids) > 1:
                asset_id.valor_amortizacao_acululada = depreciation_move_ids[
                    -2
                ].asset_depreciated_value

                
                valor_abate = depreciation_move_ids[
                    -2
                ].asset_remaining_value
                asset_id.valor_abate = valor_abate
                asset_id.valor_valia = asset_id.original_value - asset_id.valor_amortizacao_acululada
                asset_id.valor_contabilistico_residual = asset_id.original_value - asset_id.valor_amortizacao_acululada - asset_id.valor_valia
            else:
                asset_id.valor_amortizacao_acululada = 0
                asset_id.valor_contabilistico_residual = asset_id.original_value
                


    @api.onchange("asset_ids")
    def _compute_asset(self):
        asset_id = self.asset_id
        self.atividade_economica = asset_id.atividade_economica
        self.enquadramento = asset_id.enquadramento
        self.len_count = asset_id.len_count
        self.codigo_resumido = asset_id.codigo_resumido
        self.seq1 = asset_id.seq1
        self.seq = asset_id.seq
        self.codigo_resumido = asset_id.codigo_resumido
        self.vida_util = asset_id.vida_util
        self.taxa_anual = asset_id.taxa_anual
        self.method = asset_id.method
        self.method_number = asset_id.method_number
        self.prorata_computation_type = asset_id.prorata_computation_type
        self.account_asset_id = asset_id.account_asset_id
        self.account_depreciation_id = asset_id.account_depreciation_id
        self.account_depreciation_expense_id = asset_id.account_depreciation_expense_id
        self.method_period = asset_id.method_period

    @api.onchange("original_value", "acquisition_date")
    def _compute_print_page_size(self):
        data = self.acquisition_date
        if data.day >= 15:
            data = date(year=int(data.year), month=int(data.month), day=15)
            data_total = data + timedelta(days=31)
            data = date(year=int(data_total.year), month=int(data_total.month), day=1)
            self.prorata_date = data_total
        if int(data.day) <= 15:
            data = date(year=int(data.year), month=int(data.month), day=1)
            self.prorata_date = data

    # @api.model
    # def create(self, vals):
    #     account_asset_code = '1151'
    #     account_depreciation_code = '1151'
    #     account_depreciation_expense_code = '1815'
    #     created_assets = self.env['account.asset']
    #     company_ids = self.env['res.company'].search([("currency_id.name", "=", 'AOA')])
    #     for company in company_ids:
    #         asset_vals = {
    #         'company_id': company.id,
    #         'account_asset_id': self.env['account.account'].search([('code', '=', account_asset_code), ('company_id', '=', company.id)], limit=1).id,
    #         'account_depreciation_id': self.env['account.account'].search([('code', '=', account_depreciation_code), ('company_id', '=', company.id)], limit=1).id,
    #         'account_depreciation_expense_id': self.env['account.account'].search([('code', '=', account_depreciation_expense_code), ('company_id', '=', company.id)], limit=1).id
    #     }
    #         if not vals.get("num_ficha"):
    #             asset_ids = self.env["account.asset"].search([("state", "!=", "model")])
    #             contador = asset_ids[-1].num_ficha if asset_ids else 0
    #             vals["num_ficha"] = contador + 1
    #
    #         new_vals = vals.copy()
    #         new_vals.update(asset_vals)
    #         created_assets |= super(AccountAssetExtends, self).create(new_vals)
    #
    #
    #     return created_assets

    #**********************************************************************************
    #Melhorias para deixar o código robusto para ambientes single e multi-company
    #*********************************************************************************

    @api.model
    def create(self, vals):
        account_asset_code = '1151'
        account_depreciation_code = '1151'
        account_depreciation_expense_code = '1815'

        # 1) Determinar a empresa alvo para criação (sempre a empresa ativa)
        current_company = self.env.company

        def _get_account(code):
            acc = self.env['account.account'].search([
                ('code', '=', code),
                ('company_id', '=', current_company.id)
            ], limit=1)
            if not acc:
                raise UserError(_(
                    "Não existe conta contábil com código '%s' na empresa %s."
                ) % (code, current_company.name))
            return acc.id

        vals['company_id'] = current_company.id
        vals['account_asset_id'] = _get_account(account_asset_code)
        vals['account_depreciation_id'] = _get_account(account_depreciation_code)
        vals['account_depreciation_expense_id'] = _get_account(account_depreciation_expense_code)

        if not vals.get('num_ficha'):
            last = self.search(
                [
                    ('state', '!=', 'model'),
                    ('company_id', '=', current_company.id)
                ],
                order="num_ficha desc",
                limit=1
            )
            vals['num_ficha'] = (last.num_ficha if last else 0) + 1

        if not vals.get('numero_patrimonio'):
            vals['numero_patrimonio'] = self.env['ir.sequence'].next_by_code('account.asset.number') or ''

        asset = super(AccountAssetExtends, self).create(vals)
        return asset

    @api.onchange('acquisition_date', 'original_value')
    def change_prorata_date(self):
        for asset in self:
            asset.prorata_date = asset.acquisition_date

    @api.model
    def _name_search(
        self, name="", args=None, operator="ilike", limit=100, name_get_uid=None
    ):
        args = args or []
        if operator == "ilike" and not (name or "").strip():
            domain = []
        else:
            domain = [
                "|",
                "|",
                "|",
                "|",
                ("name", operator, name),
                ("num_ficha", operator, name),
                ("num_serie", operator, name),
                ("codigo_de_barra", operator, name),
                ("numero_patrimonio", operator, name),
            ]
        return self._search(
            expression.AND([domain, args]), limit=limit, access_rights_uid=name_get_uid
        )
    
    @api.onchange('date_of_use')
    def _onchange_date_of_use(self):
        for asset in self:
            asset.prorata_date = asset.date_of_use

    @api.depends('prorata_date', 'prorata_computation_type', 'asset_paused_days', 'asset_condition','date_of_use')
    def _compute_paused_prorata_date(self):
        for asset in self:
            asset.paused_prorata_date = asset.date_of_use

    def copy(self, default=None):
        self.ensure_one()
        default = dict(default or {})
        default['original_value'] = self.original_value
        default['book_value'] = self.book_value
        default['value_residual'] = self.value_residual
        return super().copy(default)
