# -*- coding: utf-8 -*-
# addons/hr_payment_penalty/models/salary_penalty_wizard.py
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class SalaryPenaltyWizard(models.TransientModel):
    _name = 'salary.penalty.wizard'
    _description = 'Registrar Multas e Juros'

    salary_payment_id = fields.Many2one(
        'account.payment.salary',
        required=True,
        ondelete='cascade',
        oldname='payment_id',
    )

    journal_id = fields.Many2one(
        'account.journal',
        required=True,
        domain="[('type', 'in', ('bank', 'cash'))]",
        default=lambda s: (
            s.env.context.get('default_journal_id')
            or s.env['account.journal'].search([('type', '=', 'bank')], limit=1)
        ),
    )

    account_id = fields.Many2one(
        'account.account',
        required=True,
    )

    amount = fields.Monetary(
        string='Valor da Multa/Juro',
        required=True,
        currency_field='currency_id',
    )

    currency_id = fields.Many2one(
        related='salary_payment_id.currency_id',
        readonly=True,
    )
    company_id = fields.Many2one(
        related='salary_payment_id.company_id',
        readonly=True,
    )

    def button_confirm(self):
        self.ensure_one()
        if self.amount <= 0:
            raise ValidationError(_("O valor deve ser maior que zero."))

        move_vals = {
            'journal_id': self.journal_id.id,
            'date': fields.Date.today(),
            'ref': _('Multas/Juros - %s') % self.salary_payment_id.name,
            'salary_penalty_id': self.salary_payment_id.id,
            'line_ids': [
                (0, 0, {
                    'name': _('Multas e Juros'),
                    'account_id': self.account_id.id,
                    'debit': self.amount,
                    'credit': 0.0,
                }),
                (0, 0, {
                    'name': _('Saída Banco'),
                    'account_id': self.journal_id.default_account_id.id,
                    'debit': 0.0,
                    'credit': self.amount,
                }),
            ],
        }
        move = self.env['account.move'].create(move_vals)
        move._post()
        return {'type': 'ir.actions.act_window_close'}


class AccountMove(models.Model):
    _inherit = 'account.move'

    salary_penalty_id = fields.Many2one(
        'account.payment.salary',
        string='Pagamento de Multas/Juros',
        ondelete='set null',
    )
