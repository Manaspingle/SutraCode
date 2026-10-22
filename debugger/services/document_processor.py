import os
import re
import uuid
import logging
from typing import List, Dict, Any, Tuple
from django.conf import settings
import pymupdf

logger = logging.getLogger(__name__)

class DocumentProcessingError(Exception):
    """Raised when document extraction or chunking fails."""
    pass

class DocumentProcessor:
    """Extracts text and metadata from PDF and TXT documents, chunking for RAG."""

    ALLOWED_EXTENSIONS = {'.pdf', '.txt'}
    MAX_FILE_SIZE = getattr(settings, 'FILE_UPLOAD_MAX_MEMORY_SIZE', 15 * 1024 * 1024)  # 15MB
    TARGET_CHUNK_SIZE = 850  # 700 - 1000 characters
    CHUNK_OVERLAP = 150

    def validate_file(self, uploaded_file) -> Tuple[bool, str]:
        """Validates file extension, MIME type, and size."""
        name = uploaded_file.name
        ext = os.path.splitext(name)[1].lower()

        if ext not in self.ALLOWED_EXTENSIONS:
            return False, f"Unsupported file format '{ext}'. Only PDF and TXT files are accepted."

        if uploaded_file.size > self.MAX_FILE_SIZE:
            mb = self.MAX_FILE_SIZE / (1024 * 1024)
            return False, f"File exceeds maximum allowed size of {mb:.0f}MB."

        if uploaded_file.size == 0:
            return False, "Uploaded file is empty."

        return True, ""

    def extract_text_and_chunks(self, file_path: str, filename: str, doc_id: str, user_id: str) -> Tuple[List[Dict[str, Any]], int]:
        """
        Extracts text from PDF or TXT file and produces chunks with metadata.
        Returns: (chunks_list, total_pages)
        """
        ext = os.path.splitext(filename)[1].lower()

        if ext == '.pdf':
            return self._process_pdf(file_path, filename, doc_id, user_id)
        elif ext == '.txt':
            return self._process_txt(file_path, filename, doc_id, user_id)
        else:
            raise DocumentProcessingError(f"Unsupported file type: {ext}")

    def _process_pdf(self, file_path: str, filename: str, doc_id: str, user_id: str) -> Tuple[List[Dict[str, Any]], int]:
        """Extracts text from PDF page by page using PyMuPDF."""
        chunks = []
        try:
            doc = pymupdf.open(file_path)
            total_pages = len(doc)

            if total_pages == 0:
                raise DocumentProcessingError("PDF contains no pages.")

            total_extracted_text = ""
            chunk_global_idx = 0

            for page_idx in range(total_pages):
                page = doc[page_idx]
                page_text = page.get_text("text")
                if not page_text or not page_text.strip():
                    continue

                total_extracted_text += page_text + "\n"
                page_num = page_idx + 1

                # Chunk the page text
                page_chunks = self._chunk_text(page_text)
                for c_text in page_chunks:
                    chunk_id = f"{doc_id}_p{page_num}_c{chunk_global_idx}"
                    chunks.append({
                        'chunk_id': chunk_id,
                        'doc_id': doc_id,
                        'user_id': user_id,
                        'filename': filename,
                        'page_number': page_num,
                        'chunk_index': chunk_global_idx,
                        'content': c_text,
                        'char_count': len(c_text)
                    })
                    chunk_global_idx += 1

            doc.close()

            if not chunks or not total_extracted_text.strip():
                raise DocumentProcessingError("No extractable text found in this PDF (document may be scanned or empty).")

            return chunks, total_pages

        except Exception as e:
            if isinstance(e, DocumentProcessingError):
                raise
            logger.error("Error processing PDF %s: %s", filename, str(e))
            raise DocumentProcessingError(f"Failed to extract text from PDF: {str(e)}")

    def _process_txt(self, file_path: str, filename: str, doc_id: str, user_id: str) -> Tuple[List[Dict[str, Any]], int]:
        """Extracts text from TXT file with encoding detection."""
        content = ""
        # Try UTF-8 first, fallback to latin-1
        for enc in ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252']:
            try:
                with open(file_path, 'r', encoding=enc) as f:
                    content = f.read()
                break
            except (UnicodeDecodeError, UnicodeError):
                continue

        if not content.strip():
            raise DocumentProcessingError("TXT document is empty or contains no readable text.")

        raw_chunks = self._chunk_text(content)
        chunks = []
        for idx, c_text in enumerate(raw_chunks):
            chunk_id = f"{doc_id}_c{idx}"
            chunks.append({
                'chunk_id': chunk_id,
                'doc_id': doc_id,
                'user_id': user_id,
                'filename': filename,
                'page_number': 1,
                'chunk_index': idx,
                'content': c_text,
                'char_count': len(c_text)
            })

        return chunks, 1

    def _chunk_text(self, text: str) -> List[str]:
        """
        Splits text into chunks of 700-1000 characters with 150 character overlap,
        respecting paragraph and sentence boundaries.
        """
        cleaned = re.sub(r'\r\n', '\n', text)
        cleaned = re.sub(r'\n{3,}', '\n\n', cleaned).strip()

        if not cleaned:
            return []

        if len(cleaned) <= self.TARGET_CHUNK_SIZE:
            return [cleaned]

        chunks = []
        start = 0
        text_len = len(cleaned)

        while start < text_len:
            end = min(start + self.TARGET_CHUNK_SIZE, text_len)

            if end < text_len:
                # Try finding a natural break point (paragraph break, sentence end, or newline)
                paragraph_break = cleaned.rfind('\n\n', start, end)
                if paragraph_break > start + 300:
                    end = paragraph_break + 2
                else:
                    newline_break = cleaned.rfind('\n', start, end)
                    if newline_break > start + 350:
                        end = newline_break + 1
                    else:
                        sentence_break = max(
                            cleaned.rfind('. ', start, end),
                            cleaned.rfind('; ', start, end),
                            cleaned.rfind(': ', start, end)
                        )
                        if sentence_break > start + 350:
                            end = sentence_break + 2

            chunk = cleaned[start:end].strip()
            if chunk:
                chunks.append(chunk)

            if end >= text_len:
                break

            # Advance start with overlap
            start = max(end - self.CHUNK_OVERLAP, start + 1)

        return chunks

# Singleton instance
document_processor = DocumentProcessor()
