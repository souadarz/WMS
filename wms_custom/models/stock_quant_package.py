# -*- coding: utf-8 -*-
"""Étiquette palette SSCC — identité imprimée, contenu et historique lus en base.

Principe de conception
----------------------
Une étiquette est du papier : elle est figée à la seconde où elle sort de l'imprimante.
Elle ne peut donc porter QUE des faits immuables :

    SSCC        l'identité de la charge          ne change jamais
    GTIN        quel produit                     la charge est unique, non réutilisée
    LOT         quel lot                         idem
    DLC         découle du lot                   idem
    Qté emballée  fait historique                vrai pour toujours

Le contenu courant et l'historique ne sont PAS imprimés : ils changent à chaque
prélèvement. Ils sont lus en base au moment du scan, le SSCC servant de clé.

Comme le SSCC est unique et jamais réutilisé (règle GS1), l'historique qui s'y rattache
est sans ambiguïté pour toute la vie de la charge.
"""

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools.barcode import get_barcode_check_digit

#: Longueur totale d'un SSCC : 1 chiffre d'extension + préfixe GS1 + série + 1 clé.
SSCC_LENGTH = 18


class StockQuantPackage(models.Model):
    _inherit = 'stock.quant.package'

    # ------------------------------------------------------------------
    # Champs
    # ------------------------------------------------------------------
    # Instantané figé au moment où l'étiquette est éditée. C'est un fait historique :
    # il ne doit JAMAIS être recalculé, sinon l'étiquette papier et la base divergent.
    wms_packed_quantity = fields.Float(
        string="Quantité à l'emballage",
        digits='Product Unit of Measure',
        readonly=True, copy=False,
        help="Quantité contenue au moment où le SSCC a été attribué.\n"
             "C'est la valeur imprimée sur l'étiquette. Elle ne bouge plus : les "
             "prélèvements ultérieurs se lisent dans l'historique, pas ici.",
    )
    wms_packed_date = fields.Datetime(
        string="Date d'emballage", readonly=True, copy=False,
        help="Horodatage de l'attribution du SSCC.",
    )

    wms_current_quantity = fields.Float(
        string="Quantité actuelle", compute='_compute_wms_content_info',
        digits='Product Unit of Measure',
        help="Quantité réellement présente, à l'instant présent.",
    )
    wms_line_count = fields.Integer(
        string="Nombre de lignes", compute='_compute_wms_content_info',
    )
    wms_is_homogeneous = fields.Boolean(
        string="Charge homogène", compute='_compute_wms_content_info',
        help="Vrai si la charge ne contient qu'un seul produit et un seul lot. "
             "Seule une charge homogène peut porter son GTIN, son lot et sa DLC sur "
             "l'étiquette.",
    )

    # ------------------------------------------------------------------
    # Calculs
    # ------------------------------------------------------------------
    @api.depends('quant_ids.quantity', 'quant_ids.product_id', 'quant_ids.lot_id')
    def _compute_wms_content_info(self):
        for package in self:
            quants = package.quant_ids
            package.wms_current_quantity = sum(quants.mapped('quantity'))
            package.wms_line_count = len(quants)
            # Une charge vide n'est pas homogène : il n'y a rien à décrire.
            package.wms_is_homogeneous = bool(quants) and \
                len(quants.product_id) == 1 and len(quants.lot_id) <= 1

    # ------------------------------------------------------------------
    # Génération du SSCC
    # ------------------------------------------------------------------
    def _wms_next_sscc(self):
        """Construit le prochain SSCC pour cette charge.

        Structure (18 chiffres) ::

            [extension:1][prefixe GS1:6-10][serie:variable][cle:1]

        La série est dimensionnée pour que le total fasse exactement 18.
        """
        self.ensure_one()
        company = self.company_id or self.env.company
        prefix = (company.gs1_company_prefix or '').strip()

        if not prefix.isdigit():
            raise UserError(_(
                "Aucun préfixe entreprise GS1 n'est configuré pour la société « %s ».\n\n"
                "Un SSCC sans préfixe GS1 ne serait pas unique au niveau mondial : deux "
                "entreprises pourraient émettre le même numéro.\n\n"
                "Renseignez-le dans Inventaire ▸ Configuration ▸ Paramètres, section "
                "« Étiquettes palette ».",
                company.display_name,
            ))
        if not 6 <= len(prefix) <= 10:
            raise UserError(_(
                "Le préfixe entreprise GS1 doit compter entre 6 et 10 chiffres "
                "(actuellement %(count)s : « %(prefix)s »).",
                count=len(prefix), prefix=prefix,
            ))

        extension = (company.sscc_extension_digit or '0').strip()
        if not (len(extension) == 1 and extension.isdigit()):
            raise UserError(_(
                "Le chiffre d'extension SSCC doit être un unique chiffre de 0 à 9 "
                "(actuellement « %s »).", extension,
            ))

        # 18 = extension(1) + prefixe + serie + cle(1)
        serial_length = SSCC_LENGTH - 2 - len(prefix)

        raw = self.env['ir.sequence'].next_by_code('wms.pallet.sscc') or '1'
        serial = ''.join(char for char in raw if char.isdigit()).lstrip('0') or '0'

        if len(serial) > serial_length:
            raise UserError(_(
                "La capacité de numérotation SSCC est épuisée : la série « %(serial)s » "
                "dépasse les %(length)s chiffres disponibles avec un préfixe GS1 de "
                "%(prefix_length)s chiffres.\n\n"
                "Un préfixe GS1 plus court laisse davantage de place, ou incrémentez le "
                "chiffre d'extension pour repartir d'une nouvelle plage.",
                serial=serial, length=serial_length, prefix_length=len(prefix),
            ))

        base = extension + prefix + serial.rjust(serial_length, '0')
        # get_barcode_check_digit ignore le dernier caractère : on ajoute un zéro fictif.
        return base + str(get_barcode_check_digit(base + '0'))

    def action_wms_assign_sscc(self):
        """Attribue un SSCC et fige l'instantané d'emballage.

        Le SSCC est écrit dans ``name`` — c'est ce champ qui fait office de code-barres
        pour ``stock.quant.package`` dans Odoo. On hérite ainsi gratuitement du calcul
        ``valid_sscc`` et des rapports d'étiquette natifs.
        """
        for package in self:
            if package.valid_sscc:
                raise UserError(_(
                    "La charge « %s » porte déjà un SSCC.\n\n"
                    "Un SSCC ne se réattribue jamais : c'est ce qui garantit que son "
                    "historique reste sans ambiguïté. Créez une nouvelle charge si le "
                    "contenu a changé de nature.", package.name,
                ))
            if not package.quant_ids:
                raise UserError(_(
                    "La charge « %s » est vide.\n\n"
                    "Attribuez le SSCC une fois la palette montée : la quantité à "
                    "l'emballage est figée à cet instant et imprimée sur l'étiquette.",
                    package.name,
                ))
            package.write({
                'name': package._wms_next_sscc(),
                'wms_packed_quantity': sum(package.quant_ids.mapped('quantity')),
                'wms_packed_date': fields.Datetime.now(),
            })
        return True

    # ------------------------------------------------------------------
    # Charge utile GS1 imprimée sur l'étiquette (immuable)
    # ------------------------------------------------------------------
    def _wms_gs1_label_payload(self):
        """Chaîne GS1 à encoder dans le DataMatrix de l'étiquette.

        N'y figurent que des données immuables. La quantité en est volontairement
        **exclue** : elle change à chaque prélèvement, et une quantité lisible par
        machine mais périmée est plus dangereuse qu'une quantité absente. Elle est
        imprimée en clair, explicitement libellée « à l'emballage ».

        Les identifiants de longueur fixe viennent d'abord, le seul identifiant de
        longueur variable (le lot) vient en dernier : cela évite d'avoir à insérer un
        séparateur FNC1, que le générateur d'images d'Odoo ne sait pas produire.
        """
        self.ensure_one()
        parts = []

        if self.valid_sscc:
            parts.append('00' + self.name)

        # GTIN, DLC et lot ne sont fiables que si la charge est homogène.
        if self.wms_is_homogeneous:
            quants = self.quant_ids
            product = quants.product_id
            lot = quants.lot_id

            if product.barcode and product.valid_ean:
                parts.append('02' + product.barcode.rjust(14, '0'))

            expiry = self._wms_lot_expiry(lot)
            if expiry:
                parts.append('17' + expiry.strftime('%y%m%d'))

            # Longueur variable : impérativement en dernier.
            if lot and len(lot.name) <= 20:
                parts.append('10' + lot.name)

        return ''.join(parts)

    @api.model
    def _wms_lot_expiry(self, lot):
        """DLC d'un lot, ou False.

        Le champ provient du module optionnel ``product_expiry``. Sans cette garde, le
        module casserait sur toute base où ce module n'est pas installé.
        """
        if not lot or 'expiration_date' not in self.env['stock.lot']._fields:
            return False
        return lot.expiration_date or False

    def _wms_label_url(self):
        """Adresse encodée dans le QR code, pour consultation au téléphone."""
        self.ensure_one()
        base = self.env['ir.config_parameter'].sudo().get_param('web.base.url', '')
        return '%s/wms/pallet/%s' % (base.rstrip('/'), self.name)

    # ------------------------------------------------------------------
    # Lecture temps réel : contenu + historique
    # ------------------------------------------------------------------
    def _wms_content(self):
        """Contenu réel de la charge, à l'instant présent."""
        self.ensure_one()
        content = []
        for quant in self.quant_ids:
            expiry = self._wms_lot_expiry(quant.lot_id)
            content.append({
                'product_id': quant.product_id.id,
                'product_name': quant.product_id.display_name,
                'sku': quant.product_id.default_code or '',
                'barcode': quant.product_id.barcode or '',
                'lot_id': quant.lot_id.id,
                'lot_name': quant.lot_id.name or '',
                'expiry': expiry,
                'quantity': quant.quantity,
                'reserved': quant.reserved_quantity,
                # available_quantity n'est pas stocké en base : on le recompose.
                'available': quant.quantity - quant.reserved_quantity,
                'uom': quant.product_uom_id.name,
            })
        return content

    def _wms_history(self, limit=100):
        """Historique des mouvements de la charge, du plus récent au plus ancien.

        Une ligne de mouvement cite la charge soit en source (``package_id``), soit en
        destination (``result_package_id``). Les deux cas doivent être couverts, et le
        cas où les deux pointent sur la même charge est un simple déplacement.

        L'historique se lit ici, jamais dans ``quant_ids`` : une charge vidée n'a plus
        aucun quant, mais elle garde tout son passé.
        """
        self.ensure_one()
        lines = self.env['stock.move.line'].search(
            [
                '&',
                ('state', '=', 'done'),
                '|', ('package_id', '=', self.id), ('result_package_id', '=', self.id),
            ],
            order='date desc, id desc',
            limit=limit,
        )

        history = []
        for line in lines:
            from_here = line.package_id.id == self.id
            into_here = line.result_package_id.id == self.id

            if from_here and into_here:
                direction, sign = 'move', 0        # déplacement, contenu inchangé
            elif into_here:
                direction, sign = 'in', 1          # ajout à la charge
            else:
                direction, sign = 'out', -1        # prélèvement

            history.append({
                'date': line.date,
                'direction': direction,
                'signed_quantity': sign * line.quantity,
                'quantity': line.quantity,
                'uom': line.product_uom_id.name,
                'product_name': line.product_id.display_name,
                'sku': line.product_id.default_code or '',
                'lot_name': line.lot_id.name or '',
                'reference': line.reference or '',
                'picking_id': line.picking_id.id,
                'picking_name': line.picking_id.name or '',
                'location_from': line.location_id.complete_name,
                'location_to': line.location_dest_id.complete_name,
            })
        return history

    def _wms_pallet_payload(self, history_limit=100):
        """Charge utile unique, consommée à la fois par l'écran interne et la page mobile.

        C'est la décision structurante du module : une seule source de données, donc
        aucune divergence possible entre les deux écrans.
        """
        self.ensure_one()
        content = self._wms_content()
        return {
            'found': True,
            'package': {
                'id': self.id,
                'name': self.name,
                'is_sscc': self.valid_sscc,
                'package_type': self.package_type_id.display_name or '',
                'location': self.location_id.complete_name or '',
                'owner': self.owner_id.display_name or '',
                'pack_date': self.pack_date,
                'packed_date': self.wms_packed_date,
                'shipping_weight': self.shipping_weight,
                'is_homogeneous': self.wms_is_homogeneous,
                'is_empty': not content,
            },
            'quantities': {
                # Ce que dit l'étiquette papier.
                'packed': self.wms_packed_quantity,
                # Ce que dit la base, maintenant.
                'current': sum(item['quantity'] for item in content),
                'reserved': sum(item['reserved'] for item in content),
                'available': sum(item['available'] for item in content),
                # L'écart : c'est lui qui rend visible que l'étiquette a vieilli.
                'delta': sum(item['quantity'] for item in content) - self.wms_packed_quantity,
            },
            'content': content,
            'history': self._wms_history(limit=history_limit),
        }

    # ------------------------------------------------------------------
    # Résolution d'un code scanné
    # ------------------------------------------------------------------
    @api.model
    def _wms_resolve_scan(self, code):
        """Retrouve une charge à partir d'un code scanné.

        Trois formes acceptées :

        1. le SSCC nu (18 chiffres), tel que lu depuis un Code128 ;
        2. une chaîne GS1 complète commençant par l'identifiant ``00`` ;
        3. la référence interne Odoo (``PACK0000042``), pour les charges sans SSCC.

        On s'appuie d'abord sur le décodeur natif d'Odoo, qui sait déjà démonter une
        chaîne GS1 ; le repli couvre les scans bruts.
        """
        code = (code or '').strip()
        if not code:
            return self.browse()

        candidates = [code]

        nomenclature = self.env.company.nomenclature_id
        if nomenclature:
            try:
                parsed = nomenclature.parse_barcode(code)
            except Exception:
                parsed = None
            # Selon la nomenclature, parse_barcode renvoie un dict ou une liste de dicts.
            for segment in (parsed if isinstance(parsed, list) else [parsed] if parsed else []):
                if isinstance(segment, dict) and segment.get('type') == 'package':
                    value = segment.get('value') or segment.get('code')
                    if value and str(value) not in candidates:
                        candidates.append(str(value))

        # Repli manuel : chaîne GS1 dont l'identifiant de tête est 00 (SSCC).
        if code.startswith('00') and len(code) >= 20 and code[2:20].isdigit():
            candidates.append(code[2:20])

        for candidate in candidates:
            package = self.search([('name', '=', candidate)], limit=1)
            if package:
                return package
        return self.browse()

    @api.model
    def wms_scan(self, code, history_limit=100):
        """Point d'entrée appelé par l'écran interne (via l'ORM) et par la page mobile."""
        package = self._wms_resolve_scan(code)
        if not package:
            return {'found': False, 'code': code}
        return package._wms_pallet_payload(history_limit=history_limit)
