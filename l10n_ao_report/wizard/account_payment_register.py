from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class AccountPaymentRegister(models.TransientModel):
    _inherit = "account.payment.register"

    account_payment_report_line_ids = fields.One2many('account.payment.report.line.register', 'account_payment_id',
                                                      string='Fluxo de Caixa')
    cash_flow_in_payment = fields.Boolean("Registar Fluxo de Caixa no Pagamento",
                                          related="company_id.cash_flow_in_payment", readonly=False)

    register_cashflow = fields.Boolean(string="Registrar Fluxo de Caixa", default=True)
    register_cashflow_computed = fields.Boolean(string="Meu Campo Computado",
                                                compute="_compute_register_cashflow_computed")
    line_cashflow = fields.Boolean(string="Linha de Fluxo", default=False)

    cash_flow_statement_rel_id = fields.Many2one('cash.flow.statement', string='Extracto do Fluxo de Caixa')

    is_cash_flow_line_invisible = fields.Boolean(default=False)

    @api.onchange('cash_flow_statement_rel_id')
    def _onchange_cash_flow_statement_rel_id(self):
        for record in self:
            # if record.cash_flow_statement_rel_id:
            #     record.account_payment_report_line_ids.create({
            #         'cash_flow_statement_line_id': record.cash_flow_statement_rel_id,
            #     })
            for amount_default in record.account_payment_report_line_ids:
                amount_default.cash_flow_statement_line_id = record.cash_flow_statement_rel_id.id

    def _compute_register_cashflow_computed(self):
        for record in self:
            record.register_cashflow_computed = True
            if record.cash_flow_in_payment and not record.account_payment_report_line_ids and not record.register_cashflow:
                record.cash_flow_in_payment = False

    @api.onchange('amount')
    def _onchange_amount(self):
        for record in self:
            if record.account_payment_report_line_ids:
                for amount_default in record.account_payment_report_line_ids:
                    amount_default.amount = record.amount
            config_value = record.sudo().company_id.cash_flow_in_payment_register
            if config_value:
                record.register_cashflow = True
            else:
                record.register_cashflow = False


    @api.onchange('account_payment_report_line_ids')
    def _onchange_amount_payment(self):
        for record in self:
            if record.account_payment_report_line_ids:
                for aprli in record.account_payment_report_line_ids:
                    if aprli.cash_flow_statement_id:
                        lines = self.env['cash.flow.statement.line'].search(
                            [('cash_flow_statement_id', '=', aprli.cash_flow_statement_id.id)], limit=1)
                        if not lines:
                            lines = self.env['cash.flow.statement.line'].create({
                                'cash_flow_statement_id': aprli.cash_flow_statement_id.id,
                                'name': '',
                            })
                        if lines:
                            aprli.cash_flow_statement_line_id = lines[0]
                            if aprli.amount == 0:
                                aprli.amount = record.amount
                        else:
                            aprli.cash_flow_statement_line_id = False
                    else:
                        aprli.cash_flow_statement_line_id = False

    @api.onchange('register_cashflow')
    def _onchange_register_cashflow(self):
        if self.register_cashflow:
            self.sudo().company_id.update({
                'cash_flow_in_payment': True
            })
        else:
            self.sudo().company_id.update({
                'cash_flow_in_payment': False
            })

    def _create_payment_vals_from_wizard(self, batch_result):
        payment_vals = super()._create_payment_vals_from_wizard(batch_result)

        if self.cash_flow_in_payment:
            if not self.account_payment_report_line_ids:
                raise ValidationError(
                    _(
                        f"É obrigatório fornecer o Fluxo de Caixa na "
                        "lista, para confirmar o pagamento."
                    )
                )

            # Adicionar a chave do fluxo de caixa no dicionario do pagamento, para a criação do pagamento
            account_payment_report_line_values = self.create_cash_flow_statement_account_move()
            payment_vals['account_payment_report_line_ids'] = account_payment_report_line_values

        return payment_vals

    def create_cash_flow_statement_account_move(self):
        data_value = []
        for record in self.account_payment_report_line_ids:
            cash_flow_statement_values = {
                'cash_flow_statement_id': record.cash_flow_statement_id.id,
                'cash_flow_statement_line_id': record.cash_flow_statement_line_id.id,
                'amount': record.amount
            }
            data_value.append((0, 0, cash_flow_statement_values))
        return data_value


class AccountPaymentReportLineRegister(models.TransientModel):
    _name = 'account.payment.report.line.register'
    _description = 'Account Payment Report Line for Register Model'

    account_payment_id = fields.Many2one('account.payment.register', 'Account Payment Register')
    cash_flow_statement_id = fields.Many2one('cash.flow.statement', string="Fluxo", required=1)
    cash_flow_statement_line_id = fields.Many2one('cash.flow.statement.line', string='Linha do Fluxo', required=1,
                                                  default='default_name')
    amount = fields.Float("Amount")

    line_cashflow = fields.Boolean(string="Linha de Fluxo", default=False)

    @api.model_create_multi
    def create(self, vals):
        account_payment_id = (
            self.env['account.payment.register']
            .sudo()
            .search(
                [
                    ("id", "=", vals[0].get('account_payment_id'))
                ]
            )
        )

        # Verificar se o fluxo escolhido já se encontra na lista
        self.account_report_line_duplicate(vals)
        # Verificar se o valor das linhas é igual ao valor do pagamento
        amount_total_lines = self.get_amount_total_lines(account_payment_id.id)
        total_amount = sum([dictionary.get("amount") for dictionary in vals]) + sum(amount_total_lines.mapped("amount"))
        self.verify_amount_total_lines(account_payment_id, total_amount)

        res = super(AccountPaymentReportLineRegister, self).create(vals)
        return res

    def verify_amount_total_lines(self, account_move_id, total_amount):
        if (
                abs(total_amount) > abs(account_move_id.amount)
        ):
            raise ValidationError(
                _(
                    "Os valores inseridos excedem o valor do "
                    "pagamento. Verifique o valor total do recibo."
                )
            )
        elif (
                abs(total_amount) < abs(account_move_id.amount)
        ):
            raise ValidationError(
                _(
                    "Os valores inseridos são inferiores o valor do "
                    "pagamento. Verifique o valor total do recibo."
                )
            )

    def account_report_line_duplicate(self, vals):
        values = {dictionary['cash_flow_statement_line_id'] for dictionary in vals}
        account_report_line_duplicate = len(values) != len(vals)
        if account_report_line_duplicate:
            raise ValidationError(
                _(
                    f"Não pode existir fluxos duplicados na "
                    "lista. Remova ou altere o valor do existente."
                )
            )

    def get_amount_total_lines(self, account_payment_id):
        account_move_lines = (
            self.sudo()
            .search(
                [
                    ("account_payment_id", "=", account_payment_id)
                ]
            )
        )
        return account_move_lines
