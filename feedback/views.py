from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import transaction

from marketplace.models import ProductImage
from marketplace.validators import validate_product_image
from marketplace.views import inspect_chat_safety
from orders.models import OrderItem, ServiceOrder
from .models import Feedback, FeedbackAttribute, FeedbackPhoto


def _clamp_rating(raw_val, default=5):
    """Ensures submitted star ratings are always valid integers between 1 and 5."""
    try:
        return max(1, min(5, int(raw_val)))
    except (ValueError, TypeError):
        return default


@login_required
def product_feedback_view(request, item_id):
    item = get_object_or_404(
        OrderItem.objects.select_related('product__provider__user', 'order'),
        id=item_id,
        order__customer=request.user,
    )

    if item.status not in ['DELIVERED', 'COMPLETED']:
        messages.error(request, "You can only review products that have been delivered or completed.")
        return redirect('orders:order_details', order_id=item.order_id)

    if hasattr(item, 'feedback'):
        messages.info(request, "You have already reviewed this product.")
        return redirect('feedback:pending_reviews')

    if request.method == 'POST':
        public_review = request.POST.get('public_review', '').strip()
        private_feedback = request.POST.get('private_feedback', '').strip()
        overall_rating = _clamp_rating(request.POST.get('overall_rating', 5))

        is_flagged, flag_msg = inspect_chat_safety(f"{public_review} {private_feedback}")
        if is_flagged:
            messages.error(request, flag_msg)
            return render(request, 'feedback/product_form.html', {'item': item})

        photo = request.FILES.get('feedback_photo')
        if photo:
            try:
                validate_product_image(photo)
            except ValidationError as exc:
                err = exc.messages[0] if hasattr(exc, 'messages') else str(exc)
                messages.error(request, err)
                return render(request, 'feedback/product_form.html', {'item': item})

        try:
            with transaction.atomic():
                feedback = Feedback.objects.create(
                    customer=request.user,
                    target_provider=item.product.provider.user,
                    transaction_type=Feedback.TransactionType.PRODUCT,
                    order_item=item,
                    product=item.product,
                    overall_rating=overall_rating,
                    public_review=public_review,
                    private_feedback=private_feedback,
                    is_verified=True,
                    status=Feedback.ModerationStatus.APPROVED,
                )

                attributes = {
                    'Product Quality': _clamp_rating(request.POST.get('attr_quality', 5)),
                    'As Described': _clamp_rating(request.POST.get('attr_described', 5)),
                    'Delivery Experience': _clamp_rating(request.POST.get('attr_delivery', 5)),
                }

                for name, rating in attributes.items():
                    FeedbackAttribute.objects.create(
                        feedback=feedback,
                        attribute_name=name,
                        rating=rating,
                    )

                if photo:
                    FeedbackPhoto.objects.create(feedback=feedback, image=photo)

            messages.success(request, f"Thank you! Your verified review for '{item.product.name}' is now live.")
            return redirect('marketplace:product_detail', slug=item.product.slug)

        except Exception as e:
            messages.error(request, f"Error saving review: {str(e)}")

    return render(request, 'feedback/product_form.html', {'item': item})


@login_required
def service_feedback_view(request, service_order_id):
    service_order = get_object_or_404(
        ServiceOrder.objects.select_related('service', 'provider__user'),
        id=service_order_id,
        customer=request.user,
        status='CONFIRMED',
    )

    if hasattr(service_order, 'feedback'):
        messages.info(request, "You have already reviewed this service.")
        return redirect('feedback:pending_reviews')

    if request.method == 'POST':
        public_review = request.POST.get('public_review', '').strip()
        private_feedback = request.POST.get('private_feedback', '').strip()
        overall_rating = _clamp_rating(request.POST.get('overall_rating', 5))

        is_flagged, flag_msg = inspect_chat_safety(f"{public_review} {private_feedback}")
        if is_flagged:
            messages.error(request, flag_msg)
            return render(request, 'feedback/service_form.html', {'job': service_order})

        photo = request.FILES.get('feedback_photo')
        if photo:
            try:
                validate_product_image(photo)
            except ValidationError as exc:
                err = exc.messages[0] if hasattr(exc, 'messages') else str(exc)
                messages.error(request, err)
                return render(request, 'feedback/service_form.html', {'job': service_order})

        try:
            with transaction.atomic():
                feedback = Feedback.objects.create(
                    customer=request.user,
                    target_provider=service_order.provider.user,
                    transaction_type=Feedback.TransactionType.SERVICE,
                    service_order=service_order,
                    service=service_order.service,
                    overall_rating=overall_rating,
                    public_review=public_review,
                    private_feedback=private_feedback,
                    is_verified=True,
                    status=Feedback.ModerationStatus.APPROVED,
                )

                attributes = {
                    'Professionalism': _clamp_rating(request.POST.get('attr_professionalism', 5)),
                    'Quality of Work': _clamp_rating(request.POST.get('attr_quality', 5)),
                    'Punctuality': _clamp_rating(request.POST.get('attr_punctuality', 5)),
                    'Communication': _clamp_rating(request.POST.get('attr_communication', 5)),
                }

                for name, rating in attributes.items():
                    FeedbackAttribute.objects.create(
                        feedback=feedback,
                        attribute_name=name,
                        rating=rating,
                    )

                if photo:
                    FeedbackPhoto.objects.create(feedback=feedback, image=photo)

            messages.success(request, f"Thank you! Your verified review for '{service_order.service.name}' is now live.")
            if service_order.service and service_order.service.slug:
                return redirect('marketplace:service_detail', slug=service_order.service.slug)
            return redirect('feedback:pending_reviews')

        except Exception as e:
            messages.error(request, f"Error saving review: {str(e)}")

    return render(request, 'feedback/service_form.html', {'job': service_order})


@login_required
def pending_reviews_list(request):
    pending_products = (
        OrderItem.objects.filter(
            order__customer=request.user,
            feedback__isnull=True,
            status__in=['DELIVERED', 'COMPLETED'],
            product__isnull=False,
        )
        .select_related('product__provider', 'order')
        .prefetch_related('product__images')
        .order_by('-order__created_at')
    )

    pending_services = (
        ServiceOrder.objects.filter(
            customer=request.user,
            feedback__isnull=True,
            status='CONFIRMED',
            service__isnull=False,
        )
        .select_related('service', 'provider')
        .order_by('-completed_at', '-created_at')
    )

    submitted_reviews = (
        Feedback.objects.filter(customer=request.user)
        .select_related('product', 'service', 'target_provider__provider_profile')
        .prefetch_related('attributes', 'photos')
        .order_by('-created_at')[:10]
    )

    context = {
        'pending_products': pending_products,
        'pending_services': pending_services,
        'submitted_reviews': submitted_reviews,
    }
    return render(request, 'feedback/pending_reviews.html', context)