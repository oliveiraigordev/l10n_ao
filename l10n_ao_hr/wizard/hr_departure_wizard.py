from odoo import models, fields, api, _
from odoo.exceptions import UserError


class HrDepartureWizard(models.TransientModel):
    _inherit = 'hr.departure.wizard'

    type_of_agreement = fields.Selection(
        [('mutual_agreement', 'Mutuo Acordo'),
         ('work_request', 'A Pedido do Trabalhador'), ('just_cause_dis', 'Justa Causa (Disciplinar)'),
         ('just_cause_ob_c', 'Justa Causa (Causas Objectivas)'), ('resignation', 'Demissão'),
         ('work_abandonment', 'Abandono de Trabalho')])

    # departure_description

    def action_register_departure(self):
        """If set_date_end is checked, set the departure date as the end date to current running contract,
        and cancel all draft contracts"""
        current_contract = self.sudo().employee_id.contract_id
        if current_contract and current_contract.date_start > self.departure_date:
            raise UserError(_("Departure date can't be earlier than the start date of current contract."))

        super(HrDepartureWizard, self).action_register_departure()
        # super(HrDepartureWizard, self).action_register_departure()
        if self.set_date_end:
            current_contract.write(
                {'contract_situation': 'termination', 'state': 'termination', 'early_warning': 'working',
                 'type_of_agreement': self.type_of_agreement, 'date_end': self.departure_date})

            self.sudo().employee_id.write(
                {
                    'employee_situation': 'termination',
                    'departure_raison': self.departure_reason_id.name,
                    'type_of_agreement': self.type_of_agreement,
                    'departure_reason_description': self.departure_description,
                })
