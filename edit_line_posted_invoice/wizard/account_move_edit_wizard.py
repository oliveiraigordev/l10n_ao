from odoo import models, fields
from odoo.exceptions import UserError


class AccountMoveEditAccountWizard(models.TransientModel):
    _name = 'account.move.edit.account.wizard'
    _description = 'Alterar lançamentos na fatura'

    move_id = fields.Many2one('account.move', string="Fatura", required=True, readonly=True)
    line_id = fields.Many2one(
        'account.move.line',
        string="Linha",
        required=True,
        domain="[('move_id', '=', move_id), ('display_type', '=', 'product')]"
    )
    new_account_id = fields.Many2one('account.account', string="Nova Conta")
    new_tax_ids = fields.Many2many('account.tax', string="Novos Impostos")


    def unhash_move(self):
        self.ensure_one()  

        if self.move_id.state == 'posted' and self.move_id.restrict_mode_hash_table:
            self.move_id.restrict_mode_hash_table = False  
            self.move_id.button_draft()  
        return 
    
    def action_confirm(self):
        if not self.env.user.has_group('account.group_account_manager'):
            raise UserError("Apenas gestores contábeis podem alterar a conta contábil.")

        self.unhash_move()

        # Atualiza a conta, se fornecida
        if self.new_account_id:
            query = """
                UPDATE account_move_line 
                SET account_id = %s 
                WHERE id = %s
            """
            self.env.cr.execute(query, (self.new_account_id.id, self.line_id.id))

        # Atualiza os impostos, se fornecidos
        if self.new_tax_ids:
            self.env.cr.execute("""
                DELETE FROM account_move_line_account_tax_rel 
                WHERE account_move_line_id = %s
            """, (self.line_id.id,))

            self.env.cr.executemany("""
                INSERT INTO account_move_line_account_tax_rel (account_move_line_id, account_tax_id) 
                VALUES (%s, %s)
            """, [(self.line_id.id, tax.id) for tax in self.new_tax_ids])

        self.move_id.sudo().action_post()
        return {'type': 'ir.actions.act_window_close'}


