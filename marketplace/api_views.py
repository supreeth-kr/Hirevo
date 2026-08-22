from rest_framework import generics, permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from django.db.models import Q
from .models import Category, Gig, FreelancerProfile, Order, User
from .serializers import (
    CategorySerializer, GigSerializer, FreelancerProfileSerializer,
    OrderSerializer
)
from .ai_recommendation import recommend_freelancers, recommend_gigs


class CategoryListAPIView(generics.ListAPIView):
    queryset = Category.objects.filter(is_active=True)
    serializer_class = CategorySerializer
    permission_classes = [permissions.AllowAny]


class GigListAPIView(generics.ListAPIView):
    serializer_class = GigSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        qs = Gig.objects.filter(status=Gig.STATUS_ACTIVE).select_related('freelancer', 'category').prefetch_related('packages')
        q = self.request.query_params.get('q', '')
        cat = self.request.query_params.get('category', '')
        if q:
            qs = qs.filter(
                Q(title__icontains=q) |
                Q(description__icontains=q) |
                Q(tags__icontains=q) |
                Q(freelancer__username__icontains=q) |
                Q(freelancer__full_name__icontains=q)
            )
        if cat:
            qs = qs.filter(category__slug=cat)
        return qs


class GigDetailAPIView(generics.RetrieveAPIView):
    queryset = Gig.objects.filter(status=Gig.STATUS_ACTIVE).select_related('freelancer', 'category').prefetch_related('packages')
    serializer_class = GigSerializer
    permission_classes = [permissions.AllowAny]


class FreelancerListAPIView(generics.ListAPIView):
    serializer_class = FreelancerProfileSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        qs = FreelancerProfile.objects.filter(user__is_active=True).select_related('user').prefetch_related('skills')
        skill = self.request.query_params.get('skill', '')
        if skill:
            qs = qs.filter(skills__name__icontains=skill)
        return qs


class FreelancerDetailAPIView(generics.RetrieveAPIView):
    queryset = FreelancerProfile.objects.filter(user__is_active=True).select_related('user').prefetch_related('skills')
    serializer_class = FreelancerProfileSerializer
    permission_classes = [permissions.AllowAny]
    lookup_field = 'user__id'


class OrderListAPIView(generics.ListAPIView):
    serializer_class = OrderSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_admin_user():
            return Order.objects.all().select_related('client', 'freelancer', 'gig', 'package')
        elif user.is_client():
            return Order.objects.filter(client=user).select_related('client', 'freelancer', 'gig', 'package')
        elif user.is_freelancer():
            return Order.objects.filter(freelancer=user).select_related('client', 'freelancer', 'gig', 'package')
        return Order.objects.none()


class AIRecommendationAPIView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        title = request.query_params.get('title', '')
        description = request.query_params.get('description', '')
        skills_str = request.query_params.get('skills', '')
        budget = request.query_params.get('budget')
        category = request.query_params.get('category')

        skills_list = [s.strip() for s in skills_str.split(',') if s.strip()] if skills_str else []
        try:
            budget_val = float(budget) if budget else None
        except ValueError:
            budget_val = None

        freelancers = recommend_freelancers(
            project_title=title,
            project_description=description,
            required_skills=skills_list,
            budget=budget_val,
            category=category,
            limit=5
        )

        gigs = recommend_gigs(
            project_title=title,
            project_description=description,
            required_skills=skills_list,
            budget=budget_val,
            category=category,
            limit=5
        )

        freelancer_data = []
        for item in freelancers:
            freelancer_data.append({
                'id': item['user'].id,
                'username': item['user'].username,
                'full_name': item['user'].full_name,
                'hourly_rate': float(item['profile'].hourly_rate),
                'experience_years': item['profile'].experience_years,
                'availability': item['profile'].availability,
                'skills': item['skills_list'],
                'avg_rating': item['avg_rating'],
                'total_reviews': item['total_reviews'],
                'skill_match_score': item['skill_score'],
                'nlp_relevance_score': item['nlp_score'],
                'experience_score': item['experience_score'],
                'rating_score': item['rating_score'],
                'availability_score': item['availability_score'],
                'price_score': item['price_score'],
                'final_match_score': item['final_score'],
            })

        gig_data = []
        for item in gigs:
            gig_data.append({
                'id': item['gig'].id,
                'title': item['gig'].title,
                'freelancer': item['gig'].freelancer.username,
                'category': item['gig'].category.name if item['gig'].category else '',
                'starting_price': item['starting_price'],
                'avg_rating': item['avg_rating'],
                'total_reviews': item['total_reviews'],
                'skill_match_score': item['skill_score'],
                'nlp_score': item['nlp_score'],
                'rating_score': item['rating_score'],
                'price_score': item['price_score'],
                'final_match_score': item['final_score'],
            })

        return Response({
            'query': {
                'title': title,
                'description': description,
                'skills': skills_list,
                'budget': budget_val,
                'category': category,
            },
            'recommended_freelancers': freelancer_data,
            'recommended_gigs': gig_data,
        })
