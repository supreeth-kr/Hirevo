from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, EmailOTP

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ('Email Verification', {'fields': ('email_verified', 'email_verified_at')}),
        ('Extra', {'fields': ('phone', 'country', 'description', 'image', 'is_seller')}),
    )
    list_filter = UserAdmin.list_filter + ('email_verified',)
    list_display = ('username', 'email', 'email_verified', 'is_seller', 'is_active')


@admin.register(EmailOTP)
class EmailOTPAdmin(admin.ModelAdmin):
    list_display = ('email', 'is_used', 'is_expired', 'created_at', 'expires_at')
    list_filter = ('is_used', 'created_at')
    search_fields = ('email',)
    readonly_fields = ('created_at', 'verified_at')
