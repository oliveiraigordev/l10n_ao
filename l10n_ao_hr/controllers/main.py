import re, logging, io
from PyPDF2 import PdfFileReader, PdfFileWriter
from odoo import models
from odoo.http import request, route, Controller, content_disposition
from odoo.tools.safe_eval import safe_eval
from odoo import http

_logger = logging.getLogger(__name__)


class HrPayroll(Controller):

    @route(["/print/simple/payslips"], type='http', auth='user')
    def get_payroll_report_simple_print(self, list_ids='', **post):
        if not request.env.user.has_group('hr_payroll.group_hr_payroll_user') or not list_ids or re.search("[^0-9|,]",
                                                                                                           list_ids):
            return request.not_found()

        ids = [int(s) for s in list_ids.split(',')]
        payslips = request.env['hr.payslip'].browse(ids)

        pdf_writer = PdfFileWriter()

        for payslip in payslips:
            report = request.env.ref('l10n_ao_hr.action_l10n_ao_hr_report_simple_payslip', False)
            report = report.with_context(lang=payslip.employee_id.sudo().address_home_id.lang)
            pdf_content, _ = request.env['ir.actions.report']. \
                with_context(lang=payslip.employee_id.sudo().address_home_id.lang). \
                sudo(). \
                _render_qweb_pdf(report, payslip.id, data={'company_id': payslip.company_id})
            reader = PdfFileReader(io.BytesIO(pdf_content), strict=False, overwriteWarnings=False)

            for page in range(reader.getNumPages()):
                pdf_writer.addPage(reader.getPage(page))

        _buffer = io.BytesIO()
        pdf_writer.write(_buffer)
        merged_pdf = _buffer.getvalue()
        _buffer.close()

        if len(payslips) == 1 and payslips.struct_id.report_id.print_report_name:
            report_name = safe_eval(payslips.struct_id.report_id.print_report_name, {'object': payslips})
        else:
            report_name = "Simple Payslips"

        pdfhttpheaders = [
            ('Content-Type', 'application/pdf'),
            ('Content-Length', len(merged_pdf)),
            ('Content-Disposition', content_disposition(report_name + '.pdf'))
        ]

        return request.make_response(merged_pdf, headers=pdfhttpheaders)

    @route(["/print/double/payslips"], type='http', auth='user')
    def get_payroll_report_double_print(self, list_ids='', **post):
        if not request.env.user.has_group('hr_payroll.group_hr_payroll_user') or not list_ids or re.search("[^0-9|,]",
                                                                                                           list_ids):
            return request.not_found()

        ids = [int(s) for s in list_ids.split(',')]
        payslips = request.env['hr.payslip'].browse(ids)

        pdf_writer = PdfFileWriter()

        for payslip in payslips:
            report = request.env.ref('l10n_ao_hr.action_l10n_ao_hr_report_double_payslip', False)
            report = report.with_context(lang=payslip.employee_id.sudo().address_home_id.lang)
            pdf_content, _ = request.env['ir.actions.report']. \
                with_context(lang=payslip.employee_id.sudo().address_home_id.lang). \
                sudo(). \
                _render_qweb_pdf(report, payslip.id, data={'company_id': payslip.company_id})
            reader = PdfFileReader(io.BytesIO(pdf_content), strict=False, overwriteWarnings=False)

            for page in range(reader.getNumPages()):
                pdf_writer.addPage(reader.getPage(page))

        _buffer = io.BytesIO()
        pdf_writer.write(_buffer)
        merged_pdf = _buffer.getvalue()
        _buffer.close()

        if len(payslips) == 1 and payslips.struct_id.report_id.print_report_name:
            report_name = safe_eval(payslips.struct_id.report_id.print_report_name, {'object': payslips})
        else:
            report_name = "Double Payslips"

        pdfhttpheaders = [
            ('Content-Type', 'application/pdf'),
            ('Content-Length', len(merged_pdf)),
            ('Content-Disposition', content_disposition(report_name + '.pdf'))
        ]

        return request.make_response(merged_pdf, headers=pdfhttpheaders)

    @route(["/print/termination/mock/receipt"], type='http', auth='user')
    def get_payroll_report_simple_print(self, list_ids='', **post):
        if not request.env.user.has_group('hr_payroll.group_hr_payroll_user') or not list_ids or re.search("[^0-9|,]",
                                                                                                           list_ids):
            return request.not_found()

        ids = [int(s) for s in list_ids.split(',')]
        payslips = request.env['hr.payslip'].browse(ids)

        pdf_writer = PdfFileWriter()

        for payslip in payslips:
            report = request.env.ref('l10n_ao_hr.action_l10n_ao_hr_report_termination_mock_receipt', False)
            report = report.with_context(lang=payslip.employee_id.sudo().address_home_id.lang)
            pdf_content, _ = request.env['ir.actions.report']. \
                with_context(lang=payslip.employee_id.sudo().address_home_id.lang). \
                sudo(). \
                _render_qweb_pdf(report, payslip.id, data={'company_id': payslip.company_id})
            reader = PdfFileReader(io.BytesIO(pdf_content), strict=False, overwriteWarnings=False)

            for page in range(reader.getNumPages()):
                pdf_writer.addPage(reader.getPage(page))

        _buffer = io.BytesIO()
        pdf_writer.write(_buffer)
        merged_pdf = _buffer.getvalue()
        _buffer.close()

        if len(payslips) == 1 and payslips.struct_id.report_id.print_report_name:
            report_name = safe_eval(payslips.struct_id.report_id.print_report_name, {'object': payslips})
        else:
            report_name = "Mock Recept"

        pdfhttpheaders = [
            ('Content-Type', 'application/pdf'),
            ('Content-Length', len(merged_pdf)),
            ('Content-Disposition', content_disposition(report_name + '.pdf'))
        ]

        return request.make_response(merged_pdf, headers=pdfhttpheaders)

    @http.route(['/file/map/download'], type='http', auth="user", website=True)
    def query_download(self, dir_path_file, **kw):
        _logger.info("Download file %s" % dir_path_file)
        with open(dir_path_file, 'rb') as f:
            file_data = f.read()

        return request.make_response(file_data, [('Content-Type', 'application/octet-stream'),
                                                 ('Content-Disposition', f'attachment; filename="{dir_path_file}"')])
