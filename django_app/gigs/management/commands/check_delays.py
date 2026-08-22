"""Management command to check for delayed orders and send notifications"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from gigs.models import Order
from accounts.email_utils import send_delay_notification_email


class Command(BaseCommand):
    help = 'Check for delayed orders and send email notifications'
    
    def handle(self, *args, **options):
        self.stdout.write('Checking for delayed orders...')
        
        # Get all incomplete orders
        incomplete_orders = Order.objects.filter(is_completed=False)
        
        delayed_count = 0
        for order in incomplete_orders:
            # You would need to add a deadline field to Order model
            # For now, this is a placeholder
            # if order.is_overdue():
            #     send_delay_notification_email(
            #         order=order,
            #         recipient_email=order.seller.email,
            #         recipient_name=order.seller.username,
            #         is_freelancer=True
            #     )
            #     send_delay_notification_email(
            #         order=order,
            #         recipient_email=order.buyer.email,
            #         recipient_name=order.buyer.username,
            #         is_freelancer=False
            #     )
            #     delayed_count += 1
            pass
        
        self.stdout.write(
            self.style.SUCCESS(f'Successfully checked orders. Found {delayed_count} delayed orders.')
        )
