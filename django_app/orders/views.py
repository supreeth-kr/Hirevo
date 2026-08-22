from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from gigs.models import Gig
from .models import Order
import stripe
import json

stripe.api_key = settings.STRIPE_SECRET_KEY

@login_required
def orders_list(request):
    if request.user.is_seller:
        orders = Order.objects.filter(seller=request.user, is_completed=True).select_related('gig', 'buyer')
    else:
        orders = Order.objects.filter(buyer=request.user, is_completed=True).select_related('gig', 'seller')
    return render(request, 'orders/orders.html', {'orders': orders})

@login_required
def pay(request, gig_id):
    gig = get_object_or_404(Gig, pk=gig_id)
    return render(request, 'orders/pay.html', {
        'gig': gig,
        'stripe_key': settings.STRIPE_PUBLISHABLE_KEY,
    })

@login_required
def create_payment_intent(request, gig_id):
    gig = get_object_or_404(Gig, pk=gig_id)
    try:
        intent = stripe.PaymentIntent.create(
            amount=int(gig.price * 100),
            currency='usd',
            automatic_payment_methods={'enabled': True},
        )
        order = Order.objects.create(
            gig=gig,
            buyer=request.user,
            seller=gig.seller,
            price=gig.price,
            payment_intent=intent.id,
        )
        return JsonResponse({'clientSecret': intent.client_secret})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

@csrf_exempt
def payment_success(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        payment_intent = data.get('payment_intent')
        order = Order.objects.filter(payment_intent=payment_intent).first()
        if order:
            order.is_completed = True
            order.gig.sales += 1
            order.gig.save()
            order.save()
            return JsonResponse({'success': True})
    return render(request, 'orders/success.html')
