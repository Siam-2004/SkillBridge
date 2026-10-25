from django.test import TestCase, RequestFactory
from django.contrib.auth import get_user_model
from django.contrib.admin.sites import AdminSite
from apps.wallets.models import WalletTransaction
from apps.wallets.admin import WalletTransactionAdmin

User = get_user_model()

class US28AdminTransactionHistoryTest(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.site = AdminSite()
        self.admin_user = User.objects.create_superuser(
            username='fin_admin',
            email='admin@fin.com',
            password='Password123!'
        )
        self.admin = WalletTransactionAdmin(WalletTransaction, self.site)

    def test_admin_transaction_interface_is_strictly_immutable(self):
        """US-28: Authorized users can trace financial history without modifying previous records."""
        request = self.factory.get('/admin/wallets/wallettransaction/')
        request.user = self.admin_user

        # Records cannot be added manually via admin interface
        self.assertFalse(self.admin.has_add_permission(request))

        # Records cannot be modified or altered via admin interface
        self.assertFalse(self.admin.has_change_permission(request))

        # Records cannot be deleted or purged via admin interface
        self.assertFalse(self.admin.has_delete_permission(request))

    def test_admin_transaction_interface_provides_traceable_fields(self):
        """US-28: Admin transaction interface includes searching, filtering, and audit details."""
        self.assertIn('transaction_type', self.admin.list_display)
        self.assertIn('amount', self.admin.list_display)
        self.assertIn('created_at', self.admin.list_display)
        self.assertIn('internal_transaction_id', self.admin.search_fields)
        self.assertTrue(len(self.admin.list_filter) > 0)