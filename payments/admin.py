from django.contrib import admin
from django.utils.html import format_html

from .models import PaymentTransaction


@admin.register(PaymentTransaction)
class PaymentTransactionAdmin(admin.ModelAdmin):
    list_display = [
        'reference', 'order', 'amount', 'status',
        'transaction_reference', 'receipt_links', 'submitted_at', 'created_at',
    ]
    list_filter = ['status', 'created_at']
    search_fields = ['reference', 'transaction_reference', 'order__order_number']
    readonly_fields = ['receipt_preview', 'submitted_at', 'verified_at', 'created_at']
    fields = [
        'order', 'amount', 'status', 'transaction_reference',
        'receipt', 'receipt_preview', 'submitted_at', 'verified_at',
        'created_at', 'reference', 'metadata',
    ]

    @admin.display(description='Receipt')
    def receipt_links(self, obj):
        if not obj.receipt:
            return '—'
        return format_html(
            '<a href="{0}" target="_blank">View</a> · <a href="{0}" download>Download</a>',
            obj.receipt.url,
        )

    @admin.display(description='Receipt preview')
    def receipt_preview(self, obj):
        if not obj.receipt:
            return 'No receipt uploaded'
        url = obj.receipt.url
        if url.lower().endswith('.pdf'):
            return format_html(
                '<a href="{0}" target="_blank">Open PDF</a> · <a href="{0}" download>Download</a>',
                url,
            )
        return format_html(
            '<a href="{0}" target="_blank"><img src="{0}" alt="Payment receipt" '
            'style="max-width:400px; max-height:400px; border:1px solid #ddd;" /></a>'
            '<br><a href="{0}" download>Download</a>',
            url,
        )
