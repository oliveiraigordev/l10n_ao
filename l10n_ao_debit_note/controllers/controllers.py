# -*- coding: utf-8 -*-
# from odoo import http


# class TransCostu(http.Controller):
#     @http.route('/transtar_dpc_payment/transtar_dpc_payment', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/transtar_dpc_payment/transtar_dpc_payment/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('transtar_dpc_payment.listing', {
#             'root': '/transtar_dpc_payment/transtar_dpc_payment',
#             'objects': http.request.env['transtar_dpc_payment.transtar_dpc_payment'].search([]),
#         })

#     @http.route('/transtar_dpc_payment/transtar_dpc_payment/objects/<model("transtar_dpc_payment.transtar_dpc_payment"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('transtar_dpc_payment.object', {
#             'object': obj
#         })
