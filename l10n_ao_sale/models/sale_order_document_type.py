# -*- coding: utf-8 -*-
from odoo import models, fields, _, api
from odoo.exceptions import ValidationError


class SaleOrderDocumentType(models.Model):
    """
        Sales Order Document Type
    """
    _name = 'sale.order.document.type'
    _description = 'Sales Order Document Type'

    name = fields.Char(string=_('Name'), required=True)
    code = fields.Char(string=_('Code'), required=True)

    _sql_constraints = [
        ('unique_name', 'UNIQUE(name)', _('name can not be duplicated')),
        ('unique_code', 'UNIQUE(code)', _('code can not be duplicated'))
    ]

    @api.constrains('name', 'code')
    def check_duplicated_record(self):
        """
        When you try to create or update record,
        if data has existing code or name, it will get error
        :return: void
        """
        for rec in self:
            if self.env["sale.order.document.type"].search(
                    ["&", ("id", "!=", rec.id), "|", ("name", "=", rec.name), ("code", "=", rec.code)]):
                raise ValidationError(_("You can not duplicate record"))

    def unlink(self):
        """
            Block  PP, OR, OU record when user try to delete them.
        """
        if self.code in ["PP", "OR", "OU"]:
            raise ValidationError(_("Document Type can not be deleted..."))

        return super(SaleOrderDocumentType, self).unlink()
