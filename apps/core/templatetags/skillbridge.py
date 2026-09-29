from __future__ import annotations
from django import template
from django.conf import settings
from django.utils import timezone
from django.utils.html import escape
from django.utils.safestring import mark_safe
from apps.core.money import fmt_coin
register = template.Library()

@register.filter(name='coin')
def coin(value):
    try:
        return fmt_coin(value or 0)
    except Exception:
        return '0.00'

@register.filter(name='coins')
def coins(value):
    return f"{coin(value)} {settings.SKILLCOIN['CODE']}"

@register.filter(name='attr')
def attr(obj, name):
    try:
        value = getattr(obj, name)
    except (AttributeError, TypeError):
        return ''
    return value if callable(value) else value

@register.filter(name='key')
def key(mapping, lookup):
    try:
        return mapping.get(lookup)
    except AttributeError:
        return None

@register.filter(name='split')
def split(value, separator=','):
    return [part.strip() for part in str(value or '').split(separator) if part.strip()]

@register.filter(name='pct')
def pct(value, total):
    try:
        total = float(total or 0)
        if total <= 0:
            return 0
        return round(float(value or 0) / total * 100, 1)
    except (TypeError, ValueError):
        return 0

@register.filter(name='stars')
def stars(value):
    try:
        rating = float(value or 0)
    except (TypeError, ValueError):
        rating = 0.0
    full = int(rating)
    half = 1 if rating - full >= 0.5 else 0
    empty = 5 - full - half
    html = '<span class="sb-stars" role="img" aria-label="%s out of 5">%s%s%s</span>' % (f'{rating:.1f}', '<span class="sb-star is-full">★</span>' * full, '<span class="sb-star is-half">★</span>' * half, '<span class="sb-star is-empty">★</span>' * empty)
    return mark_safe(html)

@register.filter(name='countdown')
def countdown(value):
    if not value:
        return '—'
    delta = value - timezone.now()
    seconds = int(delta.total_seconds())
    if seconds <= 0:
        return 'Elapsed'
    days, rem = divmod(seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes = rem // 60
    if days:
        return f'{days}d {hours}h'
    if hours:
        return f'{hours}h {minutes}m'
    return f'{minutes}m'

@register.filter(name='is_overdue')
def is_overdue(value):
    return bool(value and value < timezone.now())

@register.simple_tag(name='status_pill')
def status_pill(value, label=None):
    key = (value or '').upper()
    tone = STATUS_TONES.get(key, 'neutral')
    text = escape(label or key.replace('_', ' ').title())
    return mark_safe(f'<span class="sb-pill sb-pill--{tone}">{text}</span>')
STATUS_TONES = {'DRAFT': 'neutral', 'TODO': 'neutral', 'CLOSED': 'neutral', 'ARCHIVED': 'neutral', 'WITHDRAWN': 'neutral', 'EXPIRED': 'neutral', 'COUNTERED': 'neutral', 'OPEN': 'info', 'ACTIVE': 'info', 'IN_PROGRESS': 'info', 'SUBMITTED': 'info', 'UNDER_REVIEW': 'info', 'NEGOTIATING': 'info', 'PROCESSING': 'info', 'PROPOSAL_RECEIVED': 'info', 'READY_FOR_REVIEW': 'info', 'HIRED': 'info', 'PENDING': 'warn', 'AWAITING_CLIENT_ACTION': 'warn', 'REVISION_REQUIRED': 'warn', 'AUTO_RELEASE_PENDING': 'warn', 'ON_HOLD': 'warn', 'PENDING_REVIEW': 'warn', 'APPROVED': 'ok', 'ACCEPTED': 'ok', 'COMPLETED': 'ok', 'RELEASED': 'ok', 'PAID': 'ok', 'VERIFIED': 'ok', 'FUNDED': 'ok', 'REJECTED': 'danger', 'CANCELLED': 'danger', 'DISPUTED': 'danger', 'FAILED': 'danger', 'SUSPENDED': 'danger', 'BANNED': 'danger', 'REFUNDED': 'danger'}
