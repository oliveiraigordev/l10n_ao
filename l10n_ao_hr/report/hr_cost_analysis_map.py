# -*- coding: utf-8 -*-
from odoo import api, models, fields, _
from dateutil.parser import parse
from odoo.exceptions import ValidationError, UserError
import base64, os, tempfile
import xlsxwriter
import numpy as np, pandas as pd
import os
import io
from . import common


class ReportCostAnalysisMap(models.AbstractModel):
    _name = 'report.cost_analysis_map'
    _description = 'Cost Analysis Map'

    def get_docs_values(self, data):
        slip_filter_by = data['form']['slip_filter_by']
        contract_tipe_id = data['form']['contract_type_id']

        if slip_filter_by == 'payslip_batch':
            slip_id = data['form']['hr_payslip_run_id'][0]
            docs = self.env['hr.payslip'].search(
                [('payslip_run_id', '=', slip_id), ('company_id', '=', self.env.company.id),
                 ('state', 'in', ['done', 'paid'])])
            if contract_tipe_id:
                docs = docs.filtered(lambda p: p.contract_type_id.id == contract_tipe_id[0])

            period_start_date = self.env['hr.payslip.run'].browse(slip_id).date_start
            period_end_date = self.env['hr.payslip.run'].browse(slip_id).date_end
        else:
            start_date = data['form']['start_date']
            end_date = data['form']['end_date']
            if type(end_date) is str:
                period_start_date = parse(start_date)
                period_end_date = parse(end_date)
            else:
                period_start_date = start_date
                period_end_date = end_date

            docs = self.env['hr.payslip'].search(
                [('date_to', '>=', start_date), ('date_to', '<=', end_date), ('company_id', '=', self.env.company.id),
                 ('state', 'in', ['done', 'paid'])])
            if contract_tipe_id:
                docs = docs.filtered(lambda p: p.contract_type_id.id == contract_tipe_id[0])

        return docs, period_start_date, period_end_date

    def cost_analysis_map_report(self, docids, data=None):
        if 'form' not in data:
            raise ValidationError('This action is under development')

        docs, period_start_date, period_end_date = self.get_docs_values(data)
        if not docs:
            raise ValidationError('There is no payslips that match this criteria')

        base_url = self.env['ir.config_parameter'].get_param('web.base.url')
        year = period_start_date.year
        if period_start_date.month != period_end_date.month:
            period = '%s-%s' % (
                common.get_month_text(period_start_date.month).upper(),
                common.get_month_text(period_end_date.month).upper())
        else:
            period = '%s' % (common.get_month_text(period_start_date.month).upper())

        dir_path_file = self.create_temp_xlsx_file(period, year, docs)
        file_result = base64.b64encode(open(f'{dir_path_file}', 'rb').read())
        url_file = f'{base_url}/file/map/download?dir_path_file={dir_path_file}'
        return url_file

    def get_xlsx_dict_values(self, docs):
        data_values = []
        code_vals = ['BASE', 'ALI', 'A_CUSTO', 'ALOJAMENTO', 'SAL_FER', 'GRATIF_FER', 'GRAT_REEMB', 'FAMI',
                     'Desc_Seguro', 'RETI', 'NAT', 'ADI', 'HEXTRA_75', 'HEXTRA_50', 'CFNG', 'AVPREVIOCOMP', 'INSS',
                     'IRT']
        index = 5
        # Payslip Values
        for doc in docs:
            base_wage, alojamento, sub_alimentacao, abono_Familia, sub_natal, adiantamento, desconto_seguro, ins, irt, gratificacao, sub_trans = 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0
            ajuda_custo, decOutros, salarios_Ferias, sub_ferias, hora_extra, retroactivos, indeminizacoes_Compensacoes, gratificacao_Reembolso = 0, 0, 0, 0, 0, 0, 0, 0
            desconto_retroativos, irt_amount = 0, 0
            for line in doc.line_ids:
                if 'BASE' in line.code:
                    base_wage = abs(line.total)
                elif 'ALI' == line.code:
                    sub_alimentacao = abs(line.total)
                elif 'TRANS' == line.code:
                    sub_trans = abs(line.total)
                elif line.code in ['A_CUSTO', 'R75']:
                    ajuda_custo = abs(line.total)
                elif 'ALOJAMENTO' == line.code:
                    alojamento = abs(line.total)
                elif 'SAL_FER' in line.code:
                    salarios_Ferias = abs(line.total)
                elif 'GRATIF_FER' in line.code:
                    sub_ferias = abs(line.total)
                elif 'GRAT_REEMB' == line.code:
                    gratificacao_Reembolso = abs(line.total)
                elif 'FAMI' in line.code:
                    abono_Familia = abs(line.total)
                elif line.code in ['Desc_Seguro', 'R99', 'D19', 'D21', 'D32', 'D33', 'D34', 'D35',
                                   'D38', 'D39', 'D40']:
                    desconto_seguro += abs(line.total)
                elif line.code in ['D21', 'D22', 'D23', 'D25', '31', 'RST']:
                    desconto_retroativos += abs(line.total)
                elif 'RETI' in line.code:
                    retroactivos = abs(line.total)
                elif 'NAT' in line.code:
                    sub_natal = abs(line.total)
                elif 'ADI' in line.code:
                    adiantamento = abs(line.total)
                elif line.code in ['HEXTRA_75', 'HEXTRA_50']:
                    hora_extra += abs(line.total)
                elif line.code in ['CFNG', 'AVPREVIOCOMP']:
                    indeminizacoes_Compensacoes += abs(line.total)
                elif 'IRT' in line.code:
                    irt_amount = abs(line.total)

                if line.code in code_vals:
                    continue

                if line.category_id.code in ["DED"]:
                    decOutros += abs(line.total)

            data_values.append({
                f'A{index}': doc.employee_id.registration_number if doc.employee_id.registration_number else '',
                f'B{index}': doc.employee_id.name,
                f'C{index}': doc.employee_id.department_id.name if doc.employee_id.department_id else '',
                f'D{index}': doc.employee_id.job_id.name if doc.employee_id.job_id else '',
                f'E{index}': [category.name for category in doc.employee_id.category_ids][
                    0] if doc.employee_id.category_ids else '',
                f'F{index}': doc.employee_id.contract_type.name if doc.employee_id.contract_type else '',
                f'G{index}': base_wage,
                f'H{index}': sub_alimentacao,
                f'I{index}': sub_trans,
                f'J{index}': alojamento,
                f'K{index}': ajuda_custo,
                f'L{index}': 0,
                f'M{index}': salarios_Ferias,
                f'N{index}': sub_ferias,
                f'O{index}': sub_natal,
                f'P{index}': 0,
                f'Q{index}': abono_Familia,
                f'R{index}': hora_extra,
                f'S{index}': retroactivos,
                f'T{index}': indeminizacoes_Compensacoes,
                f'U{index}': gratificacao_Reembolso,
                f'V{index}': adiantamento,
                f'W{index}': doc.total_remunerations,
                f'X{index}': irt_amount,
                f'Y{index}': doc.collected_material_inss * 0.03,
                f'Z{index}': doc.collected_material_inss * 0.08,
                f'AA{index}': desconto_seguro,
                f'AB{index}': decOutros,
                f'AC{index}': desconto_retroativos,
                f'AD{index}': doc.total_deductions,
                f'AE{index}': doc.total_paid,
            })
            index += 1
        return data_values

    def create_temp_xlsx_file(self, period, year, docs):
        # create Cost Analysis temp file
        temp_file = tempfile.NamedTemporaryFile(mode='w+b', delete=False, suffix=".xls")
        dir_path = temp_file.name
        file = temp_file.name.split('/')
        file[-1] = f"Mapa_analise_de_Custo_com_Pessoal_{period}.xls"
        new_dir_path = '/'.join(map(str, file))
        os.rename(dir_path, new_dir_path)
        # Write file XLSX
        workbook = xlsxwriter.Workbook(new_dir_path)
        worksheet = workbook.add_worksheet()
        title_bold_blue = workbook.add_format(
            {"bold": True, "color": "000080", "align": "center", "valign": "vcenter"})
        color_format_black = workbook.add_format(
            {'bold': True, 'align': 'center', 'valign': 'vcenter', 'border': 1, 'bg_color': '#808080'})
        color_format_black.set_font_color('#000000')
        color_format_white = workbook.add_format(
            {'bold': True, 'align': 'center', 'valign': 'vcenter', 'border': 1, 'bg_color': '#e9ecef'})
        color_format_white.set_font_color('#000000')
        # Header
        # Title
        worksheet.merge_range("A1:F1", f"Mapa análise de  Custo com Pessoal({period}/{year}", title_bold_blue)
        worksheet.write_string('G1', '(Valores em AKZ)', title_bold_blue)
        # BODY
        worksheet.write_string('A4', "Funcionário", color_format_white)
        worksheet.write_string('B4', "Nome", color_format_white)
        worksheet.write_string('C4', "Departamento", color_format_white)
        worksheet.write_string('D4', "Cargo", color_format_white)
        worksheet.write_string('E4', "Categoria", color_format_white)
        worksheet.write_string('F4', "Tipo_Pessoal", color_format_white)
        worksheet.write_string('G4', "Vencimento", color_format_white)
        worksheet.write_string('H4', "Subsídio de Alimentação", color_format_white)
        worksheet.write_string('I4', "Subsídio de Transporte", color_format_white)
        worksheet.write_string('J4', "Alojamento", color_format_white)
        worksheet.write_string('K4', "Ajuda de Custo", color_format_white)
        worksheet.write_string('L4', "Gratificacao", color_format_white)
        worksheet.write_string('M4', "Salário Férias", color_format_white)
        worksheet.write_string('N4', "Sub de Ferias", color_format_white)
        worksheet.write_string('O4', "Sub. Natal", color_format_white)
        worksheet.write_string('P4', "Dif. Cambial", color_format_white)
        worksheet.write_string('Q4', "Abono de Familía", color_format_white)
        worksheet.write_string('R4', "Hora Extra", color_format_white)
        worksheet.write_string('S4', "Rectroativos", color_format_white)
        worksheet.write_string('T4', "Indeminizações e Compensações", color_format_white)
        worksheet.write_string('U4', "Gratificações e Reembolso", color_format_white)
        worksheet.write_string('V4', "Adiantamentos Salário", color_format_white)
        worksheet.write_string('W4', "Total de Remunerações", color_format_white)
        worksheet.write_string('X4', "IRT", color_format_white)
        worksheet.write_string('Y4', "INSS 3%", color_format_white)
        worksheet.write_string('Z4', "INSS 8%", color_format_white)
        worksheet.write_string('AA4', "Desconto de Seguro", color_format_white)
        worksheet.write_string('AB4', 'Outros Descontos', color_format_white)
        worksheet.write_string('AC4', 'Descontos Retroactivos', color_format_white)
        worksheet.write_string('AD4', 'Total de Descontos', color_format_white)
        worksheet.write_string('AE4', 'Total Líquido', color_format_white)

        # Payslip Values
        xlsx_values = self.get_xlsx_dict_values(docs)
        # index = 5 + len(xlsx_values)
        # Payslip Values
        for dic_value in xlsx_values:
            for key, value in dic_value.items():
                worksheet.write(key, value)

        workbook.close()
        return new_dir_path
