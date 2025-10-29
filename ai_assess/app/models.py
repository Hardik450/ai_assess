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


class Assignment(models.Model):
    author = models.ForeignKey("app.CustomUser", on_delete=models.CASCADE, related_name="assignments_author")
    title = models.CharField(max_length=256)
    description = models.TextField()
    assigned_date = models.DateField()
    due_date = models.DateField()
    assigned_to = models.ManyToManyField("app.CustomUser", related_name="assignments_assigned_to")
    evaluators = models.ManyToManyField("app.CustomUser", related_name="assignments_evaluators")


class AssessmentContent(models.Model):
    STATUS_CHOICES = [
        ("In progress", "In progress"),
        ("Submitted", "Submitted"),
        ("Checked", "Checked")
    ]
    assignment = models.ForeignKey("app.Assignment", on_delete=models.CASCADE, related_name="assessments")
    user = models.ForeignKey("app.CustomUser", on_delete=models.CASCADE, related_name="assessments")
    assessment = models.FileField(upload_to="assessments/")
    assess_text_file = models.FilePathField(path="media/assessment_texts/", null=True, blank=True, max_length=256)
    summary_file = models.FilePathField(path="media/summaries/", null=True, blank=True, max_length=256)
    score = models.FloatField(default=0)
    status = models.CharField(max_length=100, choices=STATUS_CHOICES, default="In progress")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)