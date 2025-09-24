from odoo import models, fields, api, _

class ResStateCountyAng(models.Model):
    _name = "res.state.county"
    _description = "State County"

    state_id = fields.Many2one('res.country.state', string='Province', required=True)
    name = fields.Char(string='County Name', required=True,
                       help='Administrative divisions of a State or Province')
    code = fields.Char(string='County Code', help='The County code.', required=True)



class ResCountryStateAng(models.Model):
    _inherit = "res.country.state"

    county_ids = fields.One2many("res.state.county", "state_id")