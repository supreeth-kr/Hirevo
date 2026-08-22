from rest_framework import generics, serializers
from .models import Gig

class GigSerializer(serializers.ModelSerializer):
    seller_name = serializers.CharField(source='seller.username', read_only=True)
    avg_rating = serializers.SerializerMethodField()

    class Meta:
        model = Gig
        fields = ['id', 'title', 'short_desc', 'category', 'price', 'cover', 'sales', 'avg_rating', 'seller_name']

    def get_avg_rating(self, obj):
        return obj.avg_rating()

class GigListAPI(generics.ListAPIView):
    serializer_class = GigSerializer

    def get_queryset(self):
        qs = Gig.objects.all()
        category = self.request.query_params.get('category')
        search = self.request.query_params.get('search')
        if category:
            qs = qs.filter(category__icontains=category)
        if search:
            qs = qs.filter(title__icontains=search)
        return qs

class GigDetailAPI(generics.RetrieveAPIView):
    queryset = Gig.objects.all()
    serializer_class = GigSerializer
