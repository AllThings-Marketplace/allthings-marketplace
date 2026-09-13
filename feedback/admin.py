from django.contrib import admin
from .models import Feedback, FeedbackAttribute, FeedbackPhoto

class FeedbackAttributeInline(admin.TabularInline):
    model = FeedbackAttribute
    extra = 0
    # Keeps attributes read-only so admins don't accidentally alter a customer's score
    readonly_fields = ('attribute_name', 'rating') 

class FeedbackPhotoInline(admin.TabularInline):
    model = FeedbackPhoto
    extra = 0

@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display = ['customer', 'target_provider', 'transaction_type', 'overall_rating', 'is_verified', 'created_at']
    list_filter = ['is_verified', 'transaction_type', 'overall_rating', 'created_at']
    search_fields = ['customer__username', 'target_provider__username', 'public_review', 'private_feedback']
    inlines = [FeedbackAttributeInline, FeedbackPhotoInline]
    
    # Custom bulk actions for the moderation team
    actions = ['approve_feedback', 'hide_feedback']
    
    def approve_feedback(self, request, queryset):
        queryset.update(is_verified=True)
    approve_feedback.short_description = "Approve selected feedback (Make public)"
    
    def hide_feedback(self, request, queryset):
        queryset.update(is_verified=False)
    hide_feedback.short_description = "Hide selected feedback (Remove from public)"