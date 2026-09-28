import os
import django
import sys
import random
from datetime import timedelta

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hirevo.settings')
django.setup()

from marketplace.models import Category, User, Gig, GigPackage, Order, Payment
from marketplace.services import check_and_apply_delays
from django.utils import timezone

def run():
    print("Cleaning up old dummy data...")
    # Delete dummy users and their cascading gigs/orders
    User.objects.filter(username__in=['freelancer_x', 'freelancer_y', 'client2']).delete()

    print("Fetching existing users...")
    old_freelancers = list(User.objects.filter(role=User.ROLE_FREELANCER, is_active=True))
    if not old_freelancers:
        print("No old freelancers found.")
        return

    client = User.objects.filter(role=User.ROLE_CLIENT, is_active=True).first()
    if not client:
        print("No client found.")
        return

    categories = Category.objects.all()
    if not categories.exists():
        print("No categories found.")
        return

    print("Creating gigs for existing freelancers with different prices...")
    gig_count = 1
    base_price = 1000

    for category in categories:
        for i in range(2):
            freelancer = old_freelancers[gig_count % len(old_freelancers)]
            
            # Different price for each gig
            b_price = base_price + (gig_count * 50)
            s_price = b_price * 2
            p_price = b_price * 4
            
            gig, created = Gig.objects.get_or_create(
                category=category,
                title=f'{category.name} Pro Service {gig_count}',
                freelancer=freelancer,
                defaults={
                    'description': f'High quality {category.name} services tailored for your needs.',
                    'tags': 'pro, quality',
                }
            )
            if created:
                GigPackage.objects.get_or_create(gig=gig, tier=GigPackage.BASIC, defaults={'name': 'Basic', 'price': b_price, 'delivery_days': 2, 'description': 'Basic package'})
                GigPackage.objects.get_or_create(gig=gig, tier=GigPackage.STANDARD, defaults={'name': 'Standard', 'price': s_price, 'delivery_days': 4, 'description': 'Standard package'})
                GigPackage.objects.get_or_create(gig=gig, tier=GigPackage.PREMIUM, defaults={'name': 'Premium', 'price': p_price, 'delivery_days': 7, 'description': 'Premium package'})
            gig_count += 1
            
    print(f"Created {gig_count-1} gigs.")

    # Create a delayed project for the first freelancer
    target_freelancer = old_freelancers[0]
    target_gig = Gig.objects.filter(freelancer=target_freelancer).first()
    if target_gig:
        pkg = target_gig.packages.first()
        import uuid
        order_key = str(uuid.uuid4())[:8]
        order, created = Order.objects.get_or_create(
            client=client,
            freelancer=target_freelancer,
            gig=target_gig,
            package=pkg,
            requirements=f'Automated delayed order {order_key}',
            defaults={
                'price': pkg.price,
                'status': Order.STATUS_IN_PROGRESS,
                'deadline': timezone.now() - timedelta(days=3),
                'created_at': timezone.now() - timedelta(days=6)
            }
        )
        if created:
            Payment.objects.get_or_create(order=order, client=client, freelancer=target_freelancer, amount=pkg.price, status=Payment.STATUS_PAID)
            print(f"Created a delayed order for {target_freelancer.username}.")
            count = check_and_apply_delays()
            print(f"Applied penalties to {count} overdue orders.")
        else:
            print("Delayed order already exists.")

    print("Re-seeding complete.")

if __name__ == '__main__':
    run()
