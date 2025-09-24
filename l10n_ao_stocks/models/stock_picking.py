from odoo import fields, models, api
from odoo.addons.l10n_ao.sign import sign


class SAFTStockPicking(models.Model):
    _inherit = 'stock.picking'

    name_stock_piking = fields.Char("Name Picking", readline=True)
    sequence_number = fields.Integer("Sequence Number", copy=False, readonly=True)
    hash = fields.Char(string="Hash", copy=False, readonly=True)
    hash_control = fields.Char(string="Hash Control", default="0", copy=False)
    hash_to_sign = fields.Char(string="Hash to sign", copy=False)
    saft_status_date = fields.Datetime("SAFT Status Date", copy=False)
    system_entry_date = fields.Datetime("Signature Datetime", copy=False)
    type = fields.Selection([
        ('transfer', 'Transferência'),
        ('delivery', 'Entrega'),
        ('receiver', 'Recebimento'),
        ('return', 'Devoluções'),
    ], string="Tipo de Operação", compute='_compute_operation_type', store=True)



    # source_billing = fields.Selection(string="Source Billing", size=1,
    #                                   selection=[('P', 'Documento produzido na aplicação'),
    #                                              ('I', 'Documento integradi e produzido noutra aplicação'),
    #                                              ('M', 'Documento proveniente de recuperação ou emissão manual')])

    movement_type = fields.Selection(string="Movement Type", size=2,
                                     selection=[('GR', 'Guia de remessa'),
                                                ('GT', 'Guia de transporte(Incluir aqui as guias globais).'),
                                                ('GA', 'Guia de movimentação de activos fixos próprios'),
                                                ('GC', 'Guia de consignação'),
                                                ('GD', 'Guia ou nota de devolução.')],
                                     help="Tipo de documento")

    #PARA DIFERENCIAR O TIPO DE OPERAÇÃO NO RELATORIO

    @api.depends('picking_type_id')
    def _compute_operation_type(self):
        for rec in self:
            name = (rec.picking_type_id.name or '').strip().lower() if rec.picking_type_id else ''
            code = rec.picking_type_id.code if rec.picking_type_id else ''

            if 'devolução' in name or 'devoluções' in name:
                rec.type = 'return'
            elif code == 'internal':
                rec.type = 'transfer'
            elif code == 'outgoing':
                rec.type = 'delivery'
            elif code == 'incoming':
                rec.type = 'receiver'
            else:
                rec.type = False

    def get_new_content_to_sign(self):
        content_to_sign = ""
        if self.sequence_number - 1 >= 1:
            preview_stock_picking = self.sudo().search([('state', 'in', ['done']),
                                                        ('id', "!=", self.id),
                                                        ('company_id', '=', self.company_id.id),
                                                        ('date_done', '<=', self.date_done),
                                                        ('code', '=', 'outgoing'),
                                                        ('pycking_type_id', '=', self.pycking_type_id),
                                                        ('system_entry_date', '<=', self.system_entry_date),
                                                        ('sequence_number', '=', self.sequence_number - 1)],
                                                       order="system_entry_date desc", limit=1)
            if preview_stock_picking:
                get_last_order_hash = preview_stock_picking.hash if preview_stock_picking.hash else ""
                system_entry_date = self.system_entry_date.isoformat(sep='T',
                                                                     timespec='auto') if self.system_entry_date else fields.Datetime.now().isoformat(
                    sep='T', timespec='auto')
                content_to_sign = ";".join((fields.Date.to_string(self.date_done), system_entry_date,
                                            self.name_stock_piking,
                                            get_last_order_hash))
        elif self.sequence_number - 1 == 0:
            system_entry_date = self.system_entry_date.isoformat(sep='T',
                                                                 timespec='auto') if self.system_entry_date else fields.Datetime.now().isoformat(
                sep='T', timespec='auto')
            content_to_sign = ";".join((fields.Date.to_string(self.date_done), system_entry_date,
                                        self.name_stock_piking, ""))
        return content_to_sign

    def write(self,vals):
        for picking in self:
            if vals.get("state") == 'done':
                vals['name_stock_piking'] = picking.env['ir.sequence'].with_company(picking.company_id.id).next_by_code(
                    'stock.picking', picking.date)
                vals['sequence_number'] = vals['name_stock_piking'].split("/")[1]
                pickings = super().write(vals)
                vals['hash_to_sign'] = picking.get_new_content_to_sign()
                content_signed = picking.sign_document(vals['hash_to_sign']).split(";")
                if vals['hash_to_sign'] != content_signed:
                    vals['hash_control'] = 0  # content_signed[1] if len(content_signed) >= 1 else "0" TODO: QUANDO OBTER A VALIDAÇÃO DEVO DESCOMENTAR ISTO E PASSAR O HAS_CONTROL  A 1
                    vals['hash'] = content_signed[0]
            return super().write(vals)


    def sign_document(self, content_data):
        response = ''
        if content_data:
            response = sign.sign_content(content_data)
        if response:
            return response
        return content_data





class SAFTStockMove(models.Model):
    _inherit = 'stock.move'

    # source_billing = fields.Selection(string="Source Billing", size=1,
    #                                   selection=[('P', 'Documento produzido na aplicação'),
    #                                              ('I', 'Documento integradi e produzido noutra aplicação'),
    #                                              ('M', 'Documento proveniente de recuperação ou emissão manual')])

    movement_type = fields.Selection(string="Movement Type", size=2,
                                     selection=[('GR', 'Guia de remessa'),
                                                ('GT', 'Guia de transporte(Incluir aqui as guias globais).'),
                                                ('GA', 'Guia de movimentação de activos fixos próprios'),
                                                ('GC', 'Guia de consignação'),
                                                ('GD', 'Guia ou nota de devolução.')],
                                     help="Tipo de documento")

    def get_saft_data(self):

        result = {
            "MovementOfGoods": {

                "NumberOfMovementLines": "",
                "TotalQuantityIssued": "",
                "StockMovement": [],

            }
        }

        stock_movement = self.filtered(lambda r: r.state in ['done', 'draft', 'cancel'])
        for st_movement in stock_movement:
            status_code = 'N'
            if st_movement.state == 'cancel':
                status_code = 'A'
            sale_order = st_movement.sale_line_id.mapped("order_id")
            StockMovement = {

                "DocumentNumber": st_movement.id,

                "DocumentStatus": {

                    "MovementStatus": status_code,
                    "MovementStatusDate": fields.Datetime.to_string(st_movement.__last_update),
                    "Reason": "",
                    "SourceID": st_movement.write_uid.id,
                    "SourceBilling": st_movement.source_billing
                },

                "Hash": 0,
                "HashControl": "",
                "Period": "",
                "MovementDate": st_movement.create_date,
                "MovementType": st_movement.movement_type,
                "SystemEntryDate": st_movement.date,
                "TransactionID": "",
                "CustomerID": st_movement.partner_id.id,
                "SupplierID": st_movement.partner_id.id,
                "SourceID": st_movement.create_uid.id,
                "EACCode": "",
                "MovementComments": st_movement.origin,
                "ShipTo": [{

                    "DeliveryID": picking.partner_id.vat,
                    "DeliveryDate": picking.date_done,
                    "WarehouseID": picking.location_dest_id.name,
                    "LocationID": picking.location_id.name,
                    "Address": {
                        "BuildingNumber": "",
                        "StreetName": picking.partner_id.street,
                        "AddressDetail": picking.partner_id.contact_address,
                        "City": picking.partner_id.city,
                        "PostalCode": picking.partner_id.zip,
                        "Province": picking.partner_id.state_id.name,
                        "Country": picking.partner_id.country_id.code
                    }

                } for picking in st_movement.picking_id],
                "ShipFrom": [{

                    "DeliveryID": "",
                    "DeliveryDate": "",
                    "WarehouseID": "",
                    "LocationID": picking.location_id.name,
                    "Address": {
                        "BuildingNumber": "",
                        "StreetName": picking.partner_id.street,
                        "AddressDetail": picking.partner_id.contact_address,
                        "City": picking.partner_id.city,
                        "PostalCode": picking.partner_id.zip,
                        "Province": picking.partner_id.state_id.name,
                        "Country": picking.partner_id.country_id.code
                    }

                } for picking in st_movement.picking_id],
                "MovementEndTime": st_movement.picking_id.date_done,
                "MovementStartTime": st_movement.picking_id.date_done,
                "AGTDocCodeID": "",
                "Lines": [{
                    "LineNumber": "",
                    "OrderReferences": {

                        "OriginatingON": "",
                        "OrderDate": sale_order.date_order
                    },
                    "ProductCode": st_movement.product_id.id,
                    "ProductDescription": st_movement.product_id.description,
                    "Quantity": st_movement.product_qty,
                    "UnitOfMeasure": st_movement.product_id.uom_name,
                    "UnitPrice": st_movement.product_id.price,
                    "Description": st_movement.name,
                    "ProductSerialNumber": st_movement.product_id.default_code,
                    "DebitAmount": "",
                    "CreditAmount": "",
                    "Tax": {
                        "TaxType": sale_line.tax_id.saft_tax_type,
                        "TaxCountryRegion": "AO",
                        "TaxCode": sale_line.tax_id.saft_tax_code,
                        "TaxPercentage": "",

                    },
                    "TaxExemptionReason": "",
                    "TaxExemptionCode": "",
                    "SettlementAmount": sale_line.discount,
                    "CustomsInformation": {
                        "ARCNo": "",
                        "IECAmount": ""
                    },
                } for sale_line in st_movement.sale_line_id],
                "DocumentTotals": [{

                    "TaxPayable": sale.amount_tax,
                    "NetTotal": sale.amount_untaxed,
                    "GrossTotal": sale.amount_total,
                    "Currency": {

                        "CurrencyCode": sale.currency_id.name,
                        "CurrencyAmount": sale.amount_total,
                        "ExchangeRate": sale.currency_id.rate
                    }

                } for sale in sale_order]

            }

            result['MovementOfGoods']['StockMovement'].append(StockMovement)
        result['MovementOfGoods']['NumberOfMovementLines'] = len(StockMovement)

        return result
