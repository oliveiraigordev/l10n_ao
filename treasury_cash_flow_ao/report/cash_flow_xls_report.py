# -*- coding: utf-8 -*-
from odoo import models, _
from odoo.tools.misc import xlsxwriter


class TreasuryCashFlowXlsx(models.AbstractModel):
    _name = 'report.treasury_cash_flow_ao.account_cashflow_xlsx'
    _inherit = 'report.report_xlsx.abstract'

    # ------------------------------------------------------------------
    # XLSX
    # ------------------------------------------------------------------

    def generate_xlsx_report(self, workbook, data, wizard):
        # ──────────────────────────────
        #  FORMATOS
        # ──────────────────────────────
        title_fmt = workbook.add_format({
            'bold': True, 'font_size': 16, 'align': 'center', 'valign': 'vcenter'
        })
        period_fmt = workbook.add_format({
            'italic': True, 'font_size': 11, 'align': 'center', 'valign': 'vcenter'
        })
        box_header_fmt = workbook.add_format({
            'bold': True, 'bg_color': '#d9d9d9', 'border': 1,
            'align': 'center', 'valign': 'vcenter'
        })
        cell_fmt = workbook.add_format({'border': 1})
        money_fmt = workbook.add_format({'num_format': '#,##0.00', 'border': 1})
        date_fmt = workbook.add_format({'num_format': 'dd/mm/yyyy', 'border': 1})
        total_fmt = workbook.add_format({
            'bold': True, 'bg_color': '#f0f0f0', 'border': 1,
            'align': 'center', 'valign': 'vcenter'
        })
        total_money_fmt = workbook.add_format({
            'bold': True, 'bg_color': '#f0f0f0', 'border': 1,
            'num_format': '#,##0.00'
        })

        # ──────────────────────────────
        #  SHEET, TÍTULO E PERÍODO
        # ──────────────────────────────
        sheet = workbook.add_worksheet(_('Cash-flow'))
        # Título em A1:F1
        sheet.merge_range(0, 0, 0, 5, _('Fluxo de Tesouraria'), title_fmt)
        sheet.set_row(0, 24)
        # Período em A2:F2
        start = wizard.start_date.strftime('%d/%m/%Y') if wizard.start_date else ''
        end = wizard.end_date.strftime('%d/%m/%Y') if wizard.end_date else ''
        sheet.merge_range(1, 0, 1, 5, f"({start} até {end})", period_fmt)
        sheet.set_row(1, 18)

        # ──────────────────────────────
        #  CAIXA DE INFORMAÇÃO (BOX INFO)
        # ──────────────────────────────
        info = wizard.get_cash_flow_data()
        # Cabeçalho da caixa (linha 2)
        box_headers = [_('Ref'), _('Qtd. Movimentos'), _('Saldo Inicial'), _('Saldo Final')]
        for col, title in enumerate(box_headers):
            sheet.write(2, col, title, box_header_fmt)
            sheet.set_column(col, col, 18)
        # Valores da caixa (linha 3)
        sheet.write(3, 0, info['journal_name'], cell_fmt)
        sheet.write(3, 1, info['movement_count'], cell_fmt)
        sheet.write_number(3, 2, info['start_balance'], money_fmt)
        sheet.write_number(3, 3, info['end_balance'], money_fmt)

        # ──────────────────────────────
        #  TABELA DE LANÇAMENTOS
        # ──────────────────────────────
        main_headers = [
            _('Data'),
            _('Descrição / Doc.'),
            _('Responsável'),
            _('Débito'),
            _('Crédito'),
            _('Saldo')
        ]
        header_row = 5
        for col, title in enumerate(main_headers):
            sheet.write(header_row, col, title, box_header_fmt)
            sheet.set_column(col, col, 22)

        # Dados a partir da linha 6
        row = header_row + 1
        total_debit = total_credit = 0.0
        for line in info['lines']:
            # Data
            if line['date']:
                sheet.write_datetime(row, 0, line['date'], date_fmt)
            else:
                sheet.write(row, 0, '', cell_fmt)
            # Descrição
            descr = line.get('description') or ''
            mem = line.get('memorando') or ''
            if mem:
                descr = f"{descr}  ({mem})"
            sheet.write(row, 1, descr, cell_fmt)
            # Responsável
            sheet.write(row, 2, line.get('responsible', ''), cell_fmt)
            # Valores
            debit = line.get('debit') or 0.0
            credit = line.get('credit') or 0.0
            balance = line.get('balance') or 0.0
            sheet.write_number(row, 3, debit, money_fmt)
            sheet.write_number(row, 4, credit, money_fmt)
            sheet.write_number(row, 5, balance, money_fmt)
            total_debit += debit
            total_credit += credit
            row += 1

        # ──────────────────────────────
        #  TOTALIZADOR
        # ──────────────────────────────
        total_balance = total_debit - total_credit
        sheet.write(row, 0, '', total_fmt)
        sheet.write(row, 1, '', total_fmt)
        sheet.write(row, 2, _('TOTAL'), total_fmt)
        sheet.write_number(row, 3, total_debit, total_money_fmt)
        sheet.write_number(row, 4, total_credit, total_money_fmt)
        sheet.write_number(row, 5, total_balance, total_money_fmt)



