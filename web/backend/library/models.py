import uuid

from django.conf import settings
from django.db import models


class OwnedModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True


class Device(OwnedModel):
    class Platform(models.TextChoices):
        MAC = "mac", "Mac"
        IPHONE = "iphone", "iPhone"
        IPAD = "ipad", "iPad"

    name = models.CharField(max_length=120)
    platform = models.CharField(max_length=12, choices=Platform.choices)
    last_seen_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["name"]


class Folder(OwnedModel):
    name = models.CharField(max_length=120)
    instructions_md = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        constraints = [models.UniqueConstraint(fields=["owner", "name"], name="unique_folder_per_owner")]


class FileRecord(OwnedModel):
    class Status(models.TextChoices):
        NEW = "new", "New"
        SORTED = "sorted", "Sorted"
        OTHER = "other", "Other"

    name = models.CharField(max_length=255)
    source_device = models.ForeignKey(Device, on_delete=models.SET_NULL, null=True, blank=True)
    source_kind = models.CharField(max_length=32, default="unknown")
    mime_type = models.CharField(max_length=120, blank=True)
    size_bytes = models.PositiveBigIntegerField(null=True, blank=True)
    sha256 = models.CharField(max_length=64, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.NEW)
    folder = models.ForeignKey(Folder, on_delete=models.SET_NULL, null=True, blank=True)
    classification_reason = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]


class ReviewRequest(OwnedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        ANSWERED = "answered", "Answered"

    file = models.OneToOneField(FileRecord, on_delete=models.CASCADE, related_name="review")
    question = models.TextField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    answer = models.TextField(blank=True)
    answered_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

class AgentLink(OwnedModel):
    """A Mac bridge identity and its latest local-agent snapshot."""
    label = models.CharField(max_length=120, default="Mac agent")
    token_hash = models.CharField(max_length=64, unique=True)
    snapshot = models.JSONField(default=dict)
    last_seen_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]


class AgentCommand(OwnedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        RUNNING = "running", "Running"
        DONE = "done", "Done"
        FAILED = "failed", "Failed"

    link = models.ForeignKey(AgentLink, on_delete=models.CASCADE, related_name="commands")
    action = models.CharField(max_length=24)
    payload = models.JSONField(default=dict)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    result = models.JSONField(default=dict)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]


class AppleIdentity(models.Model):
    """Apple subject, never an email address, is the account identifier."""
    subject = models.CharField(max_length=255, unique=True)
    owner = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)


class AppleLoginAttempt(models.Model):
    state_hash = models.CharField(max_length=64, unique=True)
    browser_hash = models.CharField(max_length=64)
    nonce = models.CharField(max_length=128)
    expires_at = models.DateTimeField()
    consumed_at = models.DateTimeField(null=True)


class MacPairing(OwnedModel):
    secret_hash = models.CharField(max_length=64, unique=True)
    expires_at = models.DateTimeField()
    consumed_at = models.DateTimeField(null=True)


class OnboardingProgress(models.Model):
    owner = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    initial_cleanup_confirmed = models.BooleanField(default=False)
    iphone_icloud_confirmed = models.BooleanField(default=False)
    test_started_at = models.DateTimeField(null=True)
    baseline_assets = models.JSONField(default=list)
    completed_at = models.DateTimeField(null=True)
