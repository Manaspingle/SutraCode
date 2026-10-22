import os
import json
import logging
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponseBadRequest, HttpResponseForbidden
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import ensure_csrf_cookie
from django.conf import settings
from django.urls import reverse

from debugger.models import UploadedDocument, DocumentChunk, AnalysisRecord
from debugger.forms import CodeAnalysisForm, DocumentUploadForm
from debugger.services.firebase_service import firebase_service
from debugger.services.document_processor import document_processor, DocumentProcessingError
from debugger.services.retriever import retriever
from debugger.services.debugger import debugger_pipeline
from debugger.services.gemini_service import GeminiServiceError

logger = logging.getLogger(__name__)

def _get_request_user(request) -> dict:
    """Helper to extract verified Firebase user or guest identity from request."""
    # 1. Check verified Firebase user stored in Django session
    session_user = request.session.get('firebase_user')
    if session_user and session_user.get('is_authenticated'):
        return session_user

    # 2. Check Authorization header
    auth_header = request.headers.get('Authorization', '')
    if auth_header:
        verified = firebase_service.verify_token(auth_header)
        if verified.get('is_authenticated'):
            request.session['firebase_user'] = verified
            return verified

    # 3. Fallback to guest identity
    guest_uid = request.session.get('guest_uid')
    if not guest_uid:
        import uuid
        guest_uid = f"guest_{uuid.uuid4().hex[:12]}"
        request.session['guest_uid'] = guest_uid

    return {
        'uid': guest_uid,
        'email': '',
        'name': 'Guest Developer',
        'picture': '',
        'is_authenticated': False,
    }

# ==========================================
# Template Views
# ==========================================

@ensure_csrf_cookie
def landing_view(request):
    """Product Landing Page."""
    user = _get_request_user(request)
    return render(request, 'debugger/landing.html', {'user': user})

@ensure_csrf_cookie
def debugger_view(request):
    """Optimal, developer-first Debugging Workspace."""
    user = _get_request_user(request)
    form = CodeAnalysisForm()
    upload_form = DocumentUploadForm()
    return render(request, 'debugger/debugger.html', {
        'form': form,
        'upload_form': upload_form,
        'user': user,
    })

@ensure_csrf_cookie
def results_view(request, analysis_id):
    """Dedicated Analysis Results Page."""
    user = _get_request_user(request)
    record = get_object_or_404(AnalysisRecord, id=analysis_id)
    return render(request, 'debugger/results.html', {
        'record': record,
        'user': user,
    })

@ensure_csrf_cookie
def history_view(request):
    """Analysis History View (Protected: requires sign-in/sign-up)."""
    user = _get_request_user(request)
    if not user.get('is_authenticated'):
        return redirect(f"{reverse('debugger:login')}?next={request.path}")

    records = AnalysisRecord.objects.filter(user_id=user['uid'])[:50]
    return render(request, 'debugger/history.html', {
        'records': records,
        'user': user,
    })

@ensure_csrf_cookie
def how_it_works_view(request):
    """Architecture and RAG documentation page (Protected: requires sign-in/sign-up)."""
    user = _get_request_user(request)
    if not user.get('is_authenticated'):
        return redirect(f"{reverse('debugger:login')}?next={request.path}")

    return render(request, 'debugger/how_it_works.html', {'user': user})

@ensure_csrf_cookie
def auth_view(request):
    """Unified Sign-In and Sign-Up page."""
    user = _get_request_user(request)
    next_url = request.GET.get('next', reverse('debugger:debugger'))
    mode = request.GET.get('mode', 'login')

    if user.get('is_authenticated'):
        return redirect(next_url)

    return render(request, 'debugger/auth.html', {
        'next_url': next_url,
        'mode': mode,
        'user': user
    })

def logout_view(request):
    """Logs out user and clears session."""
    if 'firebase_user' in request.session:
        del request.session['firebase_user']
    return redirect(reverse('debugger:landing'))


# ==========================================
# REST API Endpoints
# ==========================================

@require_http_methods(["POST"])
def api_session_login(request):
    """Verifies Firebase ID token and links to Django session."""
    try:
        data = json.loads(request.body)
        id_token = data.get('id_token')
        if not id_token:
            return JsonResponse({'success': False, 'error': 'Missing ID token.'}, status=400)

        verified = firebase_service.verify_token(f"Bearer {id_token}")
        if not verified.get('is_authenticated'):
            return JsonResponse({'success': False, 'error': 'Invalid authentication token.'}, status=401)

        request.session['firebase_user'] = verified
        request.session.modified = True
        return JsonResponse({'success': True, 'user': verified})
    except Exception as e:
        logger.error("Session login error: %s", str(e))
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@require_http_methods(["POST"])
def api_session_logout(request):
    """Clears authenticated session."""
    if 'firebase_user' in request.session:
        del request.session['firebase_user']
    request.session.modified = True
    return JsonResponse({'success': True})

@require_http_methods(["POST"])
def api_upload_document(request):
    """Uploads, validates, chunks, and indexes a PDF/TXT document."""
    user = _get_request_user(request)
    upload_file = request.FILES.get('document')

    if not upload_file:
        return JsonResponse({'success': False, 'error': 'No file uploaded.'}, status=400)

    is_valid, err = document_processor.validate_file(upload_file)
    if not is_valid:
        return JsonResponse({'success': False, 'error': err}, status=400)

    user_upload_dir = os.path.join(settings.MEDIA_ROOT, 'documents', str(user['uid']))
    os.makedirs(user_upload_dir, exist_ok=True)
    file_path = os.path.join(user_upload_dir, upload_file.name)

    with open(file_path, 'wb+') as dest:
        for chunk in upload_file.chunks():
            dest.write(chunk)

    ext = os.path.splitext(upload_file.name)[1].lower().replace('.', '')

    doc_record = UploadedDocument.objects.create(
        user_id=user['uid'],
        filename=upload_file.name,
        file_path=file_path,
        file_type=ext,
        file_size=upload_file.size,
        status='processing'
    )

    try:
        chunks, total_pages = document_processor.extract_text_and_chunks(
            file_path=file_path,
            filename=upload_file.name,
            doc_id=str(doc_record.id),
            user_id=user['uid']
        )

        indexed_count = retriever.index_chunks(chunks)

        chunk_objs = [
            DocumentChunk(
                document=doc_record,
                chunk_id=c['chunk_id'],
                user_id=user['uid'],
                page_number=c['page_number'],
                chunk_index=c['chunk_index'],
                content=c['content'],
                char_count=c['char_count']
            )
            for c in chunks
        ]
        DocumentChunk.objects.bulk_create(chunk_objs)

        doc_record.page_count = total_pages
        doc_record.chunk_count = indexed_count
        doc_record.status = 'ready'
        doc_record.save()

        return JsonResponse({
            'success': True,
            'document': {
                'id': str(doc_record.id),
                'filename': doc_record.filename,
                'file_type': doc_record.file_type,
                'file_size': doc_record.file_size_display,
                'page_count': doc_record.page_count,
                'chunk_count': doc_record.chunk_count,
                'status': doc_record.status,
                'uploaded_at': doc_record.uploaded_at.strftime("%b %d, %H:%M")
            }
        })

    except DocumentProcessingError as dpe:
        doc_record.status = 'empty' if 'No extractable text' in str(dpe) else 'error'
        doc_record.error_message = str(dpe)
        doc_record.save()
        return JsonResponse({'success': False, 'error': str(dpe)}, status=422)

    except Exception as e:
        logger.exception("Unexpected error processing document: %s", str(e))
        doc_record.status = 'error'
        doc_record.error_message = str(e)
        doc_record.save()
        return JsonResponse({'success': False, 'error': f"Processing failed: {str(e)}"}, status=500)


@require_http_methods(["GET"])
def api_list_documents(request):
    """Returns list of indexed documents for the current user."""
    user = _get_request_user(request)
    docs = UploadedDocument.objects.filter(user_id=user['uid'])
    data = [
        {
            'id': str(d.id),
            'filename': d.filename,
            'file_type': d.file_type,
            'file_size': d.file_size_display,
            'page_count': d.page_count,
            'chunk_count': d.chunk_count,
            'status': d.status,
            'error_message': d.error_message,
            'uploaded_at': d.uploaded_at.strftime("%b %d, %H:%M")
        }
        for d in docs
    ]
    return JsonResponse({'success': True, 'documents': data})


@require_http_methods(["POST", "DELETE"])
def api_delete_document(request, doc_id):
    """Deletes a document from disk, SQLite, and ChromaDB."""
    user = _get_request_user(request)
    try:
        doc = UploadedDocument.objects.get(id=doc_id, user_id=user['uid'])
    except UploadedDocument.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Document not found.'}, status=404)

    retriever.delete_document_chunks(doc_id=str(doc.id), user_id=user['uid'])

    if os.path.exists(doc.file_path):
        try:
            os.remove(doc.file_path)
        except OSError as e:
            logger.warning("Could not delete file from disk: %s", str(e))

    doc.delete()
    return JsonResponse({'success': True, 'message': 'Document removed from index.'})


@require_http_methods(["POST"])
def api_analyze(request):
    """Analyzes submitted code with RAG vector search and Gemini reasoning."""
    user = _get_request_user(request)

    if request.content_type == 'application/json':
        try:
            body = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'error': 'Malformed JSON payload.'}, status=400)
        language = body.get('language', 'python')
        submitted_code = body.get('submitted_code', '')
        problem_description = body.get('problem_description', '')
        error_message = body.get('error_message', '')
        expected_behavior = body.get('expected_behavior', '')
        user_question = body.get('user_question', '')
    else:
        language = request.POST.get('language', 'python')
        submitted_code = request.POST.get('submitted_code', '')
        problem_description = request.POST.get('problem_description', '')
        error_message = request.POST.get('error_message', '')
        expected_behavior = request.POST.get('expected_behavior', '')
        user_question = request.POST.get('user_question', '')

    if not submitted_code or not submitted_code.strip():
        return JsonResponse({'success': False, 'error': 'Code snippet is required.'}, status=400)

    if not problem_description or not problem_description.strip():
        return JsonResponse({'success': False, 'error': 'Problem description is required.'}, status=400)

    try:
        diagnosis = debugger_pipeline.analyze(
            user_id=user['uid'],
            language=language,
            submitted_code=submitted_code,
            problem_description=problem_description,
            error_message=error_message,
            expected_behavior=expected_behavior,
            user_question=user_question
        )
        return JsonResponse({'success': True, 'diagnosis': diagnosis})

    except GeminiServiceError as gse:
        logger.error("Gemini service error: %s", str(gse))
        return JsonResponse({'success': False, 'error': str(gse)}, status=503)

    except ValueError as ve:
        return JsonResponse({'success': False, 'error': str(ve)}, status=400)

    except Exception as e:
        logger.exception("Unexpected error in analysis: %s", str(e))
        return JsonResponse({'success': False, 'error': f"Analysis failed: {str(e)}"}, status=500)


@require_http_methods(["GET"])
def api_history(request):
    """Returns analysis history records for the authenticated user."""
    user = _get_request_user(request)
    records = AnalysisRecord.objects.filter(user_id=user['uid'])[:50]
    data = [
        {
            'id': str(r.id),
            'language': r.language,
            'summary': r.diagnosis_summary,
            'severity': r.severity,
            'status': r.status,
            'is_evidence_backed': r.is_evidence_backed,
            'created_at': r.created_at.strftime("%b %d, %Y - %H:%M")
        }
        for r in records
    ]
    return JsonResponse({'success': True, 'history': data})


@require_http_methods(["POST"])
def api_load_sample_doc(request):
    """Loads and indexes the bundled official Python Requests or FastAPI sample documentation."""
    user = _get_request_user(request)
    sample_type = request.POST.get('sample_type', 'requests')
    
    sample_path = os.path.join(settings.BASE_DIR, 'sample_docs', f"{sample_type}_guide.txt")
    if not os.path.exists(sample_path):
        return JsonResponse({'success': False, 'error': 'Sample document not found on server.'}, status=404)

    filename = f"Official_{sample_type.capitalize()}_Documentation.txt"
    with open(sample_path, 'r', encoding='utf-8') as f:
        content = f.read()

    user_upload_dir = os.path.join(settings.MEDIA_ROOT, 'documents', str(user['uid']))
    os.makedirs(user_upload_dir, exist_ok=True)
    dest_path = os.path.join(user_upload_dir, filename)
    with open(dest_path, 'w', encoding='utf-8') as f:
        f.write(content)

    doc_record = UploadedDocument.objects.create(
        user_id=user['uid'],
        filename=filename,
        file_path=dest_path,
        file_type='txt',
        file_size=len(content.encode('utf-8')),
        status='processing'
    )

    try:
        chunks, total_pages = document_processor.extract_text_and_chunks(
            file_path=dest_path,
            filename=filename,
            doc_id=str(doc_record.id),
            user_id=user['uid']
        )
        indexed_count = retriever.index_chunks(chunks)

        chunk_objs = [
            DocumentChunk(
                document=doc_record,
                chunk_id=c['chunk_id'],
                user_id=user['uid'],
                page_number=c['page_number'],
                chunk_index=c['chunk_index'],
                content=c['content'],
                char_count=c['char_count']
            )
            for c in chunks
        ]
        DocumentChunk.objects.bulk_create(chunk_objs)

        doc_record.page_count = total_pages
        doc_record.chunk_count = indexed_count
        doc_record.status = 'ready'
        doc_record.save()

        return JsonResponse({
            'success': True,
            'message': f"Sample documentation '{filename}' indexed successfully!",
            'document': {
                'id': str(doc_record.id),
                'filename': doc_record.filename,
                'file_type': doc_record.file_type,
                'file_size': doc_record.file_size_display,
                'page_count': doc_record.page_count,
                'chunk_count': doc_record.chunk_count,
                'status': doc_record.status,
                'uploaded_at': doc_record.uploaded_at.strftime("%b %d, %H:%M")
            }
        })
    except Exception as e:
        doc_record.status = 'error'
        doc_record.error_message = str(e)
        doc_record.save()
        return JsonResponse({'success': False, 'error': f"Failed to index sample doc: {str(e)}"}, status=500)
