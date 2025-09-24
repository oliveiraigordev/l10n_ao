from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class AccountPayment(models.Model):
    _inherit = "account.payment"

    account_payment_report_line_ids = fields.One2many('account.payment.report.line', 'account_payment_id',
                                                      string='Fluxo de Caixa')
    cash_flow_in_payment = fields.Boolean("Registar Fluxo de Caixa no Pagamento",
                                          related="company_id.cash_flow_in_payment", readonly=False)

    line_cashflow = fields.Boolean(string="Linha de Fluxo", default=False)
    register_cashflow = fields.Boolean(string="Registrar Fluxo de Caixa", default=False)
    register_cashflow_computed  = fields.Boolean(string="Meu Campo Computado", compute="_compute_register_cashflow_computed")
    register_count = fields.Integer(string="Meu Campo Computado", default=1)

    def _compute_register_cashflow_computed(self):
        for record in self:
            if record.register_cashflow:
                if record.account_payment_report_line_ids:
                    for line in record.account_payment_report_line_ids:
                        cash_flow_map = self.env['cash.flow.statement.map'].search(
                            [('doc_number', '=', record.display_name)])
                        for i in cash_flow_map:
                            i.unlink()
            record.register_cashflow_computed = True
            if record.cash_flow_in_payment and not record.account_payment_report_line_ids and record.state == 'posted' and not record.register_cashflow:
                record.cash_flow_in_payment = False

    @api.onchange('partner_id')
    def _onchange_cash_flow_in_payment_register(self):
        for record in self:
            if not record.partner_id:
                config_value = record.sudo().company_id.cash_flow_in_payment_register
                if config_value:
                    record.register_cashflow = True
                else:
                    record.register_cashflow = False

    @api.onchange('amount')
    def _onchange_amount(self):
        for record in self:
            if record.account_payment_report_line_ids:
                for amount_default in record.account_payment_report_line_ids:
                    amount_default.amount = record.amount

    @api.onchange('account_payment_report_line_ids')
    def _onchange_amount_payment(self):
        for record in self:
            if record.account_payment_report_line_ids:
                for  aprli in record.account_payment_report_line_ids:
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
                            if aprli.amount == 0 and record.amount != 0:
                                aprli.sudo().amount = record.amount
                        else:
                            aprli.sudo().cash_flow_statement_line_id = False
                    else:
                        aprli.sudo().cash_flow_statement_line_id = False


    @api.onchange('register_cashflow')
    def _onchange_register_cashflow(self):
        if self.ids:
            if self.sudo().register_cashflow:
                # self.register_cashflow = True
                self.company_id.update({
                    'cash_flow_in_payment': True
                })
            else:
                # self.register_cashflow = True
                self.sudo().company_id.update({
                    'cash_flow_in_payment': False
                })

        else:
            if not self.register_cashflow:
                self.sudo().register_cashflow = True
                self.sudo().company_id.update({
                    'cash_flow_in_payment': True
                })
                record = self.env['account.payment'].browse(self)
                record.invalidate_cache()
                self.env.cr.commit()



    def write(self, vals):
        payment = super(AccountPayment, self).write(vals)
        for inv in self:
            # Verificar se foi adicionado os fluxos
            if inv.account_payment_report_line_ids and inv.state == 'posted':
                # passar os fluxo de caixa escolhido no pagamento ao movimento do diário
                inv.create_cash_flow_statement_account_move()
            elif inv.register_cashflow and not inv.account_payment_report_line_ids and inv.state == 'posted':
                raise ValidationError(
                    _(
                        f"É obrigatório fornecer o Fluxo de Caixa na "
                        "lista, para confirmar o pagamento."
                    )
                )

            if inv.account_payment_report_line_ids and inv.state != 'posted':
                # Remover os fluxo de caixa escolhido no pagamento ao movimento do diário
                inv.move_id.account_move_report_line_ids.unlink()

        return payment

    def create_cash_flow_statement_account_move(self):
        data_value = []
        move_line_ids = self.move_id.line_ids.filtered(
            lambda r: r.account_id.account_type in ['asset_cash', 'asset_current'])
        for record in self.account_payment_report_line_ids:
            cash_flow_statement_line = self.update_cash_flow_statement_account_move(record)
            if not cash_flow_statement_line:
                cash_flow_statement_values = {
                    'account_id': move_line_ids.account_id.id,
                    'cash_flow_statement_id': record.cash_flow_statement_id.id,
                    'cash_flow_statement_line_id': record.cash_flow_statement_line_id.id,
                    'amount': record.amount
                }
                data_value.append((0, 0, cash_flow_statement_values))
            else:
                cash_flow_statement_line.amount = record.amount

        if data_value:
            self.move_id.write({'account_move_report_line_ids': data_value})

    def update_cash_flow_statement_account_move(self, cash_flow_line_id):
        cash_flow_statement_line = (
            self.env["account.move.report.line"]
            .sudo()
            .search(
                [
                    ("account_move_id", "=", self.move_id.id),
                    ("cash_flow_statement_id", "=", cash_flow_line_id.cash_flow_statement_id.id),
                    ("cash_flow_statement_line_id", "=", cash_flow_line_id.cash_flow_statement_line_id.id)
                ]
            )
        )
        return cash_flow_statement_line
