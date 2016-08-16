#!/usr/bin/env python

"""A program for compositing purple.com.
"""

from __future__ import print_function
import argparse
import dateutil.parser
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
            line = line.rstrip()
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
#   * A function init() taking one argument, a boolean (dryrun).
#
#   * A function composite(), which composites a page (to be stored
#     pending a future call to write()) given a content filename and
#     a template.
#
#   * A function write(), which writes out the stored pages.  Calling
#     write() should be the last interaction the compositor has with
#     the world.

class NullCompositor(object):
    """A compositor that does nothing.
    """
    def __init__(self, dryrun, verbose):
        """Nothing to do."""
        pass

    def composite(self, filename, template):
        """Nothing to do."""
        pass

    def write(self):
        """Nothing to do."""
        pass

class CopyCompositor(object):
    """A compositor that just copies input to output.
    """
    def __init__(self, dryrun, verbose):
        """Set up.  This is my first contact with the world.
        """
        # If verbose == True, write() becomes a no-op.
        self.dryrun = dryrun
        self.verbose = verbose
        self.timestamp_helper = TimestampCompositorHelper(dryrun, verbose)

    def composite(self, filename, _):
        """Note a file to (maybe) copy.
        """
        if self.dryrun:
            print('CopyCompositor: ({fn})'.format(fn=filename))
            return
        self.timestamp_helper.composite(filename)

    def write(self):
        """Write my state.  This is my last contact with the world.
        """
        if self.dryrun:
            return
        def copy_file(dest_filename, source_filename):
            """Copy source_file to dest_file."""
            with open(source_filename, 'rb') as fp_source:
                with open(dest_filename, 'wb') as fp_dest:
                    fp_dest.write(fp_source.read())
        self.timestamp_helper.write(copy_file)

class StaticCompositor(object):
    """A singleton page compositor.

    A compositor to handle static pages that have no automated
    relationship between each other.

    """
    def __init__(self, dryrun, verbose):
        """Set up.  This is my first contact with the world.
        """
        self.dryrun = dryrun
        self.verbose = verbose
        self.source_dir = ''
        self.timestamp_helper = TimestampCompositorHelper(dryrun, verbose)
        # A mapping of filenames to templates.
        self.pages = {}

    def composite(self, filename, template):
        """Prepare a page.

        Given a path (filename) and a template, prepare a page.
        """
        if self.dryrun:
            print('StaticCompositor: ({fn})'.format(fn=filename))
            return
        if '' == self.source_dir:
            self.source_dir = os.getcwd()
        self.pages[self.source_dir + '/' + filename] = template
        self.timestamp_helper.composite(filename)

    def write(self):
        """Write my state.  This is my last contact with the world.
        """
        if self.dryrun:
            return
        def static_render(dest_filename, source_filename):
            """Render source to destination.

            The source filename points to a spec file.
            The desitination filename points to the html file we'll write.
            """
            value_map = read_page_spec(source_filename)
            template = self.pages[source_filename]
            page = template.render(value_map)
            with open(dest_filename, 'w') as page_fp:
                page_fp.write(page)
        self.timestamp_helper.write(static_render)

class ImageCompositor(object):
    """An image compositor.

    Just copy images from source to destination.  Eventually, maybe
    offer more than one size for better reactivity.

    """
    # If True, write() becomes a no-op.
    dryrun = False

    # Map image filenames to image modification time.
    images = {}

    def __init__(self, dryrun, verbose):
        """Set up.  This is my first contact with the world.
        """
        self.dryrun = dryrun
        self.source_dir = ''
        self.verbose = verbose
        self.timestamp_helper = TimestampCompositorHelper(dryrun, verbose)

    def composite(self, filename, _):
        """Note an image to (maybe) copy.
        """
        # TODO(jeff@purple.com): How do I specify multiple resolutions?
        if self.dryrun:
            print('ImageCompositor: ({fn})'.format(fn=filename))
            return
        self.timestamp_helper.composite(filename)

    def write(self):
        """Write my state.  This is my last contact with the world.
        """
        if self.dryrun:
            return
        def copy_image(dest_filename, source_filename):
            """Copy source image to destination image(s)."""
            Image.open(source_filename).save(dest_filename)
        self.timestamp_helper.write(copy_image)

class BlogCompositor(object):
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

    # Slugs for us are string representations of publication dates.
    # Here we'll map all the slugs we've seen to the filenames that
    # should become visible on that date.
    slugs = {}

    # Keep track of all keywords encountered.
    keywords = set('')

    def __init__(self, dryrun, verbose):
        """Set up.  This is my first contact with the world.
        """
        self.dryrun = dryrun
        self.verbose = verbose

    def composite(self, filename, template):
        """Prepare a page.

        Given a path (filename) and a template, prepare to prepare a page.
        """
        if self.dryrun:
            print('BlogCompositor: ({fn})'.format(fn=filename))
            return
        value_map = read_page_spec(filename)
        if 'publication_date' not in value_map:
            print('{fn} has no publication date, ignored.'.format(fn=filename))
            return
        # Publication date should be of form YYYY-MM-DD, but, in the
        # end, anything understandable by dateutil.parser().
        publication_date = dateutil.parser.parse(value_map['publication_date'])
        slug = '{y}-{m:02d}-{d:02d}'.format(
            y=publication_date.year,
            m=publication_date.month,
            d=publication_date.day)
        value_map['slug'] = slug
        if slug in self.slugs:
            self.slugs[slug].add([filename])
        else:
            self.slugs[slug] = set([filename])
        self.keywords.update(value_map.get('keywords', '').split(','))
        self.pre_pages[filename] = (template, value_map)

    def write(self):
        """Write my state.  This is my last contact with the world.

        Here's the plan:

        We have pre_pages, which is a dict of (template, dictionary) pairs.
        The entries are missing the keys next_page and previous_page.

        We have a set of keywords.  Each keyword is essentially a
        projection map of the set of pages.  If the viewer clicks a
        link associated with a keyword, he should find himself viewing
        the same page but with that keyword selected, and so in the
        context of that projection.  A projection amounts to a story
        line or sequence of pages.  A special keyword, "all", is
        always implied.

        We'll write pages to '{keyword}/{filename}'.  The
        next/previous buttons will take us to the next or previous
        file in the directory {keyword} (and are no-ops if in the
        respective terminal position).  Clicking a keyword link will
        take us to the same filename in directory {keyword}.

        """
        if self.dryrun:
            return
        # TODO(jeff@purple.com):  IMPLEMENT THIS.

class TimestampCompositorHelper(object):
    """Looks like a compositor, but handles checking timestamps.

    We'd like to read and write files only if we need to.
    """
    def __init__(self, dryrun, verbose):
        """Set up.  This is my first contact with the world.
        """
        self.dryrun = dryrun
        self.verbose = verbose
        self.source_dir = ''
        # Map filenames to modification times.
        self.files = {}

    def composite(self, filename):
        """Note the modtime of a file to (maybe) process.
        """
        if '' == self.source_dir:
            self.source_dir = os.getcwd()
        if self.dryrun:
            print('TimestampCompositorHelper: ({fn})'.format(fn=filename))
            return
        try:
            src_time = os.stat(filename).st_mtime
        except OSError as error:
            print("Can't stat source file {fn}: {err}".format(
                fn=filename,
                err=str(error)))
        self.files[filename] = src_time

    def write(self, file_action):
        """Perform file_action if destination is not newer than source.

        The function file_action should take two arguments: a source
        file path and a destination file path.
        """
        if self.dryrun:
            return
        for filename, src_time in self.files.items():
            try:
                dst_time = os.stat(filename).st_mtime
            except OSError:
                # It's reasonable that it doesn't exist, but trigger an update.
                dst_time = 0
            try:
                src_time = self.files[filename]
            except KeyError:
                # This shouldn't happen.
                print('Missing source file and mtime: ' + filename)
                return
            needs_update = (dst_time < src_time)
            if needs_update:
                # TODO(jeff@purple.com): Write multiple sizes.
                source_filename = self.source_dir + '/' + filename
                print('Write: source="{sf}", file="{fn}"'.format(
                    sf=source_filename, fn=filename))
                file_action(filename, source_filename)

class Site(object):
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

    def __init__(self, site_config_path, source_path, dryrun, verbose):
        """Read and parse the site config file.

        The config file format is a sequence of lines with three white
        space separated fields: a pattern to match against path names,
        a template filename, and a compositor (a valid class name).

        Empty lines and lines beginning with '#' are ignored.

        The source_path is the directory to walk to find page
        specification files.  The actual filenames that we pass the
        compositor are relative to source_path.

        If dryrun is True, don't write the site, just indicate what we
        would have done.

        """
        self.source_path = source_path + '/'
        self.dryrun = dryrun
        self.verbose = verbose
        if self.dryrun:
            print('Dry run.')
        with open(site_config_path + '/config', 'r') as filename_fp:
            for line in filename_fp.readlines():
                if line[0] != '#' and len(line) > 0:
                    regex_string, template_string, compositor_string \
                        = line.split()
                    if dryrun:
                        found = 'Found: re="{re}", template="{template}", ' + \
                                'comp="{comp}"'
                        print(found.format(
                            re=regex_string, template=template_string,
                            comp=compositor_string))
                    regex = re.compile(regex_string)

                    compositor = globals()[compositor_string](dryrun, verbose)
                    self.actions[regex] = (template_string, compositor)
                    if template_string not in self.templates:
                        with open(site_config_path + '/' + template_string,
                                  'r') as template_fp:
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
                if self.verbose:
                    print('  Matched: {re:35}  {template:13}  {fn}'.format(
                        fn=filename, re=str(regex), template=template))
                if compositor is None:
                    print('Missing compositor for {fn}'.format(fn=filename))
                    return
                else:
                    template_contents = self.templates.get(template, None)
                    if template_contents is None:
                        print('No template available: {template}'.format(
                            template=template))
                        return
                    else:
                        compositor.composite(filename, template_contents)
                        return
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
            compositor.write()

def main():
    """Do what we do."""
    parser = argparse.ArgumentParser(
        description='Build the site.')
    parser.add_argument('--src', dest='source_path', type=str,
                        help='Path in which to find page specification files')
    parser.add_argument('--dst', dest='destination_path', type=str,
                        help='Path in which to write web site')
    parser.add_argument('--config', dest='config_path', type=str,
                        help='Path of site configuration and template '
                        + 'directory.  The configuration filename should '
                        + 'be "config".  The template '
                        + 'files are named by the config file.')
    parser.add_argument('--dryrun', dest='dryrun',
                        action='store_true',
                        help='Dry run, only indicate disposition of files.')
    parser.add_argument('-v', '--verbose', dest='verbose',
                        action='store_true',
                        help='Be terribly informative of what happens')
    args = parser.parse_args()

    site = Site(args.config_path, args.source_path, args.dryrun, args.verbose)

    # I want to get relative paths to make it easier on file creation
    # at destination_path.  In addition, I want to make sure that I
    # never match a pattern rule on an artifact of the full source
    # path name.
    initial_path = os.getcwd()  # Probably could simplify with unipath.
    os.chdir(args.source_path)
    for dir_name, dummy_subdir_list, file_list in os.walk('.'):
        site.act_on_dir(dir_name)
        for filename in file_list:
            # print('tree walk: found "{fn}"'.format(fn=filename))
            site.act_on_file(os.path.join(dir_name, filename))
    os.chdir(initial_path)
    site.write_all(args.destination_path)

if __name__ == '__main__':
    main()
