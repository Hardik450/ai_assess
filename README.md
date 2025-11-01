

# AI ASSESS

AI-powered assignment evaluation platform built with **Django**, **LangChain**, **Gemini API**, and modern document/image extraction tools. Designed for teachers and students to streamline assignment submissions, automatic feedback, and scalable EdTech innovation.

***

## 🚀 Features

- **User Roles:** Teacher and Student dashboard, assignment management.
- **AI-Based Evaluation:** Automatic feedback and scoring using state-of-the-art LLMs (Gemini, HuggingFace).
- **Asynchronous Processing:** Celery and Redis for background document/image evaluation.
- **PDF/Image Extraction:** PyMuPDF + Gemini API for robust OCR and text handling.
- **Feedback Storage:** Structured feedback and grading, support for future feature growth.
- **Clean RESTful API:** Extendable endpoints for assignments and submissions.
- **Extensive Error Logging:** For easy debugging and extension.

***

## 🛠️ Stack

- **Backend:** Django, Celery, Redis
- **AI:** LangChain, Gemini API, HuggingFace Embeddings
- **Document Processing:** PyMuPDF, Pillow (PIL)
- **Database:** Django ORM (PostgreSQL)
- **Frontend:** HTML/CSS/JS templates 

***

## 👇 Getting Started

### 1. Clone the repo

```bash
git clone https://github.com/Hardik450/ai_assess.git
cd ai_assess
```

### 2. Setup Python Environment

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Set up Environment Variables

Create a `.env` file in the project root:

```
SECRET_KEY=your_django_secret
GOOGLE_API_KEY=your_gemini_api_key
DEBUG=True
```

Set up any other keys as needed.

### 4. Initialize Database

```bash
python manage.py migrate
```

### 5. Start Services

- **Redis:**  
  `redis-server` (on Linux/macOS/WSL/Docker)
- **Celery:**  
  `celery -A ai_assess worker --loglevel=info -P solo`
- **Django Server:**  
  `python manage.py runserver`

### 6. Access Local App

Go to [http://localhost:8000/](http://localhost:8000/) in your browser.

***

## 🧑‍💻 Contributing

1. **Fork the repository**
2. **Clone your fork**
3. Create a new branch (`git checkout -b feature/your-feature`)
4. Write tests for new functionality when possible.
5. Run `python manage.py test` to validate.
6. Push and make a PR! (describe changes clearly)

### Code Style

- Python: PEP8 compliance, docstrings for key functions/classes.
- Frontend: Consistent spacing, accessibility, and responsiveness.

### Issues/Bugs

Use the [Issues tab](https://github.com/hardik450/ai_assess/issues) to report problems or request features.


***

## **Celery Installation (Python package)**
Celery is installed via `pip` (Python’s package manager).

### 1. **Basic Installation (All OS)**

In your project's virtual environment:
```bash
pip install celery
```

**Add to `requirements.txt`:**
```
celery>=5.2.0
```

***

## **Redis Installation (Message Broker)**

### **A. On Windows**

**Redis is not natively supported on Windows!**  
Users can install Redis using one of these methods:

#### **Option 1: Windows Subsystem for Linux (WSL)**
1. **Install WSL** (on Windows 10 or 11):
   - Open PowerShell and run:
     ```powershell
     wsl --install
     ```
   - Reboot, open Ubuntu (or other), and run commands below:

2. **Inside WSL (Ubuntu):**
   ```bash
   sudo apt update
   sudo apt install redis-server
   sudo service redis-server start
   redis-cli ping
   # Should print: PONG
   ```

#### **Option 2: Docker**
1. **Install Docker Desktop for Windows:**  
   [Get Docker here](https://www.docker.com/products/docker-desktop/)
2. **Run Redis as a container:**
   ```bash
   docker run -d -p 6379:6379 --name redis redis
   ```
   This runs Redis and maps it to `localhost:6379`.

#### **Option 3: Third-party Build (Not Official)**
- **Memurai:** [memurai.com](https://www.memurai.com/)
- Or older Microsoft port: [Github archive](https://github.com/microsoftarchive/redis/releases)
  - *Not recommended for production.*

***

### **B. On Linux (Ubuntu/Debian/Fedora/etc.)**

```bash
sudo apt update
sudo apt install redis-server
sudo service redis-server start  # or: sudo systemctl start redis
redis-cli ping
```

***

### **C. On macOS**

Using **Homebrew**:
```bash
brew update
brew install redis
brew services start redis
redis-cli ping
```
*Homebrew will install and start Redis as a background service.*

***

## **Celery Worker Commands**

Once Redis is running, start your Celery worker (all OS):

```bash
celery -A yourproject worker --loglevel=info -P solo
```
*On Windows, you must use* `-P solo` *to avoid errors.*

***


## 📝 License

[MIT License](LICENSE)

***

## 🙏 Acknowledgements

- [Django](https://www.djangoproject.com/)
- [LangChain](https://langchain.com/)
- [Google Gemini API](https://ai.google.dev/)
- [Hugging Face](https://huggingface.co/)
- [PyMuPDF](https://pymupdf.readthedocs.io/)

***

**Happy Coding! ❤️ Please star the repo if you like the project.**

