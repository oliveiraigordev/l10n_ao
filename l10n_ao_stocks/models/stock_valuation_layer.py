from odoo import models

class StockValuationLayer(models.Model):
    _inherit = 'stock.valuation.layer'

    def _validate_accounting_entries(self):
        am_vals = []
        for svl in self:
            # Só contabiliza em valuation automático
            tmpl = svl.product_id.product_tmpl_id.with_company(svl.company_id)
            if getattr(tmpl, 'use_product_stock_account', False):
                is_real_time = (tmpl.stock_valuation == 'real_time')
            else:
                is_real_time = (svl.with_company(svl.company_id).product_id.valuation == 'real_time')
            if not is_real_time:
                continue

            #  Ignora SVLs sem valor
            if svl.currency_id.is_zero(svl.value):
                continue

            # Gerar linhas contábeis
            move = svl.stock_move_id or svl.stock_valuation_layer_id.stock_move_id
            if not move:
                continue
            am_vals += move.with_company(svl.company_id)._account_entry_move(
                svl.quantity, svl.description or '', svl.id, svl.value
            )

        # Cria e postar os lançamentos
        if am_vals:
            moves = self.env['account.move'].sudo().create(am_vals)
            moves._post()

        # Reconciliação anglo-saxã (igual ao nativo)
        for svl in self:
            if svl.company_id.anglo_saxon_accounting:
                svl.stock_move_id._get_related_invoices()\
                    ._stock_account_anglo_saxon_reconcile_valuation(product=svl.product_id)
