# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from reportlab.lib.pagesizes import elevenSeventeen

from .ir_sequence import DEFAULT_SEQUENCE
from odoo.exceptions import ValidationError, UserError
from odoo.addons.l10n_ao.sign import sign
from functools import partial
from odoo.tools.misc import formatLang


class SaleOrderAng(models.Model):
    _inherit = 'sale.order'

    state = fields.Selection(
        selection_add=[
            ('valid', "Validated"),
            ('sent',),
        ], ondelete={'valid': 'set null'})
    sequence_number = fields.Integer("Sequence Number", copy=False, readonly=True)
    # validated_date = fields.Datetime("Date validated", copy=False, readonly=True)
    # Document Type will be applied to a sales order document
    document_type_id = fields.Many2one(
        'sale.order.document.type',
        'Document Type',
        help='Sales document type')
    amount_total_wth = fields.Monetary(_('Total w/ Withhold'), store=True, currency_field='currency_id',
                                       compute='_compute_amounts')
    document_type_code = fields.Char(related='document_type_id.code', help='Sales document type code')
    company_country_id = fields.Many2one(related="company_id.country_id")
    total_discount = fields.Monetary(_('Total Discounts'), store=True, currency_field='currency_id',
                                     compute='_compute_amount_discount')
    hash = fields.Char(string="Hash", copy=False, readonly=True)
    hash_control = fields.Char(string="Hash Control", default="0", copy=False)
    hash_to_sign = fields.Char(string="Hash to sign", copy=False)
    saft_status_date = fields.Datetime("SAFT Status Date", copy=False)
    system_entry_date = fields.Datetime("Signature Datetime", copy=False)
    counter_pricelist_id = fields.Many2one(
        comodel_name='product.pricelist',
        string="Counter Pricelist",
        readonly=False, check_company=True, required=False,  # Unrequired company
        tracking=1,
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]",
        help="The method will cal the counter pricelist for de currency")
    currency_counter_id = fields.Many2one(
        related='counter_pricelist_id.currency_id',
        depends=["counter_pricelist_id"],
        store=True, precompute=True, ondelete="restrict")
    counter_value = fields.Monetary(string="Total counter value", store=True, compute='_compute_counter_value_amounts',
                                    tracking=4)
    partner_name = fields.Char("Name", compute='set_customer_data', store=True)
    partner_street = fields.Char("Street", compute='set_customer_data', store=True)
    partner_street2 = fields.Char("Street2", compute='set_customer_data', store=True)
    partner_city = fields.Char("City", compute='set_customer_data', store=True)
    partner_state = fields.Char("State", compute='set_customer_data', store=True)
    partner_vat = fields.Char("NIF", compute='set_customer_data', store=True)
    margin_total = fields.Monetary(
         string="Margin Total",
         compute='_compute_amounts',
         currency_field='currency_id')

    bank_account_ids = fields.Many2many(
        'res.partner.bank',
        string="Contas Bancárias para Documento",
        help="Selecione as contas bancárias que deverão aparecer neste documento. Se não for selecionada nenhuma, serão exibidas as contas definidas globalmente (Show on documents)."
    )




    def action_cancel(self):
        if self.invoice_ids and self.invoice_ids.mapped("state") in ['posted']:
            raise ValidationError(_("Não pode cancelar o documento porque já existem facturas lançadas associadas ao mesmo"))

        return super(SaleOrderAng,self).action_cancel()


    # @api.model_create_multi
    # def create(self, vals_list):
    #     for sale in vals_list:
    #         if not sale.get("document_type_id"):
    #             sale["document_type_id"] = self.env.company.document_type_id.id
    #     record = super(SaleOrderAng, self).create(vals_list)
    #
    #     record.write({"name": _("New")})
    #     return record

    @api.model_create_multi
    def create(self, vals_list):
        for sale in vals_list:
            if not sale.get("document_type_id"):
                sale["document_type_id"] = self.env.company.document_type_id.id

        record = super(SaleOrderAng, self).create(vals_list)

        for rec in record:
            if rec.company_id and rec.company_id.country_id:
                if rec.company_id.country_id.code == 'AO':
                    # Para Angola,
                    rec.name = _('New')
                else:
                    # Para outo caso ,
                    if not rec.name or rec.name in ('/', _('New'), False):
                        rec.name = self.env['ir.sequence'].with_company(rec.company_id).next_by_code('sale.order')

        return record

    def set_customer_data(self):
        for pt in self:
            if pt.state == "draft":
                pt.partner_name = pt.partner_id.display_name
                pt.partner_street = pt.partner_id.street
                pt.partner_street2 = pt.partner_id.street2
                pt.partner_state = pt.partner_id.state_id.name
                pt.partner_city = pt.partner_id.city
                pt.partner_vat = pt.partner_id.vat

    @api.depends('order_line.price_subtotal', 'order_line.price_tax', 'order_line.price_total', 'counter_pricelist_id')
    def _compute_counter_value_amounts(self):
        for sale in self:
            if sale.counter_pricelist_id:
                sale.counter_value = sale.amount_total * sale.counter_pricelist_id.currency_id.rate if sale.counter_pricelist_id.currency_id.name != "AOA" else sale.amount_total * sale.counter_pricelist_id.currency_id.inverse_rate


    @api.depends('order_line.product_uom_qty', 'order_line.price_unit', 'order_line.discount')
    def _compute_amount_discount(self):
        for sale in self:
            total_price = 0
            discount_amount = 0
            for line in sale.order_line.filtered(lambda l: l.discount > 0):
                total_price = (line.product_uom_qty * line.price_unit) * (line.discount / 100)
                tax_include = line.tax_id.filtered(lambda tax: tax.price_include)
                if tax_include:
                    total_price = total_price / ((tax_include.amount + 100) / 100)
                discount_amount += total_price
            sale.update({'total_discount': discount_amount})

    def amount_by_group(self):
        for order in self:
            currency = order.currency_id or order.company_id.currency_id
            fmt = partial(formatLang, self.with_context(lang=order.partner_id.lang).env, currency_obj=currency)
            res = {}
            for line in order.order_line:
                price_reduce = line.price_unit * (1.0 - line.discount / 100.0)
                taxes = \
                    line.tax_id.compute_all(price_reduce, quantity=line.product_uom_qty, product=line.product_id,
                                            partner=order.partner_shipping_id)['taxes']
                for tax in line.tax_id:
                    if tax.tax_exigibility == 'on_payment' and tax.is_withholding:
                        continue
                    group = tax.tax_group_id
                    res.setdefault(group, {'amount': 0.0, 'base': 0.0})
                    for t in taxes:
                        if t['id'] == tax.id or t['id'] in tax.children_tax_ids.ids:
                            res[group]['amount'] += t['amount']
                            res[group]['base'] += t['base']
            res = sorted(res.items(), key=lambda l: l[0].sequence)
            order.amount_by_group = [(
                l[0].name, l[1]['amount'], l[1]['base'],
                fmt(l[1]['amount']), fmt(l[1]['base']),
                len(res),
            ) for l in res]

        # Overwrite

    @api.depends('order_line.price_subtotal', 'order_line.price_tax', 'order_line.price_total','order_line.margin_value')
    def _compute_amounts(self):
        """Compute the total amounts of the SO."""
        if self.env.company.country_id.code == 'AO':
            amount_wth = 0
            for order in self:
                order_lines = order.order_line.filtered(lambda x: not x.display_type)
                amount_untaxed = sum(order_lines.mapped('price_subtotal'))
                amount_tax = sum(order_lines.mapped('price_tax'))
                order.margin_total = sum(order_lines.mapped('amount_margin'))
                order.amount_untaxed = sum(order_lines.mapped('price_subtotal'))
                order.amount_tax = sum(order_lines.mapped('price_tax'))
                order.amount_total = order.amount_untaxed + order.amount_tax
                for line in order_lines:
                    amount_wth += sum(line.price_subtotal * (tax.amount / 100) for tax in line.tax_id if tax.is_withholding)
                order.amount_total_wth = amount_untaxed + amount_tax - amount_wth if amount_wth else 0
        else:
            self.margin_total = 0.0
            super()._compute_amounts()


    @api.returns('mail.message', lambda value: value.id)
    def message_post(self, **kwargs):
        if self.company_id.country_id.code == "AO":
            if self.state == "valid":
                if self.env.context.get('mark_so_as_sent'):
                    self.filtered(lambda o: o.state == 'valid').with_context(tracking_disable=True).write(
                        {'state': 'sent'})
        else:
            if self.env.context.get('mark_so_as_sent'):
                self.filtered(lambda o: o.state == 'draft').with_context(tracking_disable=True).write({'state': 'sent'})
        return super(SaleOrderAng, self.with_context(mail_post_autofollow=True)).message_post(**kwargs)

    def action_validate(self):
        """
            Will validate sale order only when in draft state

            :raise: ValidationError if OS not in draft state
            :return: void
        """
        for record in self:
            if record.state == "draft":
                record.state = "valid"
            else:
                raise ValidationError(_("Only draft sales order can be validate"))

    def get_new_content_to_sign(self):
        content_to_sign = ""
        if self.sequence_number - 1 >= 1:
            preview_last_order = self.sudo().search([('state', 'in', ['valid', 'sale', 'sent']),
                                                     ('id', "!=", self.id),
                                                     ('company_id', '=', self.company_id.id),
                                                     ('document_type_code', '=', self.document_type_id.code),
                                                     ('system_entry_date', '<=', self.system_entry_date),
                                                     ('sequence_number', '=', self.sequence_number - 1)],
                                                    order="system_entry_date desc", limit=1)
            if preview_last_order:
                get_last_order_hash = preview_last_order.hash if preview_last_order.hash else ""
                system_entry_date = self.system_entry_date.isoformat(sep='T',
                                                                     timespec='auto') if self.system_entry_date else fields.Datetime.now().isoformat(
                    sep='T', timespec='auto')
                content_to_sign = ";".join((fields.Date.to_string(self.date_order), system_entry_date,
                                            self.name, str(format(self.amount_total, '.2f')),
                                            get_last_order_hash))
        elif self.sequence_number - 1 == 0:
            system_entry_date = self.system_entry_date.isoformat(sep='T',
                                                                 timespec='auto') if self.system_entry_date else fields.Datetime.now().isoformat(
                sep='T', timespec='auto')
            content_to_sign = ";".join((fields.Date.to_string(self.date_order), system_entry_date,
                                        self.name, str(format(self.amount_total, '.2f')), ""))
        return content_to_sign

    def sign_document(self, content_data):
        response = ''
        if content_data:
            response = sign.sign_content(content_data)
        if response:
            return response
        return content_data

    def write(self, values):
        if self.env.company.country_id.code == "AO":
            """ 
                When country of company is AO, sales order
                Will get especific order name from document Type
                 
            """
            for sale in self:
                if sale.state == "draft" and not sale.system_entry_date and values.get("state") in [
                    "valid"] and sale.document_type_id:
                    if sale.document_type_id.code == DEFAULT_SEQUENCE["Quotation"]:
                        sequence = self.env['ir.sequence'].with_company(self.company_id).search(
                            []).next_by_code(DEFAULT_SEQUENCE["Quotation"])
                        values["name"] = f'{DEFAULT_SEQUENCE["Quotation"]} {sequence}'
                        values["sequence_number"] = sequence.split("/")[1]
                        values["system_entry_date"] = fields.Datetime.now()
                        values['saft_status_date'] = fields.Datetime.now()

                    elif sale.document_type_id.code == DEFAULT_SEQUENCE["Proforma"]:
                        sequence = self.env['ir.sequence'].with_company(self.company_id).search(
                            []).next_by_code(DEFAULT_SEQUENCE["Proforma"])
                        values["name"] = f'{DEFAULT_SEQUENCE["Proforma"]} {sequence}'
                        values["sequence_number"] = sequence.split("/")[1]
                        values["system_entry_date"] = fields.Datetime.now()
                        values['saft_status_date'] = fields.Datetime.now()

                    elif sale.document_type_id.code == DEFAULT_SEQUENCE["Proposal"]:
                        sequence = self.env['ir.sequence'].with_company(self.company_id).search([]
                                                                                                ).next_by_code(
                            DEFAULT_SEQUENCE["Proposal"])
                        values["name"] = f'{DEFAULT_SEQUENCE["Proposal"]} {sequence}'
                        values["sequence_number"] = sequence.split("/")[1]
                        values["system_entry_date"] = fields.Datetime.now()
                        values['saft_status_date'] = fields.Datetime.now()

                    if not sale.order_line:
                        raise UserError(_("Para validar o documento, você deve adicionar o produto (serviço/produto) à linha do pedido"))

                    sale.set_customer_data()
                    if not sale.hash:
                        if not self.env['ir.config_parameter'].sudo().get_param('dont_validate_tax'):
                            for line in sale.order_line.filtered(
                                    lambda r: r.display_type not in ['line_note', 'line_section']):
                                lines_tax = line.tax_id.filtered(
                                    lambda t: (t.tax_code == 'NOR' and t.tax_type in ['IVA']) or
                                              (t.tax_code in ['NS', 'ISE'] and t.tax_type in ['NS', 'IVA']))
                                if not lines_tax and values.get('state') not in ["draft"]:
                                    raise UserError(
                                        _("Existem linhas da Ordem de venda sem imposto IVA, caso o produto ou serviço não seja sujeito ao IVA\n"
                                          "Deve adicionar o IVA de isenção na linha e informar o motivo de isenção na configuração do imposto caso ainda não o tenha feito"))
                        order = super(SaleOrderAng, self).write(values)
                        values['hash_to_sign'] = sale.get_new_content_to_sign()
                        content_signed = sale.sign_document(values['hash_to_sign']).split(";")
                        if values['hash_to_sign'] != content_signed:
                            values[
                                'hash_control'] = 0  # content_signed[1] if len(content_signed) >= 1 else "0" TODO: QUANDO OBTER A VALIDAÇÃO DEVO DESCOMENTAR ISTO E PASSAR O HAS_CONTROL  A 1
                            values['hash'] = content_signed[0]
                if values.get("state") in ["valid"] and not sale.document_type_id:
                    if self.env.company.document_type_id:
                        self.document_type_id = self.env.company.document_type_id.id
                        self.action_validate()
                    else:
                        raise ValidationError(
                            _("To validate document, you must select default document type in setting of sales"))

                if sale.state in ["sale", "sent", "done", "cancel"] and (
                        "state" in values and values.get("state") == "valid"):
                    raise ValidationError(
                        _("This %s sales order can not be validate again, only draft sales order can be validated") % sale.name)

        order = super(SaleOrderAng, self).write(values)
        return order

    # def action_confirm(self):
    #     # Obtém a empresa ativa no contexto
    #     company = self.env.company
    #
    #     # Verifica se o estado é "draft" ou "cancel"
    #     if self.state in ("draft", "cancel"):
    #         if not company.country_id and company.country_id.code =="AO":
    #             raise UserError(_("Company country not confirmed, inform country of the company"))
    #
    #     return super(SaleOrderAng, self).action_confirm()

    def action_confirm(self):
        if self.state in ("draft", "cancel"):
            if self.env.company.country_id and self.env.company.country_id.code == "AO":
                raise UserError(_("Order not validate can not be confirmed"))

        return super(SaleOrderAng, self).action_confirm()

    # @api.constrains("state")
    # def check_document_type_onvalideting(self):
    #     """
    #         Propose:
    #
    #             -   Check Quotation(OU) or Proposal(OR) Sales Order have service product in their order line
    #             -   Check ProForma(PP) Sales Order have consumable product on its order line
    #             -   Context: valid state and company country code is AO
    #
    #     :raise: UserError
    #     :return: void
    #     """
    #     if self.state in ("valid", "sale", "sent", "done") and self.env.company.country_id.code == "AO":
    #
    #         if self.document_type_id.code in ("OU", "OR"):
    #             if len(self.order_line.filtered(lambda line: line.product_id.type == "service")) < 1:
    #                 raise UserError(
    #                     _("%s must have a service product to be %s") % (self.document_type_id.name, self.state))
    #
    #         # elif self.document_type_id.code == "PP":
    #         #     if len(self.order_line.filtered(lambda line: line.product_id.type in ["consu", "product"])) < 1:
    #         #         raise UserError(_("%s must have a consumable product to be %s") % self.document_type_id.name,
    #         #                         self.state)
