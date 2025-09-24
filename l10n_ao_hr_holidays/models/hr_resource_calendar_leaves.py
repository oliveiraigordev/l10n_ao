import logging
from odoo import api, models, fields, _

_logger = logging.getLogger(__name__)


class HRResourceCalendarLeaves(models.Model):
    _inherit = "resource.calendar.leaves"

    is_active = fields.Boolean()
    time_type = fields.Selection(
        selection_add=[('extra_hour', 'Extra Hour'), ('vacation', 'Vacation'), ('delay', 'Delay'),
                       ('unjustified_absence', 'unjustified Absence'),
                       ('unpaid_justified_absence', 'Unpaid Justified Absence')])
