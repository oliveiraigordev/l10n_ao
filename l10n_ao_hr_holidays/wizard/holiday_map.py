import os
import base64
import tempfile
import xlsxwriter

from datetime import date
from string import ascii_uppercase

from odoo import models, fields
from odoo.exceptions import UserError

MONTHS = [
    "Jan",
    "Fev",
    "Mar",
    "Abr",
    "Mai",
    "Jun",
    "Jul",
    "Ago",
    "Set",
    "Out",
    "Nov",
    "Dez",
]


class HolidayMap(models.TransientModel):
    _name = "wizard.holiday.map"
    _description = "Mapa de Férias"

    year = fields.Integer(
        string="Ano", required=True, default=lambda self: fields.Date.today().year
    )
    file_out = fields.Binary(string="Arquivo")
    filename_out = fields.Char(string="Nome do Arquivo")
    direction_id = fields.Many2one('hr.direction', string='Direcção', help="Direcção")

    def create_report(self):

        start_date = date(self.year, 1, 1)
        end_date = date(self.year, 12, 31)

        leave_type_id = self.env.ref(
            "l10n_ao_hr_holidays.l10n_ao_hr_leave_type_vocation"
        )
        leave_ids = self.env["hr.leave"].search(
            [
                ("date_from", ">=", start_date),
                ("date_from", "<=", end_date),
                ("state", "not in", ("draft", "refuse")),
                ("holiday_status_id", "=", leave_type_id.id),
            ]
        )

        if self.direction_id:
            leave_ids = leave_ids.filtered(lambda r: r.employee_ids.direction_id == self.direction_id)

        if not leave_ids:
            raise UserError(
                "Não foram encontradas registos de férias para o período selecionado!"
            )

        temp_file = tempfile.NamedTemporaryFile(mode="w+b", delete=False, suffix=".xls")
        dir_path = temp_file.name

        workbook = xlsxwriter.Workbook(dir_path)
        worksheet = workbook.add_worksheet()

        worksheet.set_column("A:F", 20)
        # Styles
        title_background = workbook.add_format(
            {
                "bold": True,
                "border": 1,
                "align": "center",
                "valign": "vcenter",
                "bg_color": "#203764",
                "font_color": "#FFFFFF",
            }
        )
        bold_bordered_centered = workbook.add_format(
            {"bold": True, "border": 1, "align": "center", "valign": "vcenter"}
        )
        regular_bordered = workbook.add_format({"border": 1, "valign": "vcenter"})
        regular_bordered_background = workbook.add_format(
            {"border": 1, "align": "center", "valign": "vcenter", "bg_color": "#9BC2E6"}
        )
        # Title
        worksheet.merge_range(
            "A1:S1", f"MAPA DE FÉRIAS PARA {self.year}", title_background
        )
        worksheet.merge_range("A2:B2", "Nome do Funcionário", bold_bordered_centered)
        worksheet.write_string("C2", "Função", bold_bordered_centered)
        worksheet.write_string("D2", "Admissão", bold_bordered_centered)
        letter_start_index = 4
        for month in MONTHS:
            index = letter_start_index + MONTHS.index(month)
            worksheet.write_string(
                f"{ascii_uppercase[index]}2", month, bold_bordered_centered
            )
        worksheet.write_string(
            f"{ascii_uppercase[letter_start_index + len(MONTHS)]}2",
            "Férias Geral",
            bold_bordered_centered,
        )
        worksheet.write_string(
            f"{ascii_uppercase[letter_start_index + len(MONTHS) + 1]}2",
            "Dias Marcados",
            bold_bordered_centered,
        )
        worksheet.write_string(
            f"{ascii_uppercase[letter_start_index + len(MONTHS) + 2]}2",
            "Saldo",
            bold_bordered_centered,
        )

        line_number = 3
        for employee in sorted(
                leave_ids.mapped("employee_id"), key=lambda x: x["name"]
        ):
            if employee.active:
                # Saldo geral de férias do Colaborador
                vacation_balance_report = self.env['vacation.balance.report'].search(
                    [
                        ("employee_id", "=", employee.id),
                        ("vacation_year", "=",
                         self.year if employee.contract_type.code == 'EXPATRIADO' else self.year - 1)
                    ],
                    order="vacation_year desc",
                )

                worksheet.write_string(
                    f"A{line_number}", str(line_number - 2), regular_bordered
                )
                worksheet.write_string(f"B{line_number}", employee.name, regular_bordered)
                worksheet.write_string(
                    f"C{line_number}", employee.hr_job.name if employee.hr_job else employee.job_id.name or "",
                    regular_bordered
                )
                worksheet.write_string(
                    f"D{line_number}",
                    (
                        employee.admission_date.strftime("%Y-%m-%d")
                        if employee.admission_date
                        else ""
                    ),
                    regular_bordered,
                )
                employee_leaves = leave_ids.filtered(lambda x: x.employee_id == employee)

                # Writing empty values to all cell so we can apply the bordered style
                for month in MONTHS:
                    index = letter_start_index + MONTHS.index(month)
                    worksheet.write_string(
                        f"{ascii_uppercase[index]}{line_number}", "", bold_bordered_centered
                    )

                for leave in employee_leaves:
                    start_month_index = leave.date_from.month - 1
                    end_month_index = leave.date_to.month - 1 if \
                        leave.date_to.year == leave.date_from.year else leave.date_from.month - 1  # QUANDO O ANO DA DATA DO FIM É NO SEGUINTE PEGAR O PÊS DA DATA DE FIM DO ANO PASSADO
                    if start_month_index == end_month_index:
                        index = letter_start_index + start_month_index
                        start_day = str(leave.date_from.day).zfill(2)
                        start_month = str(leave.date_from.month).zfill(2)
                        end_day = str(leave.date_to.day).zfill(2)
                        end_month = str(leave.date_to.month).zfill(2)
                        worksheet.write_string(
                            f"{ascii_uppercase[index]}{line_number}",
                            f"{start_day}/{start_month} a {end_day}/{end_month}",
                            regular_bordered_background,
                        )
                    else:
                        start_index = letter_start_index + start_month_index
                        end_index = letter_start_index + end_month_index
                        start_day = str(leave.date_from.day).zfill(2)
                        start_month = str(leave.date_from.month).zfill(2)
                        end_day = str(leave.date_to.day).zfill(2)
                        end_month = str(leave.date_to.month).zfill(2)
                        worksheet.merge_range(
                            f"{ascii_uppercase[start_index]}{line_number}:{ascii_uppercase[end_index]}{line_number}",
                            f"{start_day}/{start_month} a {end_day}/{end_month}",
                            regular_bordered_background,
                        )

                number_of_days_display = sum(employee_leaves.mapped("number_of_days_display"))
                if number_of_days_display > vacation_balance_report.vacation_days:
                    number_of_days_display = vacation_balance_report.vacation_days

                balance_days = vacation_balance_report.vacation_days - number_of_days_display
                worksheet.write_string(
                    f"{ascii_uppercase[letter_start_index + len(MONTHS)]}{line_number}",
                    str(vacation_balance_report.vacation_days or 0),
                    regular_bordered,
                )
                worksheet.write_string(
                    f"{ascii_uppercase[letter_start_index + len(MONTHS) + 1]}{line_number}",
                    str(int(number_of_days_display) or 0),
                    regular_bordered,
                )
                worksheet.write_string(
                    f"{ascii_uppercase[letter_start_index + len(MONTHS) + 2]}{line_number}",
                    str(balance_days or 0),
                    regular_bordered,
                )
                line_number += 1

        workbook.close()
        file_result = base64.b64encode(open(f"{dir_path}", "rb").read())
        self.file_out = file_result
        self.filename_out = f"Mapa_de_ferias_{self.year}.xls"
        return {
            "name": "Mapa de Férias",
            "type": "ir.actions.act_window",
            "view_type": "form",
            "view_mode": "form",
            "res_model": "wizard.holiday.map",
            "res_id": self.id,
            "target": "new"
        }
