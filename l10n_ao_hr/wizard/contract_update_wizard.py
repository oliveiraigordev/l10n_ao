# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class HRContractUpdateWizard(models.TransientModel):
    _name = 'wizard.contract.update'

    contract_id = fields.Many2one('hr.contract', string='Contrato',
                                  required=True)
    contract_type = fields.Selection(
        [('determinado', ' Determinado'), ('indeterminado', 'Indeterminada'),
         ('independente', 'Independente'), ('autonomo', 'Autonomo'), ('estagio', 'Estágio'),
         ('especial', 'Contrato de Trabalho Especial')], string='Tipo de Contrato', default='indeterminado')
    department_id = fields.Many2one('hr.department', string='Departamento')
    job_id = fields.Many2one('hr.job', string='Posição de Cargo')
    date_from = fields.Date(string='Data de Início do Novo Contracto')
    date_to = fields.Date(string='Data de Término do Contracto Actual')
    wage = fields.Float(string='Salário ')

    def update_contract(self):
        """Retorna um dicionário com os valores de todos os campos para criar uma nova instância."""
        self.ensure_one()
        try:
            # Lista de campos a serem excluídos
            exclude_fields = ['id', 'create_uid', 'create_date', 'write_uid', 'write_date', '__last_update']
            # Obtém todos os nomes dos campos, excluindo os desnecessários
            field_names = [field for field in self.env['hr.contract'].fields_get_keys() if field not in exclude_fields]
            # Lê os valores dos campos
            values = self.contract_id.read(field_names)[0]
            # Remove os campos desnecessários
            values.pop('id', None)
            values.pop('message_ids', None)
            values.pop('message_follower_ids', None)
            values.pop('message_partner_ids', None)

            # Converte campos Many2one e outros campos relacionados para IDs inteiros
            for key, value in values.items():
                if isinstance(value, tuple):
                    values[key] = value[0]

            # Criar novo contracto
            values['name'] = f'{self.contract_id.name} Actualizado'
            values['contract_type'] = self.contract_type
            values['department_id'] = self.department_id.id
            values['job_id'] = self.job_id.id
            values['date_start'] = self.date_from
            values['wage'] = self.wage

            # Atualizar contrato antigo
            self.contract_id.write({'state': 'close', 'date_end': self.date_to})
            # Criar o novo contracto actualizado
            contract = self.env['hr.contract'].sudo().create(values)

            return {
                'type': 'ir.actions.act_window',
                'name': f'Contracto {contract.name} Actualizado',
                'view_mode': 'tree',
                'res_model': "hr.contract",
                "domain": f"[('id', 'in', {contract.ids})]",
                'target': 'current',
            }
        except Exception as e:
            raise UserError(_(f'Não foi possível atualizar o contrato. Erro: {e}'))
