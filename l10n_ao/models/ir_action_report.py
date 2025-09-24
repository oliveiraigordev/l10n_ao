from odoo import models, fields, api, _
from odoo.tools.safe_eval import safe_eval
from odoo.exceptions import UserError, ValidationError


class IrActionsReportAO(models.Model):
    _inherit = 'ir.actions.report'

   #print_control = fields.Boolean("Print Control", default=True)

    # @override the method to add printing control features to the report.
    def _render_qweb_pdf(self, report_ref, res_ids=None, data=None):
        """Return an action of type ir.actions.report.

        :param res_ids: id/ids/browserecord of the records to print (if not used, pass an empty list)
        :param data: Name of the template to generate an action for
        """
        if self._get_report(report_ref).report_name in ('l10n_ao.report_invoice_triple_document'):
            invoices = self.env['account.move'].browse(res_ids)
            if any((x.state in "draft") for x in invoices):
                raise UserError(_("Os Documentos  passivos de ser entregue  ao cliente que estejam em rascunhos apenas podem ser impressos após serem assinados."))
            #if any((x.payment_state in "reversed" and x.move_type == 'out_invoice') for x in invoices):
                #raise UserError(_("As Facturas Anuladas Não podem ser impressas, caso necessário poderá recorrer a impressão da nota de crédito que a anulou."))
            #if self.print_control:
            for invoice in invoices:
                     invoice.write({"print_counter": invoice.print_counter + 1})
        elif self._get_report(report_ref).report_name in ('l10n_ao.report_payment_receipt_agt'):
            payments = self.env['account.payment'].browse(res_ids)
            if any(x.state in "draft" for x in payments):
                raise UserError(_("Os Documentos  passivos de ser entregue  ao cliente que estejam em rascunhos apenas podem ser impressos após serem assinados."))
        # elif self._get_report(report_ref).report_name in ('l10n_ao_sale.report_saleorder_agt'):
        #     sales = self.env['sale.order'].browse(res_ids)
        #     if any(x.state in "draft" for x in sales):
        #         raise UserError(_("Os Documentos  passivos de ser entregue  ao cliente que estejam em rascunhos apenas podem ser impressos após serem assinados."))

        return super(IrActionsReportAO, self)._render_qweb_pdf(report_ref, res_ids=res_ids, data=data)
