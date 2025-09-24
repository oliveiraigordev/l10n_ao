from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class AccountMovetInherit(models.Model):
    _inherit = 'account.move'

    def action_post(self):
        res = super(AccountMovetInherit, self).action_post()
        for record in self:
            lista = []
            for line in record.invoice_line_ids:
                lista.append(line.price_unit)
            if sum(lista) == 0:
                raise ValidationError(
                    "A linha do produto não pode ter valor zerado. Por favor, revise os preços antes de emitir a fatura."
                )
        return res
