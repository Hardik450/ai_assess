from django.contrib import admin
from django.urls import path
from . import views

urlpatterns = [
    path("register/", views.register, name="register"),
    path("verify_otp/<str:email>/", views.verify_otp, name="verify_otp"),
    path("resend_otp/<str:email>/", views.resend_otp, name="resend_otp"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path('check_email/', views.check_email, name='check_email'),
    path("login/", views.loginuser, name="login"),
    path("logout/", views.logoutuser, name="logout"),
    path('', views.index, name='index'),
    path("select_role/", views.select_role, name = 'select_role'),
    path("teacher_dashboard/", views.teacher_dashboard, name = 'teacher_dashboard'),
    path("student_dashboard/", views.student_dashboard, name = 'student_dashboard'),
    path("assessment_submission/<int:assignment_id>", views.assessment_submission, name = 'assessment_submission'),
    path("assessments/<int:id>/finalize/", views.finalize_assessment, name='finalize_assessment'),
    path("assessments/<int:id>/mark-reviewed/", views.mark_reviewed, name="mark_reviewed"),
    path('check_email_status/', views.check_email_status, name='check_email_status'),
    path('create_assignment/', views.create_assignment, name='create_assignment'),
]