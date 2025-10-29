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
    assignments = Assignment.objects.filter(
    Q(author=request.user) | Q(evaluators=request.user)
).distinct()

    assessments = AssessmentContent.objects.filter(assignment__in=assignments).order_by('-created_at')

    print(assessments)
    return render(request, 'teacher_dashboard.html', {'assessments': assessments, 'total_assessments': assessments.count(), 'assignments': assignments, 'total_assignments': assignments.count()})

@login_required(login_url='/ai_assess/login/')
def student_dashboard(request):
    if request.user.role != 'student':
        return redirect('dashboard')
    assignments = Assignment.objects.filter(assigned_to=request.user)
    assessments = AssessmentContent.objects.filter(user=request.user).order_by('-created_at')[:10]
    # Convert QuerySet to list of dicts for serialization
    assessments_list = list(assessments.values())
    assessments_json = json.dumps(assessments_list, cls=DjangoJSONEncoder)

    

    return render(request, "student_dashboard.html", {
        "assessments": assessments,
        "assessments_json": assessments_json,
        "total_assessments": assessments.count(),
        "assignments": assignments,
        "total_assignments": assignments.count()
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
genai.configure(api_key=google_api_key)
gemini_model = genai.GenerativeModel("gemini-2.0-flash")
def extract_text_from_image(image: Image.Image) -> str:
    """Extract text from an image using Gemini Vision."""
    try:
        response = gemini_model.generate_content([
            "Extract all text clearly from this image. There should be no extra text written above or below the extracted text from your side.",
            image
        ])
        return response.text.strip() if response.text else ""
    except Exception as e:
        print("Gemini OCR failed:", e)
        return ""


def extract_text_from_pdf(pdf_path: str) -> str:
    """Extract text from PDF using both direct text and Gemini OCR (batch per 10 pages)."""
    text_content = ""
    doc = fitz.open(pdf_path)

    batch_images = []
    page_image_paths = []

    for page_num in range(len(doc)):
        page = doc.load_page(page_num)
        text = page.get_text("text")

        if text.strip():
            # Text-based PDF page
            text_content += f"\n--- Page {page_num + 1} ---\n{text}"
        else:
            # Scanned page — collect for batch OCR
            pix = page.get_pixmap(dpi=200)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            tmp_path = f"/tmp/page_{page_num + 1}.png"
            img.save(tmp_path)
            page_image_paths.append(tmp_path)
            batch_images.append(Image.open(tmp_path))

        # Process in batches of 10 pages for speed and memory efficiency
        if len(batch_images) == 10 or page_num == len(doc) - 1:
            if batch_images:
                try:
                    response = gemini_model.generate_content([
                        "Extract all text clearly from these document pages. Preserve structure.",
                        *batch_images
                    ])
                    batch_text = response.text or ""
                    text_content += f"\n--- OCR Batch {page_num // 10 + 1} ---\n{batch_text.strip()}"
                except Exception as e:
                    print("Gemini batch OCR failed:", e)
                finally:
                    # Close all opened images
                    for img in batch_images:
                        img.close()
                    batch_images.clear()

    doc.close()

    return text_content.strip()






class Assessment_Feedback(BaseModel):
    """Complete structured feedback for a student assessment."""
    content_correctness: str = Field(..., description="Accuracy and relevance of the content.")
    clarity: str = Field(..., description="How clearly ideas are expressed.")
    coherence: str = Field(..., description="Logical flow and consistency of ideas.")
    completeness: str = Field(..., description="Degree to which the answer addresses all required points.")
    grammar_and_spelling: str = Field(..., description="Proper grammar, spelling, and punctuation usage.")
    organization: str = Field(..., description="How well the response is structured and formatted.")
    vocabulary_usage: str = Field(..., description="Appropriate and varied use of vocabulary.")
    structure: str = Field(..., description="Logical structure, paragraphing, and transitions.")
    suggestions: str = Field(..., description="Actionable suggestions for improvement.")
    total_score: float = Field(..., description="Overall score for the assessment (out of 10).")


def assessment_submission(request, assignment_id):
    if not request.user.is_authenticated:
        return redirect('login')
    assignment = get_object_or_404(Assignment, id=assignment_id)
    if assignment.assigned_to.filter(id=request.user.id).count() == 0:
        return HttpResponse("You are not assigned to this assignment.", status=403)
    if request.method == 'POST':
        try:
            parser = PydanticOutputParser(pydantic_object=Assessment_Feedback)
            format_instructions = parser.get_format_instructions().replace("{", "{{").replace("}", "}}")

            splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
            embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")

            assessment = request.FILES.get('assessment')
            assignment = get_object_or_404(Assignment, id=assignment_id)


            if not assessment:
                return HttpResponse("No assessment file uploaded", status=400)

            assessment_file_type: UploadedFile = assessment
            assessment_type = assessment_file_type.content_type
            assess_text = ""

            # ------------------ Extract text ------------------
            try:
                if assessment_type.startswith("image/"):
                    assessment.seek(0)
                    assess_image = Image.open(assessment).convert("RGB")
                    assess_text = extract_text_from_image(assess_image)

                elif assessment_type == "application/pdf":
                    assessment.seek(0)
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                        tmp.write(assessment.read())
                        tmp.flush()
                        tmp_path = tmp.name

                    assess_text = extract_text_from_pdf(tmp_path)

                else:
                    return HttpResponse("Invalid assessment file type", status=400)
            except Exception as e:
                return HttpResponse(f"Error processing assessment file: {e}", status=400)
            finally:
                if 'tmp_path' in locals() and os.path.exists(tmp_path):
                    os.unlink(tmp_path)

            # ------------------ Retrieval setup ------------------
            combined_text = f"Assessment CONTENT:\n{assess_text}"
            documents = splitter.create_documents([combined_text])
            vector_db = FAISS.from_documents(documents, embeddings)
            retriever = vector_db.as_retriever(search_type="similarity", search_kwargs={"k": 5})

            system_prompt = f"""
You are an expert educational evaluator and language model trained to assess student responses
based on the **specific assignment title and description** provided by the instructor.

Your task is to generate detailed, constructive feedback that evaluates how well the student's
submission aligns with the assignment's **intent**, **learning objectives**, and **expected outcomes**.


When analyzing the student's response, note that student answers may be unstructured,
non-sequential, or repetitive (as often seen in handwritten or exam submissions).
Please interpret the content based on meaning rather than order.
---

### 🎯 Context for Evaluation

**Assignment Title:** {assignment.title}

**Assignment Description:** {assignment.description}

**Student Submission Content:** (provided below in context)

Your evaluation should focus on how effectively the student's response fulfills the
assignment’s purpose, demonstrates understanding, and meets the expectations implied by
the title and description.

---

### 🧩 Evaluation Guidelines

1. **Relevance:** Does the response address the key points of the assignment topic?
2. **Depth of Understanding:** Does it show comprehension of the underlying concept or problem?
3. **Completeness:** Does the student answer all required aspects outlined in the description?
4. **Clarity & Coherence:** Is the explanation logically organized and easy to follow?
5. **Language & Expression:** Grammar, tone, and fluency (evaluate, but don’t over-penalize stylistic variance).
6. **Constructive Feedback:** For every weakness, provide an actionable suggestion for improvement.
7. **Scoring:** Provide a `total_score` between 0–10 representing overall performance.
8. **Tone:** Maintain fairness, encouragement, and professionalism.
9. **Consistency:** Use the same level of detail for all feedback categories.

---

### 🧱 Required JSON Output Format

Return your response in **strict JSON**, exactly following this schema:

{format_instructions}

Where:
- Each subfield within `FeedbackDetails` provides qualitative feedback for that criterion.
- `total_score` represents the overall performance score (0–10).

---

### 📄 Student Submission Context
Below is the extracted student assessment text (ignore any institutional or contact info):

{{context}}

---

### ⚠️ Important
- Do **not** include any text outside the JSON.
- Do **not** use markdown formatting or extra commentary.
- JSON keys must exactly match the schema.
"""



            prompt = ChatPromptTemplate.from_messages([
                ("system", system_prompt),
                (
                    "human",
                    """
            Analyze the assessment response provided in the context above.
            Provide detailed structured feedback according to the given schema.
            Ensure fairness, clarity, and constructive tone.
            Avoid penalizing non standard english or cultural expressions.
            """
                ),
            ])

            query = "Analyze this student’s assessment and generate feedback."
            retrieval_chain = create_retrieval_chain(
                retriever,
                create_stuff_documents_chain(llm=chat, prompt=prompt)
            )
            response = retrieval_chain.invoke({'input':query})
            raw_output = response["answer"].strip()
            print(f"DEBUG: Raw LLM Output: {raw_output}")
            if raw_output.startswith("```"):
                raw_output = raw_output.strip("```json").strip("```")
            raw_output = raw_output.replace("{{", "{").replace("}}", "}")
            assess_plan = parser.parse(raw_output)
            assess_data = assess_plan.model_dump()

            # ------------------ Save to Database ------------------
            feedback_data = {k: v for k, v in assess_data.items() if k != "total_score"}
            summary = " ".join(str(v) for v in feedback_data.values())
            score = assess_data.get("total_score", 0.0)
            status = assess_data.get("status", "In progress")
            now = timezone.now()
            # Format without spaces and colons
            formatted = now.strftime("%Y%m%d%H%M%S%f")
            text_filename = f"{request.user.id}_{assignment_id}_{formatted}_assessment.txt"
            text_dir = os.path.join(settings.MEDIA_ROOT, "assessment_texts")
            os.makedirs(text_dir, exist_ok=True)
            text_path = os.path.join(text_dir, text_filename)
            summary_filename = f"{request.user.id}_{assignment_id}_{formatted}_summary.txt"
            summary_dir = os.path.join(settings.MEDIA_ROOT, "summaries")
            os.makedirs(summary_dir, exist_ok=True)
            summary_path = os.path.join(summary_dir, summary_filename)

            with open(summary_path, "w", encoding="utf-8") as f:
                f.write(summary)

            # Write the extracted text
            with open(text_path, "w", encoding="utf-8") as f:
                f.write(assess_text)

            assessment.seek(0)
            AssessmentContent.objects.create(
                user=request.user,
                assignment=assignment,
                assessment=assessment,
                summary_file=summary_path,
                assess_text_file=text_path,
                status=status,
                score=score,
            )
            return JsonResponse({"redirect_url": "/ai_assess/student_dashboard/"})

        except Exception as e:
            import traceback
            print(traceback.format_exc())
            return HttpResponse(f"Server Error: {e}", status=500)

    return render(request, 'assessment_submission.html')

def finalize_assessment(request, id):
    if request.method == 'POST':
        try:
            assessment = AssessmentContent.objects.get(id=id)
            assessment.status = "Submitted"
            assessment.save()
            return render(request, 'teacher_dashboard.html')
        except AssessmentContent.DoesNotExist:
            return JsonResponse({"error": "Assessment not found."}, status=404)
        except Exception as e:
            return JsonResponse({"error": f"Server Error: {e}"}, status=500)
    return JsonResponse({"error": "Invalid request method."}, status=400)

def mark_reviewed(request, id):
    if request.method == 'POST':
        try:
            assessment = AssessmentContent.objects.get(id=id)
            assessment.status = "Checked"
            assessment.save()
            return render(request, 'teacher_dashboard.html')
        except AssessmentContent.DoesNotExist:
            return JsonResponse({"error": "Assessment not found."}, status=404)
        except Exception as e:
            return JsonResponse({"error": f"Server Error: {e}"}, status=500)
    return JsonResponse({"error": "Invalid request method."}, status=400)