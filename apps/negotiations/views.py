from __future__ import annotations
from django.contrib import messages
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods
from apps.core.exceptions import PermissionDenied
from apps.core.permissions import verified_required
from apps.core.views import handle_domain_errors, paginate
from apps.negotiations import services
from apps.negotiations.forms import OfferForm
from apps.negotiations.models import Negotiation
from apps.proposals.models import Proposal

def _party(negotiation, user):
    if user.pk not in {negotiation.client_id, negotiation.freelancer_id}:
        if not user.is_platform_admin:
            raise PermissionDenied('You are not part of this negotiation.')
    return negotiation

@verified_required
def negotiation_list(request):
    rows = Negotiation.objects.filter(Q(client=request.user) | Q(freelancer=request.user)).select_related('job', 'client', 'freelancer', 'current_offer').order_by('-updated_at')
    page, querystring = paginate(request, rows, 15)
    return render(request, 'negotiations/list.html', {'page': page, 'querystring': querystring, 'nav': 'negotiations', 'page_title': 'Negotiations'})

@verified_required
@handle_domain_errors
@require_http_methods(['POST'])
def open_room(request, proposal_id):
    proposal = get_object_or_404(Proposal, public_id=proposal_id, job__client=request.user)
    negotiation = services.open_negotiation(proposal=proposal, actor=request.user)
    return redirect(negotiation.get_absolute_url())

@verified_required
@handle_domain_errors
def room(request, public_id):
    negotiation = get_object_or_404(Negotiation.objects.select_related('job', 'proposal', 'client', 'freelancer', 'current_offer'), public_id=public_id)
    _party(negotiation, request.user)
    current = negotiation.current_offer
    my_turn = bool(current and negotiation.is_active and (current.receiver_id == request.user.pk) and (current.status == current.Status.ACTIVE))
    initial = {}
    if current:
        initial = {'amount': current.amount, 'deadline': current.deadline, 'deliverables': current.deliverables, 'revision_limit': current.revision_limit, 'requirements': current.requirements}
    from apps.agreements.models import Agreement
    agreement = Agreement.objects.filter(job=negotiation.job, freelancer=negotiation.freelancer).first()
    from apps.messaging.models import Conversation
    conversation = Conversation.objects.filter(job=negotiation.job, participants__user=negotiation.freelancer).first()
    return render(request, 'negotiations/room.html', {'negotiation': negotiation, 'offers': negotiation.offers.select_related('sender', 'receiver').order_by('created_at'), 'current': current, 'my_turn': my_turn, 'form': OfferForm(initial=initial), 'is_client': request.user.pk == negotiation.client_id, 'agreement': agreement, 'conversation': conversation, 'nav': 'negotiations', 'page_title': f'Negotiation — {negotiation.job.title}'})

@verified_required
@handle_domain_errors
@require_http_methods(['POST'])
def counter(request, public_id):
    negotiation = get_object_or_404(Negotiation, public_id=public_id)
    _party(negotiation, request.user)
    form = OfferForm(request.POST)
    if not form.is_valid():
        messages.error(request, 'Check the offer details and try again.')
        return redirect(negotiation.get_absolute_url())
    services.send_offer(negotiation=negotiation, sender=request.user, **form.cleaned_data)
    messages.success(request, 'Counter offer sent.')
    return redirect(negotiation.get_absolute_url())

@verified_required
@handle_domain_errors
@require_http_methods(['POST'])
def accept(request, public_id):
    negotiation = get_object_or_404(Negotiation, public_id=public_id)
    _party(negotiation, request.user)
    agreement = services.accept_offer(offer=negotiation.current_offer, actor=request.user)
    messages.success(request, 'Offer accepted. The agreement is now locked — changes need an approved modification from here on.')
    return redirect(agreement.get_absolute_url())

@verified_required
@handle_domain_errors
@require_http_methods(['POST'])
def reject(request, public_id):
    negotiation = get_object_or_404(Negotiation, public_id=public_id)
    _party(negotiation, request.user)
    services.reject_offer(offer=negotiation.current_offer, actor=request.user, note=request.POST.get('note', ''))
    messages.info(request, 'Offer rejected.')
    return redirect(negotiation.get_absolute_url())

@verified_required
@handle_domain_errors
@require_http_methods(['POST'])
def cancel(request, public_id):
    negotiation = get_object_or_404(Negotiation, public_id=public_id)
    _party(negotiation, request.user)
    services.cancel_negotiation(negotiation=negotiation, actor=request.user, reason=request.POST.get('reason', ''))
    messages.info(request, 'Negotiation closed.')
    return redirect('negotiations:list')
