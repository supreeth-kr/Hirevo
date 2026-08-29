from django.urls import path
from . import views
from . import api_views

urlpatterns = [
    # Public & Auth
    path('', views.home_view, name='home'),
    path('register/', views.register_view, name='register'),
    path('verify-otp/', views.verify_otp_view, name='verify_otp'),
    path('resend-otp/', views.resend_otp_view, name='resend_otp'),
    path('ajax-send-aadhaar-otp/', views.ajax_send_aadhaar_otp, name='ajax_send_aadhaar_otp'),
    path('ajax-verify-aadhaar-otp/', views.ajax_verify_aadhaar_otp, name='ajax_verify_aadhaar_otp'),
    path('login/', views.login_view, name='login'),

    path('admin-login/', views.admin_login_view, name='admin_login'),
    path('logout/', views.logout_view, name='logout'),
    path('password-reset/', views.password_reset_request_view, name='password_reset'),
    path('verify-reset-otp/', views.verify_reset_otp_view, name='verify_reset_otp'),
    path('reset-password/', views.reset_password_view, name='reset_password'),

    # Public Marketplace
    path('gigs/', views.gig_list_view, name='gig_list'),
    path('gigs/<int:gig_id>/', views.gig_detail_view, name='gig_detail'),
    path('gigs/<int:gig_id>/order/<str:tier>/', views.place_order_view, name='place_order'),
    path('categories/<slug:slug>/', views.category_detail_view, name='category_detail'),
    path('freelancers/<int:user_id>/', views.freelancer_public_profile_view, name='freelancer_public_profile'),
    path('recommendations/', views.recommendation_view, name='recommendations'),

    # Client Workflow
    path('client/dashboard/', views.client_dashboard_view, name='client_dashboard'),
    path('client/profile/', views.client_profile_view, name='client_profile'),
    path('client/orders/', views.client_orders_view, name='client_orders'),
    path('client/orders/<int:order_id>/', views.client_order_detail_view, name='client_order_detail'),
    path('client/orders/<int:order_id>/requirements/', views.submit_order_requirements_view, name='client_submit_requirements'),
    path('client/orders/<int:order_id>/delivery/<int:delivery_id>/approve/', views.approve_delivery_view, name='approve_delivery'),
    path('client/orders/<int:order_id>/delivery/<int:delivery_id>/revision/', views.request_revision_view, name='request_revision'),
    path('client/revision-charges/<int:charge_id>/pay/', views.pay_revision_charge_view, name='pay_revision_charge'),
    path('client/orders/<int:order_id>/review/', views.create_review_view, name='create_review'),
    path('client/payments/', views.client_payments_view, name='client_payments'),
    path('client/reviews/', views.client_reviews_view, name='client_reviews'),
    path('orders/<int:order_id>/pay/', views.simulated_payment_view, name='simulated_payment'),

    # Freelancer Workflow
    path('freelancer/dashboard/', views.freelancer_dashboard_view, name='freelancer_dashboard'),
    path('freelancer/profile/', views.freelancer_profile_view, name='freelancer_profile'),
    path('freelancer/verification/', views.freelancer_verification_view, name='freelancer_verification'),
    path('freelancer/portfolio/', views.freelancer_portfolio_view, name='freelancer_portfolio'),
    path('freelancer/portfolio/<int:item_id>/delete/', views.delete_portfolio_view, name='delete_portfolio'),
    path('freelancer/certificates/', views.freelancer_certificates_view, name='freelancer_certificates'),
    path('freelancer/certificates/<int:cert_id>/delete/', views.delete_certificate_view, name='delete_certificate'),
    path('freelancer/gigs/', views.freelancer_gigs_view, name='freelancer_gigs'),
    path('freelancer/gigs/create/', views.freelancer_gig_create_view, name='freelancer_gig_create'),
    path('freelancer/gigs/<int:gig_id>/edit/', views.freelancer_gig_edit_view, name='freelancer_gig_edit'),
    path('freelancer/gigs/<int:gig_id>/toggle/', views.freelancer_gig_toggle_view, name='freelancer_gig_toggle'),
    path('freelancer/orders/', views.freelancer_orders_view, name='freelancer_orders'),
    path('freelancer/orders/<int:order_id>/', views.freelancer_order_detail_view, name='freelancer_order_detail'),
    path('freelancer/orders/<int:order_id>/respond/<str:action>/', views.freelancer_order_respond_view, name='freelancer_order_respond'),
    path('freelancer/orders/<int:order_id>/deliver/', views.freelancer_delivery_submit_view, name='freelancer_delivery_submit'),
    path('freelancer/earnings/', views.freelancer_earnings_view, name='freelancer_earnings'),
    path('freelancer/backup-assignments/', views.freelancer_backup_assignments_view, name='freelancer_backup_assignments'),
    path('freelancer/backup-assignments/<int:assignment_id>/<str:action>/', views.freelancer_backup_respond_view, name='freelancer_backup_respond'),

    # Administrator Workflow
    path('admin-dashboard/', views.admin_dashboard_view, name='admin_dashboard'),
    path('admin-dashboard/users/', views.admin_users_view, name='admin_users'),
    path('admin-dashboard/users/<int:user_id>/toggle/', views.admin_user_toggle_active_view, name='admin_user_toggle'),
    path('admin-dashboard/clients/', views.admin_clients_view, name='admin_clients'),
    path('admin-dashboard/freelancers/', views.admin_freelancers_view, name='admin_freelancers'),
    path('admin-dashboard/verifications/', views.admin_verifications_view, name='admin_verifications'),
    path('admin-dashboard/verifications/<int:verification_id>/<str:action>/', views.admin_verification_review_view, name='admin_verification_review'),
    path('admin-dashboard/verifications/<int:verification_id>/file/<str:file_type>/', views.admin_verification_file_view, name='admin_verification_file'),
    path('admin-dashboard/gigs/', views.admin_gigs_view, name='admin_gigs'),
    path('admin-dashboard/gigs/<int:gig_id>/toggle/', views.admin_gig_toggle_view, name='admin_gig_toggle'),
    path('admin-dashboard/orders/', views.admin_orders_view, name='admin_orders'),
    path('admin-dashboard/orders/<int:order_id>/', views.admin_order_detail_view, name='admin_order_detail'),
    path('admin-dashboard/delayed/', views.admin_delayed_projects_view, name='admin_delayed_projects'),
    path('admin-dashboard/orders/<int:order_id>/assign-backup/', views.admin_assign_backup_view, name='admin_assign_backup'),
    path('admin-dashboard/penalties/', views.admin_penalties_view, name='admin_penalties'),
    path('admin-dashboard/backup-assignments/', views.admin_backup_assignments_view, name='admin_backup_assignments'),
    path('admin-dashboard/payments/', views.admin_payments_view, name='admin_payments'),
    path('admin-dashboard/categories/', views.admin_categories_view, name='admin_categories'),
    path('admin-dashboard/reviews/', views.admin_reviews_view, name='admin_reviews'),

    # Messaging
    path('messages/', views.messages_inbox_view, name='messages_inbox'),
    path('messages/<int:user_id>/', views.messages_thread_view, name='messages_thread'),

    # Notifications
    path('notifications/', views.notifications_list_view, name='notifications_list'),
    path('notifications/<int:notification_id>/read/', views.notification_mark_read_view, name='notification_mark_read'),
    path('notifications/read-all/', views.notifications_mark_all_read_view, name='notifications_mark_all_read'),

    # REST APIs
    path('api/categories/', api_views.CategoryListAPIView.as_view(), name='api_categories'),
    path('api/gigs/', api_views.GigListAPIView.as_view(), name='api_gigs'),
    path('api/gigs/<int:pk>/', api_views.GigDetailAPIView.as_view(), name='api_gig_detail'),
    path('api/freelancers/', api_views.FreelancerListAPIView.as_view(), name='api_freelancers'),
    path('api/freelancers/<int:user__id>/', api_views.FreelancerDetailAPIView.as_view(), name='api_freelancer_detail'),
    path('api/orders/', api_views.OrderListAPIView.as_view(), name='api_orders'),
    path('api/recommendations/', api_views.AIRecommendationAPIView.as_view(), name='api_recommendations'),
]
