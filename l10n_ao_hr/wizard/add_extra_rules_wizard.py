# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import html2plaintext


class HrAddExtraRules(models.TransientModel):
    _name = 'hr.add.extra.salary.rules'
    _description = 'Add Extra Rules Wizard'

    employee_ids = fields.Many2many(
        comodel_name="hr.employee",
        string="Employees",
        readonly=False,
    )
    payslip_run_id = fields.Many2one(
        comodel_name="hr.payslip.run",
        string="Payslip Run",
        readonly=True,
    )
    rule_lines_ids = fields.One2many(
        comodel_name="hr.add.extra.salary.rule.lines",
        inverse_name="add_extra_rules_id",
        string="Extra Rule Lines"
    )
    company_id = fields.Many2one(related='payslip_run_id.company_id', readonly=True)

    employee_ids_batch_list = fields.Many2many(
        comodel_name="hr.employee",
        string="Batch List of Employees",
        compute='_compute_employee_ids_batch_list',
        store=False,
        readonly=True
    )

    @api.depends('payslip_run_id')
    def _compute_employee_ids_batch_list(self):
        for record in self:
            payslips = self.env['hr.payslip'].search([('payslip_run_id', '=', record.payslip_run_id.id)])
            employee_ids = payslips.mapped('employee_id')
            record.employee_ids_batch_list = [(6, 0, employee_ids.ids)]

    def add_extra_rules_payslip(self):

        if not self.rule_lines_ids:
            raise UserError(_("You must select at least one rule."))

        # Verificar se tem alguma regra selecinada com valor 0
        for rule_line in self.rule_lines_ids:
            if rule_line.amount == 0:
                raise UserError(_("You cannot add a rule with an amount of 0."))



        payslips = self.env['hr.payslip'].search([('payslip_run_id', '=', self.payslip_run_id.id)])
        selected_employee_ids = self.employee_ids.ids
        payslips = payslips.filtered(lambda r: r.contract_id and r.contract_id.employee_id.id in selected_employee_ids)

        for payslip in payslips:
            # Verificar se a regra já não existe no payslip e emitir alerta
            if payslip.line_ids.salary_rule_id.filtered(
                    lambda r: r.code in [rule_line.salary_rule_id.code for rule_line in self.rule_lines_ids]):
                lines_exist = payslip.line_ids.salary_rule_id.filtered(
                    lambda r: r.code in [rule_line.salary_rule_id.code for rule_line in self.rule_lines_ids])
                raise UserError(_("The rules %s already exists in the payslip.") % [line.name for line in lines_exist])

            rules_to_add = []
            for rule_line in self.rule_lines_ids:
                if not self.env['hr.payslip.input.type'].search([('code', '=', rule_line.salary_rule_id.code)]):
                    raise UserError(
                        _("The rule %s does not exist in the payslip input.") % rule_line.salary_rule_id.name)

                rules_to_add.append(
                    (0, 0, {
                        'payslip_id': payslip.id,
                        'input_type_id': self.env['hr.payslip.input.type'].search(
                            [('code', '=', rule_line.salary_rule_id.code)],
                            limit=1).id,
                        'amount': rule_line.amount,
                        'hours': 0,
                        'date': fields.Date.today()
                    })
                )

            payslip.compute_sheet(add_wizard=rules_to_add)

        return {'type': 'ir.actions.act_window_close'}


class HrAddExtraRulesLines(models.TransientModel):
    _name = 'hr.add.extra.salary.rule.lines'
    _description = 'Add Extra Rule Lines Wizard'

    add_extra_rules_id = fields.Many2one(
        comodel_name="hr.add.extra.salary.rules",
        string="Add Extra Rules"
    )

    salary_rule_id = fields.Many2one(
        comodel_name="hr.salary.rule",
        string="Salary Rule", requird=True
    )
    amount = fields.Float(
        string="Amount",
        required=True
    )
