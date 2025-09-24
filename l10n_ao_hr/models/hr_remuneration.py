from odoo import models, fields, api
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
import calendar


class HRRemunerationCode(models.Model):
    _name = 'hr.extra.remuneration.code'
    _description = 'Remuneration Code'
    _order = 'name'

    name = fields.Char('Nome', required=True, help='Insert here a name for the remuneration')
    code = fields.Char('Código', required=True,
                       help='Insert here a code (3 or 4 chars) for the remuneration. This code should not have white spaces.')
    type = fields.Selection([('remuneration', 'Remuneração'), ('deduction', 'Dedução')], 'Tipo', required=True)
    remuneration_ids = fields.One2many('hr.extra.remuneration', 'remuneration_code_id',
                                       string='Remunerações no presente código')
    company_id = fields.Many2one('res.company', string='Empresa', required=True,
                                 default=lambda self: self.env.user.company_id)

    def unlink(self):
        for record in self:
            if self.env.company.country_id.code == "AO":
                return {}

            return super(HRRemunerationCode, record).unlink()


class HRRemuneration(models.Model):
    _name = 'hr.extra.remuneration'
    _description = 'Remunerations'
    _order = 'rem_type'

    name = fields.Char('Descrição')
    date_start = fields.Date('Data de Início', required=True, default=datetime.strftime(datetime.now(), '%Y-%m-01'))
    date_end = fields.Date('Data de Fim')
    amount = fields.Float('Valor', digits=(10, 2), required='True', help='Insert here the amount for the remuneration')
    # is_daily = fields.Boolean('Is Daily', help='Check this box if the value is daily')
    remuneration_code_id = fields.Many2one('hr.extra.remuneration.code', string='Código da Remuneração', required=True,
                                           help='Select the remuneration code for the remuneration')
    contract_id = fields.Many2one('hr.contract', string='Contracto', required='True',
                                  help='Select the Contract remuneration', ondelete='cascade')
    rem_type = fields.Selection([('remuneration', 'Remuneração'), ('deduction', 'Dedução')], 'Tipo')
    period = fields.Selection(
        [('quarterly', 'Trimestral'), ('semi-annually', 'Semestral'), ('annually', 'Anual')], 'Período')
    period_next_date = fields.Date('Próxima Data')

    @api.onchange('remuneration_code_id')
    def onchange_remuneration_code_id(self):
        if self.remuneration_code_id:
            self.rem_type = self.remuneration_code_id.type
            self.name = self.remuneration_code_id.name

    @api.onchange('date_start')
    def _onchange_date_start(self):
        if self.date_start and self.period:
            next_date = self.get_self_renewable_date(self.date_start)
            self.period_next_date = next_date

    @api.onchange('period')
    def onchange_is_periodic(self):
        if self.period:
            next_date = self.get_self_renewable_date(self.date_start)
            self.period_next_date = next_date

    def get_self_renewable_date(self, date_start):
        if self.period == 'quarterly':
            date_end = date_start + relativedelta(months=3)
        elif self.period == 'semi-annually':
            date_end = date_start + relativedelta(months=6)
        elif self.period == 'annually':
            date_end = date_start + relativedelta(months=12)
        day_end = calendar.monthrange(date_end.year, date_end.month)[1]
        date_end = date(date_end.year, date_end.month, day_end)
        return date_end

    @api.model
    def create(self, values):
        remuneration_code_id = values['remuneration_code_id']
        remuneration_code = self.env['hr.extra.remuneration.code'].browse([remuneration_code_id])
        values['amount'] = abs(values['amount'])
        values['rem_type'] = remuneration_code.type
        return super(HRRemuneration, self).create(values)

    # @api.multi
    def write(self, values):
        if 'remuneration_code_id' in values:
            remuneration_code_id = values['remuneration_code_id']
            remuneration_code = self.env['hr.extra.remuneration.code'].browse([remuneration_code_id])
            values['rem_type'] = remuneration_code.type
        if 'amount' in values:
            values['amount'] = abs(values['amount'])
        return super(HRRemuneration, self).write(values)
