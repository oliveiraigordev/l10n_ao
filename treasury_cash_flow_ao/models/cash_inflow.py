from odoo import models, fields, api,_
from odoo.exceptions import UserError, ValidationError

class AccountPayment(models.Model):
    _inherit = 'account.payment'

    is_direct_cash = fields.Boolean(string="Pagamento/Recebimento Direto de Caixa")
    cash_type = fields.Selection([
        ('receita', 'Receita Direta'),
        ('despesa', 'Despesa Direta')
    ], string="Tipo de Caixa", required="0")

    product_template_id = fields.Many2one(
        'product.template',
        string="Produto Associado",
        help="Produto relacionado a este pagamento ou recebimento direto."
    )

    account_id = fields.Many2one(
        'account.account',
        string="Conta Contábil do Produto",
        compute="_compute_account_from_product",
        store=True,
        readonly=False
    )
    cash_partner_name = fields.Char(
        string="Nome do Cliente/Fornecedor",
        help="Nome da pessoa ou entidade para esta operação de caixa. Não afeta a contabilidade."
    )
    company_id = fields.Many2one("res.company", string="Empresa", default=lambda self: self.env.company)

    @api.constrains('is_direct_cash', 'partner_id', 'cash_partner_name')
    def _check_required_party(self):
        for rec in self:
            if rec.is_direct_cash and not rec.cash_partner_name:
                raise ValidationError("Por favor, informe o nome do cliente/fornecedor no campo de texto.")
            if not rec.is_direct_cash and not rec.partner_id:
                raise ValidationError("Por favor, selecione o parceiro.")

    @api.depends('product_template_id', 'cash_type')
    def _compute_account_from_product(self):
        for rec in self:
            product = rec.product_template_id
            if product:
                if rec.cash_type == 'receita':
                    rec.account_id = product.property_account_income_id.id
                elif rec.cash_type == 'despesa':
                    rec.account_id = product.property_account_expense_id.id
                else:
                    rec.account_id = False
            else:
                rec.account_id = False

    def _prepare_move_line_default_vals(self, write_off_line_vals=None):
        move_lines = super()._prepare_move_line_default_vals(write_off_line_vals=write_off_line_vals)
        if self.is_direct_cash and self.account_id:
            for line in move_lines:
                if line.get('account_id') == self.destination_account_id.id:
                    line['account_id'] = self.account_id.id
        return move_lines

    def _synchronize_from_moves(self, changed_fields):
        if self._context.get('skip_account_move_synchronization'):
            return

        for pay in self.with_context(skip_account_move_synchronization=True):

            if pay.move_id.statement_line_id:
                continue

            move = pay.move_id
            move_vals_to_write = {}
            payment_vals_to_write = {}

            if 'journal_id' in changed_fields:
                if pay.journal_id.type not in ('bank', 'cash'):
                    raise UserError(_("A payment must always belongs to a bank or cash journal."))

            if 'line_ids' in changed_fields:
                all_lines = move.line_ids
                liquidity_lines, counterpart_lines, writeoff_lines = pay._seek_for_lines()

                if len(liquidity_lines) != 1:
                    raise UserError(_(
                        "Journal Entry %s is not valid. In order to proceed, the journal items must "
                        "include one and only one outstanding payments/receipts account.",
                        move.display_name,
                    ))

                # 🚫 AQUI FOI COMENTADA A RESTRIÇÃO
                # if len(counterpart_lines) != 1:
                #     raise UserError(_(
                #         "Journal Entry %s is not valid. In order to proceed, the journal items must "
                #         "include one and only one receivable/payable account (with an exception of "
                #         "internal transfers).",
                #         move.display_name,
                #     ))

                if any(line.currency_id != all_lines[0].currency_id for line in all_lines):
                    raise UserError(_(
                        "Journal Entry %s is not valid. In order to proceed, the journal items must "
                        "share the same currency.",
                        move.display_name,
                    ))

                if any(line.partner_id != all_lines[0].partner_id for line in all_lines):
                    raise UserError(_(
                        "Journal Entry %s is not valid. In order to proceed, the journal items must "
                        "share the same partner.",
                        move.display_name,
                    ))

                counterpart = counterpart_lines[0] if counterpart_lines else None

                if counterpart:
                    if counterpart.account_id.account_type == 'asset_receivable':
                        partner_type = 'customer'
                    else:
                        partner_type = 'supplier'

                    liquidity_amount = liquidity_lines.amount_currency

                    move_vals_to_write.update({
                        'currency_id': liquidity_lines.currency_id.id,
                        'partner_id': liquidity_lines.partner_id.id,
                    })

                    payment_vals_to_write.update({
                        'amount': abs(liquidity_amount),
                        'partner_type': partner_type,
                        'currency_id': liquidity_lines.currency_id.id,
                        'destination_account_id': counterpart.account_id.id,
                        'partner_id': liquidity_lines.partner_id.id,
                    })

                    if liquidity_amount > 0.0:
                        payment_vals_to_write.update({'payment_type': 'inbound'})
                    elif liquidity_amount < 0.0:
                        payment_vals_to_write.update({'payment_type': 'outbound'})

            move.write(move._cleanup_write_orm_values(move, move_vals_to_write))
            pay.write(move._cleanup_write_orm_values(pay, payment_vals_to_write))


