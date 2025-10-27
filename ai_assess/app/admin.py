from django.contrib import admin
from .models import CustomUser, AssessmentContent

# Register your models here.
admin.site.register(CustomUser)
admin.site.register(AssessmentContent)