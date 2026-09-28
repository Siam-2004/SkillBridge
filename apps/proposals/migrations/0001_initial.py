import apps.core.money
import django.db.models.deletion
import django.utils.timezone
import uuid
from decimal import Decimal
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('marketplace', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Proposal',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(db_index=True, default=django.utils.timezone.now, editable=False)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('public_id', models.UUIDField(db_index=True, default=uuid.uuid4, editable=False, unique=True)),
                ('cover_letter', models.TextField(help_text='Explain your approach, relevant experience, and why you are the best fit.', max_length=5000)),
                ('proposed_amount', apps.core.money.MoneyField(decimal_places=2, max_digits=12)),
                ('estimated_days', models.PositiveSmallIntegerField(default=7, help_text='Estimated working days to complete the job.')),
                ('deliverables', models.TextField(blank=True, help_text='List of deliverables or milestones proposed, one per line.', max_length=3000)),
                ('revision_limit', models.PositiveSmallIntegerField(default=2, help_text='Number of free review/revision rounds included.')),
                ('additional_message', models.TextField(blank=True, help_text='Optional note regarding availability, calls, or prerequisites.', max_length=2000)),
                ('status', models.CharField(choices=[('SUBMITTED', 'Submitted'), ('UNDER_REVIEW', 'Under review'), ('NEGOTIATING', 'Negotiating'), ('ACCEPTED', 'Accepted'), ('REJECTED', 'Rejected'), ('WITHDRAWN', 'Withdrawn')], db_index=True, default='SUBMITTED', max_length=20)),
                ('rejection_reason', models.TextField(blank=True)),
                ('responded_at', models.DateTimeField(blank=True, null=True)),
                ('freelancer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='proposals', to=settings.AUTH_USER_MODEL)),
                ('job', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='proposals', to='marketplace.job')),
            ],
            options={
                'ordering': ('-created_at',),
            },
        ),
        migrations.CreateModel(
            name='ProposalAttachment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(db_index=True, default=django.utils.timezone.now, editable=False)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('file', models.FileField(upload_to='proposals/%Y/%m/')),
                ('original_name', models.CharField(max_length=255)),
                ('size_bytes', models.PositiveBigIntegerField(default=0)),
                ('content_type', models.CharField(blank=True, max_length=120)),
                ('proposal', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='attachments', to='proposals.proposal')),
            ],
            options={
                'ordering': ('created_at',),
            },
        ),
        migrations.AddIndex(
            model_name='proposal',
            index=models.Index(fields=['job', 'status'], name='proposals_p_job_id_244837_idx'),
        ),
        migrations.AddIndex(
            model_name='proposal',
            index=models.Index(fields=['freelancer', 'status'], name='proposals_p_freelan_41935c_idx'),
        ),
        migrations.AddIndex(
            model_name='proposal',
            index=models.Index(fields=['status', '-created_at'], name='proposals_p_status_ee132f_idx'),
        ),
        migrations.AddConstraint(
            model_name='proposal',
            constraint=models.CheckConstraint(check=models.Q(('proposed_amount__gt', Decimal('0'))), name='proposal_amount_positive'),
        ),
        migrations.AddConstraint(
            model_name='proposal',
            constraint=models.CheckConstraint(check=models.Q(('estimated_days__gte', 1)), name='proposal_estimated_days_positive'),
        ),
        migrations.AddConstraint(
            model_name='proposal',
            constraint=models.UniqueConstraint(condition=models.Q(('status', 'WITHDRAWN'), _negated=True), fields=('job', 'freelancer'), name='unique_active_proposal_per_job'),
        ),
    ]
