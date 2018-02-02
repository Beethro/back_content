import requests

from django.shortcuts import render, get_object_or_404, redirect
from django.core.urlresolvers import reverse
from django.contrib import messages
from django.utils import timezone
from django.http import Http404

from submission import models, forms, logic
from core import models as core_models, files
from plugins.back_content import forms as bc_forms, logic as bc_logic, plugin_settings
from production import logic as prod_logic
from identifiers import logic as id_logic
from security.decorators import editor_user_required
from utils import shared
from journal import logic as journal_logic
from events import logic as event_logic


@editor_user_required
def index(request):
    if request.POST:
        article = models.Article.objects.create(journal=request.journal,
                                                date_accepted=timezone.now(),
                                                is_import=True)
        return redirect(reverse('bc_article', kwargs={'article_id': article.pk}))

    articles = models.Article.objects.filter(journal=request.journal)

    template = 'back_content/new_article.html'
    context = {
        'articles': articles,
    }

    return render(request, template, context)


@editor_user_required
def article(request, article_id):
    article = get_object_or_404(models.Article, pk=article_id, journal=request.journal)
    article_form = forms.ArticleInfo(instance=article)
    author_form = forms.AuthorForm()
    pub_form = bc_forms.PublicationInfo(instance=article)
    remote_form = bc_forms.RemoteArticle(instance=article)
    modal = None

    if request.POST:
        if 'save_section_1' in request.POST:
            article_form = forms.ArticleInfo(request.POST, instance=article)

            if article_form.is_valid():
                article_form.save()
                return redirect(reverse('bc_article', kwargs={'article_id': article.pk}))

        if 'save_section_2' in request.POST:
            correspondence_author = request.POST.get('main-author', None)

            if correspondence_author:
                author = core_models.Account.objects.get(pk=correspondence_author)
                article.correspondence_author = author
                article.save()
                return redirect(reverse('bc_article', kwargs={'article_id': article.pk}))

        if 'save_section_4' in request.POST:
            pub_form = bc_forms.PublicationInfo(request.POST, instance=article)

            if pub_form.is_valid():
                pub_form.save()
                if article.primary_issue:
                    article.primary_issue.articles.add(article)

                if article.date_published:
                    article.stage = models.STAGE_READY_FOR_PUBLICATION
                    article.save()
                return redirect(reverse('bc_article', kwargs={'article_id': article.pk}))

        if 'save_section_5' in request.POST:
            remote_form = bc_forms.RemoteArticle(request.POST, instance=article)

            if remote_form.is_valid():
                remote_form.save()
                return redirect(reverse('bc_article', kwargs={'article_id': article.pk}))

        if 'xml' in request.POST:
            for uploaded_file in request.FILES.getlist('xml-file'):
                prod_logic.save_galley(article, request, uploaded_file, True, "XML", False)

        if 'pdf' in request.POST:
            for uploaded_file in request.FILES.getlist('pdf-file'):
                prod_logic.save_galley(article, request, uploaded_file, True, "PDF", False)

        if 'other' in request.POST:
            for uploaded_file in request.FILES.getlist('other-file'):
                prod_logic.save_galley(article, request, uploaded_file, True, "Other", True)

        if 'add_author' in request.POST:
            author_form = forms.AuthorForm(request.POST)
            modal = 'author'

            author_exists = logic.check_author_exists(request.POST.get('email'))
            if author_exists:
                article.authors.add(author_exists)
                messages.add_message(request, messages.SUCCESS, '%s added to the article' % author_exists.full_name())
                return redirect(reverse('bc_article', kwargs={'article_id': article_id}))
            else:
                if author_form.is_valid():
                    new_author = author_form.save(commit=False)
                    new_author.username = new_author.email
                    new_author.set_password(shared.generate_password())
                    new_author.save()
                    new_author.add_account_role(role_slug='author', journal=request.journal)
                    article.authors.add(new_author)
                    messages.add_message(request, messages.SUCCESS, '%s added to the article' % new_author.full_name())

                    return redirect(reverse('bc_article', kwargs={'article_id': article_id}))

        if 'publish' in request.POST:
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

    template = 'back_content/article.html'
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
    :param article_id: Article object ID (INT)
    :param galley_id: Galley object ID (INT)
    :return: HttpResponse
    """

    article = get_object_or_404(models.Article, journal=request.journal, pk=article_id)
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
