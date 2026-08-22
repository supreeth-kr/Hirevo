from rest_framework import serializers
from .models import (
    User, Category, Skill, FreelancerProfile, ClientProfile,
    Gig, GigPackage, Order, Review, Payment, Notification
)


class SkillSerializer(serializers.ModelSerializer):
    class Meta:
        model = Skill
        fields = ['id', 'name']


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name', 'slug', 'description', 'icon', 'is_active']


class UserBriefSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'full_name', 'email', 'role', 'is_active']


class FreelancerProfileSerializer(serializers.ModelSerializer):
    user = UserBriefSerializer(read_only=True)
    skills = SkillSerializer(many=True, read_only=True)
    avg_rating = serializers.FloatField(read_only=True)
    total_reviews = serializers.IntegerField(read_only=True)
    completed_projects = serializers.IntegerField(read_only=True)

    class Meta:
        model = FreelancerProfile
        fields = [
            'id', 'user', 'bio', 'skills', 'experience_years',
            'hourly_rate', 'availability', 'languages', 'education',
            'location', 'website', 'avg_rating', 'total_reviews',
            'completed_projects', 'created_at'
        ]


class GigPackageSerializer(serializers.ModelSerializer):
    features_list = serializers.ListField(read_only=True)

    class Meta:
        model = GigPackage
        fields = ['id', 'tier', 'name', 'description', 'price', 'delivery_days', 'revisions', 'features', 'features_list']


class GigSerializer(serializers.ModelSerializer):
    freelancer = UserBriefSerializer(read_only=True)
    category = CategorySerializer(read_only=True)
    packages = GigPackageSerializer(many=True, read_only=True)
    avg_rating = serializers.FloatField(read_only=True)
    total_reviews = serializers.IntegerField(read_only=True)
    starting_price = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = Gig
        fields = [
            'id', 'freelancer', 'category', 'title', 'description',
            'tags', 'cover_image', 'status', 'packages', 'avg_rating',
            'total_reviews', 'starting_price', 'created_at'
        ]


class OrderSerializer(serializers.ModelSerializer):
    client = UserBriefSerializer(read_only=True)
    freelancer = UserBriefSerializer(read_only=True)
    gig_title = serializers.CharField(source='gig.title', read_only=True)
    package_tier = serializers.CharField(source='package.tier', read_only=True)

    class Meta:
        model = Order
        fields = [
            'id', 'order_id', 'client', 'freelancer', 'gig', 'gig_title',
            'package', 'package_tier', 'price', 'requirements', 'status',
            'deadline', 'completed_at', 'created_at'
        ]


class ReviewSerializer(serializers.ModelSerializer):
    client = UserBriefSerializer(read_only=True)
    freelancer = UserBriefSerializer(read_only=True)

    class Meta:
        model = Review
        fields = ['id', 'order', 'client', 'freelancer', 'gig', 'rating', 'comment', 'created_at']
