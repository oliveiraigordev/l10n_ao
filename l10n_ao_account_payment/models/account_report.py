# -*- coding: utf-8 -*-
import logging

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class AccountReport(models.Model):
    _inherit = 'account.report'

    def _get_dynamic_lines(self, options, all_column_groups_expression_totals):
        lines = super()._get_dynamic_lines(options, all_column_groups_expression_totals)
        return lines