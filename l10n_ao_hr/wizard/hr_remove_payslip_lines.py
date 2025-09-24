# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class HrPayslipRemoveLines(models.TransientModel):
    _name = 'hr.payslip.remove.lines'
    _description = 'Remuneration Lines Removal'

    employee_ids = fields.Many2many(
        comodel_name="hr.employee",
        string="Employees",
        readonly=False,
    )
    line_ids = fields.Many2many(
        comodel_name="hr.extra.remuneration.code",
        string="Remuneration Lines",
    )
    date_start = fields.Date(string="Start Date", default=fields.Date.context_today, required=True)
    date_end = fields.Date(string="End Date", default=fields.Date.context_today, required=True)

    def removal_payslip_lines(self):
        for employee in self.employee_ids:
            payslip = self.env['hr.payslip'].sudo().search(
                [('employee_id', '=', employee.id), ('state', 'in', ['draft', 'verify']),
                 ('date_from', '>=', self.date_start),
                 ('date_to', '<=', self.date_end)])
            if not payslip:
                raise UserError(_("No payslip found for employee %s between %s and %s") % (employee.name, self.date_start, self.date_end))

            remove_wizard = self.line_ids.mapped('code')
            payslip.compute_sheet(remove_wizard=remove_wizard)

        return {'type': 'ir.actions.act_window_close'}
