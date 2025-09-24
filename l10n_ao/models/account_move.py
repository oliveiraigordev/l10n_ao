# -*- coding: utf-8 -*-
from functools import partial
from odoo import models, fields, api, _
from odoo.tools.misc import formatLang
from contextlib import ExitStack, contextmanager
from odoo.exceptions import ValidationError, UserError
from odoo.tools import float_is_zero, float_compare, date_utils, DEFAULT_SERVER_DATE_FORMAT
from collections import defaultdict
from .saft_ao_file import saft_clean_void_values
from odoo.addons.l10n_ao.sign import sign
from datetime import date, timedelta
from json import dumps
import json


class AccountMoveAng(models.Model):
    _inherit = "account.move"

    _order = "invoice_date desc,name desc, id desc"

    counter_currency_id = fields.Many2one('res.currency', string='Counter currency')
    counter_value = fields.Float(compute='_compute_counter_value', string='Counter value')
    exchange_rate = fields.Float(compute='_compute_counter_value', string='Exchange Rate')
    amount_total_wth = fields.Monetary(_('Total Withhold'), store=True,
                                       currency_field='currency_id', compute='_compute_amount')
    amount_discount = fields.Monetary(_('Total Discounts'), store=True,
                                      currency_field='currency_id', compute='_compute_amount_discount')
    hash = fields.Char(string="Hash", copy=False, readonly=True)
    hash_control = fields.Char(string="Hash Control", copy=False, default="0")
    hash_to_sign = fields.Char(string="Has to sign", copy=False)
    saft_status_date = fields.Datetime("SAFT Status Date", copy=False)
    system_entry_date = fields.Datetime("Signature SAFT Datetime", copy=False)
    partner_name = fields.Char("Name", compute='set_customer_data', store=True)
    partner_street = fields.Char("Street", compute='set_customer_data', store=True)
    partner_street2 = fields.Char("Street2", compute='set_customer_data', store=True)
    partner_city = fields.Char("City", compute='set_customer_data', store=True)
    partner_state = fields.Char("State", compute='set_customer_data', store=True)
    partner_vat = fields.Char("NIF", compute='set_customer_data', store=True)
    iva_regime = fields.Char("IVA Regime", compute='set_customer_data', store=True)
    print_counter = fields.Integer("Control Number of printing", default=0, copy=False)
    journal_ao_id = fields.Many2one("account.journal.ao", copy=False)
    sequence_journal_ao = fields.Char("Sequência única Diário AO", copy=False)
    amount_tax_captive = fields.Monetary(string='Imposto Cativo', compute='_compute_amount', store=True, readonly=True)
    apply_captive = fields.Boolean("Applie Captive")
    late_wth_amount = fields.Monetary(string="Total Late Withhold",
                                      help="Field used to store amount reconciled in retention account", store=True)

    "" "este codigo é para pegar o juornal-ao que este vinculado dinamicamente com diário"""

    bank_account_ids = fields.Many2many(
        'res.partner.bank',
        string="Contas Bancárias para Documento",
        help="Selecione as contas bancárias que deverão aparecer neste documento. Se não for selecionada nenhuma, serão exibidas as contas definidas globalmente (Show on documents)."
    )

    is_retaining_entity_50 = fields.Boolean(
        related='partner_id.is_retaining_entity_50', store=True, readonly=True)

    is_retaining_entity_100 = fields.Boolean(
        related='partner_id.is_retaining_entity_100', store=True, readonly=True)

    @api.onchange('partner_id')
    def _compute_whenchange_partner(self):
        for record in self:
            record.set_customer_data()

    @api.constrains('partner_id')
    def _check_partner_address_nif(self):
        for record in self:
            if record.partner_id and record.move_type in ['out_invoice', 'out_refund']:
                partner = record.partner_id
                if not all(
                        [partner.city, partner.country_id, partner.vat]):
                    raise ValidationError(
                        "Não é possível criar uma fatura para este cliente!\n"
                        "Os seguintes campos são obrigatórios:\n"
                        "- Endereço (Cidade, País)\n"
                        "- NIF"
                    )
            record.set_customer_data()

    @api.onchange("journal_id")
    def get_jornalao_id(self):
        journal = self.journal_id.journal_ao_id
        self.journal_ao_id = journal

    @api.onchange("invoice_date")
    def onchange_date(self):
        if self.invoice_date:
            self.date = self.invoice_date

    def action_post(self):
        journal = self.journal_ao_id
        super(AccountMoveAng, self).action_post()
        if journal:
            self.journal_ao_id = journal
        else:
            self.journal_ao_id = self.journal_id.journal_ao_id

    def set_customer_data(self):
        for pt in self:
            if pt.state == "draft":
                pt.partner_name = pt.partner_id.display_name
                pt.partner_street = pt.partner_id.street
                pt.partner_street2 = pt.partner_id.street2
                pt.partner_state = pt.partner_id.state_id.name
                pt.partner_city = pt.partner_id.city
                pt.partner_vat = pt.partner_id.vat
                pt.iva_regime = pt.company_id.tax_regime_id.name

    def map_withholding_tax(self):
        tax_lines = self.invoice_line_ids.mapped("tax_ids").filtered(lambda t: t.is_withholding)
        return tax_lines

    # Override
    def _get_starting_sequence(self):
        starting_sequence = ""
        self.ensure_one()
        if self.env.company.country_id.code == "AO" and self.journal_id.type in ('sale', 'purchase'):
            if self.journal_id.type == 'sale':
                if "FT" == self.journal_id.code:
                    starting_sequence = "%s %04d/0" % (self.journal_id.code, self.date.year)
                else:
                    starting_sequence = "%s %04d/0" % (self.journal_id.code, self.date.year)
                if self.journal_id.refund_sequence and self.move_type in ('out_refund', 'in_refund'):
                    if self.move_type == 'out_refund':
                        starting_sequence = starting_sequence.replace("FT", "NC")
                    if self.move_type == 'in_refund':
                        starting_sequence = starting_sequence.replace("FTF", "NC")
            elif self.journal_id.type == 'purchase':
                if self.journal_id.code == "FTF":
                    starting_sequence = "%s %04d/0" % (self.journal_id.code, self.date.year)
                else:
                    starting_sequence = "%s %s%04d/0" % ("FTF", self.journal_id.code, self.date.year)
                if self.journal_id.refund_sequence and self.move_type in ('out_refund', 'in_refund'):
                    if self.move_type == 'out_refund':
                        starting_sequence = starting_sequence.replace("FT", "NC")
                    if self.move_type == 'in_refund':
                        starting_sequence = starting_sequence.replace("FTF", "NC")
        else:
            starting_sequence = "%s/%04d/%02d/0000" % (self.journal_id.code, self.date.year, self.date.month)
            if self.journal_id.refund_sequence and self.move_type in ('out_refund', 'in_refund'):
                starting_sequence = "R" + starting_sequence
        return starting_sequence

    def button_apply_captive_100(self):
        tax = self.env['account.tax']
        for line in self.invoice_line_ids:
            tax_id = line.tax_ids.filtered(lambda r: r.tax_type in 'IVA')
            tax_result = tax.search([('amount', '=', tax_id.amount), ('iva_tax_type', '=', 'CAT100'), (
                'type_tax_use', '=', 'sale' if self.move_type in ['out_invoice', 'out_refund'] else 'purchase')])
            if not tax_result:
                raise UserError(_("Não existe imposto cativo 100 com a mesma percentagem do imposto IVA aplicado na linha %s, por favor crie o imposto cativo 100 com a mesma percentagem do imposto IVA aplicado na linha") % line.name)
            line.write({'tax_ids': [(3, tax_id.id, 0), (4, tax_result.id, 0)]})
            

    def button_apply_captive_50(self):
        tax = self.env['account.tax']
        for line in self.invoice_line_ids:
            tax_id = line.tax_ids.filtered(lambda r: r.tax_type in 'IVA')
            tax_result = tax.search([('amount', '=', tax_id.amount), ('iva_tax_type', '=', 'CAT50'), (
                'type_tax_use', '=', 'sale' if self.move_type in ['out_invoice', 'out_refund'] else 'purchase')])
            if not tax_result:
                raise UserError(_("Não existe imposto cativo 50 com a mesma percentagem do imposto IVA aplicado na linha %s, por favor crie o imposto cativo 50 com a mesma percentagem do imposto IVA aplicado na linha") % line.name)
            line.write({'tax_ids': [(3, tax_id.id, 0), (4, tax_result.id, 0)]})

    # def button_cancel(self):
    #     if self.state == 'draft':
    #         raise ValidationError("Não é permitido anular documentos em Rascunho, os mesmos podem ser retificados ou excluídos pois os mesmos ainda não foram assinados "
    #                               "e não serão comunicados a nível da AGT")
    #     if self.invoice_date == fields.Date.today():
    #         return {
    #             'name': 'ANULAÇÃO DO DOCUMENTO',
    #             'type': 'ir.actions.act_window',
    #             'view_mode': 'form',
    #             'res_model': 'cancel.move.wizard',
    #             'target': 'new',
    #         }
    #     else:
    #         raise ValidationError(_("Não pode anular facturas cuja data seja superior ou inferior ao dia de Hoje, a anulação de factura apenas é permitida\n "
    #                                 "quando o documento foi emitido por engano ou contém erros que impedem a sua comunicação à AGT.\nSó se pode usar este método caso o destinatário\n do documento não o tenha em sua posse.É permito também anular um documento por meio de uma nota de crédito  que refere o documento original e que anula o seu valor total ou parcial. Esta opção deve ser usada quando o documento vai ser ou já foi comunicado à AGT e é necessário corrigir a respetiva situação tributária."))
    #
    #     #self.write({'auto_post': 'no', 'state': 'cancel'})

    @api.depends('invoice_line_ids.quantity', 'invoice_line_ids.price_unit', 'invoice_line_ids.discount')
    def _compute_amount_discount(self):
        for invoice in self:
            total_price = 0
            discount_amount = 0
            for line in invoice.invoice_line_ids.filtered(lambda l: l.discount > 0):
                total_price = (line.quantity * line.price_unit) * (line.discount / 100)
                tax_include = line.tax_ids.filtered(lambda tax: tax.price_include)
                if tax_include:
                    total_price = total_price / ((tax_include.amount + 100) / 100)
                discount_amount += total_price
            invoice.update({'amount_discount': discount_amount})

    # @api.depends_context('lang')
    # @api.depends(
    #     'invoice_line_ids.currency_rate',
    #     'invoice_line_ids.tax_base_amount',
    #     'invoice_line_ids.tax_line_id',
    #     'invoice_line_ids.price_total',
    #     'invoice_line_ids.price_subtotal',
    #     'invoice_payment_term_id',
    #     'partner_id',
    #     'currency_id',
    # )
    # def _compute_tax_totals(self):
    #     super()._compute_tax_totals()
    #     for move in self:
    #         amoun_tax = 0
    #         tax_id = move.invoice_line_ids.tax_ids.filtered(
    #             lambda r: r.iva_tax_type == 'CAT100' or r.iva_tax_type == 'CAT50')
    #         if len(tax_id) > 1:
    #             raise UserError(_("Não é possível aplicar mais de um imposto cativo"))
    #         elif move.move_type in ['out_invoice', 'out_refund','in_invoice', 'in_refund'] and tax_id:
    #             amoun_tax = int(move.tax_totals['amount_untaxed']) * self.env['account.tax'].search([('id', '=', tax_id.id)]).amount / 100
    #             move.tax_totals['amount_total'] = int(move['amount_untaxed']) + amoun_tax
    #             # move.tax_totals["groups_by_subtotal"]["Valor sem Impostos"]['formatted_tax_group_amount'] = str(amoun_tax) + "\xa0Kz"

    def _compute_counter_value(self):
        if self.counter_currency_id:
            rate = self.env['res.currency']._get_conversion_rate(self.currency_id, self.counter_currency_id,
                                                                 self.company_id,
                                                                 self.invoice_date or fields.Date.today())
        else:
            rate = 0.0
        self.counter_value = self.amount_total * rate
        self.exchange_rate = 1 / (rate or 1)

    # override: Adicionou-se uma condição para que ao criar novas facturas no odoo a primeira apareça em rascunho(DRAFT)
    # A primeira factura

    def resign(self, inv):
        content_hash = inv.get_new_content_to_sign()
        hash_to_sign = content_hash
        hash_control = ""
        hash = ""
        content_signed = inv.sign_move(content_hash).split(";")
        if content_hash != content_signed:
            hash_control = content_signed[1] if len(content_signed) >= 1 else "0"
            hash = content_signed[0]
        invoices = {
            "hash_control": hash_control,
            "hash": hash,
            "hash_to_sign": hash_to_sign
        }
        inv.write(invoices)

    def _reverse_moves(self, default_values_list=None, cancel=False):
        # OVERRIDE
        # Verificar se já existe uma Nota de Credito criada
        reversal_move_ids = self.env['account.move'].search([('reversed_entry_id', '=', self.id)])
        if reversal_move_ids and default_values_list:
            if default_values_list:
                new_reverse_moves = super(AccountMoveAng, self)._reverse_moves(default_values_list, cancel)
                if new_reverse_moves.state == 'posted':
                    raise ValidationError(
                        f"Não é possível criar uma nota de crédito com opção 'Reembolso Total' por já existir "
                        f"uma nota de crédito parcial, poderá utilizar a opção 'Reembolso Parcial'")

                for move_line in self.invoice_line_ids:
                    invoice_line_values = []
                    # Verificar se as quantidades existentes na nota de credito já existente
                    reversed_move_lines = reversal_move_ids.invoice_line_ids.filtered(
                        lambda p: p.product_id == move_line.product_id)
                    line_quantity = sum(reversed_move_lines.mapped('quantity'))
                    if line_quantity <= move_line.quantity:
                        reversed_move_line = new_reverse_moves.invoice_line_ids.filtered(
                            lambda p: p.product_id == move_line.product_id)
                        reversed_move_line.quantity = move_line.quantity - line_quantity
                    else:
                        raise ValidationError(
                            f"Não é possível anular esta factura, por que a quantidade informada da linha {move_line.name}, "
                            f"já foi infomada numa nota de crédito, verifique na aba outras informações")

                return new_reverse_moves
        else:
            reverse_moves = super(AccountMoveAng, self)._reverse_moves(default_values_list, cancel)
            if self._context.get('default_l10n_cl_edi_reference_doc_code') == '2':
                for move in reverse_moves:
                    move.invoice_line_ids = [[5, 0], [0, 0, {
                        'account_id': move.journal_id.default_account_id.id,
                        'name': _('Where it says: %s should say: %s') % (
                            self._context.get('default_l10n_cl_original_text'),
                            self._context.get('default_l10n_cl_corrected_text')),
                        'quantity': 1,
                        'price_unit': 0.0,
                    }, ], ]

            return reverse_moves

    @api.depends('posted_before', 'state', 'journal_id', 'date')
    def _compute_name(self):
        self = self.sorted(lambda m: (m.date, m.ref or '', m.id))
        highest_name = self[0]._get_last_sequence(lock=False) if self else False

        for move in self:
            if not highest_name and move == self[0] and not move.posted_before and move.date and (
                    not move.name or move.name == '/') and (
                    not move.move_type in ["out_invoice", "in_invoice", "out_refund", "in_refund"]):
                # In the form view, we need to compute a default sequence so that the user can edit
                # it. We only check the first move as an approximation (enough for new in form view)
                move._set_next_sequence()
            elif move.quick_edit_mode and not move.posted_before:
                # We always suggest the next sequence as the default name of the new move
                move._set_next_sequence()
            elif (move.name and move.name != '/') or move.state != 'posted':
                try:
                    move._constrains_date_sequence()
                    # The name matches the date: we don't recompute
                except ValidationError:
                    # Has never been posted and the name doesn't match the date: recompute it
                    move._set_next_sequence()
            else:
                # The name is not set yet and it is posted
                move._set_next_sequence()

            if move.state == "draft" and move.move_type in ["in_invoice"]:
                move._set_next_sequence()

        self.filtered(lambda m: not m.name).name = '/'

    # OVERRIDE DO MÉTODO COMPUTE AMOUNT PARA CALCULO DA RETENÇÃO
    @api.depends(
        'line_ids.matched_debit_ids.debit_move_id.move_id.payment_id.is_matched',
        'line_ids.matched_debit_ids.debit_move_id.move_id.line_ids.amount_residual',
        'line_ids.matched_debit_ids.debit_move_id.move_id.line_ids.amount_residual_currency',
        'line_ids.matched_credit_ids.credit_move_id.move_id.payment_id.is_matched',
        'line_ids.matched_credit_ids.credit_move_id.move_id.line_ids.amount_residual',
        'line_ids.matched_credit_ids.credit_move_id.move_id.line_ids.amount_residual_currency',
        'line_ids.balance',
        'line_ids.currency_id',
        'line_ids.amount_currency',
        'line_ids.amount_residual',
        'line_ids.amount_residual_currency',
        'line_ids.payment_id.state',
        'line_ids.full_reconcile_id')
    def _compute_amount(self):
        for move in self:
            total_untaxed, total_untaxed_currency = 0.0, 0.0
            total_tax, total_tax_currency = 0.0, 0.0
            total_residual, total_residual_currency = 0.0, 0.0
            total, total_currency = 0.0, 0.0

            amount_tax_wth = 0.0
            iva_captive_amount = 0.0

            # Só faz o cálculo de retenção se for um documento do tipo fatura
            if move.is_invoice(True):

                # -------------------------------------------
                # 1) CALCULAR BASE E VERIFICAR LIMITE DA RETENÇÃO
                # -------------------------------------------
                total_retention_base = 0.0  # Soma das linhas que possuem retenção
                wht_limit = 0.0  # Limite definido no imposto
                wht_rate = 0.0  # Alíquota de retenção

                for line in move.invoice_line_ids:
                    line_base = line.price_unit * line.quantity * (1 - (line.discount or 0.0) / 100.0)

                    for tax in line.tax_ids:
                        # Verifica se é imposto de retenção (on_payment) e pega limite/aliquota
                        if tax.tax_exigibility == 'on_payment' and tax.is_withholding:
                            if tax.limit_amount_wht > wht_limit:
                                wht_limit = tax.limit_amount_wht
                                wht_rate = tax.amount

                            total_retention_base += line_base

                if move.amount_total > wht_limit:
                    # Se o total da base de retenção exceder o limite, calcula a retenção
                    if wht_limit > 0 and total_retention_base >= wht_limit:
                        amount_tax_wth = abs(total_retention_base * (wht_rate / 100.0))

                # -------------------------------------------
                # 2) CALCULAR IVA CATIVO (SE APLICÁVEL)
                # -------------------------------------------
                for line in move.invoice_line_ids:
                    line_base = line.price_unit * line.quantity
                    for tax in line.tax_ids:
                        if tax.iva_tax_type in ['CAT50', 'CAT100'] and tax.tax_exigibility == 'on_invoice':
                            amount_tax = line_base * (tax.amount / 100.0)
                            # Se CAT50, só metade vira 'cativo'; se CAT100, todo o valor.
                            if tax.iva_tax_type == 'CAT50':
                                iva_captive_amount += abs(amount_tax - (amount_tax * 0.5))
                            else:
                                iva_captive_amount += abs(amount_tax)

            # -------------------------------------------
            # 3) SOMA DE IMPOSTOS, VALORES SEM IMPOSTOS E RESIDUAL
            # -------------------------------------------
            for line in move.line_ids:
                if move.is_invoice(True):
                    if line.display_type == 'tax' or (line.display_type == 'rounding' and line.tax_repartition_line_id):
                        # Soma de impostos
                        total_tax += line.balance
                        total_tax_currency += line.amount_currency
                        total += line.balance
                        total_currency += line.amount_currency
                    elif line.display_type in ('product', 'rounding'):
                        # Soma de valores sem impostos
                        total_untaxed += line.balance
                        total_untaxed_currency += line.amount_currency
                        total += line.balance
                        total_currency += line.amount_currency
                    elif line.display_type == 'payment_term':
                        # Soma de valores residuais
                        total_residual += line.amount_residual
                        total_residual_currency += line.amount_residual_currency
                else:
                    # Lançamento contábil diverso (não é fatura)
                    if line.debit:
                        total += line.balance
                        total_currency += line.amount_currency

            # -------------------------------------------
            # 4) DEDUÇÃO DO IVA CATIVO
            # -------------------------------------------
            move.amount_residual -= iva_captive_amount
            total_residual -= iva_captive_amount

            # -------------------------------------------
            # 5) APLICAÇÃO DOS SINAIS E ATRIBUIÇÃO NOS CAMPOS DO MOVE
            # -------------------------------------------
            sign = move.direction_sign
            move.amount_untaxed = sign * total_untaxed_currency
            move.amount_tax = sign * total_tax_currency
            move.amount_total = sign * total_currency
            move.amount_residual = -sign * total_residual_currency

            move.amount_untaxed_signed = -total_untaxed
            move.amount_tax_signed = -total_tax
            move.amount_total_signed = abs(total) if move.move_type == 'entry' else -total
            move.amount_residual_signed = total_residual
            move.amount_total_in_currency_signed = (
                abs(move.amount_total) if move.move_type == 'entry' else -(sign * move.amount_total)
            )

            # -------------------------------------------
            # 6) VALOR TOTAL COM RETENÇÃO
            # -------------------------------------------
            # Se existir retenção calculada, subtrai do total da fatura.
            move.amount_total_wth = move.amount_total - amount_tax_wth if amount_tax_wth else 0.0

            # Campo para armazenar o valor do IVA cativo
            move.amount_tax_captive = iva_captive_amount

    # def _compute_amount(self):
    #     for move in self:
    #         total_untaxed, total_untaxed_currency = 0.0, 0.0
    #         total_tax, total_tax_currency = 0.0, 0.0
    #         total_residual, total_residual_currency = 0.0, 0.0
    #         total, total_currency = 0.0, 0.0
    #         amount_tax_wth = 0.0
    #         iva_captive_amount = 0.0
    #         # Foi adicionada esta parte do código para cálculo do Imposto retenção
    #         if move.is_invoice(True):
    #             for line in move.invoice_line_ids:
    #                 for tax in line.tax_ids:
    #                     self.with_context()
    #                     tax_base_amount = line.price_unit * line.quantity
    #                     if tax.tax_exigibility == 'on_payment' and tax.is_withholding and \
    #                             tax_base_amount >= tax.limit_amount_wht:
    #                         # Tax amount.
    #                         tax_amount = tax._compute_amount(
    #                             line.price_unit * line.quantity * (1 - (line.discount or 0.0) / 100.0),
    #                             line.price_unit,
    #                             line.quantity)
    #                         amount_tax_wth += abs(tax_amount)
    #
    #                     if tax.iva_tax_type in ['CAT50', 'CAT100'] and tax.tax_exigibility == 'on_invoice':
    #                         amount_tax = tax_base_amount * (tax.amount / 100)
    #                         iva_captive_amount += abs(
    #                             amount_tax - (amount_tax * 0.5 if tax.iva_tax_type == 'CAT50' else 0))
    #
    #         for line in move.line_ids:
    #             if move.is_invoice(True):
    #                 # === Invoices ===
    #                 if line.display_type == 'tax' or (line.display_type == 'rounding' and line.tax_repartition_line_id):
    #                     # Tax amount.
    #                     total_tax += line.balance
    #                     total_tax_currency += line.amount_currency
    #                     total += line.balance
    #                     total_currency += line.amount_currency
    #                 elif line.display_type in ('product', 'rounding'):
    #                     # Untaxed amount.
    #                     total_untaxed += line.balance
    #                     total_untaxed_currency += line.amount_currency
    #                     total += line.balance
    #                     total_currency += line.amount_currency
    #                 elif line.display_type == 'payment_term':
    #                     # Residual amount.
    #                     total_residual += line.amount_residual
    #                     total_residual_currency += line.amount_residual_currency
    #
    #
    #             else:
    #                 # === Miscellaneous journal entry ===
    #                 if line.debit:
    #                     total += line.balance
    #                     total_currency += line.amount_currency
    #
    #         # dedução do IVA Cativo no montante a pagar
    #         move.amount_residual -= iva_captive_amount
    #         total_residual -= iva_captive_amount
    #
    #         sign = move.direction_sign
    #         move.amount_untaxed = sign * total_untaxed_currency
    #         move.amount_tax = sign * total_tax_currency
    #         move.amount_total = sign * total_currency
    #         move.amount_residual = -sign * total_residual_currency
    #         move.amount_untaxed_signed = -total_untaxed
    #         move.amount_tax_signed = -total_tax
    #         move.amount_total_signed = abs(total) if move.move_type == 'entry' else -total
    #         move.amount_residual_signed = total_residual
    #         move.amount_total_in_currency_signed = abs(move.amount_total) if move.move_type == 'entry' else -(
    #                 sign * move.amount_total)
    #         move.amount_total_wth = move.amount_total - amount_tax_wth if amount_tax_wth else 0.0
    #         move.amount_tax_captive = iva_captive_amount

    def get_taxes_by_group(self):
        for move in self:
            lang_env = move.with_context(lang=move.partner_id.lang).env
            invoice_tax_lines = move.invoice_line_ids.filtered(lambda line: line.tax_ids)
            # tax_balance_multiplicator = -1 if move.is_inbound(True) else 1
            # tax_include_amount = 0
            res = {}
            # There are as many tax line as there are repartition lines
            done_taxes = set()
            for line in invoice_tax_lines:
                for tax_id in line.tax_ids:
                    res.setdefault(tax_id, {'base': 0.0, 'amount': 0.0})
                    tax_amount = tax_id._compute_amount(
                        line.quantity * line.price_unit * (1 - (line.discount or 0.0) / 100.0),
                        line.price_unit, line.quantity)
                    res[tax_id]['amount'] += tax_amount
                    tax_key_add_base = tuple([tax_id.id])
                    # if tax_key_add_base not in done_taxes:
                    # if line.currency_id and line.company_currency_id and line.currency_id != line.company_currency_id: Todo: Rever este Código
                    #     amount = line.company_currency_id._convert(line.tax_base_amount, line.currency_id,
                    #                                                line.company_id,
                    #                                                line.date or fields.Date.context_today(self))
                    # else:
                    amount = line.quantity * line.price_unit * (1 - (line.discount or 0.0) / 100.0)
                    res[tax_id]['base'] += amount
                    if tax_id.price_include:
                        res[tax_id]['base'] -= tax_amount
                    # The base should be added ONCE
                    done_taxes.add(tax_key_add_base)

            res = sorted(res.items(), key=lambda l: l[0].sequence)
            result = [(
                tax.name, amounts['amount'],
                amounts['base'],
                formatLang(lang_env, amounts['amount'], currency_obj=move.currency_id),
                formatLang(lang_env, amounts['base'], currency_obj=move.currency_id),
                len(res),
                tax
            ) for tax, amounts in res]
        return result

    @contextmanager
    def _sync_unbalanced_lines(self, container):
        yield
        # Skip posted moves.
        for invoice in (x for x in container['records'] if x.state != 'posted'):

            # L10n_ao Tis
            tax_lines = invoice.line_ids.filtered(lambda t: t.tax_line_id and t.tax_line_id.is_withholding)
            if tax_lines:
                return

            # Unlink tax lines if all taxes have been removed.
            if not invoice.line_ids.tax_ids:
                # if there isn't any tax but there remains a tax_line_id, it means we are currently in the process of
                # removing the taxes from the entry. Thus, we want the automatic balancing to happen in order  to have
                # a smooth process for tax deletion
                if not invoice.line_ids.filtered('tax_line_id'):
                    continue
                invoice.line_ids.filtered('tax_line_id').unlink()

            # Set the balancing line's balance and amount_currency to zero,
            # so that it does not interfere with _get_unbalanced_moves() below.
            balance_name = _('Automatic Balancing Line')
            existing_balancing_line = invoice.line_ids.filtered(lambda line: line.name == balance_name)
            if existing_balancing_line:
                existing_balancing_line.balance = existing_balancing_line.amount_currency = 0.0

            # Create an automatic balancing line to make sure the entry can be saved/posted.
            # If such a line already exists, we simply update its amounts.
            unbalanced_moves = self._get_unbalanced_moves({'records': invoice})
            if isinstance(unbalanced_moves, list) and len(unbalanced_moves) == 1:
                dummy, debit, credit = unbalanced_moves[0]

                vals = {'balance': credit - debit}
                if existing_balancing_line:
                    existing_balancing_line.write(vals)
                else:
                    vals.update({
                        'name': balance_name,
                        'move_id': invoice.id,
                        'account_id': invoice.company_id.account_journal_suspense_account_id.id,
                        'currency_id': invoice.currency_id.id,
                    })
                    self.env['account.move.line'].create(vals)

    def _check_last_invoice_date(self, invoice):
        date = fields.Date.today()
        for invoice in invoice:
            if not invoice.move_type in ['in_invoice', 'in_refund'] and not self.env[
                'ir.config_parameter'].sudo().get_param('dont_check_invoice_date'):
                inv = self.env['account.move'].search(
                    [('state', 'in', ['posted', 'paid']), ('move_type', 'in', ['out_invoice', 'out_refund']),
                     ('invoice_date', '>', invoice.invoice_date)])

                if inv:
                    raise ValidationError(
                        _("Não pode validar Factura cuja a data seja inferior a última factura que foi validada no sistema. esta foi a última factura e última data que o sistema registrou."))

                elif invoice.invoice_date > fields.Date.today():
                    raise ValidationError(
                        _("Não pode emitir facturas para cuja a data seja superior a data de hoje, \npor favor verifique a data da factura que está a tentar adicionar e retifique a mesma."))

    def get_new_content_to_sign(self):
        content_to_sign = ""
        if self.sequence_number - 1 >= 1:
            preview_last_invoice = self.sudo().search([('state', 'in', ['posted', 'cancel']), ('id', "!=", self.id),
                                                       ('company_id', '=', self.company_id.id),
                                                       ('move_type', '=', self.move_type),
                                                       ('sequence_prefix', '=', self.sequence_prefix),
                                                       ('journal_id', '=', self.journal_id.id),
                                                       ('system_entry_date', '<=', self.system_entry_date),
                                                       ('sequence_number', '=', self.sequence_number - 1)],
                                                      order="system_entry_date desc", limit=1)
            if preview_last_invoice:
                get_last_invoice_hash = preview_last_invoice.hash if preview_last_invoice.hash else ""
                system_entry_date = self.system_entry_date.isoformat(sep='T',
                                                                     timespec='auto') if self.system_entry_date else fields.Datetime.now().isoformat(
                    sep='T', timespec='auto')
                content_to_sign = ";".join((fields.Date.to_string(self.invoice_date), system_entry_date,
                                            self.name, str(format(self.amount_total, '.2f')),
                                            get_last_invoice_hash))
        elif self.sequence_number - 1 == 0:
            system_entry_date = self.system_entry_date.isoformat(sep='T',
                                                                 timespec='auto') if self.system_entry_date else fields.Datetime.now().isoformat(
                sep='T', timespec='auto')
            content_to_sign = ";".join((fields.Date.to_string(self.invoice_date), system_entry_date,
                                        self.name, str(format(self.amount_total, '.2f')), ""))
        return content_to_sign

    def sign_move(self, content_data):
        response = sign.sign_content(content_data)
        if response:
            return response
        return content_data

    def write(self, vals):
        # Override the write method to add specific validation and logic for Angolan regulations
        # This method modifies certain behaviors, such as ensuring valid dates, tax checks,
        # and calculating sequences and hashes for invoices before they are posted.
        move = []
        if self.env.company.country_id.code == "AO":
            # Check if the company operates in Angola (country code: "AO").
            for inv in self:

                # if inv.move_type in ['out_invoice', 'out_refund']:
                #
                #     # Verificamos se o estado da fatura é 'posted' ou se está sendo alterado para 'posted'.
                #     is_posted_now = vals.get('state') == 'posted' and inv.state == 'draft'
                #     is_already_posted = inv.state == 'posted'
                #
                #     if is_posted_now or is_already_posted:
                #         if (move.restrict_mode_hash_table and move.state == "posted" and set(vals).intersection(
                #                 move._get_integrity_hash_fields())):
                #             raise UserError(
                #                 _("You cannot edit the following fields due to restrict mode being activated on the journal: %s.") % ', '.join(
                #                     move._get_integrity_hash_fields()))
                #         if (move.restrict_mode_hash_table and move.inalterable_hash and 'inalterable_hash' in vals) or (
                #                 move.secure_sequence_number and 'secure_sequence_number' in vals):
                #             raise UserError(
                #                 _('You cannot overwrite the values ensuring the inalterability of the accounting.'))
                #         if (move.posted_before and 'journal_id' in vals and move.journal_id.id != vals['journal_id']):
                #             raise UserError(
                #                 _('You cannot edit the journal of an account move if it has been posted once.'))
                #         if (move.name and move.name != '/' and move.sequence_number not in (
                #                 0, 1) and 'journal_id' in vals and move.journal_id.id != vals[
                #             'journal_id'] and not move.quick_edit_mode):
                #             raise UserError(
                #                 _('You cannot edit the journal of an account move if it already has a sequence number assigned.'))

                if vals.get('state') == "posted" and inv.state == 'draft' and inv.move_type in ['out_invoice',
                                                                                                'out_refund',
                                                                                                'in_invoice',
                                                                                                'in_refund']:
                    inv.set_customer_data()
                    inv._check_last_invoice_date(inv)
                    if not inv.system_entry_date:
                        vals['system_entry_date'] = fields.Datetime.now()
                        vals['saft_status_date'] = fields.Datetime.now()
                    if not self.env['ir.config_parameter'].sudo().get_param('dont_validate_tax') and not inv.hash:
                        # Ensure appropriate tax configurations and validations before posting the invoice.
                        for line in inv.invoice_line_ids:
                            if len(line.tax_ids.filtered(
                                    lambda l: (l.tax_type in ['IVA'] and l.iva_tax_type not in ['CAT50', 'CAT100']) or (
                                            l.tax_type in ['NS']) and not l.tax_code in [
                                        "OUT"])) > 1:
                                # Ensure that only one IVA tax is applied per invoice line.
                                # Multiple IVA taxes on a single line are not permitted.
                                raise ValidationError(
                                    _(
                                        "Não podem existir mais de um imposto do tipo IVA na mesma linha do produto/serviço"))
                                # Raise an error if multiple IVA taxes are detected on an individual line.

                            if not line.product_id:
                                continue  # If no product is set, ignore this line for further checks.

                            if line.price_unit <= 0:
                                # Validate that the price unit for all invoice lines is greater than zero.

                                raise ValidationError(
                                    (
                                        'Incompleto! Todas as linhas da fatura devem ter um preço unitário maior que zero.'))
                                # Raise an error if the price unit is invalid (zero or negative).

                            if line.quantity <= 0:
                                # Validate that the quantity for each invoice line is greater than zero.

                                raise ValidationError(
                                    ('Incompleto! Todas as linhas da fatura devem ter uma quantidade.'))
                                # Raise an error if the quantity is invalid (zero or negative).

                        check_tax_iva_exists = inv.invoice_line_ids.tax_ids.filtered(
                            lambda t: (t.tax_code == 'NOR' and t.tax_type in ['IVA']) or
                                      (t.tax_code in ['NS', 'ISE'] and t.tax_type in ['NS', 'IVA']))
                        # Verify that IVA (or valid tax exemptions) is applied to all invoice lines as required.
                        if not check_tax_iva_exists:
                            if not check_tax_iva_exists:
                                # Check if any invoice line is missing applicable IVA taxes.

                                raise ValidationError(
                                    _("Existem linhas da factura sem imposto IVA, caso o produto ou serviço não seja sujeito ao IVA\n"
                                      "Deve adicionar o IVA de isenção na linha e informar o motivo de isenção na configuração do imposto caso ainda não o tenha feito"))
                                # Raise an error if IVA or an exemption is not correctly applied.

                    move = super(AccountMoveAng, self).write(vals)
                    # Proceed with the standard write process after validations are complete.
                    vals['journal_ao_id'] = self.journal_id.journal_ao_id.id
                    vals['journal_ao_id'] = self.journal_id.journal_ao_id.id
                    # Assign the Angolan-specific journal information based on the linked journal.
                    if not inv.journal_id.journal_ao_id:
                        raise ValidationError(
                            _("Para proceder com o lançamento, queira por favor colocar o nº de diário, no diário"))
                    vals['sequence_journal_ao'] = str(
                        inv.date.month) + inv.journal_id.journal_ao_id.sequence_id.next_by_id()
                    vals['hash_to_sign'] = inv.get_new_content_to_sign()

                    move_signed = inv.sign_move(vals['hash_to_sign']).split(";")

                    if move_signed != vals['hash_to_sign']:
                        # Compare the signed hash with the original content to ensure validity.
                        vals[
                            'hash_control'] = 0  # move_signed[1] if len(move_signed) > 1 else "0" TODO: QUANDO OBTER A VALIDAÇÃO DEVO DESCOMENTAR ISTO E PASSAR O HAS_CONTROL  A 1
                        vals['hash'] = move_signed[0]
                elif inv.journal_ao_id and vals.get(
                        'state') == "posted" and inv.state == 'draft' and inv.move_type in ['entry']:
                    vals['journal_ao_id'] = inv.journal_id.journal_ao_id.id
                    vals['sequence_journal_ao'] = str(
                        inv.date.month) + inv.journal_id.journal_ao_id.sequence_id.next_by_id()

        move = super(AccountMoveAng, self).write(vals)
        return move

    def get_supplier_saft_data(self):

        result = {
            "PurchaseInvoices": {
                "NumberOfEntries": 0,
                "Invoice": []
            }
        }

        invoices = self.filtered(
            lambda r: r.state in ['posted'] and r.move_type in [
                "in_invoice"] and r.company_id.id == self.env.company.id)

        count = 0
        for inv in invoices:
            invoices_supplier = {
                "InvoiceNo": inv.ref or inv.name,
                "Hash": inv.hash,
                "SourceID": inv.user_id.id,
                "Period": int(fields.Date.to_string(inv.invoice_date)[5:7]),
                "InvoiceDate": fields.Date.to_string(inv.invoice_date),
                "PurchaseType": "FT",
                "SupplierID": inv.partner_id.id if inv.partner_id.id else inv.partner_id.ref,
                "DocumentTotals": {
                    "TaxPayable": format(inv.amount_tax, '.2f') if inv.amount_tax else "0.00",
                    "NetTotal": format(inv.amount_untaxed, '.2f'),
                    # TODO: we must review this with invoice in different currency
                    "GrossTotal": format(inv.amount_total, '.2f'),
                    "Currency": {
                        "CurrencyCode": inv.currency_id.name,
                        "CurrencyAmount": inv.amount_total,
                        "ExchangeRate": inv.currency_id.rate if inv.currency_id.rate else 0,
                    } if inv.currency_id.name != 'AOA' else ""
                },
                "WithholdingTax": [{
                    "WithholdingTaxType": tax.tax_type,
                    "WithholdingTaxDescription": tax.name,
                    "WithholdingTaxAmount": round(tax.amount * ((100) / 100), inv.currency_id.decimal_places),
                } for tax in inv.invoice_line_ids.tax_ids.filtered(lambda r: r.tax_type == 'IVA')],

            }
            count += 1
            invoices_supplier = saft_clean_void_values("", invoices_supplier)
            result["PurchaseInvoices"]["Invoice"].append(invoices_supplier)

        # result["PurchaseInvoices"]["TotalDebit"] = round(total_debit, 2)
        # result["PurchaseInvoices"]["TotalCredit"] = round(total_credit - total_cancelled_invoice, 2)
        result["PurchaseInvoices"]["NumberOfEntries"] = count

        return result

    def get_saft_data(self):
        """
        Returns a list of invoices dictionaries in saft format fields
        :return:
        """
        total_credit = 0
        total_debit = 0
        result = {
            "SalesInvoices": {
                "NumberOfEntries": 0,
                "TotalDebit": 0,
                "TotalCredit": 0,
                "Invoice": [],
            },
        }
        # iva_exemption = self.env.ref("l10n_ao.%s_account_tax_iva_sales_isento_14" % self.env.user.company_id.id)
        # iva_14 = self.env.ref("l10n_ao.%s_account_tax_iva_sales_14" % self.env.user.company_id.id)
        invoices = self.filtered(
            lambda r: r.state in ['posted', 'cancel'] and r.move_type in ["out_invoice",
                                                                          "out_refund"] and r.company_id.id == self.env.company.id)
        bug_values = {
            'invoice_no_Tax': [],
            'line_void_product_id': [],
            'empty_exemption_reason': [],
        }

        for inv in invoices:
            if not any(line.tax_ids.filtered(
                    lambda r: (r.tax_code in ['NOR', 'ISE', 'RED', 'OUT', 'INT'] and r.tax_type in ['IVA']) or
                              (r.tax_code == 'NS' and r.tax_type == 'NS')) for line in inv.invoice_line_ids):
                bug_values['invoice_no_Tax'].append(str(inv.name))
            lines = inv.mapped('invoice_line_ids').filtered(lambda l: l.display_type is False)
            for line in lines:
                i_lines = line.tax_ids.filtered(lambda t: t.tax_code == 'ISE' and not t.iva_tax_exemption_reason_id)
                if i_lines:
                    bug_values['empty_exemption_reason'].append(inv.name)
                if not line.product_id:
                    bug_values['line_void_product_id'].append(inv.name)

        bug_values['invoice_no_Tax'] = list(set(bug_values['invoice_no_Tax']))
        bug_values['empty_exemption_reason'] = list((bug_values['empty_exemption_reason']))
        bug_values['line_void_product_id'] = list(dict.fromkeys(bug_values['line_void_product_id']))
        errors = {"1": "", "2": "", "3": ""}
        if bug_values:
            if bug_values.get('invoice_no_Tax'):
                msg = _(
                    "it's not possible to generate SAFT file because the following invoices don't have taxes:\n %s") % (
                              str(bug_values['invoice_no_Tax']) + "\n")
                errors["1"] = msg
            elif bug_values.get('empty_exemption_reason'):
                msg = _(
                    "It is not possible to generate a SAFT file because the invoices that follow have iva exemption but the motive was not added, please add:\n %s") % (
                              str(bug_values['empty_exemption_reason']) + "\n")
                errors["2"] = msg
            elif bug_values.get('line_void_product_id'):
                msg = _(
                    "The lines in these invoices do not have products inserted, you must add the corresponding products for each line that is missing:\n %s") % (
                              str(bug_values['line_void_product_id']) + "\n")
                errors["3"] = msg
            if any(errors.values()):
                raise ValidationError([str(v) + "\n" for v in errors.values()])
        total_cancelled_invoice = 0
        for inv in invoices:
            status_code = 'N'
            inv_refunds = inv.filtered(lambda
                                           r: r.move_type == 'out_refund:' and r.payment_state == 'paid')  # Todo: devemos verificar qual e o campo que mapea as notas de credito associadas as facturas

            if inv.state == 'cancel':
                status_code = 'A'
            # elif inv.state == 'paid' and not abs(refund_amount_total):
            #     status_code = 'F',
            #     total_cancelled_invoice += inv.amount_untaxed

            # if inv.journal_id.self_billing is True:
            #     status_code = 'S'
            # TODO: que caso são os documentos produzidos noutra aplicação.
            source_billing = "P"

            invoice_customer = {
                "InvoiceNo": inv.name.replace(" ", " "),  # inv.name[0:3] + "" + inv.name[4:11],
                "DocumentStatus": {
                    "InvoiceStatus": status_code,
                    "InvoiceStatusDate": fields.Datetime.to_string(inv.saft_status_date)[
                                         0:10] + "T" + fields.Datetime.to_string(inv.saft_status_date)[11:20] if
                    inv.saft_status_date else fields.Datetime.to_string(inv.invoice_date)[
                                              0:10] + "T" + fields.Datetime.to_string(inv.invoice_date)[11:20],
                    "Reason": str(inv.name)[0:48] if inv.name else "",
                    "SourceID": inv.user_id.id,
                    "SourceBilling": source_billing,
                },
                "Hash": inv.hash if inv.hash else "",
                "HashControl": inv.hash_control if inv.hash_control else "0",
                "Period": int(fields.Date.to_string(inv.invoice_date)[5:7]),
                "InvoiceDate": fields.Date.to_string(inv.invoice_date),
                "InvoiceType": "NC" if inv.move_type == "out_refund" else "FT",
                "SpecialRegimes": {
                    "SelfBillingIndicator": "0",
                    # "1" if inv.journal_id.self_billing else "0", TODO: Devo adicionar o campo Self Billing
                    "CashVATSchemeIndicator": "1" if inv.company_id.tax_exigibility else "0",
                    "ThirdPartiesBillingIndicator": "0",
                },
                "SourceID": inv.user_id.id,
                "EACCode": "",
                "SystemEntryDate": fields.Datetime.to_string(
                    inv.system_entry_date)[0:10] + "T" + fields.Datetime.to_string(inv.system_entry_date)[
                                                         11:20] if inv.system_entry_date else
                fields.Datetime.to_string(inv.create_date)[0:10] + "T" + fields.Datetime.to_string(inv.create_date)[
                                                                         11:20],
                "TransactionID": fields.Date.to_string(inv.invoice_date) + " " + str(inv.journal_id.id).replace(" ",
                                                                                                                "") + " " + str(
                    inv.id),
                "CustomerID": inv.partner_id.id if (
                        inv.partner_id.vat and '999999999' not in inv.partner_id.vat) else '01',
                "ShipTo": "",  # TODO: 4.1.4.15
                "ShipFrom": "",  # TODO: 4.1.4.16
                "MovementEndTime": "",  # TODO: 4.1.4.17,
                "MovementStartTime": "",  # TODO: 4.1.4.18,
                "Line": [{
                    "LineNumber": line.id,
                    "OrderReferences": {
                        "OriginatingON": inv.invoice_origin if inv.invoice_origin else "",  # TODO:4.1.4.19.2.,
                        "OrderDate": "",
                    },
                    "ProductCode": line.product_id.id if line.product_id else "0900107",
                    "ProductDescription": str(line.name)[0:199] if line.name else line.product_id.name[0:199],
                    "Quantity": line.quantity if line.quantity else "0.00",
                    "UnitOfMeasure": line.product_uom_id.name,
                    "UnitPrice": format(line.price_unit * (1 - (line.discount or 0.0) / 100.0), '.2f'),
                    "TaxBase": "",
                    "TaxPointDate": fields.Date.to_string(inv.invoice_date),
                    "References": {
                        "Reference": inv.name,
                        "Reason": str(inv.name)[0:48] if inv.name else "",
                    } if inv.move_type == "out_refund" else "",
                    "Description": line.name[0:199],
                    "ProductSerialNumber": {
                        "SerialNumber": line.product_id.default_code if line.product_id.default_code else "Desconhecido",
                        # TODO: 4.1.4.19.12.
                    },
                    "CreditAmount" if inv.move_type == "out_invoice" else "DebitAmount": line.price_subtotal,
                    "Tax": [{
                        "TaxType": tax.tax_type,
                        "TaxCountryRegion": tax.country_id.code if tax.country_id.code else "AO",
                        # FIXME: 4.1.4.19.15.2.
                        "TaxCode": tax.tax_code,
                        "TaxAmount" if tax.amount_type in ["fixed"] else "TaxPercentage": str(
                            format(tax.amount, '.2f')),
                    } for tax in line.tax_ids if tax.tax_exigibility == "on_invoice"],
                    # todo: verificar o tax_on nos impostos tax.tax_on == "invoice"],
                    "TaxExemptionReason": line.tax_ids.filtered(lambda r: r.amount == 0)[
                                              0].iva_tax_exemption_reason_id.name[
                                          0:59] if line.tax_ids.filtered(
                        lambda
                            r: r.amount == 0) else "",
                    "TaxExemptionCode": line.tax_ids.filtered(lambda r: r.amount == 0)[
                        0].iva_tax_exemption_reason_id.code if line.tax_ids.filtered(lambda r: r.amount == 0) else "",
                    "SettlementAmount": line.discount,
                    "CustomsInformation": {  # TODO: 4.1.4.19.19.
                        "ARCNo": "",
                        "IECAmount": "",
                    },
                } for line in
                    inv.invoice_line_ids.filtered(lambda r: r.display_type not in ['line_note', 'line_section'])],
                "DocumentTotals": {
                    "TaxPayable": format(inv.amount_tax, '.2f') if inv.amount_tax and inv.amount_tax > 0 else "0.00",
                    "NetTotal": format(inv.amount_untaxed, '.2f'),
                    # TODO: we must review this with invoice in different currency
                    "GrossTotal": format(inv.amount_total, '.2f'),
                    # TODO: we must review this with invoice in different currency
                    "Currency": {
                        "CurrencyCode": inv.currency_id.name,
                        "CurrencyAmount": inv.amount_total,
                        "ExchangeRate": round(
                            inv.currency_id._get_conversion_rate(inv.currency_id, inv.company_currency_id,
                                                                 inv.company_id, inv.invoice_date), 2),
                    } if inv.currency_id.name != 'AOA' else "",
                    "Settlement": {
                        "SettlementDiscount": "",
                        "SettlementAmount": "",
                        "SettlementDate": "",
                        "PaymentTerms": inv.invoice_payment_term_id.name if inv.invoice_payment_term_id.name else "",
                    },
                    "Payment": [{
                        "PaymentMechanism": payment.payment_mechanism if payment.payment_mechanism else "OU",
                        "PaymentAmount": payment.amount,
                        "PaymentDate": fields.Date.to_string(
                            payment.date) if payment.date >= inv.invoice_date else fields.Date.to_string(
                            inv.invoice_date),
                    } for payment in inv.payment_id]

                },
                "WithholdingTax": [{
                    "WithholdingTaxType": tax.wth_type,
                    "WithholdingTaxDescription": tax.name,
                    "WithholdingTaxAmount": round(tax.amount * ((100) / 100), inv.currency_id.decimal_places),
                } for tax in inv.invoice_line_ids.tax_ids.filtered(lambda r: r.is_withholding)]
                # ["withholding", "captive"])], #todo rever que representa o captive no 14
            }
            invoice_customer = saft_clean_void_values("", invoice_customer)
            result["SalesInvoices"]["Invoice"].append(invoice_customer)
            total_debit += inv.amount_untaxed if inv.move_type == "out_refund" and inv.state in ["posted"] else 0
            total_credit += inv.amount_untaxed if inv.move_type == "out_invoice" and inv.state in ["posted"] else 0
        result["SalesInvoices"]["TotalDebit"] = round(total_debit, 2)
        result["SalesInvoices"]["TotalCredit"] = round(total_credit - total_cancelled_invoice, 2)

        result["SalesInvoices"]["NumberOfEntries"] = len(invoices)
        return result

    def get_payment_date(self):
        reconciled_line = self.line_ids.filtered(lambda x: x.reconciled)
        if not reconciled_line:
            return ""
        partial_reconcile = (
                reconciled_line.debit
                and reconciled_line.matched_credit_ids
                or reconciled_line.matched_debit_ids
        )
        dates = sorted(partial_reconcile.mapped("create_date"))
        return dates[-1].strftime("%d-%m-%Y")

    def get_supplier_payment_date(self):
        for line in self.line_ids.filtered(lambda x: x.reconciled):
            if not line:
                return ""
            partial_reconcile = (
                    line.debit
                    and line.matched_credit_ids
                    or line.matched_debit_ids
            )
            dates = partial_reconcile.mapped("create_date")

            formatted_dates = [date.strftime("%d-%m-%Y") for date in dates]
        if formatted_dates:
            return formatted_dates[0]

    def get_customer_payment_date(self):
        formatted_dates = []
        for line in self.line_ids.filtered(lambda x: x.reconciled):
            if not line:
                return ""
            partial_reconcile = (
                    line.debit
                    and line.matched_credit_ids
                    or line.matched_debit_ids
            )
            dates = partial_reconcile.mapped("create_date")

            formatted_dates = [date.strftime("%d-%m-%Y") for date in dates]
        return formatted_dates

    def get_apuramento_iva(self):
        iva_ids = self.env["apuramento.iva"].search([])

        return iva_ids

    @api.onchange('invoice_line_ids', 'tax_ids')
    def compute_line_account_id(self):
        for record in self:
            for line in record.invoice_line_ids:
                if line.product_id and len(line.tax_ids) == 1:
                    product_id = line.product_id
                    if product_id.get_account_from_sub_accounts:
                        tax_id = line.tax_ids[0]._origin
                        main_account_id = record.env['account.account']
                        if record.move_type == 'out_invoice':
                            main_account_id = product_id.property_account_income_id
                        else:
                            main_account_id = product_id.property_account_expense_id
                        account_ids = main_account_id.search([
                            ('code', 'ilike', main_account_id.code),
                            ('company_id', '=', self.env.company.id)
                        ])
                        account_id = account_ids.filtered(
                            lambda acc: tax_id in acc.tax_ids and acc.code != main_account_id.code)
                        if account_id:
                            line.account_id = account_id[0]
                    # else:
                    #     line.account_id = line.product_id.property_account_income_id or line.product_id.categ_id.property_account_income_categ_id if line.move_id.move_type in [
                    #         'out_invoice',
                    #         'out_refund'] else line.product_id.property_account_expense_id or line.product_id.categ_id.property_account_expense_categ_id
                elif line.account_id:
                    line.account_id = line.account_id
                else:
                    line.account_id = False

    def button_draft(self):
        for move in self:
            move.state = 'draft'
        super(AccountMoveAng, self).button_draft()

    @api.constrains('invoice_line_ids')
    def validate_if_service(self):
        for rec in self:
            for line in rec.invoice_line_ids:
                products = line.tax_ids.filtered(
                    lambda r: r.is_withholding is True) and not line.product_id.detailed_type == 'service'
                if products:
                    not_service = self.invoice_line_ids.filtered(lambda l: l.tax_ids.filtered(
                        lambda r: r.is_withholding) and l.product_id.detailed_type != 'service')
                    products_name = ', '.join(not_service.mapped('product_id.display_name'))
                    raise UserError(
                        _("Favor atribuir retenção somente para produtos do tipo Serviço!\nProdutos inválidos: %s") % products_name)

    @api.constrains('move_type', 'ref')
    def _check_ref_on_vendor_invoice(self):
        for move in self:
            if move.move_type == 'in_invoice' and not move.ref:
                raise ValidationError("O campo 'Referência' é obrigatório para faturas de fornecedor.")
