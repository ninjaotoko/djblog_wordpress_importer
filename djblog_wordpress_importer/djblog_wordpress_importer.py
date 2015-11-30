# -*- coding:utf-8 -*-

"""
Djblog Wordpress Importer

Es una herramienta para importar posts de Wordpress a djblog


>>> from djblog_wordpress_importer import DjblogImporter

>>> old_wp_site = "http://myoldwordpresssite.com"
>>> wp_user = "user"
>>> wp_pass = "pass"

>>> importer = DjblogImporter(old_wp_site, wp_user, wp_pass)

>>> pages = 5
>>> for page in range(pages):
>>>     # parsea la pagina N, paginación por 10
>>>     importer.parse(page)
>>>     # items tiene los posts de la pagina
>>>     for post in importer.items:
>>>         # syncroniza - guarda el modelo djblog con los datos
>>>         post.sync()
"""

import os
import datetime
import urllib2
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.core.files.images import ImageFile
from djblog.models import Post, PostType, Category, Tag, MediaContent
import requests

import logging
log = logging.getLogger(__name__)


class DjblogImporterException(Exception):
    pass


class FieldsAbstract(object):
    fields = []


class ItemAttributeAbstract(FieldsAbstract):

    def __init__(self, data, *args, **kwargs):
        for field, attribute in data.iteritems():
            setattr(self, field, attribute)
            #self.fields.append(field)


class ImportAttributesAbstract(FieldsAbstract):
    items = []

    def __init__(self, data, item_class=ItemAttributeAbstract, *args, **kwargs):
        """
        Espera un dict con los campos del post y lo transforma en propiedades
        de la clase.

        """

        if isinstance(data, (list, tuple)):
            for item in data:
                self.items.append( item_class(item) )

        elif isinstance(data, dict):
            for field, attribute in data.iteritems():
                setattr(self, field, attribute)
                #self.fields.append(field)

        #else:
        #    raise DjblogImporterException("Error type {0}".format(type(data)))
        #    setattr(self, field, attribute)


    def __iter__(self):
        for item in self.items:
            yield item


class IDAbstract(object):
    ID = None

    # ID
    def get_id(self):
        return self.ID
    id = property(get_id)
    pk = property(get_id)


class MetaAbstract(ImportAttributesAbstract):
    _meta = None

    # Meta
    def get_meta(self):
        return self._meta

    def set_meta(self, data):
        self._meta = ItemAttributeAbstract(data)
    meta = property(get_meta, set_meta)



class DjblogAuthor(IDAbstract, MetaAbstract, ImportAttributesAbstract):
    user_model = None

    def __init__(self, data, user_model=User, is_staff=True, is_active=True, 
            is_superuser=False, *args, **kwargs):
        super(DjblogAuthor, self).__init__(data, *args, **kwargs)

        self.user_model = user_model
        self.is_staff = is_staff
        self.is_active = is_active
        self.is_superuser = is_superuser


    def __repr__(self):
        return "<DjblogAuthor {0} \"{1}, {2}\">".format(self.username, 
                self.first_name, self.last_name)

    def sync(self):
        """
        Valida los datos contra el modelo para luego crearlo o bien actualizarlo

        """

        # intenta rescatar el usuario por su ID y username
        try:
            user = self.user_model.objects.get(id=self.id, username=self.username)
        except self.user_model.DoesNotExist:
            # intenta rescatar el usuario por su username
            try:
                user = self.user_model.objects.get(username=self.username)
            except self.user_model.DoesNotExist:
                # crea el usuario ya que no existe.
                user = self.user_model.objects.create(username=self.username, 
                        first_name=self.first_name, last_name=self.last_name, 
                        is_staff=self.is_staff, is_active=self.is_active, 
                        is_superuser=self.is_superuser)

        self.user = user
        return self.user


class DjblogAttachmentFile(object):
    source = None
    name = None

    def __init__(self, source, name=None, *args, **kwargs):
        self.source = source

        if not name:
            name = source.split('/')[-1]

        self.name = name

    def __repr__(self, *args, **kwargs):
        return self.name

    def download(self):
        try:
            source = urllib2.urlopen(self.source)
        except UnicodeEncodeError:
            source = urllib2.urlopen(self.source.encode('utf-8'))

        fname = open(self.name, 'wb')
        meta = source.info()
        file_size = int(meta.getheaders("Content-Length")[0])
        print "Downloading: %s Bytes: %s" % (self.name, file_size)

        file_size_dl = 0
        block_sz = 8192
        while True:
            buffer = source.read(block_sz)
            if not buffer:
                break

            file_size_dl += len(buffer)
            fname.write(buffer)
            p = file_size_dl * 100. / file_size
            status = r"%10d  [%3.2f%% %s]" % (file_size_dl, p, "#"*int(p))
            status = status + chr(8)*(len(status)+1)
            print status,

        fname.close()

        return self.name


class DjblogAttachmentObjectProperty(ItemAttributeAbstract):
    _file = None

    def __init__(self, data, *args, **kwargs):
        for field, attribute in data.iteritems():
            setattr(self, field.replace('-', '_'), attribute)

    def get_file(self):
        return self._file

    def set_file(self, data):
        self._file = data

    file = property(get_file, set_file)


class DjblogAttachmentObject:

    def __init__(self, data, *args, **kwargs):
        for field, attribute in data.iteritems():
            setattr(self, field.replace('-', '_'), DjblogAttachmentObjectProperty(attribute))
    

class DjblogAttachmentMeta(ImportAttributesAbstract):
    
    def get_sizes(self):
        return self._sizes

    def set_sizes(self, data):
        objects = []
        if not isinstance(data, (list, tuple)):
            data = [data]

        for item in data:
            objects.append(DjblogAttachmentObject(item))
        
        self._sizes = objects
    sizes = property(get_sizes, set_sizes)


class DjblogFeaturedImage(IDAbstract, MetaAbstract, ImportAttributesAbstract):
    _source = None

    def __repr__(self):
        return "<DjblogFeaturedImage {0}...>".format(self.source)

    # attachments
    def get_attachment_meta(self):
        return self._attachment_meta

    def set_attachment_meta(self, data):
        self._attachment_meta = DjblogAttachmentMeta(data)
    attachment_meta = property(get_attachment_meta, set_attachment_meta)

    def get_source(self):
        return self._source

    def set_source(self, data):
        self._source = DjblogAttachmentFile(data)
    source = property(get_source, set_source)


class DjblogTag(ImportAttributesAbstract):
    
    def sync(self, *args, **kwargs):
        try:
            tag = Tag.objects.get(slug=self.slug)
        except Tag.DoesNotExist:
            tag = Tag.objects.create(name=self.name, slug=self.slug)

        self.tag = tag
        return self.tag


class DjblogCategory(ImportAttributesAbstract):
    
    def sync(self, *args, **kwargs):
        try:
            category = Category.objects.get(slug=self.slug)
        except Category.DoesNotExist:
            category = Category.objects.create(name=self.name, slug=self.slug)

        self.category = category
        return self.category


class DjblogTerms(MetaAbstract, ImportAttributesAbstract):
    _tags = []
    _category = []

    def __repr__(self):
        return "<DjblogTerms {0}...>".format(self.__dict__.keys()[0])

    def get_category(self):
        return self._category

    def set_category(self, data):
        """
        Espera una lista con las categorías asociadas al post
        """
        
        self._category = [DjblogCategory(category) for category in data]
    category = property(get_category, set_category)
    categories = property(get_category, set_category)


    def get_post_tag(self):
        return self._tags

    def set_post_tag(self, data):
        """
        Espera una lista con los tags asociadas al post
        """
        
        self._tags = [DjblogTag(tag) for tag in data]
    post_tag = property(get_post_tag, set_post_tag)
    tags = property(get_post_tag, set_post_tag)


class DjblogPost(IDAbstract, MetaAbstract, ImportAttributesAbstract):

    def __repr__(self):
        return "<DjblogPost ID:{0} \"{1}...\">".format(self.id, self.slug)

    # Parse title
    def get_title(self):
        return self._title #.decode('utf-8') #.decode('iso-8859-1').encode('utf-8')

    def set_title(self, title):
        self._title = title.encode('utf-8')
    title = property(get_title, set_title)


    # Author
    def get_author(self):
        return self._author

    def set_author(self, data):
        self._author = DjblogAuthor(data)
    author = property(get_author, set_author)


    # Featured Image
    def get_featured_image(self):
        return self._featured_image

    def set_featured_image(self, data):
        self._featured_image = DjblogFeaturedImage(data)
    featured_image = property(get_featured_image, set_featured_image)
    media_content = property(get_featured_image, set_featured_image)


    # Terms
    def get_terms(self):
        return self._terms

    def set_terms(self, data):
        self._terms = DjblogTerms(data)
    terms = property(get_terms, set_terms)

    
    # Category
    def get_category(self):
        return self.terms.get_category()

    def set_category(self, data):
        self.terms.set_category(data)
    category = property(get_category, set_category)
    categories = property(get_category, set_category)

    
    # Tag
    def get_post_tag(self):
        return self.terms.get_post_tag()

    def set_post_tag(self, data):
        self.terms.set_post_tag(data)
    post_tag = property(get_post_tag, set_post_tag)
    tags = property(get_post_tag, set_post_tag)

    
    # Date
    def get_date(self):
        return self._date

    def set_date(self, data):
        self._date = datetime.datetime.strptime(data, '%Y-%m-%dT%H:%M:%S')
    date = property(get_date, set_date)


    def sync(self, *args, **kwargs):
        try:
            post_type = PostType.objects.get(post_type_slug=self.type)
        except:
            post_type = PostType.objects.create(post_type_slug=self.type, 
                    post_type_name=self.type)

        try:
            post = Post.objects.get(slug=self.slug, post_type=post_type)
        except Post.DoesNotExist:
            post = Post.objects.create(title=self.title, slug=self.slug, 
                    content=self.content, content_rendered=self.content, 
                    pub_date=self.date, publication_date=self.date,
                    post_type=post_type)

        self.post = post
        self.post.author = self.author.sync()

        # sync categories
        for category in self.categories:
            category.sync()
            
            self.post.category.add(category.category)

        # sync tags
        for tag in self.tags:
            tag.sync()
            
            self.post.tags.add(tag.tag)

        if self.media_content.source:

            ct = ContentType.objects.get_for_model(self.post)
            mc = MediaContent.objects.filter(content_type=ct, object_pk=self.post.pk, title=self.media_content.title)

            # Solo si ya no tiene una imagen asociada entonces, asocia una
            if not mc:

                try:
                    # baja la imagen asociada
                    media_file = self.media_content.source.download()
                except urllib2.HTTPError:
                    pass
                    #raise DjblogImporterException("Error de codificación al descargar el archivo")
                else:

                    try:
                        m = MediaContent(content_type=ct, object_pk=self.post.pk, title=self.media_content.title)
                        print u"Asocia la imagen {0} al post {1}".format(media_file, self.post.slug)
                        m.content.save(media_file, ImageFile(open(media_file, 'r')))
                        log.info("Imagen cargada/actualizada %s", media_file)

                        log.info("Elimina el archivo temporal %s", media_file)
                        try:
                            os.remove(media_file)
                        except (OSError, ValueError):
                            log.warning("ERROR al eliminar el archivo temporal %s", media_file)
                            pass

                    except IOError:
                        log.info("IOError")
                    
                    except DjblogImporterException:
                        pass

        self.post.save()
        return self.post


class DjblogImporter(object):

    def __init__(self, site, user, passw, *args, **kwargs):
        self.site = site.rstrip('/')
        self.auth = (user, passw)
        self.endpoint = self.site + '/posts/'
        self._requests = requests

    def import_items(self, data, *args, **kwargs):

        self.items = []

        if isinstance(data, (list, tuple)):
            for item in data:
                self.items.append( DjblogPost(item) )

        elif isinstance(data, dict):
            self.items.append( DjblogPost(data) )

    def __iter__(self):
        for item in self.items:
            self.post = item
            yield item

    def parse(self, page=1):
        data = self._requests.get(self.endpoint, {'page': page})

        if not data.ok:
            raise data.status

        self.import_items(data.json())
        return self.items
