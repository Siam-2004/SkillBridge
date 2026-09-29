from __future__ import annotations
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
ZERO = Decimal('0.00')
CENT = Decimal('0.01')

def to_coin(value) -> Decimal:
    if value is None or value == '':
        raise ValidationError('An amount is required.')
    try:
        amount = Decimal(str(value).strip().replace(',', ''))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValidationError('Enter a valid SkillCoin amount.') from exc
    if not amount.is_finite():
        raise ValidationError('Enter a valid SkillCoin amount.')
    return amount.quantize(CENT, rounding=ROUND_HALF_UP)

def positive_coin(value) -> Decimal:
    amount = to_coin(value)
    if amount <= ZERO:
        raise ValidationError('Amount must be greater than zero.')
    return amount

def fmt_coin(value) -> str:
    return f'{to_coin(value):,.2f}'

class MoneyField(models.DecimalField):

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('max_digits', 14)
        kwargs.setdefault('decimal_places', 2)
        kwargs.setdefault('default', ZERO)
        validators = list(kwargs.pop('validators', []))
        validators.append(MinValueValidator(ZERO))
        kwargs['validators'] = validators
        super().__init__(*args, **kwargs)

    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        kwargs.pop('validators', None)
        for key in ('max_digits', 'decimal_places'):
            kwargs.pop(key, None)
        if kwargs.get('default') == ZERO:
            kwargs.pop('default')
        return (name, path, args, kwargs)

class SignedMoneyField(MoneyField):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.validators = [v for v in self.validators if not isinstance(v, MinValueValidator)]
