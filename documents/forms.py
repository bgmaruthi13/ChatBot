import hashlib
import os

from django.core.exceptions import ValidationError
from django.forms import ModelForm
from pypdf import PdfReader

from .models import Document

MAX_UPLOAD_SIZE = 50 * 1024 * 1024  # 50MB
MAX_PAGES = 500


class DocumentUploadForm(ModelForm):
    class Meta:
        model = Document
        fields = ["file"]

    def clean_file(self):
        uploaded = self.cleaned_data["file"]

        ext = os.path.splitext(uploaded.name)[1].lower()
        if ext != ".pdf":
            raise ValidationError("Only PDF files are accepted.")

        if uploaded.size > MAX_UPLOAD_SIZE:
            raise ValidationError("File exceeds the 50MB size limit.")

        digest = hashlib.sha256()
        for chunk in uploaded.chunks():
            digest.update(chunk)
        file_hash = digest.hexdigest()
        uploaded.seek(0)

        existing = Document.objects.filter(file_hash=file_hash).first()
        if existing:
            raise ValidationError(
                f'This exact file was already uploaded as "{existing.title}".'
            )

        # Page-count limit only - a corrupted/unreadable PDF is left to
        # process_document's own failure handling (documents/services.py,
        # verified in BACKLOG 2.3/6.1), not rejected here, so that
        # existing "ends in status=failed" behavior stays intact.
        try:
            page_count = len(PdfReader(uploaded).pages)
        except Exception:
            page_count = None
        finally:
            uploaded.seek(0)

        if page_count is not None and page_count > MAX_PAGES:
            raise ValidationError(
                f"Document has {page_count} pages, which exceeds the {MAX_PAGES}-page limit."
            )

        self.instance.file_hash = file_hash
        return uploaded
