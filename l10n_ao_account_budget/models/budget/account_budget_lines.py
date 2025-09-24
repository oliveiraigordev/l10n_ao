from odoo import fields, api, models, _
from odoo.exceptions import ValidationError, UserError

MONTHS_LIST = [
    {"name": "january", "id": 1},
    {"name": "february", "id": 2},
    {"name": "march", "id": 3},
    {"name": "april", "id": 4},
    {"name": "may", "id": 5},
    {"name": "june", "id": 6},
    {"name": "july", "id": 7},
    {"name": "august", "id": 8},
    {"name": "september", "id": 9},
    {"name": "october", "id": 10},
    {"name": "november", "id": 11},
    {"name": "december", "id": 12},
]


class AccountBudgetLines(models.Model):
    _name = "account.budget.lines"

    name = fields.Char(compute=False)

    account_budget_id = fields.Many2one(string="Orçamento", comodel_name="account.budget", required=True)
    account_id = fields.Many2one(string="Conta", comodel_name="account.account", required=True)
    account_budget_line_group_id = fields.Many2one("account.budget.group", store=True, string="Posição Orçamental")
    company_id = fields.Many2one(related="account_budget_id.company_id")
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id', readonly=True)

    account_code = fields.Char(string="Conta", related="account_id.code")
    budget_year = fields.Char(string="Ano orçado", related="account_budget_id.budget_year", store=True)
    budget_type = fields.Selection(string="Tipo de orçamento", related="account_budget_id.budget_type", store=True)

    budget_line_type = fields.Selection([
        ("in_coming", "Entrada"), ("out_coming", "Saída")
    ], string="Tipo de movimento", required=False, compute="compute_budget_line_type", readonly=False, store=True)

    january = fields.Monetary(string="Janeiro", store=True)
    february = fields.Monetary(string="Fevereiro", store=True)
    march = fields.Monetary(string="Março", store=True)
    april = fields.Monetary(string="Abril", store=True)
    may = fields.Monetary(string="Maio", store=True)
    june = fields.Monetary(string="Junho", store=True)
    july = fields.Monetary(string="Julho", store=True)
    august = fields.Monetary(string="Agosto", store=True)
    september = fields.Monetary(string="Setembro", store=True)
    october = fields.Monetary(string="Outubro", store=True)
    november = fields.Monetary(string="Novembro", store=True)
    december = fields.Monetary(string="Dezembro", store=True)
    total = fields.Monetary(string="Total Orçamentado", compute="_compute_total")

    january_accomplished = fields.Monetary(string='Realizado', compute="_compute_month_accomplished")
    february_accomplished = fields.Monetary(string="Realizado", compute="_compute_month_accomplished")
    march_accomplished = fields.Monetary(string='Realizado', compute="_compute_month_accomplished")
    april_accomplished = fields.Monetary(string='Realizado', compute="_compute_month_accomplished")
    may_accomplished = fields.Monetary(string='Realizado', compute="_compute_month_accomplished")
    june_accomplished = fields.Monetary(string='Realizado', compute="_compute_month_accomplished")
    july_accomplished = fields.Monetary(string='Realizado', compute="_compute_month_accomplished")
    august_accomplished = fields.Monetary(string='Realizado', compute="_compute_month_accomplished")
    september_accomplished = fields.Monetary(string='Realizado', compute="_compute_month_accomplished")
    october_accomplished = fields.Monetary(string='Realizado', compute="_compute_month_accomplished")
    november_accomplished = fields.Monetary(string='Realizado', compute="_compute_month_accomplished")
    december_accomplished = fields.Monetary(string='Realizado', compute="_compute_month_accomplished")

    total_accomplished = fields.Monetary(string="Total Realizado", compute="_compute_total_accomplished")

    january_variance = fields.Float("Desvio %")
    february_variance = fields.Float("Desvio %")
    march_variance = fields.Float("Desvio %")
    april_variance = fields.Float("Desvio %")
    may_variance = fields.Float("Desvio %")
    june_variance = fields.Float("Desvio %")
    july_variance = fields.Float("Desvio %")
    august_variance = fields.Float("Desvio %")
    september_variance = fields.Float("Desvio %")
    october_variance = fields.Float("Desvio %")
    november_variance = fields.Float("Desvio %")
    december_variance = fields.Float("Desvio %")
    total_variance = fields.Float(string="Total Desvio %", compute="_compute_total_variance")

    @api.depends("account_id")
    def compute_budget_line_type(self):
        for rec in self:
            if rec.account_code:
                if int(rec.account_code[0]) == 7:
                    rec.budget_line_type = "out_coming"
                elif int(rec.account_code[0]) == 6:
                    rec.budget_line_type = "in_coming"


    @api.model_create_multi
    def create(self, vals_list):
        for val in vals_list:
            domain = [
                ('account_budget_line_group_id', '=', val.get('account_budget_line_group_id', "")),
                ('account_budget_id', '=', val.get('account_budget_id', "")),
                ('account_id', '=', val.get('account_id', "")),
            ]
            if self.env['account.budget.lines'].search_count(domain):
                raise UserError(_("Budgetary position already exists, update before save it."))

        return super(AccountBudgetLines, self).create(vals_list)

    def action_open_budget_entries(self):
        action = self.env['ir.actions.act_window']._for_xml_id('account.action_account_moves_all_a')
        action['domain'] = [
            ('account_id', '=', self.account_id.id),
            ('date', '>=', self.account_budget_id.date_from),
            ('date', '<=', self.account_budget_id.date_to)
        ]
        return action

    def _compute_month_accomplished(self):
        query = self.env["account.move.line"]
        for rec in self:
            if rec.budget_type == "economic":
                domain = [
                    ('parent_state', '=', 'posted'),
                    ("account_id", "=", rec.account_id.id)
                ]
                for month in MONTHS_LIST:
                    _sum = 0
                    for aml in query.search(domain):
                        invoice_date = aml.move_id.invoice_date
                        if invoice_date and invoice_date.month == month["id"] and int(rec.budget_year) == invoice_date.year:
                            balance = aml.balance if aml.balance > 0 else - aml.balance
                            _sum += balance
                            for tax in aml.tax_ids:
                                if tax.is_withholding and tax.tax_scope == "service":
                                    _sum -= balance * (tax.amount / 100)
                                else:
                                    _sum += balance * (tax.amount / 100)
                    rec["{month}_accomplished".format(month=month["name"])] = _sum

            elif rec.budget_type == "financial":
                for month in MONTHS_LIST:
                    _sum = 0
                    domain = [("payment_state", "=", "posted"), ("account_code", "=", rec.account_id.code)]
                    for account_prl in self.env["account.payment.report.line"].search(domain):
                        payment_date = account_prl.payment_date
                        if payment_date and payment_date.month == month["id"] and int(rec.budget_year) == payment_date.year:
                            _sum = _sum + account_prl.amount
                    rec["{month}_accomplished".format(month=month["name"])] = _sum

    def _compute_total(self):
        for record in self:
            record.total = sum([record[month["name"]] for month in MONTHS_LIST])

    def _compute_total_accomplished(self):
        for record in self:
            record.total_accomplished = sum(
                [record["{name}_accomplished".format(name=month["name"])] for month in MONTHS_LIST])

    def _compute_total_variance(self):
        for record in self:
            record._compute_month_fields_variance()
            total_variance = -(
                    record.total - record.total_accomplished) / record.total if record.total != 0 else 0.0
            record.total_variance = total_variance

    def _compute_month_fields_variance(self):
        """
            Compute all fields variance from first until current month of the current year (with prefix month of year)

        return
        """

        for month in MONTHS_LIST:
            month = month["name"]
            for record in self:
                percentage_total = -(record[month] - record["{0}_accomplished".format(month)]) / record[month] \
                    if record[month] != 0 else 0.0
                record["{0}_variance".format(month)] = percentage_total
