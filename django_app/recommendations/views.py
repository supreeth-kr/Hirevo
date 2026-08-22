from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from .engine import get_recommendations

@login_required
def recommendations_api(request):
    gigs = get_recommendations(request.user)
    data = [{'id': g.id, 'title': g.title, 'price': str(g.price), 'category': g.category} for g in gigs]
    return JsonResponse({'recommendations': data})
