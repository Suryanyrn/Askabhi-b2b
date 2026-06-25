import uuid
from django.db import models
from django.contrib.auth.models import User
from onboarding.models import Company

class AuditLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name='audit_logs')
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    user_name = models.CharField(max_length=200) # Store name so if user is deleted we still have it
    role = models.CharField(max_length=50) # 'ADMIN' or 'MANAGER'
    action = models.CharField(max_length=500)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.role} {self.user_name}: {self.action} at {self.timestamp}"
