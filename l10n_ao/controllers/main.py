from odoo import http
from odoo.http import request
from odoo.addons.web.controllers.main import content_disposition

class SAFTController(http.Controller):

    @http.route('/web/download/saft_ao_file/<int:file_id>', type='http', auth='user')
    def download_saft_file(self, file_id, **kwargs):

        saft_file = request.env["saft.register.file"].search([("id", "=", file_id)])
        return request.make_response(saft_file.xml_text,
                                 [('Content-Type', 'application/xml'),
                                  ('Content-Disposition', content_disposition(saft_file.name + ".xml"))])