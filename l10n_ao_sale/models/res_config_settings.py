# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    document_type_id = fields.Many2one(
        related="company_id.document_type_id",
        config_parameter='default_document_type_id',
        readonly=False)
    margin_cost = fields.Boolean(_("Margin Cost"), store=True, readonly=False, related="company_id.margin_cost")


