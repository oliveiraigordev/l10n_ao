# -*- coding: utf-8 -*-
# © 2024 NOSI.

from odoo import models, api, _, fields
from odoo.exceptions import ValidationError, UserError

class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    amount_tax = fields.Monetary(
        string='Valor IVA',
        compute="_compute_valor_iva"
    )

    @api.depends('product_id', 'quantity', 'price_unit', 'tax_ids', 'price_subtotal')
    def _compute_valor_iva(self):
        for record in self:
            value_tax = 0
            for tax in record.tax_ids:
                if tax.iva_tax_type not in ['CAT50', 'CAT100']:
                    value_tax = ((record.price_subtotal * tax.amount) / 100)
            record.amount_tax = value_tax

    @api.depends('balance', 'move_id.is_storno')
    def _compute_debit_credit(self):
        for line in self:
            if not line.is_storno:
                
                value = line.balance
                if not line.name and line.move_id.amount_tax_captive:
                    if line.balance < 0.0:
                        value = (line.move_id.amount_total - line.move_id.amount_tax_captive) * -1
                    else:
                        value = (line.move_id.amount_total - line.move_id.amount_tax_captive) 

                line.debit = value if line.balance > 0.0 else 0.0
                line.credit = -value if line.balance < 0.0 else 0.0
            else:
                line.debit = line.balance if line.balance < 0.0 else 0.0
                line.credit = -line.balance if line.balance > 0.0 else 0.0

    @api.constrains('account_id', 'display_type')
    def _check_payable_receivable(self):
        for line in self:
            account_type = line.account_id.account_type
            if line.move_id.is_sale_document(include_receipts=True):
                if (line.display_type == 'payment_term') ^ (account_type == 'asset_receivable'):
                    pass
            if line.move_id.is_purchase_document(include_receipts=True) and line.product_id:
                if (line.display_type == 'payment_term') ^ (account_type == 'liability_payable'):
                    pass
