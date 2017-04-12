from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.admin.views.decorators import staff_member_required
from django.core.urlresolvers import reverse
from django.contrib import messages

from submission import models, forms, logic
from core import models as core_models
from plugins.back_content import forms as bc_forms
from production import logic as prod_logic


@staff_member_required
def index(request):
    article = models.Article.objects.create(journal=request.journal)

    return redirect(reverse('bc_article', kwargs={'article_id': article.pk}))

@staff_member_required
def article(request, article_id):
    article = get_object_or_404(models.Article, pk=article_id, journal=request.journal)
    article_form = forms.ArticleInfo(instance=article)
    author_form = forms.AuthorForm()
    pub_form = bc_forms.PublicationInfo(instance=article)
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

        if 'save_section_3' in request.POST:
            pub_form = bc_forms.PublicationInfo(request.POST, instance=article)

            if pub_form.is_valid():
                pub_form.save()
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
            form = forms.AuthorForm(request.POST)
            modal = 'author'

            author_exists = logic.check_author_exists(request.POST.get('email'))
            if author_exists:
                article.authors.add(author_exists)
                messages.add_message(request, messages.SUCCESS, '%s added to the article' % author_exists.full_name())
                return redirect(reverse('submit_authors', kwargs={'article_id': article_id}))
            else:
                if form.is_valid():
                    new_author = form.save(commit=False)
                    new_author.username = new_author.email
                    new_author.set_password(logic.generate_password())
                    new_author.save()
                    new_author.add_account_role(role_slug='author', journal=request.journal)
                    article.authors.add(new_author)
                    messages.add_message(request, messages.SUCCESS, '%s added to the article' % new_author.full_name())

                    return redirect(reverse('bc_article', kwargs={'article_id': article_id}))

    template = 'back_content/article.html'
    context = {
        'article': article,
        'article_form': article_form,
        'form': author_form,
        'pub_form': pub_form,
        'galleys': prod_logic.get_all_galleys(article),
        'modal': modal
    }

    return render(request, template, context)


@staff_member_required
def xml_import(request):
    template = 'back_content/xml_import.html'
    context = {}

    return render(request, template, context)
