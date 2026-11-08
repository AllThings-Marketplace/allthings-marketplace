from django.urls import path
from . import views

app_name = 'ops'

urlpatterns = [
    path('', views.ops_overview, name='overview'),
    path('kyc/', views.kyc_moderation_list, name='kyc_list'),
    path('kyc/<int:profile_id>/', views.kyc_dossier_detail, name='kyc_detail'),
    path('listings/', views.listing_moderation_list, name='listing_list'),
    path('listings/<str:item_type>/<int:item_id>/action/', views.moderate_listing_action, name='moderate_listing'),
    path('disputes/', views.disputes_arbitration_list, name='disputes_list'),
]