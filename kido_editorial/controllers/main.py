import time
from odoo import http
from odoo.http import request
from odoo.exceptions import AccessError, UserError
from odoo.tools import email_normalize
from odoo.addons.website_sale.controllers.main import WebsiteSale
from werkzeug.exceptions import NotFound


class KidoWebsiteSale(WebsiteSale):
    @http.route()
    def shop(self, **kwargs):
        response = super().shop(**kwargs)
        if request.website.kido_enabled and hasattr(response, 'qcontext'):
            response.template = 'kido_editorial.shop_page'
        return response

    @http.route()
    def product(self, product, category='', search='', **kwargs):
        response = super().product(product, category=category, search=search, **kwargs)
        if request.website.kido_enabled and hasattr(response, 'qcontext'):
            response.template = 'kido_editorial.product_page'
        return response


class KidoController(http.Controller):
    def _designer(self):
        return request.env.user.has_group('website.group_website_designer')

    def _allowed(self):
        if not request.website.kido_enabled and not self._designer():
            raise NotFound()

    @http.route('/kido-preview', type='http', auth='user', website=True, sitemap=False)
    def preview(self, **kwargs):
        if not self._designer():
            raise NotFound()
        page = request.env.ref('kido_editorial.page_home')
        return request.render('kido_editorial.page_home_view', {'main_object': page, 'kido_preview': True})

    @http.route('/kido/shop-preview', type='http', auth='user', website=True, sitemap=False)
    def shop_preview(self, **kwargs):
        if not self._designer():
            raise NotFound()
        return request.render('kido_editorial.shop_page', {'kido_preview': True})

    @http.route('/kido/catalog', type='json', auth='public', website=True)
    def catalog(self):
        self._allowed()
        return {'products': request.website._kido_catalog(),
                'currency': request.website.currency_id.name,
                'threshold': request.website.kido_shipping_threshold}

    @http.route('/kido/questions', type='json', auth='public', website=True)
    def questions(self):
        self._allowed()
        questions = request.env['kido.quiz.question'].sudo().search([])
        return [{'id': q.key, 'title': q.name, 'kicker': q.kicker or '', 'hint': q.hint or '',
                 'options': [{'value': o.value, 'label': o.label, 'desc': o.description or '',
                              'icon': o.icon or '',
                              'scores': [{'need': r.need, 'weight': r.weight} for r in o.score_ids]}
                             for o in q.option_ids]} for q in questions]

    @http.route('/kido/cart', type='json', auth='public', website=True)
    def cart(self):
        self._allowed()
        order = request.website.sale_get_order()
        if not order:
            return {'lines': [], 'quantity': 0, 'total': 0, 'subtotal': 0}
        return {'quantity': order.cart_quantity, 'total': order.amount_total,
                'subtotal': order.amount_untaxed,
                'lines': [{'line_id': line.id, 'quantity': line.product_uom_qty,
                           'name': line.product_id.display_name,
                           'price': line.price_total,
                           'img': '/web/image/product.product/%s/image_128' % line.product_id.id}
                          for line in order.website_order_line if not line.is_delivery]}

    @http.route('/kido/add', type='json', auth='public', website=True)
    def add(self, item_ids, quantity=1):
        self._allowed()
        if not isinstance(item_ids, list) or not item_ids or len(item_ids) > 12:
            raise UserError('La selección no es válida. Revisa tu rutina.')
        try:
            ids = [int(i) for i in item_ids]
            qty = int(quantity)
        except (ValueError, TypeError):
            raise UserError('Cantidad no válida.')
        if qty < 1 or qty > 10 or len(set(ids)) != len(ids):
            raise UserError('Cantidad no válida.')
        eligible = request.website._kido_items().filtered(lambda i: i.id in ids)
        if set(eligible.ids) != set(ids):
            raise UserError('Algún producto ya no está disponible en esta selección.')
        variants = []
        for item in eligible:
            p = item.product_id
            if p.product_variant_count != 1 or p.attribute_line_ids:
                raise UserError('Selecciona las opciones de %s en su ficha.' % p.name)
            info = p._get_combination_info(p._get_first_possible_combination(), add_qty=qty)
            if not p._is_add_to_cart_possible() or info.get('prevent_zero_price_sale'):
                raise UserError('%s no se puede añadir en este momento.' % p.name)
            variants.append(p.product_variant_id.id)
        # Roll back the complete bundle if any addition fails; keep stock checks native.
        warnings = []
        with request.env.cr.savepoint():
            order = request.website.sale_get_order(force_create=True)
            if order.state != 'draft':
                request.website.sale_reset()
                order = request.website.sale_get_order(force_create=True)
            for variant_id in variants:
                result = order._cart_update(product_id=variant_id, add_qty=qty)
                if result.get('warning'):
                    raise UserError(result['warning'])
                if not result.get('quantity'):
                    raise UserError('No hay disponibilidad suficiente para completar la selección.')
        request.session['website_sale_cart_quantity'] = order.cart_quantity
        return {'cart': self.cart(), 'warnings': warnings}

    @http.route('/kido/remove', type='json', auth='public', website=True)
    def remove(self, line_id):
        self._allowed()
        order = request.website.sale_get_order()
        if order:
            line = order.website_order_line.filtered(lambda l: l.id == int(line_id))
            if not line or line.is_delivery:
                raise AccessError('La línea no pertenece a tu cesta.')
            order._cart_update(product_id=line.product_id.id, line_id=line.id, set_qty=0)
            request.session['website_sale_cart_quantity'] = order.cart_quantity
        return self.cart()

    def _form_guard(self, values):
        self._allowed()
        if values.get('company_fax'):
            raise UserError('No se ha podido enviar la solicitud.')
        now = time.time()
        if now - request.session.get('kido_last_form', 0) < 15:
            raise UserError('Espera unos segundos antes de volver a enviar.')
        email = email_normalize(values.get('email', '').strip())
        if not email or not values.get('consent'):
            raise UserError('Introduce un correo válido y acepta la política de privacidad.')
        request.session['kido_last_form'] = now
        return email

    @http.route('/kido/club', type='http', auth='public', website=True, methods=['POST'], csrf=True)
    def club(self, **values):
        try:
            email = self._form_guard(values)
            mailing_list = request.website.kido_mailing_list_id
            if not mailing_list:
                raise UserError('El Club Kido estará disponible próximamente.')
            Contact = request.env['mailing.contact'].sudo()
            contact = Contact.search([('email', '=ilike', email)], limit=1)
            if not contact:
                contact = Contact.create({'email': email, 'list_ids': [(4, mailing_list.id)]})
            else:
                contact.write({'list_ids': [(4, mailing_list.id)]})
            # Explicit form opt-in reactivates only this requested list.
            request.env['mailing.subscription'].sudo().search([
                ('contact_id', '=', contact.id), ('list_id', '=', mailing_list.id)
            ]).write({'opt_out': False})
            consent = request.env['kido.club.consent'].sudo().create({
                'email': email, 'contact_id': contact.id, 'website_id': request.website.id,
                'source': 'guide' if values.get('source') == 'guide' else 'club',
            })
            if request.website.kido_send_welcome:
                request.env.ref('kido_editorial.club_welcome').sudo().send_mail(consent.id, force_send=False)
            return request.make_json_response({'ok': True, 'message': 'Ya formas parte del Club Kido. Gracias por acompañarnos.'})
        except UserError as exc:
            return request.make_json_response({'ok': False, 'message': str(exc)}, status=400)

    @http.route('/kido/contact', type='http', auth='public', website=True, methods=['POST'], csrf=True)
    def contact(self, **values):
        try:
            email = self._form_guard(values)
            name = str(values.get('name', '')).strip()[:150]
            message = str(values.get('message', '')).strip()[:5000]
            if not name or not message:
                raise UserError('Completa el nombre y el mensaje.')
            # Plain text to CRM, no notification/email side effects requested here.
            from markupsafe import escape
            request.env['crm.lead'].sudo().create({
                'name': 'Kido web: %s' % str(values.get('subject', 'Consulta'))[:120],
                'contact_name': name, 'email_from': email,
                'description': '<p>%s</p>' % escape(message).replace('\n', '<br/>'),
                'type': 'lead', 'team_id': request.website.kido_contact_team_id.id or False,
            })
            return request.make_json_response({'ok': True, 'message': 'Hemos recibido tu consulta. El equipo de Kido la revisará.'})
        except UserError as exc:
            return request.make_json_response({'ok': False, 'message': str(exc)}, status=400)
