# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import json
import logging
from odoo import api, fields, models, tools, _
from odoo.exceptions import UserError
from odoo.tools import parse_date
import requests
from datetime import date


_logger = logging.getLogger(__name__)

class CurrencyAOA(models.Model):
    _inherit = "res.currency"

    rate_percentage = fields.Float("Rate Percentage")
    def get_update_currency_rate(self):
        for cur in self.env["res.currency"].search([("active", "=", True), ("id", "!=", self.env.company.currency_id.id)]):
            try:
                request_url = f"https://www.bna.ao/service/rest/taxas/get/taxa/referencia?moeda={cur.name.lower()}&tipocambio=b"
                response = requests.get(request_url, verify=False, timeout=30)
                #response = response.replace("false", "False")
                if response.status_code == 200:
                    response = response.text
                    data = json.loads(response)
                    rate = data['genericResponse'][0]['taxa']
                    if not len(self.env['res.currency.rate'].search([('name', '=', date.today()),
                                                                     ('company_id', '=', 1),
                                                                     ('currency_id', '=', cur.id)])):
                        # if cur.rate_percentage > 0:
                        #     rate_percentage = rate * cur.rate_percentage
                        #     rate = rate_percentage + rate
                        self.env['res.currency.rate'].create({'currency_id': cur.id, 'company_id': 1, 'rate': 1.0 / float(rate), 'inverse_company_rate':float(rate)})
            except Exception as err:
                _logger.error(_("Some Error occourred while trying to get the rates for currency %s, you can see thw "
                                "error \n %s") % (cur.name, err))





