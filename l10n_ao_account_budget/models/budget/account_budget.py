from odoo import fields, api, models, _


class AccountBudget(models.Model):
    _name = "account.budget"
    _description = "Orçamento"
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char('Nome do orçamento', required=True, states={'done': [('readonly', True)]})
    budget_year = fields.Char(string="Ano orçamentado", compute="_compute_budget_year", readonly=True)

    date_from = fields.Date('data de inicio', states={'done': [('readonly', True)]},
                            default=fields.Date.today().replace(month=1, day=1, year=fields.Date.today().year))
    date_to = fields.Date('data de fim', states={'done': [('readonly', True)]},
                          default=fields.Date.today().replace(month=12, day=31, year=fields.Date.today().year))

    state = fields.Selection([
        ('draft', 'Draft'), ('cancel', 'Cancelled'),
        ('confirm', 'Confirmed'), ('validate', 'Validated'), ('done', 'Done')
    ], 'Estado', default='draft', index=True, required=True, readonly=True, copy=False, tracking=True)
    budget_type = fields.Selection([("economic", "Económico"), ("financial", "Financeiro")], string="Tipo de orçamento",
                                   required=True, states={'done': [('readonly', True)]})

    initial_balance = fields.Monetary(
        string="Saldo inicial", currency_field='currency_id', store=True,
        states={'done': [('readonly', True)], 'validate': [('readonly', True)], 'confirm': [('readonly', True)]}
    )

    account_budget_line_ids = fields.One2many('account.budget.lines', 'account_budget_id', 'Linhas do orçamento',
                                              states={'done': [('readonly', True)]}, copy=True)
    user_id = fields.Many2one('res.users', 'Responsável', default=lambda self: self.env.user)
    company_id = fields.Many2one('res.company', 'Empresa', required=True, default=lambda self: self.env.company)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id', string="Moeda", readonly=True)
    account_budget_group_ids = fields.Many2many(
        'account.budget.group', 'account_budget_group_rel',
        'account_id', 'budget_id', string="Posições orçamentais", required=True,
        states={'done': [('readonly', True)], 'validate': [('readonly', True)], 'confirm': [('readonly', True)]}
    )

    @api.model_create_multi
    def create(self, vals_list):
        records = super(AccountBudget, self).create(vals_list)
        for record in records:
            record.create_account_budget_lines()

        return records

    def write(self, vals):
        _rec = super(AccountBudget, self).write(vals)
        if _rec and "account_budget_group_ids" in vals:
            self.create_account_budget_lines()

        return _rec

    def create_account_budget_lines(self):
        if self.state == "draft":
            lines_model = self.env["account.budget.lines"]
            self.account_budget_line_ids.unlink()

            for group in self.account_budget_group_ids:
                for account in group.account_ids:
                    if not lines_model.search([
                        ("account_budget_line_group_id", "=", group.id),
                        ("account_id", "=", account.id),
                        ("account_budget_id", "=", self.id)
                    ]):
                        lines_model.create({
                            "account_budget_id": self.id,
                            "account_id": account.id,
                            "account_budget_line_group_id": group.id
                        })

    def action_budget_confirm(self):
        self.write({'state': 'confirm'})

    def action_budget_draft(self):
        self.write({'state': 'draft'})

    def action_budget_validate(self):
        self.write({'state': 'validate'})

    def action_budget_cancel(self):
        self.write({'state': 'cancel'})

    def action_budget_done(self):
        self.write({'state': 'done'})

    @api.onchange('date_from')
    def _compute_budget_year(self):
        for record in self:
            if record.date_from:
                record.budget_year = record.date_from.year

    def action_account_budget_lines(self):
        self.ensure_one()
        view_id = self.env.ref("l10n_ao_account_budget.account_budget_lines_tree_view").id
        if self.budget_type == "economic":
            view_id = self.env.ref("l10n_ao_account_budget.account_budget_economic_lines_tree_view").id
        return {
            "name": _("Linhas do orçamento"),
            "type": "ir.actions.act_window",
            "view_id": view_id,
            "search_view_id": self.env.ref("l10n_ao_account_budget.account_budget_lines_search_view").id,
            "view_type": "tree",
            "view_mode": "list",
            "res_model": "account.budget.lines",
            "domain": [("account_budget_id", "=", self.id)],
            "context": {
                "default_account_budget_id": self.id,
                'search_default_budget_line_category_by': 1,
            },
        }

    def action_account_budget_line_report(self):
        self.ensure_one()
        action = {
            "type": "ir.actions.act_window",
            "view_type": "tree",
            "view_mode": "list",
            "res_model": "account.budget.lines",
            "context": {
                "default_account_budget_id": self.id,
            }
        }
        if self.budget_type == "economic":
            action["name"] = _("Orçamento Econômico")
            action["domain"] = [("budget_type", "=", "economic")]
            action["view_id"] = self.env.ref("l10n_ao_account_budget.view_economic_budget_tree").id
            action["search_view_id"] = self.env.ref("l10n_ao_account_budget.view_economic_budget_tree").id

        elif self.budget_type == "financial":
            action["name"] = _("Orçamento Financeiro")
            action["domain"] = [("budget_type", "=", "financial")]
            action["view_id"] = self.env.ref("l10n_ao_account_budget.view_financial_budget_tree").id
            action["search_view_id"] = self.env.ref("l10n_ao_account_budget.view_financial_budget_filter").id

        return action
