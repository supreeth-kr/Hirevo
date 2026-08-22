from django.shortcuts import redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from gigs.models import Gig
from .models import Review

@login_required
def create_review(request, gig_id):
    gig = get_object_or_404(Gig, pk=gig_id)
    if request.method == 'POST' and not request.user.is_seller:
        star = int(request.POST.get('star', 5))
        description = request.POST.get('description', '')
        if not Review.objects.filter(gig=gig, user=request.user).exists():
            Review.objects.create(gig=gig, user=request.user, star=star, description=description)
            gig.total_stars += star
            gig.star_number += 1
            gig.save()
            messages.success(request, 'Review submitted!')
        else:
            messages.error(request, 'You already reviewed this gig.')
    return redirect('gig_detail', pk=gig_id)
