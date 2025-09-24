# -*- coding: utf-8 -*-
from odoo import api, models, fields, _
from dateutil.parser import parse
from odoo.exceptions import ValidationError, UserError
from xml.dom.minidom import parseString
from dicttoxml2 import dicttoxml
import base64, os, tempfile
import xlsxwriter


class ReportRemunerationMap(models.AbstractModel):
    _name = 'report.remuneration_map'
    _description = 'Remuneration Map'

    def get_docs_values(self, data):
        slip_filter_by = data['form']['slip_filter_by']
        contract_tipe_id = data['form']['contract_type_id']

        if slip_filter_by == 'payslip_batch':
            slip_id = data['form']['hr_payslip_run_id'][0]
            docs = self.env['hr.payslip'].search(
                [('payslip_run_id', '=', slip_id), ('company_id', '=', self.env.company.id)])
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

            docs = self.env['hr.payslip'].search([('date_to', '>=', start_date), ('date_to', '<=', end_date),
                                                  ('company_id', '=', self.env.company.id),
                                                  ('state', 'in', ['done', 'paid'])])
            if contract_tipe_id:
                docs = docs.filtered(lambda p: p.contract_type_id.id == contract_tipe_id[0])

        return docs, period_start_date, period_end_date

    def remuneration_map_report(self, docids, report_file, data=None):

        docs, period_start_date, period_end_date = self.get_docs_values(data)
        year = period_start_date.year
        if not docs:
            raise ValidationError('There is no payslips that match this criteria')

        months = {1: _('01'), 2: _('02'), 3: _('03'), 4: _('04'), 5: _('05'), 6: _('06'), 7: _('07'), 8: _('08'),
                  9: _('09'), 10: _('10'), 11: _('11'), 12: _('12'), }

        def create_remuneration_dict(period, docs):
            remuneration_map_dict = {}
            code_vals = ['BASE', 'CHEF', 'NAT', 'PREM', 'REPR', 'ATA', 'FER', 'HEXTRA_50',
                         'HEXTRA_75', 'CORES', 'RENC', 'RENDES', 'FALHA', 'FAMI', 'TRANS', 'ALI', 'FJNR', 'FI']
            remuneration_map_dict["MapaRemuneracoes"] = {
                "AgenteRetencao": {'strNifAgente': self.env.company.vat, 'strAnoMes': period}}
            remuneration_map_dict["MapaRemuneracoes"]['Remuneracao'] = []
            for doc in docs:
                decDescontoFaltas = decAlimentacao = decTransporte = decAbonoFamilia = decOutros = decAbonoFalhas = decBaseWage = 0
                decSubsidioRepresentacao = decSubsidioAtavio = decHorasExtras = decSubsidioFerias = decCompensacaoRescisao = desIRT = 0
                decRendaCasa = decReembolsoDespesas = decPremios = decSubsidioNatal = decOutrosSubsidiosSujeitos = decSubsidioChefia = 0
                for line in doc.line_ids:
                    if 'BASE' == line.code:
                        decBaseWage += abs(line.total)
                    elif 'ALI' == line.code:
                        decAlimentacao = abs(line.total)
                    elif 'TRANS' == line.code:
                        decTransporte = abs(line.total)
                    elif 'FAMI' in line.code:
                        decAbonoFamilia = abs(line.total)
                    elif 'FALHA' in line.code:
                        decAbonoFalhas = abs(line.total)
                    elif 'RENDES' in line.code:
                        decReembolsoDespesas = abs(line.total)
                    elif 'RENC' in line.code:
                        decRendaCasa = line.total
                    elif 'CORES' in line.code:
                        decCompensacaoRescisao = abs(line.total)
                    elif 'FER' in line.code:
                        decSubsidioFerias = abs(line.total)
                    elif 'ATA' in line.code:
                        decSubsidioAtavio = abs(line.total)
                    elif 'REPR' in line.code:
                        decSubsidioRepresentacao = abs(line.total)
                    elif 'PREM' in line.code:
                        decPremios = abs(line.total)
                    elif 'NAT' in line.code:
                        decSubsidioNatal = abs(line.total)
                    elif line.code in ['HEXTRA_50', 'HEXTRA_75']:
                        decHorasExtras += abs(line.total)
                    elif line.code in ['FJNR', 'FI']:
                        decDescontoFaltas += abs(line.total)
                    elif 'IRT' in line.code:
                        desIRT = abs(line.total)

                    if line.code in code_vals:
                        continue

                    if line.category_id.code in ['ALW', "ABO", "DED"]:
                        decOutros += abs(line.total)
                    elif line.category_id.code in ['COMP', "ABOIRT", "ABOINSSIRT", "DEDINSSIRT"]:
                        decOutrosSubsidiosSujeitos += abs(line.total)

                salario_iliquido = [decBaseWage, decDescontoFaltas, decTransporte, decAlimentacao, decPremios,
                                    decOutros, decSubsidioFerias, decOutrosSubsidiosSujeitos, decSubsidioChefia]
                baseTributavelSS = sum(salario_iliquido) - decSubsidioFerias
                contribuicaoSS = baseTributavelSS * 0.03
                remuneration_map_dict["MapaRemuneracoes"]['Remuneracao'].append({
                    "strNifFuncionario": doc.employee_id.fiscal_number if doc.employee_id.fiscal_number else '',
                    "strNomeFuncionario": doc.employee_id.name,
                    "strNumSS": doc.employee_id.social_security if doc.employee_id.social_security else '',
                    "strProvincia": doc.employee_id.address_province if doc.employee_id.address_province else '',
                    "strMunicipio": doc.employee_id.address_county if doc.employee_id.address_county else '',
                    "decSalarioBase": decBaseWage,
                    "decDescontoFaltas": decDescontoFaltas,
                    "SubsidiosNaoSujeitosIRT": {"decAlimentacao": decAlimentacao, "decTransporte": decTransporte,
                                                "decAbonoFamilia": decAbonoFamilia,
                                                "decReembolsoDespesas": decReembolsoDespesas,
                                                "decOutros": decOutros},
                    "strManualExcSubsNaoSujeitosIRT": 'N',
                    "decExcSubsNaoSujeitosIRT": 0,
                    "SubsidiosSujeitosIRT": {"decAbonoFalhas": decAbonoFalhas, "decRendaCasa": decRendaCasa,
                                             "decCompensacaoRescisao": decCompensacaoRescisao,
                                             "decSubsidioFerias": decSubsidioFerias,
                                             "decHorasExtras": decHorasExtras,
                                             "decSubsidioAtavio": decSubsidioAtavio,
                                             "decSubsidioRepresentacao": decSubsidioRepresentacao,
                                             "decPremios": decPremios, "decSubsidioNatal": decSubsidioNatal,
                                             "decOutrosSubsidiosSujeitos": decOutrosSubsidiosSujeitos},
                    "decSalarioIliquido": sum(salario_iliquido),
                    "strManualBaseTributavelSS": "N",
                    "decBaseTributavelSS": baseTributavelSS,
                    "strIsentoSS": "N",
                    "decContribuicaoSS": contribuicaoSS,
                    "decBaseTributavelIRT": baseTributavelSS - contribuicaoSS - decAbonoFamilia - decTransporte - decAlimentacao,
                    "strIsentoIRT": "N",
                    "decIRTApurado": desIRT
                })
            return remuneration_map_dict

        def get_xlsx_dict_values(docs):
            data_values = []
            code_vals = ['BASE', 'CHEF', 'NAT', 'PREM', 'REPR', 'ATA', 'FER', 'HEXTRA_50',
                         'HEXTRA_75', 'CORES', 'RENC', 'RENDES', 'FALHA', 'FAMI', 'TRANS', 'ALI', 'FJNR', 'FI']
            index = 5
            # Payslip Values
            for doc in docs:
                decDescontoFaltas = decAlimentacao = decTransporte = decAbonoFamilia = decOutros = decAbonoFalhas = desIRT = 0.0
                decSubsidioRepresentacao = decSubsidioAtavio = decHorasExtras = decSubsidioFerias = decCompensacaoRescisao = decSubsidioChefia = 0.0
                decRendaCasa = decReembolsoDespesas = decPremios = decSubsidioNatal = decOutrosSubsidiosSujeitos = decBaseWage = 0.0
                for line in doc.line_ids:
                    if 'BASE' == line.code:
                        decBaseWage += abs(line.total)
                    elif line.code in ['ALI', 'sub_ali']:
                        decAlimentacao = abs(line.total)
                    elif line.code in ['TRANS', 'sub_trans']:
                        decTransporte = abs(line.total)
                    elif line.code in ['FAMI', 'sub_fam']:
                        decAbonoFamilia = abs(line.total)
                    elif 'FALHA' in line.code:
                        decAbonoFalhas = abs(line.total)
                    elif 'RENDES' in line.code:
                        decReembolsoDespesas = abs(line.total)
                    elif 'RENC' in line.code:
                        decRendaCasa = line.total
                    elif 'CORES' in line.code:
                        decCompensacaoRescisao = abs(line.total)
                    elif line.code in ['GRATIF_FER', 'FER']:
                        decSubsidioFerias = abs(line.total)
                    elif 'ATA' in line.code:
                        decSubsidioAtavio = abs(line.total)
                    elif 'REPR' in line.code:
                        decSubsidioRepresentacao = abs(line.total)
                    elif 'PREM' in line.code:
                        decPremios = abs(line.total)
                    elif 'NAT' in line.code:
                        decSubsidioNatal = abs(line.total)
                    elif line.code in ['HEXTRA_50', 'HEXTRA_75']:
                        decHorasExtras += abs(line.total)
                    elif line.code in ['FJNR', 'FI']:
                        decDescontoFaltas += abs(line.total)
                    elif 'IRT' in line.code:
                        # transformar o valor para negativo para positivo
                        desIRT = abs(line.total)

                    if line.code in code_vals:
                        continue

                    if line.category_id.code in ['ALW', "ABO"] and line.code not in ['R891', 'R36']:
                        decOutros += abs(line.total)
                    elif line.category_id.code in ['COMP', "ABOIRT", "ABOINSSIRT", "DEDINSSIRT"]:
                        decOutrosSubsidiosSujeitos += abs(line.total)
                    elif line.category_id.code in ['PREMIO']:
                        decPremios += abs(line.total)

                data_values.append({
                    f'A{index}': doc.employee_id.fiscal_number if doc.employee_id.fiscal_number else '',
                    f'B{index}': doc.employee_id.name,
                    f'C{index}': doc.employee_id.social_security if doc.employee_id.social_security else '',
                    f'D{index}': doc.employee_id.address_province if doc.employee_id.address_province else '',
                    f'E{index}': doc.employee_id.address_county if doc.employee_id.address_county else '',
                    f'F{index}': decBaseWage,
                    f'G{index}': decDescontoFaltas,
                    f'H{index}': decAlimentacao,
                    f'I{index}': decTransporte,
                    f'J{index}': decAbonoFamilia,
                    f'K{index}': decReembolsoDespesas,
                    f'L{index}': decOutros,
                    f'M{index}': 'N',
                    f'N{index}': decAlimentacao + decTransporte + decAbonoFamilia + decReembolsoDespesas + decOutros,
                    f'O{index}': decAbonoFalhas,
                    f'P{index}': decRendaCasa,
                    f'Q{index}': decCompensacaoRescisao,
                    f'R{index}': decSubsidioFerias,
                    f'S{index}': decHorasExtras,
                    f'T{index}': decSubsidioAtavio,
                    f'U{index}': decSubsidioRepresentacao,
                    f'V{index}': decPremios,
                    f'W{index}': decSubsidioNatal,
                    f'X{index}': decOutrosSubsidiosSujeitos,
                    f'Y{index}': doc.total_remunerations,
                    f'Z{index}': 'N',
                    f'AA{index}': doc.collected_material_inss,
                    f'AB{index}': 'N',
                    f'AC{index}': doc.collected_material_inss * 0.03,
                    f'AD{index}': doc.collected_material_irt if doc.collected_material_irt_with_exedent == 0 else doc.collected_material_irt_with_exedent,
                    f'AE{index}': "N" if doc.contract_id.irt_exempt else "S",
                    f'AF{index}': desIRT,
                })
                index += 1

            return data_values

        def create_temp_xlsx_file(period, docs):
            # create remuneration temp file
            temp_file = tempfile.NamedTemporaryFile(mode='w+b', delete=False, suffix=".xls")
            dir_path = temp_file.name
            file = temp_file.name.split('/')
            file[-1] = f"Mapa_de_remuneracao_{period}.xls"
            new_dir_path = '/'.join(map(str, file))
            os.rename(dir_path, new_dir_path)
            # Write file XLSX
            workbook = xlsxwriter.Workbook(new_dir_path)
            worksheet = workbook.add_worksheet()
            cell_format = workbook.add_format(
                {'bold': True, 'align': 'center', 'valign': 'vcenter', 'border': 1, 'bg_color': '#808080'})
            cell_format.set_font_color('#000000')
            color_format_silver = workbook.add_format(
                {'bold': True, 'align': 'center', 'valign': 'vcenter', 'border': 1, 'bg_color': '#A9A9A9', })
            color_format_silver.set_font_color('#191970')
            color_format_black = workbook.add_format(
                {'bold': True, 'align': 'center', 'valign': 'vcenter', 'border': 1, 'bg_color': '#808080'})
            color_format_black.set_font_color('#000000')
            color_format_white = workbook.add_format(
                {'bold': True, 'align': 'center', 'valign': 'vcenter', 'border': 1, 'bg_color': '#e9ecef'})
            color_format_white.set_font_color('#000000')
            # Header
            # BODY
            worksheet.write_string('A1', self.env.company.vat, color_format_white)
            worksheet.write_string('A2', period, color_format_white)
            worksheet.write_string('B1', "NIF do Contribuinte", color_format_black)
            worksheet.set_column('B1:B1', 25)  # Column Widths
            worksheet.write_string('B2', "Período (AAAA-MM)", color_format_black)
            worksheet.set_column('B2:B2', 25)  # Column Widths

            worksheet.write_string('A4', "NIF Trabalhador", color_format_black)
            worksheet.set_column('A4:A4', 15)  # Column Widths
            worksheet.write_string('B4', "Nome", color_format_black)
            worksheet.write_string('C4', "Nº Segurança Social", color_format_black)
            worksheet.set_column('C4:C4', 15)  # Column Widths
            worksheet.write_string('D4', "Província", color_format_black)
            worksheet.set_column('D4:D4', 10)  # Column Widths
            worksheet.write_string('E4', "Município", color_format_black)
            worksheet.set_column('E4:E4', 10)  # Column Widths
            worksheet.write_string('F4', "Salário Base", color_format_black)
            worksheet.set_column('F4:F4', 10)  # Column Widths
            worksheet.write_string('G4', "Descontos por Falta", color_format_black)
            worksheet.set_column('G4:G4', 15)  # Column Widths
            worksheet.set_column('C3:L3', 35)  # Column Widths
            worksheet.set_column('O3:X3', 35)  # Column Widths
            worksheet.write_string('H4', "Subsídio Alimentação", color_format_silver)
            worksheet.write_string('I4', "Subsídio Transporte", color_format_silver)
            worksheet.write_string('J4', "Abono Família", color_format_silver)
            worksheet.write_string('K4', "Reembolso de Despesas", color_format_silver)
            worksheet.write_string('L4', "Outros", color_format_silver)
            worksheet.write_string('O4', "Abono de Falhas", color_format_silver)
            worksheet.write_string('P4', "Subsídio Renda de Casa", color_format_silver)
            worksheet.write_string('Q4', "Compensação Por Rescisão", color_format_silver)
            worksheet.write_string('R4', "Subsídio de Férias", color_format_silver)
            worksheet.write_string('S4', "Horas Extras", color_format_silver)
            worksheet.write_string('T4', "Subsídio de Atavio", color_format_silver)
            worksheet.write_string('U4', "Subsídio de Representação", color_format_silver)
            worksheet.write_string('V4', "Prémios", color_format_silver)
            worksheet.write_string('W4', "Subsídio de Natal", color_format_silver)
            #worksheet.write_string('X4', "Subsídio de Chefia", color_format_silver)
            worksheet.write_string('X4', "Outros Subsídios Sujeitos", color_format_silver)
            # worksheet.set_column('X4:X4', 30)
            # HEADER: MERGE COLUMN
            worksheet.merge_range('M3:M4', "", cell_format)
            worksheet.write_string('M3', 'Cálculo Manual de Excesso de Subsídios?', cell_format)
            worksheet.set_column('M3:M3', 40)  # Column Widths
            worksheet.merge_range('N3:N4', "", cell_format)
            worksheet.write_string('N3', 'Excesso Subsídios Não Sujeitos', cell_format)
            worksheet.set_column('N3:N3', 30)
            worksheet.merge_range('H3:L3', "", cell_format)
            worksheet.write_string('H3', 'Subsídios Não Sujeitos a IRT (Art. 2º do CIRT)', cell_format)
            worksheet.merge_range('O3:X3', "", cell_format)
            worksheet.write_string('O3', 'Subsídios Sujeitos a IRT ', cell_format)
            worksheet.merge_range('Y3:Y4', "", cell_format)
            worksheet.write_string('Y3', 'Salário Ilíquido', cell_format)
            worksheet.set_column('Y3:Y3', 43)  # Column Widths
            worksheet.merge_range('Z3:Z4', "", cell_format)
            worksheet.write_string('Z3', 'Cálculo Manual da Base Trib. Seg. Social?', cell_format)
            worksheet.set_column('Z3:Z3', 45)  # Column Widths
            worksheet.merge_range('AA3:AA4', "", cell_format)
            worksheet.write_string('AA3', 'Base Tributável Segurança Social', cell_format)
            worksheet.set_column('AA3:AA3', 35)  # Column Widths
            worksheet.merge_range('AB3:AB4', "", cell_format)
            worksheet.write_string('AB3', 'Não Sujeito a Segurança Social?', cell_format)
            worksheet.set_column('AB3:AB3', 35)  # Column Widths
            worksheet.merge_range('AC3:AC4', "", cell_format)
            worksheet.write_string('AC3', 'Contribuição Segurança Social', cell_format)
            worksheet.set_column('AC3:AC3', 35)  # Column Widths
            worksheet.merge_range('AD3:AD4', "", cell_format)
            worksheet.write_string('AD3', 'Base Tributável IRT', cell_format)
            worksheet.set_column('AD3:AD3', 25)  # Column Widths
            worksheet.merge_range('AE3:AE4', "", cell_format)
            worksheet.write_string('AE3', 'Isento IRT?', cell_format)
            worksheet.set_column('AE3:AE3', 15)  # Column Widths
            worksheet.merge_range('AF3:AF4', "", cell_format)
            worksheet.write_string('AF3', 'IRT Apurado', cell_format)
            worksheet.set_column('AF3:AF3', 15)  # Column Widths

            # Payslip Values
            xlsx_values = get_xlsx_dict_values(docs)
            index = 5 + len(xlsx_values)
            # Payslip Values
            for dic_value in xlsx_values:
                for key, value in dic_value.items():
                    # extract numbers from string
                    from_key = ''.join(map(str, [int(s) for s in [*key] if s.isdigit()]))
                    if 'M' in key:
                        worksheet.data_validation(key, {'validate': 'list', 'source': ['S', 'N']})
                        worksheet.write(key, 'S') if value == 'S' else worksheet.write(key, 'N')
                    elif 'Z' in key:
                        worksheet.data_validation(key, {'validate': 'list', 'source': ['S', 'N']})
                        worksheet.write(key, 'S') if value == 'S' else worksheet.write(key, 'N')
                    elif 'AB' in key:
                        worksheet.data_validation(key, {'validate': 'list', 'source': ['S', 'N']})
                        worksheet.write(key, 'S') if value == 'S' else worksheet.write(key, 'N')
                    elif 'AE' in key:
                        worksheet.data_validation(key, {'validate': 'list', 'source': ['S', 'N']})
                        worksheet.write(key, 'S') if value == 'S' else worksheet.write(key, 'N')
                    else:
                        worksheet.write(key, value)

            workbook.close()
            return new_dir_path

        def create_xml_file(remuneration_map_dict):
            remuneration_map_xml = dicttoxml(remuneration_map_dict, root=False, attr_type=False)
            dom = parseString(remuneration_map_xml)
            data = dom.toprettyxml().replace('<?xml version="1.0" ?>', '<?xml version="1.0" encoding="UTF-8" ?>')

            return data

        def create_temp_xml_file(xml_data):
            temp_file = tempfile.NamedTemporaryFile(mode='w+b', delete=False, suffix=".xml")
            dir_path = temp_file.name
            file = temp_file.name.split('/')
            file[-1] = f"REMUNERATION_MAP_PERIOD_{period}.xml"
            new_dir_path = '/'.join(map(str, file))
            os.rename(dir_path, new_dir_path)
            temp_file.write(xml_data.encode("utf-8"))
            temp_file.seek(0)
            file = base64.b64encode(open(new_dir_path).read().encode("utf-8"))
            return new_dir_path

        base_url = self.env['ir.config_parameter'].get_param('web.base.url')
        period = '%d-%s' % (period_start_date.year, months[period_end_date.month])
        if report_file == 'xml':
            remuneration_map_dict = create_remuneration_dict(period, docs)
            xml_data = create_xml_file(remuneration_map_dict)
            dir_path_file = create_temp_xml_file(xml_data)
        elif report_file == 'xlsx':
            dir_path_file = create_temp_xlsx_file(period, docs)
        else:
            return {}

        file_result = base64.b64encode(open(f'{dir_path_file}', 'rb').read())
        url_file = f'{base_url}/file/map/download?dir_path_file={dir_path_file}'
        return url_file
