from django.shortcuts import get_object_or_404, redirect, render

from documents.models import Document

from .models import ChatSession
from .services import ask


def chat_index(request):
    documents = Document.objects.filter(status=Document.Status.READY)
    return render(
        request,
        "chat/index.html",
        {"documents": documents, "active_nav": "chat"},
    )


def chat_session(request, document_id):
    document = get_object_or_404(Document, pk=document_id, status=Document.Status.READY)
    session = ChatSession.objects.filter(document=document).first()
    if session is None:
        session = ChatSession.objects.create(document=document)

    if request.method == "POST":
        question = request.POST.get("question", "").strip()
        if question:
            ask(question, document.pk, session)
        return redirect("chat:session", document_id=document.pk)

    return render(
        request,
        "chat/session.html",
        {
            "document": document,
            "session": session,
            # Named chat_messages, not messages - "messages" is reserved
            # by django.contrib.messages' context processor (base.html's
            # flash-message banner) and would silently shadow it.
            "chat_messages": session.messages.all(),
            "active_nav": "chat",
        },
    )
