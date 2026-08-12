# -*- coding: utf-8 -*-
"""Page mobile : le QR de l'étiquette pointe ici.

Sécurité — pourquoi ``auth='user'``
-----------------------------------
Cette page expose des niveaux de stock. En accès libre, toute étiquette sortie de
l'entrepôt (sur un colis, chez un client, dans un salon) deviendrait une fenêtre ouverte
sur le stock de l'entreprise.

Exiger une session coûte une seule connexion par téléphone : le cookie persiste ensuite.
En pratique la gêne est nulle, et la fuite est fermée.

Si un accès sans compte devenait indispensable, il faudrait une adresse signée (clé HMAC
dérivée de ``database.secret``) avec péremption — et non un simple passage en
``auth='public'``.
"""

from odoo import http
from odoo.http import request


class WmsPalletController(http.Controller):

    @http.route(
        ['/wms/pallet/<string:code>'],
        type='http', auth='user', methods=['GET'], website=False,
    )
    def wms_pallet_page(self, code, **kwargs):
        """Rend la fiche palette : contenu réel et historique, lus à l'instant du scan."""
        payload = request.env['stock.quant.package'].wms_scan(code)
        return request.render('wms_custom.wms_pallet_page', {
            'payload': payload,
            'code': code,
        })

    @http.route(
        ['/wms/pallet/data/<string:code>'],
        type='json', auth='user', methods=['POST'],
    )
    def wms_pallet_data(self, code, **kwargs):
        """Même charge utile en JSON, pour le rafraîchissement périodique de la page."""
        return request.env['stock.quant.package'].wms_scan(code)
