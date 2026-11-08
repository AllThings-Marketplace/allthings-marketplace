from django.urls import path
from . import ops_views

app_name = 'ops'

urlpatterns = [
    path('', ops_views.ops_overview, name='overview'),
    path('kyc/', ops_views.kyc_moderation_list, name='kyc_list'),
    path('kyc/<int:profile_id>/', ops_views.kyc_dossier_detail, name='kyc_detail'),
    path('listings/', ops_views.listing_moderation_list, name='listing_list'),
    path('listings/<str:item_type>/<int:item_id>/action/', ops_views.moderate_listing_action, name='moderate_listing'),
    path('disputes/', ops_views.disputes_arbitration_list, name='disputes_list'),
]