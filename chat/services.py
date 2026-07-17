from vectorstore.client import query as vector_query
from vectorstore.embedding import embed


def retrieve(query, document_id, top_k=5):
    """Embed `query` and return the top_k most similar chunks for the
    given document, nearest first. Same shape as vectorstore.client.query().
    """
    vector = embed(query)
    return vector_query(vector, document_id=document_id, top_k=top_k)


def ask(question, document_id, session):
    """Full ask/answer round trip for one chat turn: persist the user
    message, retrieve relevant chunks, generate an answer, persist the
    assistant message. Returns the assistant ChatMessage.
    """
    from .llm import get_provider
    from .models import ChatMessage

    ChatMessage.objects.create(session=session, role=ChatMessage.Role.USER, content=question)

    chunks = retrieve(question, document_id=document_id)
    answer = get_provider().generate(question, chunks)

    source_chunks = [
        {"chunk_id": c["chunk_id"], "page_number": c["page_number"]} for c in chunks
    ]
    return ChatMessage.objects.create(
        session=session,
        role=ChatMessage.Role.ASSISTANT,
        content=answer,
        source_chunks=source_chunks,
    )
