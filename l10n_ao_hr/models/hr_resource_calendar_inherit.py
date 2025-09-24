from odoo import fields, models, api, _
from odoo.exceptions import AccessError, UserError, ValidationError


class HRSchedule(models.Model):
    _inherit = 'resource.calendar'

    define_manual_week_hours = fields.Boolean('Definir manualmente as horas da semana',
                                              help='Check this box if you want to manually define the total of week hours for this schedule')
    manual_week_hours = fields.Float('Manual Semana Horas', digits=(10, 2), help='Total work hours in the week')
    computed_week_hours = fields.Float(compute='compute_computed_week_hours', string='Horas semanais computadas')
    week_hours_final = fields.Float(compute='compute_week_hours_final', string='Total de horas semanais')
    calendar_type = fields.Selection([('normal', 'Normal'), ('trabalho_por_turnos', 'Horário de trabalho por turnos'),
                                      ('trabalho_em_tempo_parcial', 'Horário de trabalho em tempo parcial'),
                                      ('regime_de_disponibilidade', 'Horário regime de disponibilidade'), (
                                          'alternância_de_tempo_trabalho_e_tempo_de_repouso',
                                          'Horário com alternância de tempo de trabalho e tempo de repouso'),
                                      ('trabalhador_estudante', 'Horário do trabalhador estudante'),
                                      ('Trabalho_nocturno', 'Horário de Trabalho nocturno')],
                                     string="Tipo de Calendário", default='normal')

    def write(self, vals):
        res = super().write(vals)
        if self.env.company.country_id.code == "AO":
            for record in self:
                if record.calendar_type == 'trabalho_por_turnos':
                    if int(record.full_time_required_hours) > 44 or int(record.computed_week_hours) > 44:
                        raise UserError(
                            _(f"As horas para este Horário de Trabalho não pode exceder 44 horas semanalmente."))

        return res

    def compute_computed_week_hours(self):
        res = {}
        time_float = 0
        if self.env.company.country_id.code == "AO":
            for schedule in self:
                for line in schedule.attendance_ids:
                    time_float += (line.hour_to - line.hour_from)
                res[schedule.id] = time_float
        self.computed_week_hours = time_float
        return time_float

    def compute_week_hours_final(self):
        res = 0
        for schedule in self:
            if schedule.define_manual_week_hours:
                res = schedule.manual_week_hours
                schedule.week_hours_final = schedule.manual_week_hours
            else:
                res = schedule.computed_week_hours
                schedule.week_hours_final = schedule.computed_week_hours
        return res


class HRResourceCalendarAttendance(models.Model):
    _inherit = "resource.calendar.attendance"

    day_period = fields.Selection(selection_add=[('afternoon',), ('night', 'Night')],
                                  ondelete={'night': 'set default'})
