import logging
from typing import Dict, Any, List, Optional
from django.conf import settings
from debugger.models import UploadedDocument, AnalysisRecord
from debugger.services.retriever import retriever
from debugger.services.gemini_service import gemini_service, GeminiServiceError

logger = logging.getLogger(__name__)

class DebuggerPipeline:
    """Orchestrates RAG retrieval, Gemini evidence synthesis, and persistence."""

    def build_retrieval_query(
        self,
        language: str,
        problem: str,
        error: str = "",
        expected: str = "",
        code: str = ""
    ) -> str:
        """
        Synthesizes a high-signal search query from code, language, and reported behavior.
        Extracts key function names, exception types, and terminology.
        """
        parts = [f"Language: {language}"]
        if problem:
            parts.append(f"Problem: {problem.strip()}")
        if error:
            parts.append(f"Error: {error.strip()}")
        if expected:
            parts.append(f"Expected: {expected.strip()}")

        # Extract top 5 lines of code or code snippet to capture specific APIs/functions
        if code:
            code_lines = [line.strip() for line in code.strip().splitlines() if line.strip() and not line.strip().startswith(('#', '//', '/*'))]
            key_code_terms = " ".join(code_lines[:4])
            if key_code_terms:
                parts.append(f"Context: {key_code_terms[:200]}")

        return " | ".join(parts)

    def analyze(
        self,
        user_id: str,
        language: str,
        submitted_code: str,
        problem_description: str,
        error_message: str = "",
        expected_behavior: str = "",
        user_question: str = ""
    ) -> Dict[str, Any]:
        """
        Executes evidence-grounded debugging analysis:
        1. Checks user's document knowledge base.
        2. Retrieves top semantically relevant passages via ChromaDB.
        3. Invokes Gemini 3.1 with strict evidence-grounding instructions.
        4. Distinguishes documentation-backed claims vs code hypothesis.
        5. Saves analysis history record.
        """
        if not submitted_code or not submitted_code.strip():
            raise ValueError("Submitted code cannot be empty.")
        if not problem_description or not problem_description.strip():
            raise ValueError("Problem description is required.")

        # Check document count for this user
        user_docs_count = UploadedDocument.objects.filter(user_id=user_id, status='ready').count()

        # Step 1: Vector Retrieval (RAG)
        retrieved_passages: List[Dict[str, Any]] = []
        is_evidence_backed = False
        documentation_status = "ok"

        if user_docs_count == 0:
            documentation_status = "no_documents_uploaded"
        else:
            query = self.build_retrieval_query(
                language=language,
                problem=problem_description,
                error=error_message,
                expected=expected_behavior,
                code=submitted_code
            )

            retrieved_passages = retriever.retrieve_relevant_passages(
                query=query,
                user_id=user_id,
                top_k=getattr(settings, 'TOP_K_RESULTS', 5),
                threshold=getattr(settings, 'SIMILARITY_THRESHOLD', 0.35)
            )

            if not retrieved_passages:
                documentation_status = "no_relevant_evidence"
            else:
                is_evidence_backed = True
                documentation_status = "grounded"

        # Step 2: Synthesis with Gemini
        diagnosis = gemini_service.diagnose_bug(
            language=language,
            submitted_code=submitted_code,
            problem_description=problem_description,
            error_message=error_message,
            expected_behavior=expected_behavior,
            user_question=user_question,
            retrieved_passages=retrieved_passages
        )

        # Enhance limitations message if documentation was missing or irrelevant
        if documentation_status == "no_documents_uploaded":
            diagnosis['limitations'] = (
                "Notice: No programming documentation has been uploaded to your knowledge base yet. "
                "Evidence-grounded debugging requires official documentation to verify specifications. "
                "The analysis above is a tentative code-based hypothesis."
            )
            diagnosis['is_evidence_backed'] = False
            status = 'no_evidence'
        elif documentation_status == "no_relevant_evidence":
            diagnosis['limitations'] = (
                "Notice: Uploaded documents in your knowledge base do not contain passages with sufficient "
                "semantic relevance to this specific problem. The analysis above is a code-based hypothesis "
                "without documentation verification."
            )
            diagnosis['is_evidence_backed'] = False
            status = 'no_evidence'
        else:
            diagnosis['is_evidence_backed'] = True
            status = 'completed'

        diagnosis['documentation_status'] = documentation_status
        diagnosis['retrieved_passages'] = retrieved_passages

        # Step 3: Persist Analysis Record
        try:
            record = AnalysisRecord.objects.create(
                user_id=user_id,
                language=language,
                problem_description=problem_description,
                error_message=error_message,
                expected_behavior=expected_behavior,
                user_question=user_question,
                submitted_code=submitted_code,
                diagnosis_summary=diagnosis.get('summary', ''),
                severity=diagnosis.get('severity', 'medium'),
                code_observations=diagnosis.get('code_observations', []),
                root_causes=diagnosis.get('root_causes', []),
                corrected_code=diagnosis.get('corrected_code', ''),
                change_explanation=diagnosis.get('change_explanation', ''),
                suggested_tests=diagnosis.get('suggested_tests', []),
                evidence=retrieved_passages,
                limitations=diagnosis.get('limitations', ''),
                is_evidence_backed=diagnosis['is_evidence_backed'],
                status=status
            )
            diagnosis['analysis_id'] = str(record.id)
            diagnosis['created_at'] = record.created_at.isoformat()
        except Exception as e:
            logger.error("Failed to persist analysis record: %s", str(e))
            diagnosis['analysis_id'] = ""

        return diagnosis

# Singleton instance
debugger_pipeline = DebuggerPipeline()
