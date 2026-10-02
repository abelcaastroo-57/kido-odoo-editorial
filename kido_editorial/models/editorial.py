import json
from markupsafe import Markup
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class Website(models.Model):
    _inherit = 'website'

    kido_enabled = fields.Boolean('Activar diseño Kido', default=False)
    kido_previous_homepage_id = fields.Many2one('website.page', copy=False)
    kido_contact_team_id = fields.Many2one('crm.team', string='Equipo de consultas Kido')
    kido_mailing_list_id = fields.Many2one('mailing.list', string='Lista Club Kido')
    kido_send_welcome = fields.Boolean('Enviar bienvenida del Club', default=False)
    kido_terms_ready = fields.Boolean('Datos legales revisados', default=False)
    kido_reviews_verified = fields.Boolean('Opiniones verificadas y autorizadas', default=False)
    kido_shipping_notice = fields.Char('Aviso superior', default='Cosmética coreana auténtica · Tienda en Tenerife')
    kido_shipping_threshold = fields.Float('Umbral informativo de envío gratuito', default=70)

    def action_kido_preview(self):
        self.ensure_one()
        return {'type': 'ir.actions.act_url', 'url': '/kido-preview', 'target': 'new'}

    def action_kido_activate(self):
        self.ensure_one()
        if not self.env.user.has_group('base.group_system'):
            raise UserError(_('Solo un administrador puede activar el diseño.'))
        if not self._kido_items(limit=1):
            raise UserError(_('Vincule al menos un producto real y publicable antes de activar el diseño.'))
        home = self.env.ref('kido_editorial.page_home')
        pages = self.env['website.page'].search([('view_id.key', '=like', 'kido_editorial.page_%')])
        conflicting = pages.filtered(lambda p: p.website_id and p.website_id != self)
        if conflicting:
            raise UserError(_('Este paquete ya está asignado a otro sitio. Instale una copia por sitio.'))
        if not self.kido_enabled:
            self.kido_previous_homepage_id = self.homepage_id
        # Pages remain unindexed: publication approval is a separate deployment step.
        pages.write({'website_id': self.id, 'is_published': True, 'website_indexed': False})
        self.write({'kido_enabled': True, 'homepage_id': home.id})
        return self.action_kido_preview()

    def action_kido_restore(self):
        self.ensure_one()
        if not self.env.user.has_group('base.group_system'):
            raise UserError(_('Solo un administrador puede restaurar el diseño.'))
        self.write({'kido_enabled': False, 'homepage_id': self.kido_previous_homepage_id.id or False})
        return True

    def _kido_items(self, limit=None):
        self.ensure_one()
        domain = [('website_id', '=', self.id), ('active', '=', True), ('product_id', '!=', False)]
        items = self.env['kido.editorial.item'].sudo().search(domain, order='sequence, id')
        eligible = self.env['product.template'].search(self.sale_product_domain())
        result = items.filtered(lambda i: i.product_id in eligible and i.product_id.is_published)
        return result[:limit] if limit else result

    def _kido_catalog(self):
        rows = []
        for item in self._kido_items():
            product = item.product_id.with_context(website_id=self.id)
            combination = product._get_first_possible_combination()
            info = product._get_combination_info(combination, add_qty=1)
            variant_id = info.get('product_id')
            # Configurable products are selected on their native product page.
            simple = product.product_variant_count == 1 and not product.attribute_line_ids
            rows.append({
                'id': int(item.local_key) if (item.local_key or '').isdigit() else item.id,
                'item_id': item.id, 'template_id': product.id,
                'variant_id': variant_id if simple else False,
                'brand': item.brand or '', 'name': product.name,
                'price': info.get('price', 0), 'price_text': False,
                'need': item.need or '', 'step': item.step or '',
                'ingredient': item.ingredient or '', 'badge': item.badge or '',
                'img': '/web/image/product.template/%s/image_1024' % product.id,
                'url': product.website_url,
                'available': bool(variant_id and product._is_add_to_cart_possible()
                                  and not info.get('prevent_zero_price_sale')),
                'collection': item.collection or '',
                'routine_eligible': item.routine_eligible,
            })
        return rows

    def _kido_catalog_json(self):
        # Safe inside a script node, including hostile catalog text.
        return Markup(json.dumps(self._kido_catalog(), ensure_ascii=False).replace('<', '\\u003c').replace('&', '\\u0026'))


class EditorialItem(models.Model):
    _name = 'kido.editorial.item'
    _description = 'Selección editorial de Kido'
    _order = 'sequence, id'

    name = fields.Char(required=True)
    website_id = fields.Many2one('website', required=True, ondelete='cascade')
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    local_key = fields.Char('Referencia de maqueta')
    product_id = fields.Many2one('product.template', string='Producto real', ondelete='restrict')
    brand = fields.Char('Marca')
    need = fields.Selection([('hidratacion', 'Hidratación'), ('luminosidad', 'Luminosidad'),
                             ('calma', 'Calma'), ('poros', 'Poros'), ('firmeza', 'Firmeza')])
    step = fields.Selection([('limpiar', 'Limpieza'), ('tratar', 'Tratamiento'),
                             ('hidratar', 'Hidratación'), ('proteger', 'Protección')])
    ingredient = fields.Char('Ingrediente destacado')
    badge = fields.Char('Etiqueta editorial')
    routine_eligible = fields.Boolean('Apto para la rutina facial automática', default=False)
    collection = fields.Selection([('favoritos', 'Favoritos'), ('novedades', 'Novedades')])
    _sql_constraints = [('unique_local_key', 'unique(website_id, local_key)',
                         'La referencia de maqueta debe ser única por sitio.')]

    @api.constrains('website_id', 'product_id')
    def _check_unique_product(self):
        for item in self.filtered('product_id'):
            if self.search_count([('id', '!=', item.id), ('website_id', '=', item.website_id.id),
                                  ('product_id', '=', item.product_id.id)]):
                raise ValidationError(_('Un producto solo puede aparecer una vez en la selección de este sitio.'))


class ClubConsent(models.Model):
    _name = 'kido.club.consent'
    _description = 'Consentimiento Club Kido'
    _order = 'create_date desc'

    email = fields.Char(required=True)
    website_id = fields.Many2one('website', required=True)
    contact_id = fields.Many2one('mailing.contact', ondelete='set null')
    consent_version = fields.Char(required=True, default='2026-10-02')
    source = fields.Selection([('club', 'Club'), ('guide', 'Guía')], required=True)
    consent_date = fields.Datetime(default=fields.Datetime.now, required=True)


class QuizQuestion(models.Model):
    _name = 'kido.quiz.question'
    _description = 'Pregunta de rutina Kido'
    _order = 'sequence, id'

    name = fields.Char(required=True)
    key = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    kicker = fields.Char()
    hint = fields.Char()
    option_ids = fields.One2many('kido.quiz.option', 'question_id', string='Opciones')
    _sql_constraints = [('unique_key', 'unique(key)', 'La clave de pregunta debe ser única.')]


class QuizOption(models.Model):
    _name = 'kido.quiz.option'
    _description = 'Respuesta de rutina Kido'
    _order = 'sequence, id'

    question_id = fields.Many2one('kido.quiz.question', required=True, ondelete='cascade')
    sequence = fields.Integer(default=10)
    value = fields.Char(required=True)
    label = fields.Char(required=True)
    description = fields.Char()
    icon = fields.Char()
    score_ids = fields.One2many('kido.quiz.weight', 'option_id', string='Prioridades')


class QuizWeight(models.Model):
    _name = 'kido.quiz.weight'
    _description = 'Regla de recomendación Kido'

    option_id = fields.Many2one('kido.quiz.option', required=True, ondelete='cascade')
    need = fields.Selection([('hidratacion', 'Hidratación'), ('luminosidad', 'Luminosidad'),
                             ('calma', 'Calma'), ('poros', 'Poros'), ('firmeza', 'Firmeza')], required=True)
    weight = fields.Integer('Peso', default=1, required=True)
