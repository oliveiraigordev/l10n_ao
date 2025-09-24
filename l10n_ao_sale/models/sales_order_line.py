# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class SalesOrderLine(models.Model):
    _inherit = 'sale.order.line'

    margin_value = fields.Float(string="Margin (%)", compute='_compute_margin', store=True, digits='Margin', readonly=False, precompute=True)
    amount_margin = fields.Float(string="Amount Margin")
    margin_cost = fields.Boolean(_("Margin Cost", store=True, related="company_id.margin_cost"))


    def _prepare_invoice_line(self, **optional_values):
        res = super(SalesOrderLine,self)._prepare_invoice_line()
        res['margin_value'] = self.margin_value
        return  res

    @api.depends('product_id', 'product_uom', 'product_uom_qty')
    def _compute_margin(self):
         for line in self:
             if not line.product_id or line.display_type:
                 line.margin_value = 0.0
             #line.margin_value = 0.0

    @api.onchange('discount')
    def valid_discount(self):
        """
            Validate discount range (0 -100%) when field visible to end user

        :return: void
        """
        if self.env.company.country_id and self.env.company.country_id.code == "AO" and self.discount >= 0 and self.discount <= 100:
            pass
        else:
            raise UserError(_("discount must be in range of 0 - 100 % "))

    # override
    @api.depends('product_uom_qty', 'discount', 'price_unit', 'tax_id', 'margin_value')
    def _compute_amount(self):
        """
        Compute the amounts of the SO line.
        """
        #FEZ-SE OVERRIDE DO MÉTODO PARA CALCULO DA MARGEM NA LINHA E TAMBÉM UPDATE DA LINHA
        if self.env.company.country_id.code == 'AO':
            for line in self:
                margin_value = 0
                vat_settlement = 0
                margin_result = line.price_unit * (line.margin_value / 100)
                tax = line.tax_id.filtered(lambda r: r.tax_exigibility == 'on_invoice' and r.margin_affect)
                if line.margin_value > 0:
                    margin_value = margin_result * line.product_uom_qty
                    if tax:
                        margin_value = margin_value + (margin_value * (tax.amount / 100))
                price = ((line.price_unit + (margin_result + (margin_result * (tax.amount / 100)))) * (1 - (line.discount or 0.0) / 100.0))
                taxes_ids = line.tax_id.filtered(lambda r: not r.tax_exigibility == 'on_payment' and not r.is_withholding)
                taxes = taxes_ids.compute_all(price, line.order_id.currency_id, line.product_uom_qty,
                                              product=line.product_id, partner=line.order_id.partner_shipping_id,margin_value=margin_value)

                line.update({
                    'amount_margin': margin_value if margin_value else 0,
                    'price_tax': sum(t.get('amount', 0.0) for t in taxes.get('taxes', [])),
                    'price_total': taxes['total_included'],
                    'price_subtotal': taxes['total_excluded'],
                })
                if self.env.context.get('import_file', False) and not self.env.user.user_has_groups(
                        'account.group_account_manager'):
                    line.tax_id.invalidate_cache(['invoice_repartition_line_ids'], [line.tax_id.id])
        else:
            super()._compute_amount()

    @api.onchange("tax_id")
    def check_duplicated_tax(self):
        pass

    @api.constrains("tax_id")
    def check_tax_inline(self):
        """
            Will check bellow cases:
                - Order line must have two or one tax included
                - If has two tax included must be 'IVA and Retenção (NS)'
                - Order line must have tax included
                - If product of order line does not have IVA, must be included IVA 0%
                - Order line must have only One IVA tax and NS (check tax type)

        :return: void
        """
        if self.env.company.country_id.code == "AO":
            for line in self:
                if len(line.filtered(lambda r: r.display_type not in ["line_section", "line_note"]).tax_id.filtered(
                        lambda r: r.tax_type == "IVA")) > 1:
                    raise UserError(_("Order line has more than one IVA tax"))
                elif len(line.filtered(lambda r: r.display_type not in ["line_section", "line_note"]).tax_id.filtered(
                        lambda r: r.tax_type == "NS")) > 1:
                    raise UserError(_("Product has more than One 'Não Sujeição Tax (NS)'"))

            for tax in self.filtered(lambda r: r.display_type not in ["line_section", "line_note"]):
                if len(tax.tax_id) > 2 or len(tax.tax_id) < 1:
                    raise ValidationError(_(" Min. one(1) and max two(2) tax are accepted in the same order line"))

                elif len(tax.tax_id) == 2:
                    for tx in tax.tax_id:
                        if not tx.tax_type in ("IVA", "NS"):
                            raise ValidationError(_("Only IVA and NS type of tax are accepted in the same order line"))

                elif not tax.tax_id:
                    raise ValidationError(_("There is a line without tax,  please, add tax for Saft validation"))
                else:
                    if len(tax.tax_id.filtered(lambda r: r.tax_type == "IVA")) == 0:
                        raise ValidationError(
                            _("There is a line without iva tax,  please, add IVA tax to product! If is isent add IVA 0"))

    @api.constrains("product_id")
    def check_product_id(self):
        """
            Propose:

                -   Check Quotation(OU) or Proposal(OR) Sales Order have service product in their order line
                -   Check ProForma(PP) Sales Order have consumable product on its order line
                -   Context: valid state and company country code is AO

        :raise: UserError
        :return: void
        """
        pass
        # if self.order_id.state in ("valid", "sale", "sent", "done") and self.env.company.country_id.code == "AO":
        #     if self.order_id.document_type_code in ("OU", "OR"):
        #         if len(self.filtered(lambda line: line.product_id.type == "service")) < 1:
        #             raise UserError(_("%s must have a service product to be %s") % (
        #             self.order_id.document_type_id.name, self.order_id.state))

            # elif self.order_id.document_type_id.code == "PP":
            #     if len(self.filtered(lambda line: line.product_id.type == "consu")) < 1:
            #         raise UserError(_("%s must have a consumable product to be %s") % (
            #         self.order_id.document_type_id.name, self.order_id.state))
