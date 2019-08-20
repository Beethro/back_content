from django import forms

from submission import models
from core import models as core_models

from django.utils.translation import ugettext_lazy as _

from hvad.forms import TranslatableModelForm 

class PublicationInfo(forms.ModelForm):
    class Meta:
        model = models.TransArticle
        fields = ('date_accepted', 'date_published', 'page_numbers', 'primary_issue', 'peer_reviewed', 'render_galley')

    def __init__(self, *args, **kwargs):
        super(PublicationInfo, self).__init__(*args, **kwargs)
        if 'instance' in kwargs:
            article = kwargs['instance']
            self.fields['primary_issue'].queryset = article.journal.issue_set.all()
            #self.fields['render_galley'].queryset = article.galley_set.all()
            self.fields['date_accepted'].widget.attrs['class'] = 'datepicker'
            self.fields['date_published'].widget.attrs['class'] = 'datepicker'


class RemoteArticle(forms.ModelForm):
    class Meta:
        model = models.TransArticle
        fields = ('is_remote', 'remote_url')


class RemoteParse(forms.Form):
    url = forms.CharField(required=True, label="Enter a URL or a DOI.")
    mode = forms.ChoiceField(required=True, choices=(('url', 'URL'), ('doi', 'DOI')))


class BackContentAuthorForm(forms.ModelForm):

    class Meta:
        model = core_models.Account
        exclude = (
            'date_joined',
            'activation_code'
            'date_confirmed'
            'confirmation_code'
            'reset_code'
            'reset_code_validated'
            'roles'
            'interest'
            'is_active'
            'is_staff'
            'is_admin'
            'password',
            'username',
            'roles',

        )

        widgets = {
            'first_name': forms.TextInput(attrs={'placeholder': 'First name'}),
            'middle_name': forms.TextInput(attrs={'placeholder': 'Middle name'}),
            'last_name': forms.TextInput(attrs={'placeholder': 'Last name'}),
            'biography': forms.Textarea(
                attrs={'placeholder': 'Enter biography here'}),
            'institution': forms.TextInput(attrs={'placeholder': 'Institution'}),
            'department': forms.TextInput(attrs={'placeholder': 'Department'}),
            'twitter': forms.TextInput(attrs={'placeholder': 'Twitter handle'}),
            'linkedin': forms.TextInput(attrs={'placeholder': 'LinkedIn profile'}),
            'impactstory': forms.TextInput(attrs={'placeholder': 'ImpactStory profile'}),
            'orcid': forms.TextInput(attrs={'placeholder': 'ORCID ID'}),
            'email': forms.TextInput(attrs={'placeholder': 'Email address'}),

        }

    def __init__(self, *args, **kwargs):
        super(BackContentAuthorForm, self).__init__(*args, **kwargs)
        self.fields['password'].required = False
        self.fields['first_name'].required = False
        self.fields['last_name'].required = False
        self.fields['institution'].required = False

class TransArticleInfo(TranslatableModelForm):

    class Meta:
        model = models.TransArticle
        fields = ('title', 'subtitle', 'abstract', 'non_specialist_summary',
                  'language', 'section', 'license', 'primary_issue',
                  'page_numbers', 'is_remote', 'remote_url', 'peer_reviewed')

        widgets = {
            'title': forms.TextInput(attrs={'placeholder': _('Title')}),
            'title_de': forms.TextInput(attrs={'placeholder': _('Title (de)')}),
            'subtitle': forms.TextInput(attrs={'placeholder': _('Subtitle')}),
            'subtitle_de': forms.TextInput(attrs={'placeholder': _('Subtitle')}),
            'abstract': forms.Textarea(attrs={'placeholder': _('Enter your article\'s abstract here')}),
            'abstract_de': forms.Textarea(attrs={'placeholder': _('Enter your article\'s abstract here (de)')}),
        }

    def __init__(self, *args, **kwargs):
        elements = kwargs.pop('additional_fields', None)
        submission_summary = kwargs.pop('submission_summary', None)
        journal = kwargs.pop('journal', None)

        super(TransArticleInfo, self).__init__(*args, **kwargs)
        if 'instance' in kwargs:
            article = kwargs['instance']
            self.fields['section'].queryset = models.Section.objects.language().fallbacks('en').filter(
                journal=article.journal,
                public_submissions=True,
            )
            self.fields['license'].queryset = models.Licence.objects.filter(
                journal=article.journal,
                available_for_submission=True,
            )
            self.fields['section'].required = True
            self.fields['license'].required = True
            self.fields['primary_issue'].queryset = article.journal.issues()

            abstracts_required = article.journal.get_setting(
                'general',
                'abstract_required',
            )

            if abstracts_required:
                self.fields['abstract'].required = True

            if submission_summary:
                self.fields['non_specialist_summary'].required = True

            # Pop fields based on journal.submissionconfiguration
            if journal:
                if not journal.submissionconfiguration.subtitle:
                    self.fields.pop('subtitle')

                if not journal.submissionconfiguration.abstract:
                    self.fields.pop('abstract')

                if not journal.submissionconfiguration.language:
                    self.fields.pop('language')

                if not journal.submissionconfiguration.license:
                    self.fields.pop('license')

                if not journal.submissionconfiguration.keywords:
                    self.fields.pop('keywords')

                if not journal.submissionconfiguration.keywords:
                    self.fields.pop('keywords_de')

                if not journal.submissionconfiguration.section:
                    self.fields.pop('section')

            # Add additional fields
            if elements:
                for element in elements:
                    if element.kind == 'text':
                        self.fields[element.name] = forms.CharField(
                            widget=forms.TextInput(attrs={'div_class': element.width}),
                            required=element.required)
                    elif element.kind == 'textarea':
                        self.fields[element.name] = forms.CharField(widget=forms.Textarea,
                                                                    required=element.required)
                    elif element.kind == 'date':
                        self.fields[element.name] = forms.CharField(
                            widget=forms.DateInput(attrs={'class': 'datepicker', 'div_class': element.width}),
                            required=element.required)

                    elif element.kind == 'select':
                        choices = render_choices(element.choices)
                        self.fields[element.name] = forms.ChoiceField(
                            widget=forms.Select(attrs={'div_class': element.width}), choices=choices,
                            required=element.required)

                    elif element.kind == 'email':
                        self.fields[element.name] = forms.EmailField(
                            widget=forms.TextInput(attrs={'div_class': element.width}),
                            required=element.required)
                    elif element.kind == 'check':
                        self.fields[element.name] = forms.BooleanField(
                            widget=forms.CheckboxInput(attrs={'is_checkbox': True}),
                            required=element.required)

                    self.fields[element.name].help_text = element.help_text
                    self.fields[element.name].label = element.name

                    if article:
                        try:
                            check_for_answer = models.FieldAnswer.objects.get(field=element, article=article)
                            self.fields[element.name].initial = check_for_answer.answer
                        except models.FieldAnswer.DoesNotExist:
                            pass

    def save(self, commit=True, request=None):
        article = super(ArticleInfo, self).save(commit=False)

        if request:
            import submission.models as submission_models
            posted_keywords_de = request.POST.get('keywords_de','').split(',')
            for keyword_de in posted_keywords_de:
                if keyword_de != '':
                    obj, _ = submission_models.KeywordDe.objects.get_or_create(
                            word=keyword_de)
                    article.keywords_de.add(obj)

            for keyword_de in article.keywords_de.all():
                if keyword_de.word not in posted_keywords_de:
                    article.keywords_de.remove(keyword_de)



            additional_fields = models.Field.objects.filter(journal=request.journal)

            for field in additional_fields:
                answer = request.POST.get(field.name, None)
                if answer:
                    try:
                        field_answer = models.FieldAnswer.objects.get(article=article, field=field)
                        field_answer.answer = answer
                        field_answer.save()
                    except models.FieldAnswer.DoesNotExist:
                        field_answer = models.FieldAnswer.objects.create(article=article, field=field, answer=answer)

            request.journal.submissionconfiguration.handle_defaults(article)

        if commit:
            article.save()

        return article

class LanguageInfo(forms.Form):
    language_code = forms.CharField(label='Language', max_length=100)