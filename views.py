import requests
import json

from django.shortcuts import render, get_object_or_404, redirect
from django.core.urlresolvers import reverse
from django.contrib import messages
from django.utils import timezone, translation
from django.http import Http404
from django.template import loader
from django.template import RequestContext
from django.core import serializers
from django.http import JsonResponse
from django.contrib.messages import get_messages

from submission import models, forms, logic
from core import models as core_models, files
from plugins.back_content import forms as bc_forms, logic as bc_logic, plugin_settings
from production import logic as prod_logic
from identifiers import logic as id_logic
from security.decorators import editor_user_required
from utils import shared
from journal import logic as journal_logic
from events import logic as event_logic
from utils import views


@editor_user_required
def index(request):
    if request.POST:
        article = models.TransArticle.objects.language('en').fallbacks('en').create(journal=request.journal,
                                                date_accepted=timezone.now(),
                                                is_import=True)
        return redirect(reverse('bc_article', kwargs={'article_id': article.pk}))

    articles = models.TransArticle.objects.language().fallbacks('en').filter(journal=request.journal)

    template = 'back_content/new_article.html'
    context = {
        'articles': articles,
    }

    return render(request, template, context)

@editor_user_required
def article(request, article_id):
    
    current_language = translation.get_language()

    if request.POST:
        if 'language_code' in request.POST:
            languageForm = bc_forms.LanguageInfo(request.POST)
            if languageForm.is_valid():
                current_language = languageForm.cleaned_data['language_code']

    article = models.TransArticle.objects.language(current_language).fallbacks('en').filter(pk=article_id).first()
    keywords = models.TransKeyword.objects.language(current_language).filter(articles__id=article_id).values_list("word", flat=True)

    #if not current_language in article.get_available_languages():
    #    article.translate(current_language)
   
    article_form = forms.TransArticleInfo(instance=article, keywords=keywords, language=current_language)
    author_form = bc_forms.BackContentAuthorForm()
    pub_form = bc_forms.PublicationInfo(instance=article)
    remote_form = bc_forms.RemoteArticle(instance=article)
    modal = None

    if request.POST:        
        if not 'no_commit' in request.POST:
            if 'add_author' in request.POST:
                return handleAddAuthor(request, article)
            
            if 'xml' in request.POST or 'pdf' in request.POST or 'other' in request.POST:
                return handleFileUpload(request, article)
                
            if 'publish' in request.POST:
                handleSaveForm(request, article, current_language)
                if not article.stage == models.STAGE_PUBLISHED:
                    id_logic.generate_crossref_doi_with_pattern(article)
                    article.stage = models.STAGE_PUBLISHED
                    article.snapshot_authors(article)
                    article.save()

                if plugin_settings.IS_WORKFLOW_PLUGIN:
                    workflow_kwargs = {'handshake_url': 'bc_article',
                                    'request': request,
                                    'article': article,
                                    'switch_stage': True}
                    return event_logic.Events.raise_event(event_logic.Events.ON_WORKFLOW_ELEMENT_COMPLETE,
                                                        task_object=article,
                                                        **workflow_kwargs)
                else:
                    return redirect(reverse('bc_index'))

            if 'draft' in request.POST:
                handleSaveForm(request, article, current_language)
                return redirect(reverse('bc_index'))

            if 'delete' in request.POST:
                return redirect(reverse('bc_delete_article', kwargs={'article_id': article_id}))
          
    template = 'back_content/submission.html'
    context = {
        'current_language': current_language,
        'article': article,
        'article_form': article_form,
        'form': author_form,
        'pub_form': pub_form,
        'remote_form': remote_form,
        'galleys': prod_logic.get_all_galleys(article),
        'modal': modal,
    }

    return render(request, template, context)

@editor_user_required
def article_old(request, article_id):
    article = get_object_or_404(models.TransArticle, pk=article_id, journal=request.journal)

    if not article.license:
        default_configuration = request.journal.submissionconfiguration
        article.license = default_configuration.default_license

    article_form = forms.ArticleInfo(instance=article)
    author_form = bc_forms.BackContentAuthorForm()
    pub_form = bc_forms.PublicationInfo(instance=article)
    remote_form = bc_forms.RemoteArticle(instance=article)
    modal = None

    if request.POST:
        if 'add_author' in request.POST:
            return handleAddAuthor(request, article)
        
        if 'xml' in request.POST or 'pdf' in request.POST or 'other' in request.POST:
            return handleFileUpload(request, article)

        if 'publish' in request.POST:
            handleSaveForm(request, article)
            if not article.stage == models.STAGE_PUBLISHED:
                id_logic.generate_crossref_doi_with_pattern(article)
                article.stage = models.STAGE_PUBLISHED
                article.snapshot_authors(article)
                article.save()

            if plugin_settings.IS_WORKFLOW_PLUGIN:
                workflow_kwargs = {'handshake_url': 'bc_article',
                                   'request': request,
                                   'article': article,
                                   'switch_stage': True}
                return event_logic.Events.raise_event(event_logic.Events.ON_WORKFLOW_ELEMENT_COMPLETE,
                                                      task_object=article,
                                                      **workflow_kwargs)
            else:
                return redirect(reverse('bc_index'))

        if 'draft' in request.POST:
            handleSaveForm(request, article)
            return redirect(reverse('bc_index'))

        if 'delete' in request.POST:
            return redirect(reverse('bc_delete_article', kwargs={'article_id': article_id}))

    template = 'back_content/submission_old.html'
    context = {
        'article': article,
        'article_form': article_form,
        'form': author_form,
        'pub_form': pub_form,
        'galleys': prod_logic.get_all_galleys(article),
        'remote_form': remote_form,
        'modal': modal
    }

    return render(request, template, context)

@editor_user_required
def delete_article(request, article_id):
    article = models.TransArticle.objects.filter(pk=article_id)
    article.delete()
    messages.add_message(request, messages.SUCCESS, '%s deleted', article_id)
    return redirect(reverse('bc_index'))

@editor_user_required
def delete_author(request, article_id, author_id):
    """Allows submitting author to delete an author object."""
    article = models.TransArticle.objects.language().filter(pk=article_id).first()
    author = get_object_or_404(
        core_models.Account,
        pk=author_id
    )

    article.authors.remove(author)

    if article.correspondence_author == author:
        article.correspondence_author = None
        article.save()

    try:
        ordering = models.TransArticleAuthorOrder.objects.get(
            article=article,
            author=author,
        ).delete()
    except models.TransArticleAuthorOrder.DoesNotExist:
        pass

    return redirect(reverse('bc_article', kwargs={'article_id': article_id}))


@editor_user_required
def xml_import_upload(request):
    if request.POST and request.FILES:
        xml_file = request.FILES.get('xml_file')
        filename, path = files.save_file_to_temp(xml_file)
        return redirect(reverse('bc_xml_import_parse', kwargs={'filename': filename}))

    template = 'back_content/xml_import.html'
    context = {}

    return render(request, template, context)


@editor_user_required
def xml_import_parse(request, filename):
    path = files.get_temp_file_path_from_name(filename)

    article = logic.import_from_jats_xml(path, request.journal)
    return redirect(reverse('bc_article', kwargs={'article_id': article.pk}))


@editor_user_required
def doi_import(request):
    form = bc_forms.RemoteParse()

    if request.POST:
        form = bc_forms.RemoteParse(request.POST)
        if form.is_valid():
            print(form.cleaned_data)
            url = form.cleaned_data['url']
            mode = form.cleaned_data['mode']

            if mode == 'doi':
                r = requests.get('https://api.crossref.org/v1/works/{0}'.format(url)).json()
                article = bc_logic.get_and_parse_doi_metadata(r, request, doi=url)
                return redirect(reverse('bc_article', kwargs={'article_id': article.pk}))
            else:
                r = requests.get(url)
                article = bc_logic.parse_url_results(r, request)
                return redirect(reverse('bc_article', kwargs={'article_id': article.pk}))

    template = 'back_content/doi_import.html'
    context = {
        'form': form,
    }

    return render(request, template, context)


@editor_user_required
def preview_xml_galley(request, article_id, galley_id):
    """
    Allows an editor to preview an article's XML galleys.
    :param request: HttpRequest
    :param article_id: TransArticle object ID (INT)
    :param galley_id: Galley object ID (INT)
    :return: HttpResponse
    """

    article = get_object_or_404(models.TransArticle, journal=request.journal, pk=article_id)
    galley = core_models.Galley.objects.filter(article=article, file__mime_type__contains='/xml', pk=galley_id)

    if not galley:
        raise Http404

    content = journal_logic.list_galleys(article, galley)

    template = 'journal/article.html'
    context = {
        'article': article,
        'galleys': galley,
        'article_content': content
    }

    return render(request, template, context)


def handleAddAuthor(request, article):
    author_form = bc_forms.BackContentAuthorForm(request.POST)
    modal = 'author'
    context = { }


    author_exists = logic.check_author_exists(request.POST.get('email'))
    if author_exists:
        author_on_article = article.authors.filter(id=author_exists.id)

        if not author_on_article:
            article.authors.add(author_exists)
            messages.add_message(request, messages.SUCCESS, '%s added to the article' % author_exists.full_name())
            context = { 
                'url': reverse('bc_delete_author', kwargs={'article_id': article.pk, 'author_id': author_exists.pk }), 
                'author': serializers.serialize('json', [author_exists], fields=["first_name", "last_name", "email"]) 
            }
        else:
            messages.add_message(request, messages.ERROR, '%s is already author' % author_exists.full_name())
    else:
        if author_form.is_valid():
            if author_form.cleaned_data["first_name"] and author_form.cleaned_data["last_name"] and author_form.cleaned_data["institution"]:
                new_author = author_form.save(commit=False)
                new_author.username = new_author.email
                new_author.set_password(shared.generate_password())
                new_author.save()
                new_author.add_account_role(role_slug='author', journal=request.journal)
                article.authors.add(new_author)
                messages.add_message(request, messages.SUCCESS, '%s added to the article' % new_author.full_name())
                context = { 
                    'url': reverse('bc_delete_author', kwargs={'article_id': article.pk, 'author_id': author_exists.pk }), 
            'author': serializers.serialize('json', [new_author], fields=["first_name", "last_name", "email"]) 
                }
            else:
                messages.add_message(request, messages.ERROR, '%s could not be found. Enter Firstname, Lastname and Institution' % request.POST.get('email'))

    data = {
        'msg': loader.render_to_string('core/messages.html', { 'messages': get_messages(request) }, None),
        'context': json.dumps(context)
    }
    return JsonResponse(data)

def handleFileUpload(request, article):
    context = { }
    galley = None

    if 'xml' in request.POST:
        for uploaded_file in request.FILES.getlist('xml-file'):
            if not files.check_in_memory_mime_with_types(in_memory_file=uploaded_file, mime_types=files.MIMETYPES_WITH_FIGURES):
                messages.add_message(request, messages.WARNING, 'File is not XML/HTML!')
            else:
                galley = prod_logic.save_galley(article, request, uploaded_file, True, "XML", True)
                messages.add_message(request, messages.SUCCESS, 'File added!')

    if 'pdf' in request.POST:
        for uploaded_file in request.FILES.getlist('pdf-file'):
            if not files.check_in_memory_mime_with_types(in_memory_file=uploaded_file, mime_types=files.PDF_MIMETYPES):
                messages.add_message(request, messages.WARNING, 'File is not PDF!')
            else:
                galley = prod_logic.save_galley(article, request, uploaded_file, True, "PDF", True)
                messages.add_message(request, messages.SUCCESS, 'File added!')

    if 'other' in request.POST:
        for uploaded_file in request.FILES.getlist('other-file'):
            galley = prod_logic.save_galley(article, request, uploaded_file, True, "Other", True)
            messages.add_message(request, messages.SUCCESS, 'File added!')

    if galley != None:
        context['galley']= serializers.serialize('json', [galley], fields=["article", "file", "label"])
    
    data = {
        'msg': loader.render_to_string('core/messages.html', { 'messages': get_messages(request) }, None),
        'context': json.dumps(context)
    }
    return JsonResponse(data)

def handleSaveForm(request, article, current_language):

    article_form = forms.TransArticleInfo(request.POST, instance=article, language=current_language)

    if article_form.is_valid():
        keywords = article_form.cleaned_data['keywords']
        article_form.save()
    print(article_form.errors)

    correspondence_author = request.POST.get('main-author', None)

    if correspondence_author:
        author = core_models.Account.objects.get(pk=correspondence_author)
        article.correspondence_author = author
        article.save()

    pub_form = bc_forms.PublicationInfo(request.POST, instance=article)

    if pub_form.is_valid():
        pub_form.save()
        if article.primary_issue:
            article.primary_issue.articles.add(article)

        if article.date_published:
            article.stage = models.STAGE_READY_FOR_PUBLICATION
            article.save()

    remote_form = bc_forms.RemoteArticle(request.POST, instance=article)

    if remote_form.is_valid():
        remote_form.save()

    return True