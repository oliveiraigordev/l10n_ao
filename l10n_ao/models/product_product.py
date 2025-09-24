from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from .saft_ao_file import saft_clean_void_values


class ProductProductAng(models.Model):

    _inherit="product.product"

    def get_saft_data(self):
        type = ""
        result = {'Product': []}
        for product in self:
            if product.type in ["consu","product"]:
                type = "P"
            elif product.type == "service":
                type = "S"
            product_val = {
                'ProductType': type,
                'ProductCode': product.id,
                'ProductGroup': product.categ_id.name[0:49],
                'ProductDescription': product.name[0:199],
                'ProductNumberCode': product.default_code[0:59] if product.default_code else "Desconhecido",
            }
            # if product.unnumber:
            #     product_val['UNNumber'] = product.unnumber
            # if product.customs_details:
            #     product_val['CustomsDetails'] = product.customs_details
            product_val = saft_clean_void_values("", product_val)
            result['Product'].append(product_val)
        return result

    get_account_from_sub_accounts = fields.Boolean(
        string="Lançamentos via Sub-conta contabilistica",
        help="Habilitando esse campo, o sistema atribuirá a sub-conta que pertence ao mesmo grupo da conta, baseando-se no imposto configurado nela.",
        related="product_tmpl_id.get_account_from_sub_accounts"
    )

    # @api.depends("name","description")
    # def _validate_name_and_description(self, vals):
    #     if not self.env["ir.config_parameter"].sudo().get_param('dont_validate_product'):
    #         invoices = self.env['account.move'].search([('state','in',['posted'])])
    #         if (vals.get('name') or vals.get('description')) and invoices.invoice_line_ids.filtered(lambda r:r.product_id.id == self.id):
    #            raise ValidationError("Já existem facturas aprovadas cujo o produto está associado, pelo que não poderá alterar o nome nem a descrição do mesmo.")
    #     return super(ProductProductAng, self).write(vals)

class ProductTemplateAng(models.Model):

    _inherit="product.template"

    detailed_type = fields.Selection(selection_add=[('imobi','Imobilizado')],  tracking=True, ondelete={'imobi': 'set consu'})
    type = fields.Selection(selection_add=[
        ('imobi', 'Imobilizado')
    ], ondelete={'imobi': 'set consu'})

    operation_type = fields.Selection(string="Tipo de Operação",
                                selection=[('MFI', 'Meios Fixos e Investimentos'),
                                           ('INV', 'Existências/Inventários'),                                          
                                           ('OBC', 'Outros Bens de Consumo'),
                                           ('SERV', 'Serviços'),
                                           ('IMPT', 'Imposto dedutível nas importações de bens'),
                                           ('SCE', 'Serviços Contratados no Estrangeiro'),])
    
    tipology = fields.Char('Tipologia', compute='_compute_tipology', store=True)


    periodic_dec_dest_field = fields.Char('Campo de Destino na Declaração Periódica', compute='_compute_periodic_dest', store=True)
        
    
    @api.depends('operation_type')
    def _compute_periodic_dest(self):
        dest_dict = {
            'MFI'  : '16',
            'INV'  : '18',
            'OBC'  : '20',
            'SERV' : '22', 
            'IMPT' : '',
            'SCE'  : '',

        }
       
        for rec in self:
            if rec.operation_type:
                rec.periodic_dec_dest_field = dest_dict[rec.operation_type]
            

    @api.depends('operation_type')
    def _compute_tipology(self):
        for rec in self:
            if rec.operation_type:
             rec.tipology = rec.operation_type


    #TODO: FAZER  A VERIFICAÇÃO PARA QUE QUANDO O MUDAR-MOS O TIPO DE PRODUTO PARA imobi possa permitir verificar na fixa do producto se ele é IN/OUT e quality of point

    def _compute_product_tooltip(self):
        super()._compute_product_tooltip()
        for record in self:
            if record.type == 'imobi':
                record.product_tooltip += _(
                    "Imobilizados são produtos físicos que não são geridos no inventário: consideram-se sempre disponíveis."
                )

    @api.model_create_multi
    def create(self,vals_list):
        for val in vals_list:
            if val.get('list_price') and val.get('list_price') < 0:
                raise ValidationError("O Valor do Preço do producto deve ser sempre Maior que Zero")
        return super(ProductTemplateAng, self).create(vals_list)

    def write(self, vals):
        for product in self:
            if not self.env["ir.config_parameter"].sudo().get_param('dont_validate_product') and self.env.company.country_id.code == "AO":
                invoices = self.env['account.move'].search([('state', 'in', ['posted'])])
                if vals.get('list_price') and vals.get('list_price') < 0:
                    raise ValidationError("O Valor do Preço do producto deve ser sempre Maior que Zero")
                if not product.taxes_id and not vals.get("taxes_id"):
                    raise ValidationError("Na configuração do produto deve existir pelo menos um imposto do tipo IVA, caso o producto seja isento deve adicionar o IVA de isenção.")
                if (vals.get('name') or vals.get('description')) and invoices.invoice_line_ids.filtered(lambda r:r.product_id.id == self.id):
                   raise ValidationError("Já existem facturas aprovadas cujo o produto está associado, pelo que não poderá alterar o nome nem a descrição do mesmo.")
                if vals.get("list_price") and vals.get("list_price") < 0:
                    raise ValidationError(
                        "O preço unitário do produto não pode ser menor que Zero.")
            return super(ProductTemplateAng, self).write(vals)

    get_account_from_sub_accounts = fields.Boolean(
        string="Lançamentos via Sub-conta contabilistica",
        help="Habilitando esse campo, o sistema atribuirá a sub-conta que pertence ao mesmo grupo da conta, baseando-se no imposto configurado nela.",
        default=True
    )