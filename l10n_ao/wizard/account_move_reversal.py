# -*- coding: utf-8 -*-
from odoo import models, fields, api, _


class TISAccountMoveReversal(models.TransientModel):  # -u rental_management_extension
    _inherit = 'account.move.reversal'
