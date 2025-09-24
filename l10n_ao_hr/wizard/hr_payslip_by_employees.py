from odoo import models, fields, api, _
from odoo.osv import expression


class HrPayslipEmployees(models.TransientModel):
    _inherit = 'hr.payslip.employees'

    contract_type = fields.Many2one('hr.contract.type', string='Tipo de Funcionário')

    @api.depends('department_id', 'contract_type')
    def _compute_employee_ids(self):
        for wizard in self:
            domain = wizard._get_available_contracts_domain()
            if wizard.department_id:
                domain = expression.AND([
                    domain,
                    [('department_id', 'child_of', self.department_id.id)]
                ])

            if wizard.contract_type:
                domain = expression.AND([
                    domain,
                    [('contract_type', '=', self.contract_type.id)]
                ])

            if wizard.contract_type and wizard.department_id:
                domain = expression.AND([
                    domain,
                    [('department_id', 'child_of', self.department_id.id),
                     ('contract_type', '=', self.contract_type.id)]
                ])

            wizard.employee_ids = self.env['hr.employee'].search(domain)
