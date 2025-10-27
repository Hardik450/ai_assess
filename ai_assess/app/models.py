from django.db import models

# Create your models here.
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.contrib.postgres.fields import JSONField
# Create your models here.

class CustomUser(AbstractUser):
    name = models.CharField(max_length=128)
    phone_number = models.CharField(max_length=20)
    email = models.EmailField(unique=True)
    age = models.PositiveIntegerField(null=True, blank=True)
    gender = models.CharField(
        max_length=50,
        choices = [("male", "Male"), ("female", "Female"), ("other", "Other")],
        default="other",
        null=True,
        blank=True
    )
    country = models.CharField(max_length=50, null=True, blank=True)
    language = models.CharField(max_length=100, null=True, blank=True, default='English')
    role = models.CharField(max_length=50, choices=[("teacher","Teacher"), ("student","Student")], null=True, blank=True)
    profile_picture = models.CharField(max_length=256, null=True, blank=True)
    profile_picture_text = models.TextField(null=True, blank=True)

class AssessmentContent(models.Model):
    STATUS_CHOICES = [
        ("In progress", "In progress"),
        ("Reviewed", "Reviewed"),
        ("Completed", "Completed")
    ]

    user = models.ForeignKey("app.CustomUser", on_delete=models.CASCADE, related_name="assessments")
    teacher = models.EmailField()
    assessment = models.FileField(upload_to="assessments/")
    assess_text_file = models.FilePathField(path="media/assessment_texts/", null=True, blank=True, max_length=256)
    feedback = models.JSONField(default=dict)
    score = models.FloatField(default=0)
    status = models.CharField(max_length=100, choices=STATUS_CHOICES, default="In progress")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)