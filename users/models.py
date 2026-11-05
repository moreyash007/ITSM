from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = 'admin', 'Admin'
        AGENT = 'agent', 'Agent'
        END_USER = 'end_user', 'End User'

    role = models.CharField(max_length=20, choices=Role.choices, default=Role.END_USER)
    department = models.CharField(max_length=100, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True)

    @property
    def is_admin_role(self):
        return self.role == self.Role.ADMIN

    @property
    def is_agent(self):
        return self.role in [self.Role.ADMIN, self.Role.AGENT]

    def __str__(self):
        return f"{self.get_full_name() or self.username} ({self.get_role_display()})"
