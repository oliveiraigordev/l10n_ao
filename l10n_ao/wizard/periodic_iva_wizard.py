from datetime import date, timedelta

from odoo import models, fields, api
from odoo.tools import float_is_zero
from odoo.exceptions import UserError


class PeriodicIvaMap(models.TransientModel):
    _name = "periodic.iva.map"
    _description = "Periodic Iva Map"

    month = fields.Selection(
        [
            ("1", "Janeiro"),
            ("2", "Fevereiro"),
            ("3", "Março"),
            ("4", "Abril"),
            ("5", "Maio"),
            ("6", "Junho"),
            ("7", "Julho"),
            ("8", "Agosto"),
            ("9", "Setembro"),
            ("10", "Outubro"),
            ("11", "Novembro"),
            ("12", "Dezembro"),
        ],
        string="Mês",
    )
    year = fields.Integer(string="Ano")

    @api.model
    def default_get(self, fields_list):
        res = super(PeriodicIvaMap, self).default_get(fields_list)
        today = fields.Date.today()
        year = today.year
        month = today.month - 1
        if month == 0:
            month = 12
            year -= 1
        res.update({"month": str(month), "year": year})
        return res

    def print_report(self):
        start_date = date(self.year, int(self.month), 1)
        if int(self.month) == 12:
            end_date = date(self.year, int(self.month), 31)
        else:
            end_date = date(self.year, int(self.month) + 1, 1) + timedelta(days=-1)
        move_ids = self.env["account.move"].search(
            [
                ("move_type", "in", ["out_invoice", "in_invoice", "in_refund", "out_refund"]),
                ("state", "=", "posted"),
                ("invoice_date", ">=", start_date),
                ("invoice_date", "<=", end_date),
            ]
        
        )

       

        if not move_ids:
            raise UserError(
                "Não foi encontrada nenhuma Declaração Periódica para o período selecionado!"
            )
        return self.env.ref("l10n_ao.report_action_periodic_iva").report_action(
            move_ids
        )
