import logging
from odoo import models, fields, api, Command, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class BankRecWidget(models.Model):
    _inherit = 'bank.rec.widget'

    # --------------------------------------------------
    # CAMPOS
    # --------------------------------------------------
    salary_move_ids = fields.Many2many(
        'account.move.line',
        'bank_rec_salary_move_rel',
        'widget_id',
        'move_line_id',
        string="Movimentos de Salário Pendentes",
        compute='_compute_salary_moves',
        readonly=True,
    )

    salary_move_selected = fields.Many2many(
        'account.move.line',
        'bank_rec_salary_selected_rel',
        'widget_id',
        'move_line_id',
        string="Movimentos Selecionados"
    )

    # --------------------------------------------------
    # 1.  CARREGAR LINHAS PENDENTES (CRÉDITO)
    # --------------------------------------------------

    @api.depends('st_line_id')
    def _compute_salary_moves(self):
        for wiz in self:
            # --- Precisa de extrato ---
            if not wiz.st_line_id:
                wiz.salary_move_ids = [(5, 0, 0)]
                continue

            st_line = wiz.st_line_id
            journal = st_line.journal_id

            # --- Pagamentos cujos diários (principal, impostos ou parciais)
            #     tenham relação com o diário do extrato ---
            pagamentos = self.env['account.payment.salary'].search([
                ('date', '<=', st_line.date),
                '|',
                ('journal_id', '=', journal.id),  # principal
                '|',
                ('tax_move_ids.journal_id', '=', journal.id),  # impostos
                ('partial_move_ids.journal_id', '=', journal.id),  # parciais
            ])
            if not pagamentos:
                wiz.salary_move_ids = [(5, 0, 0)]
                continue

            # --- Movimentos contábeis ligados a esses pagamentos ---
            movs = (
                    pagamentos.mapped('move_id')
                    | pagamentos.mapped('tax_move_ids')
                    | pagamentos.mapped('partial_move_ids')
            ).filtered(lambda m: m)

            # --- Todos os diários envolvidos ---
            journals_parc = (movs.mapped('journal_id') | journal).filtered(lambda j: j)

            # --- Contas transitórias de TODOS esses diários ---
            contas = (
                    journals_parc.mapped('outbound_payment_method_line_ids.payment_account_id')
                    | journals_parc.mapped('default_account_id')
            ).filtered(lambda a: a)

            # Inclui quaisquer contas 48xxxxx usadas nos movimentos (pagamentos parciais)
            contas |= movs.mapped('line_ids.account_id').filtered(lambda a: a.code.startswith('48'))

            if not contas:
                wiz.salary_move_ids = [(5, 0, 0)]
                continue

            # --- Linhas a crédito, não reconciliadas, nessas contas ---
            linhas = self.env['account.move.line'].search([
                ('move_id', 'in', movs.ids),
                ('account_id', 'in', contas.ids),
                ('reconciled', '=', False),
                ('balance', '<', 0),
            ])

            wiz.salary_move_ids = [(6, 0, linhas.ids)]

    # --------------------------------------------------
    # 2.  AÇÃO PRINCIPAL DE RECONCILIAÇÃO
    # --------------------------------------------------
    def action_reconcile_salary(self):
        self.ensure_one()
        if not self.salary_move_selected:
            raise UserError(_("Selecione ao menos um movimento de salário."))

        st_line = self.st_line_id
        journal  = st_line.journal_id

        bank_acc = journal.default_account_id
        if not bank_acc:
            raise UserError(_("Defina a conta bancária padrão para o diário %s") % journal.display_name)

        liq_line_old = st_line.move_id.line_ids.filtered(lambda l: l.account_id == bank_acc)[:1]
        if not liq_line_old:
            raise UserError(_("Não encontrei linha de liquidez para o diário."))

        # ----------- CRIAR NOVAS LINHAS (LIQUIDEZ + DÉBITOS) -----------
        cmd = []
        # nova linha de liquidez (crédito)
        cmd.append(Command.create({
            'sequence': 0,
            'account_id': liq_line_old.account_id.id,
            'date': liq_line_old.date,
            'name': liq_line_old.name,
            'partner_id': liq_line_old.partner_id.id,
            'currency_id': liq_line_old.currency_id.id,
            'amount_currency': liq_line_old.amount_currency,
            'balance': liq_line_old.balance,  # crédito (negativo)
        }))

        # débitos (contrapartida) — inverter sinal se necessário
        for idx, aml in enumerate(self.salary_move_selected, start=1):
            bal = aml.balance if aml.balance > 0 else -aml.balance
            amt_cur = aml.amount_currency if aml.amount_currency > 0 else -aml.amount_currency
            cmd.append(Command.create({
                'sequence': idx,
                'account_id': aml.account_id.id,
                'date': aml.date,
                'name': aml.name,
                'partner_id': aml.partner_id.id,
                'currency_id': aml.currency_id.id,
                'amount_currency': amt_cur,
                'balance': bal,
            }))

        # ----------- BALANÇO -----------
        deb = sum(c[2]['balance'] for c in cmd if c[2]['balance'] > 0)
        cred = abs(sum(c[2]['balance'] for c in cmd if c[2]['balance'] < 0))
        if deb != cred:
            raise UserError(_("Os comandos gerados não estão equilibrados."))

        # ----------- EXECUTAR -----------
        params = {
            'command_list': cmd,
            'salary_ids': self.salary_move_selected.ids,
        }
        self.js_action_reconcile_st_line(st_line.id, params)
        self.next_action_todo = {'type': 'reconcile_st_line'}

    # --------------------------------------------------
    # 3.  LADO JS / EXECUÇÃO TÉCNICA
    # --------------------------------------------------
    @api.model
    def js_action_reconcile_st_line(self, st_line_id, params):
        if not params.get('salary_ids'):
            return super(BankRecWidget, self).js_action_reconcile_st_line(st_line_id, params)
        st_line = self.env['account.bank.statement.line'].browse(st_line_id)
        move    = st_line.move_id
        move_ctx = move.with_context(skip_invoice_sync=True,
                                     skip_invoice_line_sync=True,
                                     skip_account_move_synchronization=True,
                                     force_delete=True)

        move_ctx.write({'line_ids': [Command.clear()] + params['command_list']})
        if move_ctx.state == 'draft':
            move_ctx.action_post()
        for idx, aml_id in enumerate(params['salary_ids'], start=1):
            nova_linha = move_ctx.line_ids.filtered(lambda l: l.sequence == idx)
            salary_orig = self.env['account.move.line'].browse(aml_id)
            if not nova_linha:
                continue
            if nova_linha.account_id != salary_orig.account_id:
                continue
            (nova_linha + salary_orig).with_context(no_exchange_difference=True).reconcile()
