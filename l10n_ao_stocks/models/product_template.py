import logging
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    use_product_stock_account = fields.Boolean(
        string="Usar configuração de estoque no produto?",
        help="Quando ativo, este produto usará as contas e métodos definidos abaixo "
             "em vez dos definidos na categoria."
    )

    costing_method = fields.Selection([
        ('standard', 'Preço Padrão'),
        ('fifo', 'FIFO'),
        ('average', 'Custo Médio')],
        string="Método de Custeio",
        default='standard',
        help="Substitui o método definido na categoria."
    )

    stock_valuation = fields.Selection([
        ('manual_periodic', 'Manual'),
        ('real_time', 'Automática')],
        string="Valorização de Inventário",
        default='manual_periodic',
        help="Substitui a avaliação da categoria."
    )

    stock_input_account_id = fields.Many2one('account.account', "Conta de Entrada de Estoque")
    stock_output_account_id = fields.Many2one('account.account', "Conta de Saída de Estoque")
    stock_valuation_account_id = fields.Many2one('account.account', "Conta de Valorização de Estoque")
    stock_journal_id = fields.Many2one('account.journal', "Diário de Estoque")

    total_route_ids = fields.Many2many('stock.route', related='categ_id.total_route_ids', readonly=False)
    removal_strategy_id = fields.Many2one('product.removal', related='categ_id.removal_strategy_id', readonly=False, store=True)
    putaway_rule_ids = fields.One2many('stock.putaway.rule', 'category_id', related='categ_id.putaway_rule_ids', readonly=False)
    packaging_reserve_method = fields.Selection(related='categ_id.packaging_reserve_method', readonly=False)
    categ_parent_id = fields.Many2one('product.category', related='categ_id.parent_id', store=False)
    cat_income_account_id = fields.Many2one('account.account', related='categ_id.property_account_income_categ_id', store=False)
    cat_expense_account_id = fields.Many2one('account.account', related='categ_id.property_account_expense_categ_id', store=False)
    cat_price_difference_account_id = fields.Many2one('account.account', related='categ_id.property_account_expense_categ_id', readonly=False)

    # ---------------- Validations & onchange ----------------
    @api.constrains('use_product_stock_account','stock_valuation',
                    'stock_input_account_id','stock_output_account_id',
                    'stock_valuation_account_id','stock_journal_id')
    def _check_stock_accounts(self):
        for tmpl in self:
            if tmpl.use_product_stock_account and tmpl.stock_valuation == 'real_time':
                missing = []
                if not tmpl.stock_input_account_id:
                    missing.append("Conta de Entrada")
                if not tmpl.stock_output_account_id:
                    missing.append("Conta de Saída")
                if not tmpl.stock_valuation_account_id:
                    missing.append("Conta de Valorização")
                if not tmpl.stock_journal_id:
                    missing.append("Diário de Estoque")
                if missing:
                    raise ValidationError(_("Preencha os seguintes campos obrigatórios para valorização em tempo real: %s")
                                          % ', '.join(missing))

    @api.onchange('use_product_stock_account')
    def _onchange_use_product_stock_account(self):
        if not self.use_product_stock_account:
            self.stock_input_account_id = False
            self.stock_output_account_id = False
            self.stock_valuation_account_id = False
            self.stock_journal_id = False
            self.stock_valuation = 'manual_periodic'

    def _get_product_accounts(self):
        """Devolve contas de stock. Se o produto tiver config própria. """
        self.ensure_one()
        tmpl = self.with_company(self.env.company)

        accounts = super(ProductTemplate, tmpl)._get_product_accounts()
        if tmpl.use_product_stock_account:
            if tmpl.stock_input_account_id:
                accounts['stock_input'] = tmpl.stock_input_account_id
            if tmpl.stock_output_account_id:
                accounts['stock_output'] = tmpl.stock_output_account_id
            if tmpl.stock_valuation_account_id:
                accounts['stock_valuation'] = tmpl.stock_valuation_account_id
        return accounts

    def get_product_accounts(self, fiscal_pos=None):
        """Inclui o diário"""
        self.ensure_one()
        tmpl = self.with_company(self.env.company)
        accounts = super(ProductTemplate, tmpl).get_product_accounts(fiscal_pos=fiscal_pos)
        if tmpl.use_product_stock_account and tmpl.stock_journal_id:
            accounts['stock_journal'] = tmpl.stock_journal_id
        return accounts

    # ---------------- Custeio & Valorização ----------------
    def _get_product_costing_method(self):
        if self.use_product_stock_account:
            return self.costing_method
        res = super(ProductTemplate, self)._get_product_costing_method()
        return res

    def _get_product_stock_valuation(self):
        if self.use_product_stock_account:
            return self.stock_valuation
        res = super(ProductTemplate, self)._get_product_stock_valuation()
        return res
