from odoo import fields, models
from odoo.exceptions import UserError


class HRLeaveType(models.Model):
    _inherit = 'hr.leave.type'

    time_type = fields.Selection(
        selection_add=[('vacation', 'Férias'), ('extra_hour', 'Extra Hour'), ('delay', 'Delay'),
                       ('unjustified_absence', 'unjustified Absence'),
                       ('unpaid_justified_absence', 'Unpaid Justified Absence')])
    dont_validate_vacation = fields.Boolean(string='Não valida regras de férias')

    # Do not allow user to edit time_type for leave type vacation
    def write(self, values):
        leave_type_vocation_id = self.env.ref('l10n_ao_hr_holidays.l10n_ao_hr_leave_type_vocation')
        # Check if 'time_type' in vals and if the value is different from 'vacation'
        # and block the edit of this field only
        if leave_type_vocation_id in self and values.get("time_type", "vacation") != "vacation":
            raise UserError("Não é possível editar o 'Tipo de Férias' deste objeto!")
        return super(HRLeaveType, self).write(values)

    # Do not allow user to unlink leave type vacation
    def unlink(self):
        leave_type_vocation_id = self.env.ref('l10n_ao_hr_holidays.l10n_ao_hr_leave_type_vocation')
        if leave_type_vocation_id in self:
            raise UserError("Não é possível remover este objeto!")
        return super(HRLeaveType, self).unlink()

    def getVacationLogo(self, ):
        icon_id = self.env.ref("l10n_ao_hr_holidays.l10n_ao_hr_leave_type_vocation").mapped('icon_id')
        return icon_id.image_src
