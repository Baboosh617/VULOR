import logging

from django.contrib import admin

from .models import Order, OrderItem
from services.email_service import send_payment_rejected

logger = logging.getLogger(__name__)

class OrderItemInline(admin.TabularInline):
    model = OrderItem
    readonly_fields = ['product', 'quantity', 'price', 'size', 'color']
    extra = 0

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ['order_number', 'user', 'total_amount', 'status', 'payment_status', 'created_at']
    list_filter = ['status', 'payment_status', 'created_at']
    search_fields = ['order_number', 'user__email', 'user__username']
    readonly_fields = [
    'order_number',
    'user',
    'total_amount',
    'created_at',
    'updated_at',
    'status',
    ]
    inlines = [OrderItemInline]
    actions = ['mark_payment_confirmed', 'mark_payment_rejected']

    fieldsets = (
        ('Order Information', {
            'fields': ('order_number', 'user', 'total_amount', 'status')
        }),
        ('Shipping Information', {
            'fields': ('shipping_address', 'shipping_city', 'shipping_state', 'shipping_zipcode', 'shipping_country')
        }),
        ('Customer Information', {
            'fields': ('customer_email', 'customer_phone', 'order_notes')
        }),
        ('Payment Information', {
            'fields': ('payment_status', 'payment_method')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )

    @admin.action(description='Mark payment as confirmed')
    def mark_payment_confirmed(self, request, queryset):
        confirmed = 0
        for order in queryset.exclude(payment_status='success'):
            order.confirm_payment()
            confirmed += 1
        self.message_user(request, f'{confirmed} order(s) marked as paid.')

    @admin.action(description='Mark payment as rejected')
    def mark_payment_rejected(self, request, queryset):
        rejected = 0
        for order in queryset.filter(payment_status='pending_verification'):
            order.reject_payment()
            try:
                send_payment_rejected(order.user, order)
            except Exception:
                logger.error(f'Failed to send payment rejection email for order {order.id}', exc_info=True)
            rejected += 1
        self.message_user(request, f'{rejected} order(s) rejected; customers notified.')

@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ['order', 'product', 'quantity', 'price']
    list_filter = ['order__status']
    search_fields = ['order__order_number', 'product__name']
