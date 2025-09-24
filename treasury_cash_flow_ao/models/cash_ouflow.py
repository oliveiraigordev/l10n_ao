from datetime import datetime
from odoo import models, api, fields


class CashOutflow(models.Model):
    _name = 'account.cash.outflow'
    _description = 'Operações de Tesouraria'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string="Referência", required=True, default="Novo", copy=False, readonly=True)
    operation_type = fields.Selection([
        ('outbound', 'Out'), ('inbound', 'In')
    ], string="Operation Type")
    entity_type = fields.Selection([
        ('customer', 'Cliente'),
        ('supplier', 'Fornecedor')
    ], string="Tipo de Entidade", required=True)
    payment_amount = fields.Monetary(string="Valor do Pagamento", required=True)
    payment_date = fields.Date(string="Data de Pagamento", required=True, default=fields.Date.today)
    memo = fields.Text(string="Observações")
    customer = fields.Char(string="Cliente")
    journal_id = fields.Many2one('account.journal', string="Diário", required=True)
    currency_id = fields.Many2one('res.currency', string='Moeda', required=True, default=lambda self: self.env.company.currency_id)

    # Estado do fluxo de caixa
    state = fields.Selection([
        ('draft', 'Rascunho'),
        ('posted', 'Confirmado'),
        ('cancelled', 'Cancelado'),
    ], string='Estado', default='draft', tracking=True)

    move_id = fields.Many2one('account.move', string="Lançamento Contábil")
    date_update = fields.Datetime(string="Última Atualização", readonly=True)

    @api.model
    def create(self, vals):
        if vals.get('name', 'Novo') == 'Novo':
            vals['name'] = self.env['ir.sequence'].next_by_code('account.treasury.operation') or 'Novo'
        return super().create(vals)

    # def write(self, values):
    #     values['date_update'] = datetime.now()
    #     return super(TreasuryOperation, self).write(values)
    #
    # def post(self):
    #     self.journal_entries()
    #     self.state = 'posted'
    #
    # def action_draft(self):
    #     if self.move_id:
    #         self.move_id.unlink()
    #     self.state = 'draft'

    # def action_cancel(self):
    #     if self.move_id:
    #         reversal = self.env["account.move.reversal"].create({
    #             'move_ids': [(6, 0, [self.move_id.id])],
    #             'date_mode': 'custom',
    #             'journal_id': self.journal_id.id,
    #             'date': fields.Date.today()
    #         })
    #         reversal.reverse_moves()
    #     self.state = 'cancelled'


class Treasury(models.Model):
    _name = 'account.treasury.cashflow'
    _description = 'Operações de Tesouraria'
