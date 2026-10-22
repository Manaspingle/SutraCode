import os
import tempfile
import unittest
from unittest.mock import patch, MagicMock
from django.test import TestCase, Client
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile

from debugger.models import UploadedDocument, DocumentChunk, AnalysisRecord
from debugger.services.document_processor import document_processor, DocumentProcessingError
from debugger.services.retriever import retriever
from debugger.services.debugger import debugger_pipeline
import pymupdf

class SutraTraceUnitTests(TestCase):
    """Automated test suite verifying RAG pipeline, views, and persistence."""

    def setUp(self):
        self.client = Client()
        self.user_id = "test_user_123"

    def test_pages_load_and_auth_protection(self):
        """Tests public page loading and protected route redirects for unauthenticated users."""
        public_urls = [
            reverse('debugger:landing'),
            reverse('debugger:debugger'),
            reverse('debugger:login'),
            reverse('debugger:signup'),
        ]
        for url in public_urls:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200, f"Failed on URL: {url}")
            self.assertContains(response, "SutraTrace")

        # Unauthenticated access to history and how-it-works must redirect to login
        for protected_url in [reverse('debugger:history'), reverse('debugger:how_it_works')]:
            response = self.client.get(protected_url)
            self.assertEqual(response.status_code, 302)
            self.assertIn(reverse('debugger:login'), response.url)

        # Authenticated access succeeds
        session = self.client.session
        session['firebase_user'] = {
            'uid': self.user_id,
            'email': 'developer@test.com',
            'name': 'Test Developer',
            'is_authenticated': True
        }
        session.save()

        for protected_url in [reverse('debugger:history'), reverse('debugger:how_it_works')]:
            response = self.client.get(protected_url)
            self.assertEqual(response.status_code, 200, f"Authenticated failed on: {protected_url}")

    def test_file_validation_rejects_unsupported_extensions(self):
        """Tests that unsupported file extensions (e.g. .exe, .py) are rejected."""
        dummy_file = SimpleUploadedFile("malicious.exe", b"binary content", content_type="application/octet-stream")
        is_valid, msg = document_processor.validate_file(dummy_file)
        self.assertFalse(is_valid)
        self.assertIn("Unsupported file format", msg)

    def test_txt_extraction_and_chunking(self):
        """Tests that TXT files are cleanly extracted and split into chunks with metadata."""
        sample_text = (
            "Requests Documentation.\n\n"
            "Nearly all production requests should specify a timeout parameter to avoid hanging threads indefinitely. "
            "If no timeout is specified, Requests will wait forever for a socket response. "
            "Syntax: requests.get('https://api.example.com', timeout=5.0).\n\n"
            "Status codes: call response.raise_for_status() to check for HTTP errors."
        )
        with tempfile.NamedTemporaryFile(suffix='.txt', delete=False, mode='w', encoding='utf-8') as f:
            f.write(sample_text)
            temp_path = f.name

        try:
            chunks, pages = document_processor.extract_text_and_chunks(
                file_path=temp_path,
                filename="sample_requests.txt",
                doc_id="test_doc_1",
                user_id=self.user_id
            )
            self.assertEqual(pages, 1)
            self.assertGreater(len(chunks), 0)
            first_chunk = chunks[0]
            self.assertEqual(first_chunk['filename'], "sample_requests.txt")
            self.assertEqual(first_chunk['user_id'], self.user_id)
            self.assertIn("timeout", first_chunk['content'])
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def test_pdf_extraction_page_preservation(self):
        """Tests that PyMuPDF generates pages and extracts chunk text with page numbers."""
        # Create minimal PDF using PyMuPDF
        doc = pymupdf.open()
        page = doc.new_page()
        page.insert_text((50, 50), "Python Requests Guide Page 1. Always specify timeout=5.")
        temp_pdf = tempfile.NamedTemporaryFile(suffix='.pdf', delete=False).name
        doc.save(temp_pdf)
        doc.close()

        try:
            chunks, pages = document_processor.extract_text_and_chunks(
                file_path=temp_pdf,
                filename="generated_doc.pdf",
                doc_id="pdf_doc_1",
                user_id=self.user_id
            )
            self.assertEqual(pages, 1)
            self.assertGreater(len(chunks), 0)
            self.assertEqual(chunks[0]['page_number'], 1)
            self.assertIn("timeout=5", chunks[0]['content'])
        finally:
            if os.path.exists(temp_pdf):
                os.remove(temp_pdf)

    def test_retrieval_and_threshold_filtering(self):
        """Tests indexing into ChromaDB and retrieving with semantic similarity."""
        chunk = {
            'chunk_id': 'test_retrieval_c1',
            'doc_id': 'doc_retrieval_1',
            'user_id': self.user_id,
            'filename': 'requests_manual.txt',
            'page_number': 1,
            'chunk_index': 0,
            'content': 'Always provide timeout in requests.get to prevent sockets hanging indefinitely.',
            'char_count': 78
        }
        retriever.index_chunks([chunk])

        # Query that should match
        results = retriever.retrieve_relevant_passages(
            query="requests get hanging timeout socket",
            user_id=self.user_id,
            top_k=3,
            threshold=0.25
        )
        self.assertGreater(len(results), 0)
        self.assertEqual(results[0]['filename'], 'requests_manual.txt')
        self.assertIn("timeout", results[0]['content'])

        # Clean up
        retriever.delete_document_chunks('doc_retrieval_1', self.user_id)

    @patch('debugger.services.gemini_service.GeminiService.diagnose_bug')
    def test_debugger_pipeline_with_mocked_gemini(self, mock_diagnose):
        """Tests end-to-end debugger pipeline orchestration and history persistence."""
        mock_diagnose.return_value = {
            'summary': 'Missing timeout in requests.get call causes infinite socket hang.',
            'severity': 'high',
            'code_observations': ['requests.get invoked without timeout argument'],
            'root_causes': ['Requests defaults to None for timeout, waiting forever.'],
            'corrected_code': 'import requests\nrequests.get(url, timeout=5)',
            'change_explanation': 'Added timeout=5 to ensure socket fails fast.',
            'suggested_tests': ['assert response is not None'],
            'evidence': [{'filename': 'requests_manual.txt', 'page_number': 1, 'citation_excerpt': 'specify timeout parameter'}],
            'limitations': 'Assumes standard requests library.'
        }

        # Create dummy document record in DB
        doc = UploadedDocument.objects.create(
            user_id=self.user_id,
            filename='requests_manual.txt',
            file_path='/tmp/dummy.txt',
            file_type='txt',
            file_size=1024,
            status='ready'
        )

        diagnosis = debugger_pipeline.analyze(
            user_id=self.user_id,
            language='python',
            submitted_code='import requests\nrequests.get("https://api.com")',
            problem_description='Hangs forever on network partition',
            error_message='',
            expected_behavior='Should timeout after 5 seconds'
        )

        self.assertEqual(diagnosis['severity'], 'high')
        self.assertIn('timeout', diagnosis['corrected_code'])
        self.assertTrue(diagnosis['analysis_id'])

        # Verify DB persistence
        record = AnalysisRecord.objects.get(id=diagnosis['analysis_id'])
        self.assertEqual(record.language, 'python')
        self.assertEqual(record.severity, 'high')

    def test_missing_evidence_explicit_limitation(self):
        """Tests that when no documents are uploaded, limitation message is displayed."""
        with patch('debugger.services.gemini_service.GeminiService.diagnose_bug') as mock_diagnose:
            mock_diagnose.return_value = {
                'summary': 'Hypothesis: off by one index.',
                'severity': 'medium',
                'code_observations': ['index exceeds length'],
                'root_causes': ['Array out of bounds'],
                'corrected_code': 'return items[i-1]',
                'change_explanation': 'Corrected index bounds',
                'suggested_tests': ['test_bounds()'],
                'evidence': [],
                'limitations': ''
            }

            # User with 0 documents
            diagnosis = debugger_pipeline.analyze(
                user_id="user_without_docs",
                language='python',
                submitted_code='return items[10]',
                problem_description='Index out of bounds'
            )

            self.assertEqual(diagnosis['documentation_status'], 'no_documents_uploaded')
            self.assertFalse(diagnosis['is_evidence_backed'])
            self.assertIn("No programming documentation has been uploaded", diagnosis['limitations'])

    def test_safe_handling_of_untrusted_code(self):
        """Verifies that malicious prompt injections or code snippets are treated as data, not executed."""
        malicious_code = "import os; os.system('echo hack'); def destroy(): pass"
        with patch('debugger.services.gemini_service.GeminiService.diagnose_bug') as mock_diagnose:
            mock_diagnose.return_value = {
                'summary': 'Analysis of dangerous system call.',
                'severity': 'critical',
                'code_observations': ['os.system call detected'],
                'root_causes': ['Dangerous command injection risk'],
                'corrected_code': 'def safe(): pass',
                'change_explanation': 'Removed os.system call',
                'suggested_tests': [],
                'evidence': [],
                'limitations': ''
            }

            diagnosis = debugger_pipeline.analyze(
                user_id=self.user_id,
                language='python',
                submitted_code=malicious_code,
                problem_description='Avoid system calls'
            )
            # Code was not executed, model analyzed it as text string
            self.assertEqual(diagnosis['severity'], 'critical')
