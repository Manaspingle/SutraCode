from django import forms

LANGUAGE_CHOICES = [
    ('python', 'Python'),
    ('javascript', 'JavaScript'),
    ('java', 'Java'),
    ('cpp', 'C++'),
    ('c', 'C'),
    ('sql', 'SQL'),
]

class CodeAnalysisForm(forms.Form):
    language = forms.ChoiceField(
        choices=LANGUAGE_CHOICES,
        initial='python',
        widget=forms.Select(attrs={'class': 'form-select select-custom', 'id': 'languageSelector'})
    )
    submitted_code = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control code-editor-area',
            'id': 'submittedCode',
            'placeholder': 'Paste your buggy code snippet here...',
            'rows': 14,
            'spellcheck': 'false'
        }),
        max_length=50000,
        required=True
    )
    problem_description = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control text-custom',
            'id': 'problemDescription',
            'placeholder': 'What unexpected behavior or bug are you encountering?',
            'rows': 3
        }),
        max_length=5000,
        required=True
    )
    error_message = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control text-custom font-mono',
            'id': 'errorMessage',
            'placeholder': 'Optional: Traceback, error logs, or compiler messages...',
            'rows': 3
        }),
        max_length=5000,
        required=False
    )
    expected_behavior = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control text-custom',
            'id': 'expectedBehavior',
            'placeholder': 'What was the expected output or specification?',
            'rows': 2
        }),
        max_length=5000,
        required=False
    )
    user_question = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'form-control text-custom',
            'id': 'userQuestion',
            'placeholder': 'Optional: Specific question (e.g. Why does this mutate state?)'
        }),
        max_length=2000,
        required=False
    )

class DocumentUploadForm(forms.Form):
    document = forms.FileField(
        widget=forms.FileInput(attrs={
            'class': 'form-control file-input-custom',
            'id': 'documentFileInput',
            'accept': '.pdf,.txt'
        }),
        required=True
    )
