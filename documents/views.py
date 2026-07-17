import threading

from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from .forms import DocumentUploadForm
from .models import Document
from .services import delete_document_vectors, process_document


def document_list(request):
    documents = Document.objects.all()
    return render(
        request,
        "documents/list.html",
        {"documents": documents, "active_nav": "documents"},
    )


def document_upload(request):
    if request.method == "POST":
        form = DocumentUploadForm(request.POST, request.FILES)
        if form.is_valid():
            document = form.save(commit=False)
            document.title = document.file.name
            document.status = Document.Status.PENDING
            document.save()
            # No Celery/Redis yet (see BACKLOG.md 6.2) - a plain thread
            # is enough to keep the upload response from blocking on
            # extraction/embedding.
            threading.Thread(target=process_document, args=(document,), daemon=True).start()
            return redirect("documents:list")
    else:
        form = DocumentUploadForm()

    return render(
        request,
        "documents/upload.html",
        {"form": form, "active_nav": "documents"},
    )


def document_detail(request, pk):
    document = get_object_or_404(Document, pk=pk)
    return render(
        request,
        "documents/detail.html",
        {"document": document, "active_nav": "documents"},
    )


def document_status(request, pk):
    document = get_object_or_404(Document, pk=pk)
    return JsonResponse(
        {
            "status": document.status,
            "status_display": document.get_status_display(),
            "page_count": document.page_count,
        }
    )


def document_delete(request, pk):
    document = get_object_or_404(Document, pk=pk)

    if request.method == "POST":
        document.file.delete(save=False)
        delete_document_vectors(document.pk)
        document.delete()
        messages.success(request, "Document deleted.")
        return redirect("documents:list")

    return render(
        request,
        "documents/delete_confirm.html",
        {"document": document, "active_nav": "documents"},
    )
