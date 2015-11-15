#!/usr/bin/python3

"""A program for compositing purple.com.
"""

import dateutil
import jinja2
from PIL import Image
import re

def read_page_spec(filename):
    """Read a page spec, return a dict.

    The page specification alternates lines that match r'^:\\w+:$' with
    blocks of zero or more lines that match anything not beginning
    with ':'.

    The returned dict maches each :key: (sans fore and aft ":") with
    the non-key lines that follow.

    """
    spec = {}
    key = None
    value = []
    pattern = re.compile(r'^:\w+:$')
    with open(filename, 'r') as page_spec_fp:
        for line in page_spec_fp.readlines():
            line.rstrip()
            if re.match(pattern, line):
                if key is not None:
                    # This is not our first key, so output the (key,
                    # value) we've collected thus far.
                    spec[key] = '\n'.join(value)
                    value = []
                key = line[1:-1]
            else:
                value.append(line)
    if key is not None:
        spec[key] = '\n'.join(value)
    return spec

class StaticCompositor:
    """A singleton page compositor.

    A compositor to handle static pages that have no automated
    relationship between each other.

    """
    # A mapping of filenames to rendered pages.
    pages = {}

    def __init(self):
        """Set up.  This is my first contact with the world.
        """
        pass

    def write(self, production_path):
        """Write my state.  This is my last contact with the world.
        """
        for filename, page in self.pages.items():
            with open(production_path + filename, 'w') as page_fp:
                page_fp.write(page)

    def composite(self, filename, template, source_path):
        """Prepare a page.

        Given a path (filename) and a template, prepare a page.
        """
        value_map = read_page_spec(source_path + filename)
        page = template.render(value_map)
        self.pages[filename] = page

class ImageCompositor:
    """An image compositor.

    Just copy images from source to destination.  Eventually, maybe
    offer more than one size for better reactivity.

    """
    # Map image filenames to image full filenames.
    images = {}

    def __init(self):
        """Set up.  This is my first contact with the world.
        """
        pass

    def write(self, production_path):
        """Write my state.  This is my last contact with the world.
        """
        for filename, source_filename in self.images.items():
            # TODO(jeff@purple.com): Check mod dates (if more recent,
            # do nothing).
            Image.open(source_filename).save(production_path + filename)

    def composite(self, filename, template, source_path):
        """Note an image to (maybe) copy.
        """
        template = None         # Unused.
        self.images[filename] = source_path + filename

class BlogCompositor:
    """A singleton page compositor.

    A compositor to handle blog pages.  The key feature here is that
    blogs have a publication_date (before which no page should be
    emitted) and they link from one to the next.

    In addition (future improvement), emit keyword pages based on the
    CSV values of :keywords: fields.  Pages linked from the keyword
    pages should have previous and next pointers to each other rather
    than to their normal previous and next pages.  In other words,
    they permit moving within a keyword sequence.

    """
    # A mapping of filenames to (template, dictionary) pairs.  The
    # dictionaries are for rendering the templates, but are missing
    # the keys 'next_page' and 'previous_page', which can only be
    # computed at the end once the entire sequence is known.
    pre_pages = {}

    # Map slugs to the filename keys in pre_pages.
    slugs = {}

    # Keep track of all keywords encountered.
    keywords = set('')

    def __init(self):
        """Set up.  This is my first contact with the world.
        """
        pass

    def write(self):
        """Write my state.  This is my last contact with the world.
        """

    def composite(self, filename, template, source_path):
        """Prepare a page.

        Given a path (filename) and a template, prepare to prepare a page.
        """
        value_map = read_page_spec(source_path + filename)
        if 'publication_date' not in value_map:
            print('{fn} has no publication date, ignored.'.format(fn=filename))
            return
        # Publication date should be of form YYYY-MM-DD, but, in the
        # end, anything understandable by dateutil.parser().
        publication_date = dateutil.parser.parse(value_map['publication_date'])
        value_map['slug'] = '{y}-{m:02d}-{d:02d}'.format(
            y=publication_date.year,
            m=publication_date.month,
            d=publication_date.day)
        self.slugs[value_map['slug']] = filename
        self.keywords.update(value_map.get('keywords', '').split(','))
        self.pre_pages[filename] = (template, value_map)

class Site:
    """Encapsulate a web site's specification.

    """

    # Map prefix to (template, compositor instance).
    actions = {}

    # A length-sorted list of prefixes, such that the first match
    # while iterating is the correct match.
    prefixes = []

    # Don't read template files more than once.  This is a map from
    # template filename to the compiled contents of those files.
    templates = {}

    # Where to find page specification files.
    source_path = ''

    def __init__(self, site_config_filename, source_path):
        """Read and parse the site config file.

        The config file format is a sequence of lines with three white
        space separated fields: a pattern to match at beginning of
        path name, a template filename, and a compositor (a valid
        class name).

        Empty lines and lines beginning with '#' are ignored.

        The source_path is the directory to walk to find page
        specification files.  The actual filenames that we pass the
        compositor are relative to source_path.

        """
        self.source_path = source_path + '/'
        with open(site_config_filename, 'r') as filename_fp:
            for line in filename_fp.readlines():
                if line[0] != '#' and len(line) > 0:
                    prefix, template, compositor = line.split()
                    self.actions[prefix] = (template, compositor)
                    if template not in self.templates:
                        with open(template, 'r') as template_fp:
                            self.templates[template] = jinja2.Template(
                                template_fp.read())
                    self.prefixes.append(prefix)
        self.prefixes.sort(key=len)

    def act_on_file(self, filename):
        """Do whatever we need to do with the path filename.
        """
        for prefix in self.prefixes:
            if filename.startswith(prefix):
                template, compositor = self.actions.get(prefix, (None, None))
                if compositor is None:
                    print('Missing compositor for {fn}'.format(fn=filename))
                else:
                    template_contents = self.templates.get(template, None)
                    if template_contents is None:
                        print('No template available: {template}'.format(
                            template=template))
                    else:
                        compositor(filename, template_contents,
                                   self.source_path)
        print('No path match for {fn}'.format(fn=filename))

    def write_all(self, production_path):
        """Tell all compositors to write and prepare for clean-up.

        The production_path is the string to prepend to all page
        filenames, since we write production in a different directory
        than the source.

        """
        for template, compositor in self.actions.values():
            compositor.write(production_path)

if __name__ == '__main__':
    pass

