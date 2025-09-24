from odoo import fields, models, api, _
from odoo.exceptions import ValidationError
from odoo.tools.misc import formatLang
from datetime import timedelta



class TreasuryCashFlow(models.TransientModel):
    _name = 'treasury.cash.flow.report'
    _description = 'Cash Flow Report'
    _rec_name = "start_date"

    start_date = fields.Datetime(
        string='Start Date',
        default=fields.Datetime.now()
    )
    end_date = fields.Datetime(
        string='End Date',
        default=fields.Datetime.now()
    )
    journal_id = fields.Many2one(
        'account.journal',
        string='Diário',
        domain=[('type', 'in', ['bank', 'cash'])],
        required=True,
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Moeda',
        required=True,
        default=lambda self: self.env.user.company_id.currency_id
    )

    def amount_format(self, amount):
        return formatLang(self.env, amount)

    def get_cash_flow_data(self):
        lines = []

        start_day = self.start_date.date()

        domain_before = [
            ('journal_id', '=', self.journal_id.id),
            ('date', '<', start_day),
            ('state', '=', 'posted'),
        ]
        all_before = self.env['account.payment'].search(domain_before)

        if not all_before:
            balance = 0.0
            last_date = start_day
        else:
            # 1) Encontra a última data em que houve pagamento
            last_date = max(all_before.mapped('date'))
            # 2) Filtra só os pagamentos nessa última data
            payments_prev = all_before.filtered(lambda p: p.date == last_date)
            balance = 0.0
            for p in payments_prev:
                if p.payment_type == 'inbound':
                    balance += p.amount
                else:
                    balance -= p.amount

        lines.append({
            'date': last_date,
            'description': _('Saldo em %s') % last_date,
            'responsible': '',
            'debit': '',
            'credit': '',
            'balance': balance,
        })

        # Movimentos no período [start_day … end_day]
        domain_range = [
            ('journal_id', '=', self.journal_id.id),
            ('date', '>=', start_day),
            ('date', '<=', self.end_date.date()),
            ('state', '=', 'posted'),
        ]
        payments = self.env['account.payment'].search(domain_range, order="date asc")

        total_in = total_out = 0.0

        for p in payments:
            debit = credit = 0.0
            if p.payment_type == 'inbound':
                debit = p.amount
                total_in += p.amount
                balance += p.amount
            else:
                credit = p.amount
                total_out += p.amount
                balance -= p.amount

            lines.append({
                'date': p.date,
                'description': p.payment_number or p.name or '',
                'memorando': p.ref or '',
                'responsible': p.create_uid.name if p.create_uid else '',
                'debit': debit,
                'credit': credit,
                'balance': balance,
            })

        return {
            'journal_name': self.journal_id.name,
            'movement_count': len(payments),
            'start_balance': lines[0]['balance'],
            'total_debit': total_in,
            'total_credit': total_out,
            'end_balance': balance,
            'lines': lines,
        }


    def print_xlsx(self):
        return self.env.ref(
            'treasury_cash_flow_ao.action_cashflow_xlsx'
        ).report_action(self)


    def print_report(self):
        return self.env.ref('treasury_cash_flow_ao.report_cash_flow').report_action(self)
        raise ValidationError(_('Nenhum lançamento encontrado para este intervalo de datas!'))


class TreasuryCashFlow(models.Model):
    _name = 'account.cash.outflow'
    _description = 'Cash Flow Report'
