from odoo import http
from odoo.http import request
import requests

class NIFController(http.Controller):

    def serach_db_nif(self, term=""):
        results = []
        
        if term:
            partners = request.env['res.partner'].sudo().search(
                [('vat', 'ilike', term)], limit=10
            )
            results = [
                {"id": p.id, "vat": p.vat, "name": p.name, "new": False, "address": p.contact_address_complete, "phone": p.phone, "email": p.email}
                for p in partners if p.vat
            ]
        return results

    @http.route('/nif/autocomplete', type='json', auth='user')
    def nif_autocomplete(self, term="", **kwargs):
        results = []
        if term:
            _local_results = self.serach_db_nif(term)
            if(len(_local_results)) > 0:
                return _local_results
            
             # consulta API externa
            base_url = request.env["ir.config_parameter"].sudo().get_param("nif.search.url")
            if base_url:
                full_url = f"{base_url}{term}"
                try:
                    response = requests.get(full_url, timeout=10)
                    if response.status_code == 200:
                        data = response.json()

                        if data.get("success") and data.get("data"):
                            payload = data["data"]

                            # se a API devolve apenas um objeto
                            if isinstance(payload, dict) and "nif" in payload:
                                results.append({
                                    "id": payload.get("nif"),
                                    "vat": payload.get("nif"),
                                    "name": payload.get("gsmc") or payload.get("companyName"),
                                    "address": payload.get("nsrdz") or payload.get("addressDbb"),
                                    "phone": payload.get("lxfs"),
                                    "mobile": payload.get("lxfs"),
                                    "email": payload.get("email"),
                                    "new": True,
                                })
                except Exception as e:
                    print("Erro na chamada à API NIF:", e)
            else:
                print("Parâmetro nif.search.url não encontrado.")

        return results