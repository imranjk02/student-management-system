import os
from dotenv import load_dotenv

load_dotenv()

class Config:

    SECRET_KEY = os.getenv("SECRET_KEY")

    MONGO_URI = os.getenv("MONGO_URI")

    MONGO_DB = os.getenv("MONGO_DB", "student_management")

    UPLOAD_FOLDER = os.path.join("static", "uploads")

    MAX_CONTENT_LENGTH = 16 * 1024 * 1024

    ALLOWED_EXTENSIONS = {
        "pdf", "doc", "docx",
        "ppt", "pptx", "zip",
        "jpg", "jpeg", "png"
    }