#!/usr/bin/python3

"""A program for compositing purple.com.
"""

import argparse
import dateutil
import jinja2
import os
from PIL import Image
import re

def read_page_spec(filename):
    """Read a page spec, return a dict.

    The page specification alternates lines that match r'^:\\w+:$'
    (that is, lines of the form ":key:") with blocks of zero or more
    lines that match anything not beginning with ':'.

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

# Compositors have three public methods:
#
#   * A function init() taking no arguments.
#
#   * A function composite(), which composites a page (to be stored
#     pending a future call to write()) given a content filename and
#     a template.
#
#   * A function write(), which writes out the stored pages.  Calling
#     write() should be the last interaction the compositor has with
#     the world.

class StaticCompositor:
    """A singleton page compositor.

    A compositor to handle static pages that have no automated
    relationship between each other.

    """
    # If True, write() becomes a no-op.
    dryrun = False

    # A mapping of filenames to rendered pages.
    pages = {}

    def __init(self, dryrun):
        """Set up.  This is my first contact with the world.
        """
        self.dryrun = dryrun

    def composite(self, filename, template, source_path):
        """Prepare a page.

        Given a path (filename) and a template, prepare a page.
        """
        if self.dryrun:
            print('StaticCompositor: ({fn}, {sp})'.format(
                fn=filename, sp=source_path))
            return
        value_map = read_page_spec(source_path + filename)
        page = template.render(value_map)
        self.pages[filename] = page

    def write(self, production_path):
        """Write my state.  This is my last contact with the world.
        """
        if self.dryrun:
            return
        for filename, page in self.pages.items():
            with open(os.path.join(production_path, filename), 'w') as page_fp:
                page_fp.write(page)

class ImageCompositor:
    """An image compositor.

    Just copy images from source to destination.  Eventually, maybe
    offer more than one size for better reactivity.

    """
    # If True, write() becomes a no-op.
    dryrun = False

    # Map image filenames to image full filenames.
    images = {}

    def __init(self, dryrun):
        """Set up.  This is my first contact with the world.
        """
        self.dryrun = dryrun

    def composite(self, filename, template, source_path):
        """Note an image to (maybe) copy.
        """
        # TODO(jeff@purple.com): How do I specify multiple resolutions?
        if self.dryrun:
            print('ImageCompositor: ({fn}, {sp})'.format(
                fn=filename, sp=source_path))
            return
        template = None         # Unused.
        self.images[filename] = source_path + filename

    def write(self, production_path):
        """Write my state.  This is my last contact with the world.
        """
        if self.dryrun:
            return
        for filename, source_filename in self.images.items():
            # TODO(jeff@purple.com): Check mod dates (if more recent,
            # do nothing).
            Image.open(source_filename).save(
                os.path.join(production_path, filename))

class BlogCompositor:
    """A singleton page compositor.

    A compositor to handle blog pages.  The key feature here is that
    blogs have a publication_date (before which no page should be
    emitted) and they link from one to the next.

    The expected keys are these:

      :publication_date:    (YYYY-MM-DD format)
      :image:
      :title:
      :keywords:    (CSV)
      :markdown:    (if body is in markdown)
      :html:        (if body is in html)

    In addition (future improvement), emit keyword pages based on the
    CSV values of :keywords: fields.  Pages linked from the keyword
    pages should have previous and next pointers to each other rather
    than to their normal previous and next pages.  In other words,
    they permit moving within a keyword sequence.

    """
    # If True, write() becomes a no-op.
    dryrun = False

    # A mapping of filenames to (template, dictionary) pairs.  The
    # dictionaries are for rendering the templates, but are missing
    # the keys 'next_page' and 'previous_page', which can only be
    # computed at the end once the entire sequence is known.
    pre_pages = {}

    # Map slugs to the filename keys in pre_pages.
    slugs = {}

    # Keep track of all keywords encountered.
    keywords = set('')

    def __init(self, dryrun):
        """Set up.  This is my first contact with the world.
        """
        self.dryrun = dryrun

    def composite(self, filename, template, source_path):
        """Prepare a page.

        Given a path (filename) and a template, prepare to prepare a page.
        """
        if self.dryrun:
            print('BlogCompositor: ({fn}, {sp})'.format(
                fn=filename, sp=source_path))
            return
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

    def write(self):
        """Write my state.  This is my last contact with the world.
        """
        if self.dryrun:
            return
        # TODO(jeff@purple.com):  IMPLEMENT THIS.

class Site:
    """Encapsulate a web site's specification.

    """
    # A list of directories (in top-down order) whose existance we will
    # need to ensure in order to write the site.
    directories = []

    # Map regex to (template, compositor instance).
    actions = {}

    # A list of regex's, such that the first match while iterating is
    # the correct match.
    regexes = []

    # Don't read template files more than once.  This is a map from
    # template filename to the compiled contents of those files.
    templates = {}

    # Where to find page specification files.
    source_path = ''

    def __init__(self, site_config_filename, source_path, dryrun):
        """Read and parse the site config file.

        The config file format is a sequence of lines with three white
        space separated fields: a pattern to match at beginning of
        path name, a template filename, and a compositor (a valid
        class name).

        Empty lines and lines beginning with '#' are ignored.

        The source_path is the directory to walk to find page
        specification files.  The actual filenames that we pass the
        compositor are relative to source_path.

        If dryrun is True, don't write the site, just indicate what we
        would have done.

        """
        self.source_path = source_path + '/'
        with open(site_config_filename, 'r') as filename_fp:
            for line in filename_fp.readlines():
                if line[0] != '#' and len(line) > 0:
                    regex_string, template_string, compositor_string \
                        = line.split()
                    regex = re.compile(regex_string)
                    compositor = globals()[compositor_string](dryrun)
                    self.actions[regex] = (template_string, compositor)
                    if template_string not in self.templates:
                        with open(template_string, 'r') as template_fp:
                            self.templates[template_string] = jinja2.Template(
                                template_fp.read())
                    self.regexes.append(regex)

    def act_on_dir(self, dirname):
        """Note the directories shose existance we'll need to ensure.
        """
        self.directories.append(dirname)

    def act_on_file(self, filename):
        """Do whatever we need to do with the path filename.
        """
        for regex in self.regexes:
            if regex.match(filename):
                template, compositor = self.actions.get(regex, (None, None))
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
        os.chdir(production_path)
        for directory in self.directories:
            if os.path.exists(directory):
                if not os.path.isdir(directory):
                    print('File "{dir}" exists but is not a directory.'.format(
                        dir=directory))
            else:
                os.mkdir(directory, mode=0o755)
        for dummy_template, compositor in self.actions.values():
            compositor.write(production_path)

def main():
    """Do what we do."""
    parser = argparse.ArgumentParser("Build the site.")
    parser.add_argument('--src', dest='source_path', type=str,
                        help='Path in which to find page specification files')
    parser.add_argument('--dst', dest='destination_path', type=str,
                        help='Path in which to write web site')
    parser.add_argument('--config', dest='config_path', type=str,
                        help='Path of site configuration file')
    parser.add_argument('--dryrun', dest='dryrun', type=bool,
                        help='Dry run, only indicate disposition of files.')
    args = parser.parse_args()

    site = Site(args.config_path, args.source_path, args.dryrun)
    # I want to get relative paths to make it easier on file creation
    # at destination_path.  In addition, I want to make sure that I
    # never match a pattern rule on an artifact of the full source
    # path name.
    os.chdir(args.source_path)
    for dir_name, dummy_subdir_list, file_list in os.walk('.'):
        site.act_on_dir(dir_name)
        for filename in file_list:
            site.act_on_file(os.path.join(dir_name, filename))
    site.write_all(args.destination_path)

if __name__ == '__main__':
    main()
