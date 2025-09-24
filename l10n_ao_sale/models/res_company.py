# -*- coding: utf-8 -*-
from odoo import models, fields, _, api
from odoo.exceptions import ValidationError
from .ir_sequence import DEFAULT_SEQUENCE


class ResCompany(models.Model):
    _inherit = 'res.company'

    document_type_id = fields.Many2one(
        'sale.order.document.type',
        'Document Type',
        help='Default document type used by sales order')
    country_code = fields.Char(related="country_id.code")
    margin_cost = fields.Boolean(_("Margin Cost"), store=True, readonly=False)

    @api.model_create_multi
    def create(self, values):
        companies = super(ResCompany, self).create(values)
        for company in companies:
            if company.country_id.code == "AO":
                company.create_doc_type_sequence()
        return companies

    def write(self, values):
        record = super(ResCompany, self).write(values)
        for sale in self:
            if sale.country_id.code == "AO":
                sale.create_doc_type_sequence()

        return record

    def create_doc_type_sequence(self):
        """
        Will create sequences whenever country code of company is AO
        :return: void
        """
        company = self
        if company.country_id.code == "AO":
            sequence = self.env["ir.sequence"]
            value = {
                'implementation': 'no_gap',
                'prefix': '%(range_year)s/',
                'padding': 0,
                'use_date_range': True,
                'company_id': company.id,
            }
            domain = ("company_id", "=", company.id)
            if not sequence.search([("code", "=", DEFAULT_SEQUENCE["Quotation"]), domain]):
                value["name"] = "SalesOrder: Quotation"
                value["code"] = DEFAULT_SEQUENCE["Quotation"]
                sequence.create(value)

            if not sequence.search([("code", "=", DEFAULT_SEQUENCE["Proforma"]), domain]):
                value["name"] = "SalesOrder: Proforma"
                value["code"] = DEFAULT_SEQUENCE["Proforma"]
                sequence.create(value)

            if not sequence.search([("code", "=", DEFAULT_SEQUENCE["Proposal"]), domain]):
                value["name"] = "SalesOrder: Proposal"
                value["code"] = DEFAULT_SEQUENCE["Proposal"]
                sequence.create(value)
