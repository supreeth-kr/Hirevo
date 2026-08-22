from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from .models import Gig, GigImage, CATEGORY_CHOICES
from .forms import GigForm
from recommendations.engine import get_recommendations
from hirevo.form_utils import add_bootstrap_classes

def home(request):
    featured_gigs = Gig.objects.order_by('-sales')[:8]
    recommended = get_recommendations(request.user) if request.user.is_authenticated else []
    return render(request, 'gigs/home.html', {
        'featured_gigs': featured_gigs,
        'categories': CATEGORY_CHOICES,
        'recommended': recommended,
    })

def gig_list(request):
    category = request.GET.get('category', '')
    search = request.GET.get('search', '')
    min_price = request.GET.get('min', '')
    max_price = request.GET.get('max', '')
    sort = request.GET.get('sort', 'sales')

    gigs = Gig.objects.all()
    if category:
        gigs = gigs.filter(category__icontains=category)
    if search:
        gigs = gigs.filter(Q(title__icontains=search) | Q(description__icontains=search))
    if min_price:
        gigs = gigs.filter(price__gte=min_price)
    if max_price:
        gigs = gigs.filter(price__lte=max_price)
    gigs = gigs.order_by('-created_at' if sort == 'createdAt' else '-sales')

    return render(request, 'gigs/gig_list.html', {
        'gigs': gigs,
        'category': category,
        'search': search,
        'categories': CATEGORY_CHOICES,
    })

def gig_detail(request, pk):
    gig = get_object_or_404(Gig, pk=pk)
    reviews = gig.reviews.select_related('user').all()
    return render(request, 'gigs/gig_detail.html', {'gig': gig, 'reviews': reviews})

@login_required
def gig_create(request):
    if not request.user.is_seller:
        messages.error(request, 'Only sellers can create gigs.')
        return redirect('home')
    form = GigForm(request.POST or None)
    add_bootstrap_classes(form)
    if request.method == 'POST' and form.is_valid():
        gig = form.save(commit=False)
        gig.seller = request.user
        gig.save()
        extra = request.POST.get('extra_images', '')
        for url in [u.strip() for u in extra.split(',') if u.strip()]:
            GigImage.objects.create(gig=gig, image=url)
        messages.success(request, 'Gig created successfully!')
        return redirect('my_gigs')
    return render(request, 'gigs/gig_form.html', {'form': form})

@login_required
def my_gigs(request):
    gigs = Gig.objects.filter(seller=request.user)
    return render(request, 'gigs/my_gigs.html', {'gigs': gigs})

@login_required
def gig_delete(request, pk):
    gig = get_object_or_404(Gig, pk=pk, seller=request.user)
    if request.method == 'POST':
        gig.delete()
        messages.success(request, 'Gig deleted.')
    return redirect('my_gigs')
