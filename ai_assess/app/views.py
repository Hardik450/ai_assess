from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.utils import timezone
from django.core.mail import send_mail
import random
from datetime import timedelta
from typing import List, Dict
from django.http import JsonResponse, HttpResponse
from django.contrib.auth.decorators import login_required
from django.core.files.uploadedfile import UploadedFile
from .models import AssessmentContent, CustomUser, Assignment
from django.contrib.auth import get_user_model
import os
import tempfile
from langchain.prompts import ChatPromptTemplate
from langchain.chains.retrieval import create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from django.core.serializers.json import DjangoJSONEncoder
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.output_parsers import PydanticOutputParser
from langchain_community.document_loaders import PyMuPDFLoader
import pytesseract
from django.db.models import Q
from PIL import Image
from dotenv import load_dotenv
import threading
import json
load_dotenv()
google_api_key = os.getenv("GOOGLE_API_KEY")
chat = ChatGoogleGenerativeAI(temperature=0, model="gemini-2.0-flash", api_key=google_api_key)
User = get_user_model()
# Create your views here.


def index(request):
    return render(request, 'index.html')


otp_storage = {}

def register(request):
    if request.method == 'POST':
        name = request.POST['name']
        phone_number = request.POST['number']
        email = request.POST['email']
        age = request.POST['age']
        gender = request.POST['gender']
        password = request.POST['password']
        conf_pass = request.POST['confpass']

        if password != conf_pass:
            return render(request, 'signup.html', {'error': 'Passwords do not match.'})
        if User.objects.filter(email=email).exists():
            return render(request, 'signup.html', {'error': 'Email already exists.'})
        if User.objects.filter(phone_number=phone_number).exists():
            return render(request, 'signup.html', {'error': 'Phone number already exists.'})
        
        otp = random.randint(100000, 999999)
        otp_storage[email] = {
            'otp': otp,
            'name': name,
            'phone_number': phone_number,
            'email': email,
            'age': age,
            'gender': gender,
            'password': password,
            'otp_time': timezone.now()
        }
        send_otp_mail(name, email, otp)
        return redirect('verify_otp', email=email)
    if request.user.is_authenticated:
        return redirect('dashboard')
    return render(request, 'signup.html')

def verify_otp(request, email):
    if request.user.is_authenticated:
        return redirect('dashboard')
    otp_data = otp_storage.get(email)
    if otp_data is None:
        return redirect('register')
    otp_time = otp_data['otp_time']
    otp_expired = timezone.now() > otp_time + timedelta(minutes=5)
    if request.method == 'POST':
        entered_otp = request.POST.get('entered_otp')
        if (not otp_expired and str(otp_data['otp']) == entered_otp):
            user_create = User.objects.create_user(
                username=email,
                email=email,
                name=otp_data['name'],
                password=otp_data['password'],
                gender=otp_data['gender'],
                age=otp_data['age'],
                phone_number=otp_data['phone_number']
            )
            login(request, user_create)
            return redirect('select_role')
        else:
            return render(request, 'verify_otp.html', {
                'error': 'Invalid OTP.',
                'email': email,
                'otp_expired': otp_expired
            })
    return render(request, 'verify_otp.html', {
        'email': email,
    })

def resend_otp(request, email):
    if request.user.is_authenticated:
        return redirect('dashboard')
    otp_data = otp_storage.get(email)
    if otp_data is None:
        return redirect('register')
    otp = random.randint(100000, 999999)
    otp_data['otp_time'] = timezone.now()
    otp_data['otp'] = otp
    otp_storage[email] = otp_data
    send_otp_mail(otp_data['name'], email, otp)
    return redirect('verify_otp', email)

def send_otp_mail(name, email, otp):
    threading.Thread(target=send_mail, args=(
        'Your OTP for email verification',
        f'Hey, {name}.\nYour OTP is: {otp}.',
        'hello@gmail.com',
        [email],
    ), kwargs={'fail_silently': False}).start()
    
from itertools import chain
@login_required(login_url='/ai_assess/login/')
def dashboard(request):
    if request.user.role == 'teacher':
        return redirect('teacher_dashboard')
    elif request.user.role == 'student':
        return redirect('student_dashboard')
    else:
        return redirect('select_role')

def check_email(request):
    email = request.GET.get('email', None)
    data = {
        'is_taken': User.objects.filter(email__iexact=email).exists()
    }
    return JsonResponse(data)

def select_role(request):
    """Page to select role after SSO login"""
    if not request.user.is_authenticated:
        return redirect("login")
    
    if request.user.role:
        if request.user.role == "teacher":
            return redirect("teacher_dashboard")
        elif request.user.role == "student":
            return redirect("student_dashboard")

    if request.method == "POST":
        role = request.POST.get("role")
        user = User.objects.get(id=request.user.id)
        user.role = role
        user.save()
        if role == "teacher":
            return redirect("teacher_dashboard")
        elif role == "student":
            return redirect("student_dashboard")
        else:
            return render(request, "select_role.html")

    return render(request, "select_role.html")

def loginuser(request):
    error = ''
    if request.method == 'POST':
        identifier = request.POST['identifier']
        password = request.POST['password']
        user_login = authenticate(request, username=identifier, password=password)
        if user_login is not None:
            login(request, user_login)
        else:
            error = 'Invalid username or password'
    if request.user.is_authenticated:
        return redirect('dashboard')
    return render(request, 'login.html', {'error': error})

def logoutuser(request):
    logout(request)
    return redirect('login')



@login_required(login_url='/ai_assess/login/')
def teacher_dashboard(request):
    if request.user.role != 'teacher':
        return redirect('dashboard')
    assignments = Assignment.objects.filter(Q(author=request.user) | Q(evaluators=request.user)).distinct()
    assessments = AssessmentContent.objects.filter(assignment__in=assignments).order_by('-created_at')

    # Get summary for each assessment
    summary_content = {}
    for a in assessments:
        try:
            if hasattr(a, 'summary_file') and a.summary_file:
                summary_path = os.path.join("/media/summaries/", a.summary_file)
                with open(summary_path, 'r', encoding='utf-8') as f:
                    summary_content[a.id] = f.read()
            else:
                summary_content[a.id] = None
        except Exception:
            summary_content[a.id] = None

    return render(request, 'teacher_dashboard.html', {
        'assessments': assessments,
        'total_assessments': assessments.count(),
        'assignments': assignments,
        'total_assignments': assignments.count(),
        'summary_content': summary_content
    })

@login_required(login_url='/ai_assess/login/')
def student_dashboard(request):
    if request.user.role != 'student':
        return redirect('dashboard')
    assignments = Assignment.objects.filter(assigned_to=request.user)
    assessments = AssessmentContent.objects.filter(user=request.user).order_by('-created_at')[:10]
    assessments_list = list(assessments.values())
    assessments_json = json.dumps(assessments_list, cls=DjangoJSONEncoder)

    # Get summary for each assessment
    summary_content = {}
    for a in assessments:
        try:
            if hasattr(a, 'summary_file') and a.summary_file:
                summary_path = os.path.join("/media/summaries/", a.summary_file)
                with open(summary_path, 'r', encoding='utf-8') as f:
                    summary_content[a.id] = f.read()
            else:
                summary_content[a.id] = None
        except Exception:
            summary_content[a.id] = None

    return render(request, "student_dashboard.html", {
        "assessments": assessments,
        "assessments_json": assessments_json,
        "total_assessments": assessments.count(),
        "assignments": assignments,
        "total_assignments": assignments.count(),
        'summary_content': summary_content
    })



def create_assignment(request):
    if request.method == 'POST':
        title = request.POST['title']
        description = request.POST['description']
        assigned_date = request.POST['assigned_date']
        due_date = request.POST['due_date']

        # Split emails into list
        assigned_to_emails = [email.strip() for email in request.POST['assigned_to'].replace(',', ' ').split() if email.strip()]
        evaluator_emails = [email.strip() for email in request.POST['evaluators'].replace(',', ' ').split() if email.strip()]

        assignment = Assignment.objects.create(
            author=request.user,
            title=title,
            description=description,
            assigned_date=assigned_date,
            due_date=due_date
        )

        assigned_to_users = CustomUser.objects.filter(email__in=assigned_to_emails, role="student")
        assignment.assigned_to.set(assigned_to_users)

        evaluator_users = CustomUser.objects.filter(email__in=evaluator_emails, role="teacher")
        assignment.evaluators.set(evaluator_users)

        assignment.save()
        return redirect('teacher_dashboard')

    return render(request, 'create_assignment.html')

def check_email_status(request):
    email = request.GET.get('email', None)
    user = CustomUser.objects.filter(email__iexact=email).first()
    if user:
        data = {
            'exists': True,
            'role': user.role  # e.g. 'student' or 'teacher'
        }
    else:
        data = {
            'exists': False,
            'role': None
        }
    return JsonResponse(data)


from typing import Dict, Optional
from pydantic import BaseModel, Field
import fitz  # PyMuPDF
import google.generativeai as genai
import uuid
from django.conf import settings




# class Assessment_Feedback(BaseModel):
#     """Complete structured feedback for a student assessment."""
#     content_correctness: str = Field(..., description="Accuracy and relevance of the content.")
#     clarity: str = Field(..., description="How clearly ideas are expressed.")
#     coherence: str = Field(..., description="Logical flow and consistency of ideas.")
#     completeness: str = Field(..., description="Degree to which the answer addresses all required points.")
#     grammar_and_spelling: str = Field(..., description="Proper grammar, spelling, and punctuation usage.")
#     organization: str = Field(..., description="How well the response is structured and formatted.")
#     vocabulary_usage: str = Field(..., description="Appropriate and varied use of vocabulary.")
#     structure: str = Field(..., description="Logical structure, paragraphing, and transitions.")
#     suggestions: str = Field(..., description="Actionable suggestions for improvement.")
#     total_score: float = Field(..., description="Overall score for the assessment (out of 10).")

from .tasks import async_extract_text_and_feedback
from django.core.files.storage import default_storage
def assessment_submission(request, assignment_id):
    if not request.user.is_authenticated:
        return redirect('login')
    assignment = get_object_or_404(Assignment, id=assignment_id)
    if assignment.assigned_to.filter(id=request.user.id).count() == 0:
        return HttpResponse("You are not assigned to this assignment.", status=403)
    if assignment.due_date < timezone.now().date():
        return HttpResponse("The due date for this assignment has passed.", status=403)
    if AssessmentContent.objects.filter(user=request.user, assignment=assignment).exists():
        return HttpResponse("You have already submitted an assessment for this assignment.", status=403)
    if request.method == 'POST':
        try:
            # parser = PydanticOutputParser(pydantic_object=Assessment_Feedback)
            # format_instructions = parser.get_format_instructions().replace("{", "{{").replace("}", "}}")

            # splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
            # embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")

            assessment = request.FILES.get('assessment')
            assignment = get_object_or_404(Assignment, id=assignment_id)


            if not assessment:
                return HttpResponse("No assessment file uploaded", status=400)

            assessment_file_type: UploadedFile = assessment
            assessment_type = assessment_file_type.content_type

            # Save file to disk for celery task
            filename = default_storage.save(f"tmp/{assessment.name}", assessment)
            file_path = default_storage.path(filename)

            # Kick off background job
            async_extract_text_and_feedback.delay(request.user.id, assignment_id, file_path, assessment_type)

            # Instantly respond to user
            return JsonResponse({"msg": "Assessment processing started. You will be notified when feedback is ready."})

        except Exception as e:
            import traceback
            print(traceback.format_exc())
            return HttpResponse(f"Server Error: {e}", status=500)

    return render(request, 'assessment_submission.html')

def write_teacher_feedback(assessment, teacher_feedback):
    if assessment.teacher_feedback_file:
        with open(assessment.teacher_feedback_file, "a", encoding="utf-8") as f:
            f.write(teacher_feedback)
    else:
        now = timezone.now()
        formatted = now.strftime("%Y%m%d%H%M%S%f")
        feedback_filename = f"{assessment.user.id}_{assessment.assignment.id}_{formatted}_feedback.txt"
        feedback_dir = os.path.join(settings.MEDIA_ROOT, "teacher_feedbacks")
        os.makedirs(feedback_dir, exist_ok=True)
        feedback_path = os.path.join(feedback_dir, feedback_filename)
        with open(feedback_path, "w", encoding="utf-8") as f:
            f.write(teacher_feedback)
        assessment.teacher_feedback_file = feedback_path


def finalize_assessment(request, id):
    if request.user.role != 'teacher':
        return redirect('dashboard')
    if request.method == 'POST':
        try:
            assessment = AssessmentContent.objects.get(id=id)
            data = json.loads(request.body.decode())
            teacher_feedback = data.get("teacher_feedback", "")
            assessment.status = "Submitted"
            assessment.score = data.get("score", assessment.score)
            write_teacher_feedback(assessment, teacher_feedback)

            assessment.save()
            return JsonResponse({
                "message": "Assessment finalized successfully.",
                "status": assessment.status,
                "score": assessment.score,
                "teacher_feedback_file": assessment.teacher_feedback_file,
            })
        except AssessmentContent.DoesNotExist:
            return JsonResponse({"error": "Assessment not found."}, status=404)
        except Exception as e:
            return JsonResponse({"error": f"Server Error: {e}"}, status=500)
    return JsonResponse({"error": "Invalid request method."}, status=400)

def mark_reviewed(request, id):
    if request.user.role != 'teacher':
        return redirect('dashboard')
    if request.method == 'POST':
        try:
            assessment = AssessmentContent.objects.get(id=id)
            assessment.status = "Checked"
            
            data = json.loads(request.body.decode())
            teacher_feedback = data.get("teacher_feedback", "")
            assessment.score = data.get("score", assessment.score)
            write_teacher_feedback(assessment, teacher_feedback)

            assessment.save()
            return JsonResponse({
                "message": "Assessment marked as reviewed successfully.",
                "status": assessment.status,
                "score": assessment.score,
                "teacher_feedback_file": assessment.teacher_feedback_file,
            })
        except AssessmentContent.DoesNotExist:
            return JsonResponse({"error": "Assessment not found."}, status=404)
        except Exception as e:
            return JsonResponse({"error": f"Server Error: {e}"}, status=500)
    return JsonResponse({"error": "Invalid request method."}, status=400)