# -*- coding:utf-8 -*-
import decimal
import os

from django.conf import settings
from django.db import models
from django.utils.translation import ugettext_lazy as _
from django_images.models import Image
from mothertongue.models import MothertongueModelTranslate
from prices import Price
from satchless.category.models import CategorizedProductMixin
from satchless.contrib.tax.flatgroups.models import TaxedProductMixin, TaxedVariantMixin
from satchless.contrib.stock.singlestore.models import VariantStockLevelMixin
import satchless.product.models
from satchless.util.models import construct

from categories.models import Category


class DiscountGroup(models.Model):

    name = models.CharField(_('group name'), max_length=100)
    rate = models.DecimalField(_('rate'), max_digits=4, decimal_places=2,
                               help_text=_('Percentile rate of the discount.'))
    rate_name = models.CharField(_('name of the rate'), max_length=30,
                                 help_text=_(u'Name of the rate which will be '
                                             'displayed to the user.'))

    def get_discount_amount(self, price):
        return price * self.rate * decimal.Decimal('0.01')

    def __unicode__(self):
        return self.name


class Product(TaxedProductMixin,
              construct(CategorizedProductMixin, category=Category),
              satchless.product.models.Product):

    QTY_MODE_CHOICES = (
        ('product', _("per product")),
        ('variant', _("per variant"))
    )
    qty_mode = models.CharField(_("Quantity pricing mode"), max_length=10,
                                choices=QTY_MODE_CHOICES, default='variant',
                                help_text=_("In 'per variant' mode the unit "
                                            "price will depend on quantity "
                                            "of single variant being sold. In "
                                            "'per product' mode, total "
                                            "quantity of all product's "
                                            "variants will be used."))
    price = models.DecimalField(_("base price"), max_digits=12, decimal_places=4)
    discount = models.ForeignKey(DiscountGroup, null=True, blank=True,
                                 related_name='products')

    def _get_base_price(self, quantity):
        overrides = self.qty_price_overrides.all()
        overrides = overrides.filter(min_qty__lte=quantity).order_by('-min_qty')
        currency = settings.SATCHESS_DEFAULT_CURRENCY
        try:
            override = overrides[0]
            return Price(override.price, currency=currency)
        except PriceQtyOverride.DoesNotExist:
            return Price(self.price, currency=currency)


class PriceQtyOverride(models.Model):
    """
    Overrides price of product unit, depending of total quantity being sold.
    """
    product = models.ForeignKey(Product, related_name='qty_price_overrides')
    min_qty = models.DecimalField(_("minimal quantity"), max_digits=10,
                                  decimal_places=4)
    price = models.DecimalField(_("unit price"), max_digits=12,
                                decimal_places=4)

    class Meta:
        ordering = ('min_qty',)


class Variant(TaxedVariantMixin, VariantStockLevelMixin,
              satchless.product.models.Variant):
    price_offset = models.DecimalField(_("unit price offset"),
                                       default=decimal.Decimal(0),
                                       max_digits=12, decimal_places=4)

    def get_price_for_item(self, discount=True, quantity=1, **kwargs):
        currency = settings.SATCHESS_DEFAULT_CURRENCY
        price = self.product._get_base_price(quantity=quantity)
        price += Price(self.price_offset, currency=currency)
        if discount and self.product.discount:
            price -= self.product.discount.get_discount_amount(price)
        return price


class ProductImage(Image):
    product = models.ForeignKey(Product, related_name="images")
    caption = models.CharField(_("Caption"), max_length=128, blank=True)
    order = models.PositiveIntegerField(blank=True)

    class Meta:
        ordering = ('order',)

    def __unicode__(self):
        return os.path.basename(self.image.name)

    def save(self, *args, **kwargs):
        if self.order is None:
            self.order = self.product.images.aggregate(max_order=models.Max("order"))['max_order'] or 0
        return super(ProductImage, self).save(*args, **kwargs)


class Make(models.Model):
    name = models.TextField(_("manufacturer"), default='', blank=True)
    logo = models.ImageField(upload_to="make/logo/")

    def __unicode__(self):
        return self.name


class ProductBase(MothertongueModelTranslate, Product):
    name = models.CharField(_('name'), max_length=128)
    description = models.TextField(_('description'), blank=True)
    meta_description = models.TextField(_('meta description'), blank=True,
                                        help_text=_('Description used by search'
                                                    ' and indexing engines.'))
    make = models.ForeignKey(Make, null=True, blank=True, on_delete=models.SET_NULL,
        help_text=_("Product manufacturer"))
    main_image = models.ForeignKey(ProductImage, null=True, blank=True, on_delete=models.SET_NULL,
            help_text=_("Main product image (first image by default)"))
    translated_fields = ('name', 'description', 'meta_description', 'manufacture')
    translation_set = 'translations'

    class Meta:
        abstract = True


class ProductTranslation(models.Model):
    language = models.CharField(max_length=5, choices=settings.LANGUAGES[1:])
    name = models.CharField(_('name'), max_length=128)
    description = models.TextField(_('description'), blank=True)
    manufacture = models.TextField(_("manufacture"), default='', blank=True)
    meta_description = models.TextField(_('meta description'), blank=True,
            help_text=_("Description used by search and indexing engines"))

    class Meta:
        abstract = True

    def __unicode__(self):
        return "%s@%s" % (self.name, self.language)


class ColoredVariant(Variant):
    COLOR_CHOICES = (('red', _("Red")), ('green', _("Green")), ('blue', _("Blue")))
    color = models.CharField(max_length=32, choices=COLOR_CHOICES)
    class Meta:
        abstract = True


class Cardigan(ProductBase):
    class Meta:
        verbose_name = _('Cardigan')
        verbose_name_plural = _('Cardigans')


class CardiganTranslation(ProductTranslation):
    product = models.ForeignKey(Cardigan, related_name='translation')


class CardiganVariant(ColoredVariant):
    product = models.ForeignKey(Cardigan, related_name='variants')
    SIZE_CHOICES = (('S', 'S'), ('XS', 'XS'), ('M', 'M'), ('L', 'L'), ('XL', 'XL'))
    size = models.CharField(choices=SIZE_CHOICES, max_length=2)

    def __unicode__(self):
        return '%s (%s / %s)' % (self.product, self.get_color_display(), self.get_size_display())


class Dress(ProductBase):
    class Meta:
        verbose_name = _('Dress')
        verbose_name_plural = _('Dresses')


class DressTranslation(ProductTranslation):
    product = models.ForeignKey(Dress, related_name='translations')


class DressVariant(ColoredVariant):
    product = models.ForeignKey(Dress, related_name='variants')
    SIZE_CHOICES = tuple([(str(s),str(s)) for s in range(8, 15)])
    size = models.CharField(choices=SIZE_CHOICES, max_length=2)

    def __unicode__(self):
        return '%s (%s / %s)' % (unicode(self.product), self.get_color_display(),
                                 self.get_size_display())


class Hat(ProductBase):
    class Meta:
        verbose_name = _('Hat')
        verbose_name_plural = _('Hats')


class HatTranslation(ProductTranslation):
    product = models.ForeignKey(Hat, related_name='translations')


class HatVariant(Variant):
    product = models.ForeignKey(Hat, related_name='variants')

    def __unicode__(self):
        return unicode(self.product)


class Jacket(ProductBase):
    class Meta:
        verbose_name = _('Jacket')
        verbose_name_plural = _('Jackets')


class JacketTranslation(ProductTranslation):
    product = models.ForeignKey(Jacket, related_name='translations')


class JacketVariant(ColoredVariant):
    product = models.ForeignKey(Jacket, related_name='variants')
    SIZE_CHOICES = tuple([(str(s),str(s)) for s in range(36, 49)])
    size = models.CharField(choices=SIZE_CHOICES, max_length=2)

    def __unicode__(self):
        return '%s (%s / %s)' % (unicode(self.product), self.get_color_display(),
                                 self.get_size_display())


class Shirt(ProductBase):
    class Meta:
        verbose_name = _('Shirt')
        verbose_name_plural = _('Shirts')


class ShirtTranslation(ProductTranslation):
    product = models.ForeignKey(Shirt, related_name='translations')


class ShirtVariant(ColoredVariant):
    product = models.ForeignKey(Shirt, related_name='variants')
    SIZE_CHOICES = tuple([(str(s),str(s)) for s in range(8, 17)])
    size = models.CharField(choices=SIZE_CHOICES, max_length=2)

    def __unicode__(self):
        return '%s (%s / %s)' % (unicode(self.product), self.get_color_display(),
                                 self.get_size_display())


class TShirt(ProductBase):
    class Meta:
        verbose_name = _('TShirt')
        verbose_name_plural = _('TShirts')


class TShirtTranslation(ProductTranslation):
    product = models.ForeignKey(TShirt, related_name='translations')


class TShirtVariant(ColoredVariant):
    product = models.ForeignKey(TShirt, related_name='variants')
    SIZE_CHOICES = (('S', 'S'), ('XS', 'XS'), ('M', 'M'), ('L', 'L'), ('XL', 'XL'))
    size = models.CharField(choices=SIZE_CHOICES, max_length=2)

    def __unicode__(self):
        return u'%s / %s / %s' % (self.product, self.get_color_display(), self.get_size_display())


class Trousers(ProductBase):
    class Meta:
        verbose_name = _('Trousers')
        verbose_name_plural = _('Trousers')


class TrousersTranslation(ProductTranslation):
    product = models.ForeignKey(Trousers, related_name='translations')


class TrousersVariant(ColoredVariant):
    product = models.ForeignKey(Trousers, related_name='variants')
    SIZE_CHOICES = tuple([(str(s),str(s)) for s in range(30, 39)])
    size = models.CharField(choices=SIZE_CHOICES, max_length=2)

    def __unicode__(self):
        return '%s / %s' % (self.get_color_display(), self.get_size_display())


def assign_main_image(sender, instance, **kwargs):
    if not kwargs.get('raw', False) and instance.product.main_image == None \
            and instance.product.images.exists():
        instance.product.main_image = instance.product.images.all()[0]
        instance.product.save()
models.signals.post_save.connect(assign_main_image, sender=ProductImage)

def assign_new_main_image(sender, instance, **kwargs):
    try:
        if instance.product.main_image == instance and instance.product.images.exists():
            instance.product.main_image = instance.product.images.all()[0]
            instance.product.save()
    except Product.DoesNotExist:
        pass
models.signals.post_delete.connect(assign_new_main_image, sender=ProductImage)

