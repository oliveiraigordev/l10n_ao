# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class HrTaxPayWizard(models.TransientModel):
    _name = 'hr.tax.pay.wizard'
    _description = 'Pagamento de Impostos / Multas & Juros (Folha)'

    # Origem / contexto
    salary_payment_id = fields.Many2one('account.payment.salary', required=True, readonly=True)
    company_id = fields.Many2one('res.company', required=True, default=lambda s: s.env.company, readonly=True)
    currency_id = fields.Many2one('res.currency', required=True, default=lambda s: s.env.company.currency_id, readonly=True)

    # Dados do pagamento
    date = fields.Date(required=True, default=fields.Date.context_today)
    journal_id = fields.Many2one('account.journal', required=True, domain=[('type', 'in', ('bank', 'cash'))])
    payment_ref = fields.Char(string='Referência', default='Pagamento de Impostos')

    # Opções
    include_taxes = fields.Boolean(string='Pagar Impostos (IRT/INSS)', default=True)
    include_surcharges = fields.Boolean(string='Pagar Multas & Juros', default=False)
    consolidate_move = fields.Boolean(string='Consolidar num único movimento', default=True)

    # Impostos
    pay_irt = fields.Boolean(string='Pagar IRT', default=True)
    pay_ss = fields.Boolean(string='Pagar INSS', default=True)
    pay_ss8 = fields.Boolean(string='Pagar INSS 8%', default=True)
    irt_amount = fields.Monetary(string='Valor IRT', currency_field='currency_id')
    inss_amount = fields.Monetary(string='Valor INSS', currency_field='currency_id')
    inss8_amount = fields.Monetary(string='Valor INSS 8%', currency_field='currency_id')
    irt_account_id = fields.Many2one('account.account', string='Conta IRT a pagar')
    inss_account_id = fields.Many2one('account.account', string='Conta INSS a pagar')
    inss8_account_id = fields.Many2one('account.account', string='Conta INSS 8% a pagar')

    # Multas & Juros (4 campos simples)
    penalty_amount = fields.Monetary(string='Valor da Multa', currency_field='currency_id')
    interest_amount = fields.Monetary(string='Valor dos Juros', currency_field='currency_id')
    penalty_account_id = fields.Many2one('account.account', string='Conta da Multa')
    interest_account_id = fields.Many2one('account.account', string='Conta dos Juros')

    # Totais
    total_taxes = fields.Monetary(compute='_compute_totals', string='Total Impostos', currency_field='currency_id')
    total_surcharges = fields.Monetary(compute='_compute_totals', string='Total Multas & Juros', currency_field='currency_id')
    total_to_pay = fields.Monetary(compute='_compute_totals', string='Total a Pagar', currency_field='currency_id')

    # ------------------------- defaults -------------------------

    @api.model
    def default_get(self, fields_list):
        vals = super().default_get(fields_list)
        salary = self.env['account.payment.salary'].browse(self.env.context.get('active_id'))

        if salary:
            vals.update({
                'salary_payment_id': salary.id,
                'company_id': salary.company_id.id,
                'currency_id': salary.currency_id.id or salary.company_id.currency_id.id,
                'date': salary.date,
                'journal_id': salary.journal_id.id,
                'payment_ref': 'Pagamento Impostos - %s' % (salary.name or salary.ref or salary.id),
                'irt_amount': abs(salary.hr_irt_amount or 0.0),
                'inss_amount': abs(salary.hr_ss_amount or 0.0),
                'inss8_amount': abs(salary.hr_ss_amount8 or 0.0),
                'pay_irt': bool(salary.pay_irt and not salary.irt_paid),
                'pay_ss': bool(salary.pay_ss and not salary.ss_paid),
                'pay_ss8': bool(salary.pay_ss8 and not salary.ss8_paid),
                'include_taxes': bool(salary.pay_tax),
            })

            # contas padrão de impostos (como no teu action_pay_tax)
            irt_rule = self.env['hr.salary.rule'].search([('category_id.code', '=', 'IRT')], limit=1)
            inss_rule = self.env['hr.salary.rule'].search([('category_id.code', '=', 'INSS')], limit=1)
            inss8_rule = self.env['hr.salary.rule'].search([('category_id.code', '=', 'INSS8')], limit=1)

            vals['irt_account_id'] = (irt_rule.account_credit.id
                                      if irt_rule and irt_rule.account_credit
                                      else self._check_account('3431', salary.company_id).id)
            vals['inss_account_id'] = (inss_rule.account_credit.id
                                       if inss_rule and inss_rule.account_credit
                                       else self._check_account('34951', salary.company_id).id)

            vals['inss8_account_id'] = (inss8_rule.account_credit.id
                                       if inss8_rule and inss8_rule.account_credit
                                       else self._check_account('34951', salary.company_id).id)
        return vals

    @api.model
    def _check_account(self, code, company):
        acct = self.env['account.account'].search([('code', '=', code), ('company_id', '=', company.id)], limit=1)
        if not acct:
            raise ValidationError(_("Conta %s não encontrada no plano da empresa %s.") % (code, company.display_name))
        return acct

    # ------------------------- totais -------------------------

    @api.depends('include_taxes', 'include_surcharges',
                 'pay_irt', 'pay_ss','pay_ss8','irt_amount', 'inss_amount','inss8_amount',
                 'penalty_amount', 'interest_amount')
    def _compute_totals(self):
        for w in self:
            taxes = 0.0
            if w.include_taxes:
                if w.pay_irt:
                    taxes += abs(w.irt_amount or 0.0)
                if w.pay_ss:
                    taxes += abs(w.inss_amount or 0.0)
                if w.pay_ss8:
                    taxes += abs(w.inss8_amount or 0.0)

            surch = 0.0
            if w.include_surcharges:
                surch += abs(w.penalty_amount or 0.0)
                surch += abs(w.interest_amount or 0.0)

            w.total_taxes = taxes
            w.total_surcharges = surch
            w.total_to_pay = taxes + surch

    # ------------------------- helpers -------------------------

    def _bank_account_id(self):
        self.ensure_one()
        j = self.journal_id
        pending = j.outbound_payment_method_line_ids.mapped('payment_account_id').filtered(lambda a: a)[:1]
        if pending:
            return pending.id
        if j.default_account_id:
            return j.default_account_id.id
        return self._check_account('43101001', self.company_id).id

    # ------------------------- montar moves -------------------------

    def _vals_move_taxes(self):
        self.ensure_one()
        if not self.include_taxes:
            return None

        lines = []
        total = 0.0
        if self.pay_irt and (self.irt_amount or 0.0) > 0.0:
            total += abs(self.irt_amount)
            lines.append({
                'name': 'Liquidação de IRT',
                'account_id': self.irt_account_id.id,
                'debit': abs(self.irt_amount),
                'credit': 0.0,
            })
        if self.pay_ss and (self.inss_amount or 0.0) > 0.0:
            total += abs(self.inss_amount)
            lines.append({
                'name': 'Liquidação de INSS',
                'account_id': self.inss_account_id.id,
                'debit': abs(self.inss_amount),
                'credit': 0.0,
            })

        if self.pay_ss8 and (self.inss8_amount or 0.0) > 0.0:
            total += abs(self.inss8_amount)
            lines.append({
                'name': 'Liquidação de INSS 8%',
                'account_id': self.inss8_account_id.id,
                'debit': abs(self.inss8_amount),
                'credit': 0.0,
            })
        if not lines:
            return None

        lines.append({
            'name': self.payment_ref or 'Pagamento Impostos',
            'account_id': self._bank_account_id(),
            'debit': 0.0,
            'credit': total,
        })
        return {
            'journal_id': self.journal_id.id,
            'date': self.date,
            'ref': self.payment_ref or 'Pagamento Impostos',
            'salary_tax_payment_id': self.salary_payment_id.id,
            'line_ids': [(0, 0, l) for l in lines],
        }

    def _vals_move_surcharges(self):
        self.ensure_one()
        if not self.include_surcharges:
            return None

        lines = []
        total = 0.0

        if (self.penalty_amount or 0.0) > 0.0:
            if not self.penalty_account_id:
                raise ValidationError(_("Informe a conta da Multa."))
            amt = abs(self.penalty_amount)
            total += amt
            lines.append({
                'name': 'Multa',
                'account_id': self.penalty_account_id.id,
                'debit': amt,
                'credit': 0.0,
            })

        if (self.interest_amount or 0.0) > 0.0:
            if not self.interest_account_id:
                raise ValidationError(_("Informe a conta dos Juros."))
            amt = abs(self.interest_amount)
            total += amt
            lines.append({
                'name': 'Juros',
                'account_id': self.interest_account_id.id,
                'debit': amt,
                'credit': 0.0,
            })

        if not lines:
            return None

        lines.append({
            'name': self.payment_ref or 'Pagamento Multas & Juros',
            'account_id': self._bank_account_id(),
            'debit': 0.0,
            'credit': total,
        })

        vals = {
            'journal_id': self.journal_id.id,
            'date': self.date,
            'ref': self.payment_ref or 'Pagamento Multas & Juros',
            'line_ids': [(0, 0, l) for l in lines],
        }
        # marca a origem (se existir o campo dedicado)
        if 'salary_penalty_id' in self.env['account.move']._fields:
            vals['salary_penalty_id'] = self.salary_payment_id.id
        else:
            vals['salary_tax_payment_id'] = self.salary_payment_id.id
        return vals

    # ------------------------- confirmar -------------------------

    def action_confirm(self):
        self.ensure_one()
        pay = self.salary_payment_id

        if not (self.include_taxes or self.include_surcharges):
            raise UserError(_('Selecione Impostos e/ou Multas & Juros.'))
        if self.total_to_pay <= 0:
            raise UserError(_('O total a pagar é zero.'))

        # Evitar duplicidade de impostos
        if self.include_taxes:
            if self.pay_irt and pay.irt_paid:
                raise ValidationError(_("O IRT já foi pago para este lançamento."))
            if self.pay_ss and pay.ss_paid:
                raise ValidationError(_("O INSS já foi pago para este lançamento."))
            if self.pay_ss8 and pay.ss8_paid:
                raise ValidationError(_("O INSS 8% já foi pago para este lançamento."))

        created = self.env['account.move']

        if self.consolidate_move and self.include_taxes and self.include_surcharges:
            vt = self._vals_move_taxes() or {'line_ids': []}
            vs = self._vals_move_surcharges() or {'line_ids': []}

            tax_lines = [l[2] for l in vt['line_ids']]
            sur_lines = [l[2] for l in vs['line_ids']]
            lines = tax_lines + sur_lines
            if not lines:
                raise UserError(_('Sem linhas para lançar.'))

            bank_id = self._bank_account_id()
            payload = [l for l in lines if not (l.get('credit') and l.get('account_id') == bank_id)]
            total_debit = sum(l['debit'] for l in payload)
            payload.append({
                'name': self.payment_ref or 'Pagamento Impostos/Multas & Juros',
                'account_id': bank_id,
                'debit': 0.0,
                'credit': total_debit,
            })

            vals = {
                'journal_id': self.journal_id.id,
                'date': self.date,
                'ref': self.payment_ref or 'Pagamento Impostos/Multas & Juros',
                'salary_tax_payment_id': pay.id,
                'line_ids': [(0, 0, l) for l in payload],
            }
            if 'salary_penalty_id' in self.env['account.move']._fields:
                vals['salary_penalty_id'] = pay.id

            mv = self.env['account.move'].create(vals)
            mv.action_post()
            created |= mv
        else:
            vt = self._vals_move_taxes()
            if vt:
                m1 = self.env['account.move'].create(vt)
                m1.action_post()
                created |= m1
            vs = self._vals_move_surcharges()
            if vs:
                m2 = self.env['account.move'].create(vs)
                m2.action_post()
                created |= m2

        if self.include_taxes:
            if self.pay_irt and (self.irt_amount or 0.0) > 0:
                pay.irt_paid = True
            if self.pay_ss and (self.inss_amount or 0.0) > 0:
                pay.ss_paid = True
            if self.pay_ss8 and (self.inss_amount or 0.0) > 0:
                pay.ss8_paid = True

        return {
            'type': 'ir.actions.act_window',
            'name': _('Movimentos Gerados'),
            'res_model': 'account.move',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', created.ids)],
        }


class HrTaxPayWizardSurchargeLine(models.TransientModel):
    _name = 'hr.tax.pay.wizard.surcharge.line'
    _description = 'Linha Multas & Juros (Wizard)'

    wizard_id = fields.Many2one('hr.tax.pay.wizard', ondelete='cascade')
    kind = fields.Selection([('interest', 'Juros'), ('penalty', 'Multa')], default='interest', required=True)
    tax_code = fields.Selection([('IRT', 'IRT'), ('INSS', 'INSS'),('OTHER', 'Outro')], string='Relacionado a', default='OTHER')
    name = fields.Char(string='Descrição')
    account_id = fields.Many2one('account.account', string='Conta de Despesa/Resultado', required=True)
    amount = fields.Monetary(string='Valor', required=True)
    currency_id = fields.Many2one(related='wizard_id.currency_id', readonly=True)

    def display_name_wizard(self):
        self.ensure_one()
        lbl_k = dict(self._fields['kind'].selection).get(self.kind, '')
        lbl_t = dict(self._fields['tax_code'].selection).get(self.tax_code, '')
        base = ('%s %s' % (lbl_k, lbl_t)).strip()
        return self.name or base
