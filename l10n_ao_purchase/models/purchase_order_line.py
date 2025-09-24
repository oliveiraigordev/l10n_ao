from odoo import models, fields, api, _
class PurchaseOrderLineAOA(models.Model):
    _inherit = "purchase.order.line"

    margin_value = fields.Float(string="Margin (%)", compute='_compute_margin', store=True, digits='Margin',
                                readonly=False, precompute=True)

    @api.depends('product_id')
    def _compute_margin(self):
        for line in self:
            line.margin_value = 0.0