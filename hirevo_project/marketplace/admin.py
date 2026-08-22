from django.contrib import admin
from .models import (User, Category, Skill, FreelancerProfile, ClientProfile,
                     Portfolio, Certificate, Gig, GigPackage, Order, Delivery,
                     Revision, Payment, Review, Message, Notification, Penalty,
                     BackupAssignment, ProjectHistory)


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ['username', 'full_name', 'email', 'role', 'is_active', 'date_joined']
    list_filter = ['role', 'is_active']
    search_fields = ['username', 'email', 'full_name']
    ordering = ['-date_joined']


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'is_active']
    prepopulated_fields = {'slug': ('name',)}


@admin.register(Skill)
class SkillAdmin(admin.ModelAdmin):
    list_display = ['name']
    search_fields = ['name']


@admin.register(FreelancerProfile)
class FreelancerProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'experience_years', 'hourly_rate', 'availability']
    list_filter = ['availability']


@admin.register(Gig)
class GigAdmin(admin.ModelAdmin):
    list_display = ['title', 'freelancer', 'category', 'status', 'created_at']
    list_filter = ['status', 'category']
    search_fields = ['title', 'freelancer__username']


@admin.register(GigPackage)
class GigPackageAdmin(admin.ModelAdmin):
    list_display = ['gig', 'tier', 'price', 'delivery_days', 'revisions']


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ['order_id', 'client', 'freelancer', 'status', 'price', 'deadline', 'created_at']
    list_filter = ['status']
    search_fields = ['order_id', 'client__username', 'freelancer__username']
    ordering = ['-created_at']


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ['transaction_id', 'order', 'client', 'amount', 'status', 'paid_at']
    list_filter = ['status']


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ['order', 'client', 'freelancer', 'rating', 'created_at']
    list_filter = ['rating']


@admin.register(Penalty)
class PenaltyAdmin(admin.ModelAdmin):
    list_display = ['order', 'freelancer', 'order_amount', 'penalty_amount', 'status', 'created_at']
    list_filter = ['status']


@admin.register(BackupAssignment)
class BackupAssignmentAdmin(admin.ModelAdmin):
    list_display = ['order', 'primary_freelancer', 'backup_freelancer', 'assigned_by', 'status', 'assigned_at']
    list_filter = ['status']


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['user', 'title', 'is_read', 'created_at']
    list_filter = ['is_read']


@admin.register(ProjectHistory)
class ProjectHistoryAdmin(admin.ModelAdmin):
    list_display = ['order', 'action', 'performed_by', 'created_at']


admin.site.register(ClientProfile)
admin.site.register(Portfolio)
admin.site.register(Certificate)
admin.site.register(Delivery)
admin.site.register(Revision)
admin.site.register(Message)
