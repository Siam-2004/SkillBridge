from __future__ import annotations
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods
from apps.agreements import services
from apps.agreements.models import Agreement
from apps.core.exceptions import PermissionDenied
from apps.core.permissions import freelancer_required, verified_required
from apps.core.views import handle_domain_errors, paginate

@freelancer_required
def my_contracts(request):
    status_filter = request.GET.get('status', '')
    qs = Agreement.objects.filter(freelancer=request.user).select_related('job', 'client', 'offer').order_by('-created_at')
    if status_filter:
        qs = qs.filter(status=status_filter)
    page, querystring = paginate(request, qs, 15)
    counts = {'all': Agreement.objects.filter(freelancer=request.user).count(), 'active': Agreement.objects.filter(freelancer=request.user, status=Agreement.Status.ACTIVE).count(), 'in_progress': Agreement.objects.filter(freelancer=request.user, status=Agreement.Status.IN_PROGRESS).count(), 'completed': Agreement.objects.filter(freelancer=request.user, status=Agreement.Status.COMPLETED).count()}
    return render(request, 'agreements/my_contracts.html', {'page': page, 'querystring': querystring, 'counts': counts, 'current_status': status_filter, 'nav': 'contracts', 'page_title': 'Accepted Jobs & Contracts'})

def _agreement_party(agreement, user):
    if user.pk not in {agreement.client_id, agreement.freelancer_id}:
        if not user.is_platform_admin:
            raise PermissionDenied('You are not a party to this agreement.')
    return agreement

@verified_required
@handle_domain_errors
def agreement_detail(request, public_id):
    agreement = get_object_or_404(Agreement.objects.select_related('job', 'client', 'freelancer', 'offer', 'payment_transaction').prefetch_related('attachments'), public_id=public_id)
    _agreement_party(agreement, request.user)
    is_client = request.user.pk == agreement.client_id
    is_freelancer = request.user.pk == agreement.freelancer_id
    from apps.messaging.models import Conversation
    conversation = Conversation.objects.filter(job=agreement.job, participants__user=agreement.freelancer).first()
    return render(request, 'agreements/detail.html', {'agreement': agreement, 'job': agreement.job, 'is_client': is_client, 'is_freelancer': is_freelancer, 'conversation': conversation, 'nav': 'jobs', 'page_title': f'Agreement — {agreement.job.title}'})

@verified_required
@handle_domain_errors
@require_http_methods(['POST'])
def submit_work_view(request, public_id):
    agreement = get_object_or_404(Agreement, public_id=public_id)
    _agreement_party(agreement, request.user)
    submission_text = request.POST.get('work_submission', '')
    submission_link = request.POST.get('submission_link', '')
    files = request.FILES.getlist('files')
    if not files and 'file' in request.FILES:
        files = [request.FILES['file']]
    services.submit_work(agreement=agreement, freelancer=request.user, submission_text=submission_text, submission_link=submission_link, files=files)
    messages.success(request, 'Your deliverables have been submitted! The client will review your work and release the payment.')
    return redirect('agreements:detail', public_id=agreement.public_id)

@verified_required
@handle_domain_errors
@require_http_methods(['POST'])
def approve_and_pay_view(request, public_id):
    agreement = get_object_or_404(Agreement, public_id=public_id)
    _agreement_party(agreement, request.user)
    feedback = request.POST.get('feedback', '')
    services.complete_agreement_and_release_payment(agreement=agreement, client=request.user, feedback=feedback)
    messages.success(request, f'Deliverables approved! Payment of {agreement.amount:,.2f} SkillCoin has been released to {agreement.freelancer.full_name}.')
    return redirect('agreements:detail', public_id=agreement.public_id)
