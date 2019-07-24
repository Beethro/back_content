from django.conf.urls import url

from plugins.back_content import views

from journal.views import article_figure

urlpatterns = [
    url(r'^$', views.index, name='bc_index'),
    url(r'^article/(?P<article_id>\d+)/$', views.article, name='bc_article'),
    url(r'^article/(?P<article_id>\d+)/authors/(?P<author_id>\d+)/delete/$', views.delete_author, name='bc_delete_author'),
    
    url(r'^xml_import/$', views.xml_import_upload, name='bc_xml_import_upload'),
    url(r'^xml_import/(?P<filename>[\w.-]{0,256})$', views.xml_import_parse, name='bc_xml_import_parse'),

    url(r'^doi_import/$', views.doi_import, name='bc_doi_import'),

    url(r'^article/(?P<article_id>\d+)/galley/(?P<galley_id>\d+)/$', views.preview_xml_galley,
        name='bc_preview_xml_galley'),

    url(r'^article/(?P<article_id>\d+)/galley/(?P<galley_id>\d+)/figures/(?P<file_name>.*)/$',
        article_figure,
        name='bc_article_figure'),
]
