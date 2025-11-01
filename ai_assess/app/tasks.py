# from typing import Dict, Optional
# from pydantic import BaseModel, Field
# import fitz  # PyMuPDF
# import google.generativeai as genai
# import uuid
# from django.conf import settings
# from django.shortcuts import render, get_object_or_404, redirect
# from django.http import HttpResponse, JsonResponse
# from django.utils import timezone
# from django.core.files.uploadedfile import UploadedFile
# from .models import Assignment, AssessmentContent
# from langchain.prompts import ChatPromptTemplate
# from langchain.chains.retrieval import create_retrieval_chain
# from langchain.chains.combine_documents import create_stuff_documents_chain
# from langchain_community.vectorstores import FAISS
# from langchain_huggingface import HuggingFaceEmbeddings
# from django.core.serializers.json import DjangoJSONEncoder
# from langchain.text_splitter import RecursiveCharacterTextSplitter
# from langchain_google_genai import ChatGoogleGenerativeAI
# from langchain.output_parsers import PydanticOutputParser
# from langchain_community.document_loaders import PyMuPDFLoader
# import os
# import tempfile
# from PIL import Image
# from dotenv import load_dotenv
# load_dotenv()
# google_api_key = os.getenv("GOOGLE_API_KEY")
# chat = ChatGoogleGenerativeAI(temperature=0, model="gemini-2.0-flash", api_key=google_api_key)

# genai.configure(api_key=google_api_key)
# gemini_model = genai.GenerativeModel("gemini-2.0-flash")
# def extract_text_from_image(image: Image.Image) -> str:
#     """Extract text from an image using Gemini Vision."""
#     try:
#         response = gemini_model.generate_content([
#             "Extract all text clearly from this image. There should be no extra text written above or below the extracted text from your side.",
#             image
#         ])
#         return response.text.strip() if response.text else ""
#     except Exception as e:
#         print("Gemini OCR failed:", e)
#         return ""


# def extract_text_from_pdf(pdf_path: str) -> str:
#     """Extract text from PDF using both direct text and Gemini OCR (batch per 10 pages)."""
#     text_content = ""
#     doc = fitz.open(pdf_path)

#     batch_images = []
#     page_image_paths = []

#     for page_num in range(len(doc)):
#         page = doc.load_page(page_num)
#         text = page.get_text("text")

#         if text.strip():
#             # Text-based PDF page
#             text_content += f"\n--- Page {page_num + 1} ---\n{text}"
#         else:
#             # Scanned page — collect for batch OCR
#             pix = page.get_pixmap(dpi=200)
#             img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
#             tmp_path = f"/tmp/page_{page_num + 1}.png"
#             img.save(tmp_path)
#             page_image_paths.append(tmp_path)
#             batch_images.append(Image.open(tmp_path))

#         # Process in batches of 10 pages for speed and memory efficiency
#         if len(batch_images) == 10 or page_num == len(doc) - 1:
#             if batch_images:
#                 try:
#                     response = gemini_model.generate_content([
#                         "Extract all text clearly from these document pages. Preserve structure.",
#                         *batch_images
#                     ])
#                     batch_text = response.text or ""
#                     text_content += f"\n--- OCR Batch {page_num // 10 + 1} ---\n{batch_text.strip()}"
#                 except Exception as e:
#                     print("Gemini batch OCR failed:", e)
#                 finally:
#                     # Close all opened images
#                     for img in batch_images:
#                         img.close()
#                     batch_images.clear()

#     doc.close()

#     return text_content.strip()


# from celery import shared_task

# @shared_task
# def async_extract_text_and_feedback(user_id, user, format_instructions, splitter, embeddings, assignment_id, file_path, assessment_type,  parser, assessment, assignment):
#     # 1. Open file and extract text (OCR/LLM)
#     # 2. Run LLM feedback eval
#     # 3. Save output in DB or write files
#     # Use code logic from your view, but **do not** use Django request/response objects
#     # ------------------ Extract text ------------------
#     try:
#         if assessment_type.startswith("image/"):
#             assessment.seek(0)
#             assess_image = Image.open(assessment).convert("RGB")
#             assess_text = extract_text_from_image(assess_image)

#         elif assessment_type == "application/pdf":
#             assessment.seek(0)
#             with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
#                 tmp.write(assessment.read())
#                 tmp.flush()
#                 tmp_path = tmp.name

#             assess_text = extract_text_from_pdf(tmp_path)

#         else:
#             return HttpResponse("Invalid assessment file type", status=400)
#     except Exception as e:
#         return HttpResponse(f"Error processing assessment file: {e}", status=400)
#     finally:
#         if 'tmp_path' in locals() and os.path.exists(tmp_path):
#             os.unlink(tmp_path)

#     # ------------------ Retrieval setup ------------------
#     combined_text = f"Assessment CONTENT:\n{assess_text}"
#     documents = splitter.create_documents([combined_text])
#     vector_db = FAISS.from_documents(documents, embeddings)
#     retriever = vector_db.as_retriever(search_type="similarity", search_kwargs={"k": 5})

#     system_prompt = f"""
# You are an expert educational evaluator and language model trained to assess student responses
# based on the **specific assignment title and description** provided by the instructor.

# Your task is to generate detailed, constructive feedback that evaluates how well the student's
# submission aligns with the assignment's **intent**, **learning objectives**, and **expected outcomes**.


# When analyzing the student's response, note that student answers may be unstructured,
# non-sequential, or repetitive (as often seen in handwritten or exam submissions).
# Please interpret the content based on meaning rather than order.
# ---

# ### 🎯 Context for Evaluation

# **Assignment Title:** {assignment.title}

# **Assignment Description:** {assignment.description}

# **Student Submission Content:** (provided below in context)

# Your evaluation should focus on how effectively the student's response fulfills the
# assignment’s purpose, demonstrates understanding, and meets the expectations implied by
# the title and description.

# ---

# ### 🧩 Evaluation Guidelines

# 1. **Relevance:** Does the response address the key points of the assignment topic?
# 2. **Depth of Understanding:** Does it show comprehension of the underlying concept or problem?
# 3. **Completeness:** Does the student answer all required aspects outlined in the description?
# 4. **Clarity & Coherence:** Is the explanation logically organized and easy to follow?
# 5. **Language & Expression:** Grammar, tone, and fluency (evaluate, but don’t over-penalize stylistic variance).
# 6. **Constructive Feedback:** For every weakness, provide an actionable suggestion for improvement.
# 7. **Scoring:** Provide a `total_score` between 0–10 representing overall performance.
# 8. **Tone:** Maintain fairness, encouragement, and professionalism.
# 9. **Consistency:** Use the same level of detail for all feedback categories.

# ---

# ### 🧱 Required JSON Output Format

# Return your response in **strict JSON**, exactly following this schema:

# {format_instructions}

# Where:
# - Each subfield within `FeedbackDetails` provides qualitative feedback for that criterion.
# - `total_score` represents the overall performance score (0–10).

# ---

# ### 📄 Student Submission Context
# Below is the extracted student assessment text (ignore any institutional or contact info):

# {{context}}

# ---

# ### ⚠️ Important
# - Do **not** include any text outside the JSON.
# - Do **not** use markdown formatting or extra commentary.
# - JSON keys must exactly match the schema.
# """



#     prompt = ChatPromptTemplate.from_messages([
#         ("system", system_prompt),
#         (
#             "human",
#             """
#     Analyze the assessment response provided in the context above.
#     Provide detailed structured feedback according to the given schema.
#     Ensure fairness, clarity, and constructive tone.
#     Avoid penalizing non standard english or cultural expressions.
#     """
#         ),
#     ])

#     query = "Analyze this student’s assessment and generate feedback."
#     retrieval_chain = create_retrieval_chain(
#         retriever,
#         create_stuff_documents_chain(llm=chat, prompt=prompt)
#     )
#     response = retrieval_chain.invoke({'input':query})
#     raw_output = response["answer"].strip()
#     print(f"DEBUG: Raw LLM Output: {raw_output}")
#     if raw_output.startswith("```"):
#         raw_output = raw_output.strip("```json").strip("```")
#     raw_output = raw_output.replace("{{", "{").replace("}}", "}")
#     assess_plan = parser.parse(raw_output)
#     assess_data = assess_plan.model_dump()

#     # ------------------ Save to Database ------------------
#     feedback_data = {k: v for k, v in assess_data.items() if k != "total_score"}
#     summary = " ".join(str(v) for v in feedback_data.values())
#     score = assess_data.get("total_score", 0.0)
#     status = assess_data.get("status", "Submitted")
#     now = timezone.now()
#     # Format without spaces and colons
#     formatted = now.strftime("%Y%m%d%H%M%S%f")
#     text_filename = f"{user_id}_{assignment_id}_{formatted}_assessment.txt"
#     text_dir = os.path.join(settings.MEDIA_ROOT, "assessment_texts")
#     os.makedirs(text_dir, exist_ok=True)
#     text_path = os.path.join(text_dir, text_filename)
#     summary_filename = f"{user_id}_{assignment_id}_{formatted}_summary.txt"
#     summary_dir = os.path.join(settings.MEDIA_ROOT, "summaries")
#     os.makedirs(summary_dir, exist_ok=True)
#     summary_path = os.path.join(summary_dir, summary_filename)

#     with open(summary_path, "w", encoding="utf-8") as f:
#         f.write(summary)

#     # Write the extracted text
#     with open(text_path, "w", encoding="utf-8") as f:
#         f.write(assess_text)

    

#     assessment.seek(0)
#     AssessmentContent.objects.create(
#         user=user,
#         assignment=assignment,
#         assessment=assessment,
#         summary_file=summary_path,
#         assess_text_file=text_path,
#         status=status,
#         score=score,
#     )
#     pass

from celery import shared_task
from django.contrib.auth import get_user_model

from ai_assess import settings
from .models import Assignment, AssessmentContent
from PIL import Image
import os
import tempfile
import fitz  # PyMuPDF
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain.prompts import ChatPromptTemplate
from langchain.chains.retrieval import create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain.output_parsers import PydanticOutputParser
from langchain_google_genai import ChatGoogleGenerativeAI
import google.generativeai as genai
from pathlib import Path
from pydantic import BaseModel, Field
from django.utils import timezone
import logging
from django.core.files import File


# Setup Gemini and Chat AI models outside task
google_api_key = os.getenv("GOOGLE_API_KEY")
genai.configure(api_key=google_api_key)
gemini_model = genai.GenerativeModel("gemini-2.0-flash")
chat = ChatGoogleGenerativeAI(temperature=0, model="gemini-2.0-flash", api_key=google_api_key)


# Your Pydantic model for assessment feedback should be imported or redefined here
class Assessment_Feedback(BaseModel):
    content_correctness: str = Field(...)
    clarity: str = Field(...)
    coherence: str = Field(...)
    completeness: str = Field(...)
    grammar_and_spelling: str = Field(...)
    organization: str = Field(...)
    vocabulary_usage: str = Field(...)
    structure: str = Field(...)
    suggestions: str = Field(...)
    total_score: float = Field(...)


# Extraction helpers
def extract_text_from_image(image: Image.Image) -> str:
    try:
        response = gemini_model.generate_content([
            "Extract all text clearly from this image. There should be no extra text written above or below the extracted text from your side.",
            image
        ])
        return response.text.strip() if response.text else ""
    except Exception as e:
        logging.error(f"Gemini OCR failed: {e}")
        return ""

def extract_text_from_pdf(pdf_path: str) -> str:
    text_content = ""
    doc = fitz.open(pdf_path)
    batch_images = []

    for page_num in range(len(doc)):
        page = doc.load_page(page_num)
        text = page.get_text("text")

        if text.strip():
            text_content += f"\n--- Page {page_num + 1} ---\n{text}"
        else:
            pix = page.get_pixmap(dpi=200)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            batch_images.append(img)

        if len(batch_images) == 10 or page_num == len(doc) - 1:
            if batch_images:
                try:
                    response = gemini_model.generate_content([
                        "Extract all text clearly from these document pages. Preserve structure.",
                        *batch_images
                    ])
                    batch_text = response.text or ""
                    batch_index = (page_num // 10 + 1)
                    text_content += f"\n--- OCR Batch {batch_index} ---\n{batch_text.strip()}"
                except Exception as e:
                    logging.error(f"Gemini batch OCR failed: {e}")
                finally:
                    for img in batch_images:
                        img.close()
                    batch_images.clear()

    doc.close()
    return text_content.strip()


@shared_task
def async_extract_text_and_feedback(user_id: int, assignment_id: int, file_path: str, assessment_type: str):
    try:
        User = get_user_model()
        user = User.objects.get(pk=user_id)
        assignment = Assignment.objects.get(pk=assignment_id)

        # Prepare LangChain components
        parser = PydanticOutputParser(pydantic_object=Assessment_Feedback)
        splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
        embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")

        # Extract text from uploaded file
        assess_text = ""
        try:
            if assessment_type.startswith("image/"):
                img = Image.open(file_path).convert("RGB")
                assess_text = extract_text_from_image(img)
                img.close()
            elif assessment_type == "application/pdf":
                assess_text = extract_text_from_pdf(file_path)
            else:
                logging.error("Invalid assessment file type in async task.")
                return
        except Exception as e:
            logging.error(f"Error processing assessment file in async task: {e}")
            return
        

        # Setup retrieval chain with embeddings
        combined_text = f"Assessment CONTENT:\n{assess_text}"
        documents = splitter.create_documents([combined_text])
        vector_db = FAISS.from_documents(documents, embeddings)
        retriever = vector_db.as_retriever(search_type="similarity", search_kwargs={"k": 5})

        # Prepare system prompt for evaluation
        format_instructions = parser.get_format_instructions().replace("{", "{{").replace("}", "}}")
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
        response = retrieval_chain.invoke({'input': query})
        raw_output = response["answer"].strip()
        if raw_output.startswith("```"):
            raw_output = raw_output.strip("```json").strip("```")
        raw_output = raw_output.replace("{{", "{").replace("}}", "}")
        assess_plan = parser.parse(raw_output)
        assess_data = assess_plan.model_dump()

        # Save to DB and files
        feedback_data = {k: v for k, v in assess_data.items() if k != "total_score"}
        summary = " ".join(str(v) for v in feedback_data.values())
        score = assess_data.get("total_score", 0.0)
        status = assess_data.get("status", "Submitted")
        now = timezone.now()
        formatted = now.strftime("%Y%m%d%H%M%S%f")

        text_dir = os.path.join(settings.MEDIA_ROOT, "assessment_texts")
        os.makedirs(text_dir, exist_ok=True)
        text_path = os.path.join(text_dir, f"{user_id}_{assignment_id}_{formatted}_assessment.txt")
        with open(text_path, "w", encoding="utf-8") as f:
            f.write(assess_text)

        summary_dir = os.path.join(settings.MEDIA_ROOT, "summaries")
        os.makedirs(summary_dir, exist_ok=True)
        summary_path = os.path.join(summary_dir, f"{user_id}_{assignment_id}_{formatted}_summary.txt")
        with open(summary_path, "w", encoding="utf-8") as f:
            f.write(summary)

        # Save the assessment file permanently to the model's FileField
        with open(file_path, 'rb') as f:
            django_file = File(f)
            assessment_content = AssessmentContent(
                user=user,
                assignment=assignment,
                summary_file=summary_path,
                assess_text_file=text_path,
                status=status,
                score=score,
            )
            # Assign the file to the 'assessment' FileField
            assessment_content.assessment.save(os.path.basename(file_path), django_file, save=False)
            assessment_content.save()

        # Optionally delete the temp file after saving if no longer needed
        os.remove(file_path)

        return "Task completed successfully"
    except Exception as e:
        logging.error(f"Error in async_extract_text_and_feedback task: {e}")
        return f"Task failed due to error: {e}"