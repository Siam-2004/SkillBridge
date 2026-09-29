from __future__ import annotations
from django import forms
from apps.core.money import ZERO, positive_coin
from apps.proposals.models import Proposal

class ProposalForm(forms.ModelForm):

    class Meta:
        model = Proposal
        fields = ['proposed_amount', 'estimated_days', 'deliverables', 'revision_limit', 'cover_letter', 'additional_message']
        widgets = {'proposed_amount': forms.NumberInput(attrs={'step': '0.01', 'min': '1'}), 'estimated_days': forms.NumberInput(attrs={'min': '1'}), 'deliverables': forms.Textarea(attrs={'rows': 4, 'placeholder': 'List what you will produce and deliver (one per line).'}), 'cover_letter': forms.Textarea(attrs={'rows': 6, 'placeholder': 'Explain your relevant experience, proposed technical solution, and delivery roadmap.'}), 'additional_message': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Optional message (e.g. your working hours, preferred communication tool).'})}
        help_texts = {'proposed_amount': 'Your total bid in SkillCoin (1 SKC = 1 BDT).', 'estimated_days': 'Number of business/calendar days you need to deliver.', 'revision_limit': 'Free revision rounds you commit to provide.', 'deliverables': 'Clear milestones and output items.'}

    def clean_proposed_amount(self):
        amount = self.cleaned_data.get('proposed_amount')
        if amount is None or amount <= ZERO:
            raise forms.ValidationError('Proposed amount must be greater than zero.')
        return positive_coin(amount)

    def clean_estimated_days(self):
        days = self.cleaned_data.get('estimated_days')
        if days is None or days < 1:
            raise forms.ValidationError('Estimated days must be at least 1.')
        return days

    def clean_cover_letter(self):
        letter = (self.cleaned_data.get('cover_letter') or '').strip()
        if len(letter) < 30:
            raise forms.ValidationError('Please provide a meaningful cover letter (at least 30 characters).')
        return letter
