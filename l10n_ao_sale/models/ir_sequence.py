# -*- coding: utf-8 -*-
from odoo import models, fields, _, api
from odoo.exceptions import ValidationError

DEFAULT_SEQUENCE = {
    "Quotation": "OU",
    "Proposal": "OR",
    "Proforma": "PP"
}


class IrSequence(models.Model):
    _inherit = 'ir.sequence'

    def check_duplicated_code(self, values):
        if "code" in values and values["code"] in DEFAULT_SEQUENCE.values():
            if not self.search(
                    [("code", "=", values["code"]), ("company_id", "=",
                                                     values["company_id"] if "company_id" in values and values[
                                                         "company_id"] else False),
                     ("prefix", "=", "%(range_year)s/")]):
                pass
            else:
                raise ValidationError(
                    _("You can not duplicate %s for the current company you are creating/editing") % (self.name))

    def unlink(self):
        """
            Override for prevent cases user want to delete  PP, OR and OU sequence.
        """
        for sequence in self:
            if sequence.code in DEFAULT_SEQUENCE.values() and sequence.prefix == "%(range_year)s/":
                raise ValidationError(_(
                    "the sequence %s  can not be deleted") % sequence.name)

        return super(IrSequence, self).unlink()

    @api.model_create_multi
    def create(self, values):
        for value in values:
            if not value.get("company_id"):
                if ("code" and "prefix" in value and value.get("code") in DEFAULT_SEQUENCE.values()) and value.get(
                        "prefix") == "%(range_year)s/":
                    default_fields = super(IrSequence, self).default_get(self.fields_get())
                    return default_fields

            self.check_duplicated_code(value)
        return super(IrSequence, self).create(values)

    def create_sequence_when_ao(self):
        for company in self.env["res.company"].search([("country_code", "=", "AO")]):
            company.create_doc_type_sequence()
