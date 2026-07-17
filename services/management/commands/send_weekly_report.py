from django.core.management.base import BaseCommand

from services.admin_report_service import send_weekly_sales_report


class Command(BaseCommand):
    help = (
        "Send the weekly sales report email to ADMIN_EMAIL. Cron-runnable "
        "equivalent of the Celery send_weekly_sales_report_task, for "
        "environments with no worker/beat deployed."
    )

    def handle(self, *args, **options):
        send_weekly_sales_report()
        self.stdout.write(self.style.SUCCESS("Weekly sales report sent."))
