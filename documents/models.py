from django.db import models


class Document(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        READY = "ready", "Ready"
        FAILED = "failed", "Failed"

    file = models.FileField(upload_to="documents/")
    title = models.CharField(max_length=255)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )
    page_count = models.PositiveIntegerField(null=True, blank=True)
    error_message = models.TextField(blank=True, default="")
    file_hash = models.CharField(max_length=64, blank=True, default="", db_index=True)

    class Meta:
        ordering = ["-uploaded_at"]

    def __str__(self):
        return self.title


class Chunk(models.Model):
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name="chunks")
    text = models.TextField()
    page_number = models.PositiveIntegerField()
    chunk_index = models.PositiveIntegerField()
    embedded = models.BooleanField(default=False)

    class Meta:
        ordering = ["document_id", "chunk_index"]
        constraints = [
            models.UniqueConstraint(
                fields=["document", "chunk_index"], name="unique_chunk_index_per_document"
            )
        ]

    def __str__(self):
        return f"{self.document.title} chunk {self.chunk_index}"
