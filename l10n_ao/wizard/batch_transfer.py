from odoo import models, fields


class BatchTransfer(models.TransientModel):
    _name = 'l10n_ao.batch.transfer'
    _description = 'Batch Transfer Wizard'

    ref = fields.Text(string='Referência', required=True)
    amount = fields.Monetary(
        string='Valor',
        required=True,
        currency_field='currency_id',
    )
    currency_id = fields.Many2one(
        comodel_name='res.currency',
        string='Moeda',
        required=True,
        default=lambda self: self.env.company.currency_id,
    )
    origin_account_id = fields.Many2one(
        'account.account',
        string='Conta de Transferência',
        required=True,
    )
    destination_account_id = fields.Many2one(
        'account.account',
        string='Conta de Destino',
        required=True,
    )
    transfer_date = fields.Date(
        string='Data de Transferência',
        required=True,
        default=fields.Date.context_today,
    )
    origin_account_balance = fields.Float(
        related='origin_account_id.current_balance',
        string='Saldo da Conta de Transferência',
        readonly=True
    )
    destination_account_balance = fields.Float(
        related='destination_account_id.current_balance',
        string='Saldo da Conta de Destino',
        readonly=True
    )

    def action_transfer(self):
        self.ensure_one()
        if self.amount <= 0:
            raise ValueError("O valor da transferência deve ser positivo.")

        move_vals = {
            'move_type': 'entry',
            'journal_id': self.env.ref('l10n_ao.journal_internal_transfer').id,
            'ref': self.ref,
            'line_ids': [
                (0, 0, {
                    'account_id': self.origin_account_id.id,
                    'name': f'Transferência para {self.destination_account_id.name}',
                    'credit': self.amount,
                    'debit': 0.0,
                }),
                (0, 0, {
                    'account_id': self.destination_account_id.id,
                    'name': f'Transferência de {self.origin_account_id.name}',
                    'credit': 0.0,
                    'debit': self.amount,
                }),
            ],
        }
        move = self.env['account.move'].create(move_vals)
        move.action_post()
        return move