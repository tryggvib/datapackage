# -*- coding: utf-8 -*-

# datapackage.py - Load and manage data packages defined by dataprotocols.org
# Copyright (C) 2013 Tryggvi Björgvinsson
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import urllib
import csv
import json
import itertools
import os
import datetime
import time
import base64
import re
import sys
if sys.version_info[0] < 3:
    import urlparse
    urllib.parse = urlparse
    urllib.request = urllib
    next = lambda x: x.next()
    bytes = str
    str = unicode
else:
    import urllib.request

from . import sources
from . import licenses
from .util import verify_version, parse_version, format_version
from .util import is_local, is_url


class DataPackage(object):
    """
    Package for loading and managing a data package as defined by:
    http://www.dataprotocols.org/en/latest/data-packages.html
    """

    FIELD_PARSERS = {
        'number': float,
        'integer': int,
        'date': lambda x:
            datetime.datetime.strptime(x, '%Y-%m-%d').date(),
        'time': lambda x: time.strptime(x, '%H:%M'),
        'datetime': lambda x:
            datetime.datetime.strptime(x, '%Y-%m-%dT%H:%M:%S%Z'),
        'boolean': bool,
        'binary': base64.b64decode,
        'object': json.loads,
        'json': json.loads,
        'geojson': json.loads,
        'array': list,
        }

    def _field_parser(self, field):
        """
        Return a type casting function (field parser) based on the data
        package field types. This returns the default type/functions for
        the types except when the field type is either data or datetime.
        In that case it returns the correctly formatted string (YYYY/MM/DD
        is even supported). Also if the field type is geopoint it returns
        the a function that parses the value as as
        {'lat': latitude_as_float, 'lon': longitude_as_float}
        """

        # If a format is provided with the field we need a different way
        # to cast it as datetime
        if (field['type'] == 'date' or field['type'] == 'datetime') \
                and 'format' in field:

            # Get the format into its own variable, we need to make some
            # replacements
            format_string = field['format']
            # Order of the replacements is important since month and minutes
            # can be denoted in a similar fashion
            replacement_order = [('hh', '%m'), (':mm', ':%M'), ('ss', '%S'),
                                 ('yyyy', '%Y'), ('yy', '%y'), ('mm', '%m'),
                                 ('dd', '%d')]

            # For each replacement we substitute (and ignore the case)
            for (old, new) in replacement_order:
                format_string = re.sub("(?i)%s" % old, new, format_string)

            # Return the parser (here's a difference between date and datetime
            if field['type'] == 'datetime':
                return lambda x: datetime.datetime.strptime(x, format_string)
            else:
                return lambda x: \
                    datetime.datetime.strptime(x, format_string).date()

        # If type is geopoint we need to create a parser that can parse three
        # different formats into one dictionary
        if field['type'] == 'geopoint':
            def parse_geopoint(value):
                # Try to load it as json ( if it an dictionary object or array)
                try:
                    parsed = json.loads(value)
                    if type(parsed) == list:
                        # Geopoint coded as [123.4, 567.8]
                        return {'lat': parsed[0], 'lon': parsed[1]}
                    else:
                        # Geopoint coded as {'lat':123.4, 'lon':567.8}
                        return parsed
                except:
                    # Geopoint probably coded as "123.4, 567.8"
                    geotuple = value.split(',')
                    return {'lat': float(geotuple[0]), 'lon': float(geotuple[1])}

            # Return the parser
            return parse_geopoint

        # If none of the edge cases we use the default field parsers and fall
        # back on unicode type if no parser is found
        return self.FIELD_PARSERS.get(field['type'], str)

    def __init__(self, uri, opener=None):
        """
        Construct a DataPackage.

        :param basestring uri: URI or file path to the data package.
            ``datapackage.json`` should exist under this URI.
        :param function opener: optional function instead of ``urllib.urlopen``
            to read data; e.g. ``opener=zf.open`` where ``zf = ZipFS('a.zip')``
        :type opener: function
        """
        self.opener = opener or urllib.request.urlopen
        # Bind the URI to this instance
        self.uri = uri
        # Load the descriptor as a dictionary into a variable
        self.descriptor = self.get_descriptor()
        # Load the resources as a dictionary into a variable
        self.resources = self.get_resources()

    def open_resource(self, path):
        # use os.path.join if the path is local, otherwise use urljoin
        # -- we don't want to just use os.path.join because otherwise
        # on Windows it will try to create URLs with backslashes
        if is_local(self.uri):
            return self.opener(os.path.join(self.uri, path))
        else:
            return self.opener(urllib.parse.urljoin(self.uri, path))

    @property
    def name(self):
        """The name of the dataset as described by its descriptor. This is a
        required property, described by the datapackage protocol as
        follows:

        short url-usable (and preferably human-readable) name of the
        package. This MUST be lower-case and contain only alphanumeric
        characters along with ".", "_" or "-" characters. It will
        function as a unique identifier and therefore SHOULD be unique
        in relation to any registry in which this package will be
        deposited (and preferably globally unique).

        The name SHOULD be invariant, meaning that it SHOULD NOT
        change when a data package is updated, unless the new package
        version should be considered a distinct package, e.g. due to
        significant changes in structure or interpretation. Version
        distinction SHOULD be left to the version field. As a
        corollary, the name also SHOULD NOT include an indication of
        time range covered.

        """
        name = self.descriptor.get('name')
        if not name:
            raise KeyError("datapackage does not have a name")
        return name

    @name.setter
    def name(self, val):
        if not val:
            raise ValueError("datapackage name must be non-empty")
        self.descriptor['name'] = val


    @property
    def licenses(self):
        """MUST be an array. Each entry MUST be a hash with a type and a url
        property linking to the actual text. The type SHOULD be an
        Open Definition license ID if an ID exists for the license and
        otherwise may be the general license name or identifier.

        """
        licenses.get_licenses(self.descriptor)

    @licenses.setter
    def licenses(self, val):
        licenses.set_licenses(self.descriptor, val)

    def add_license(self, license_type, url=None):
        """Adds a license to the list of licenses for the datapackage.

        :param string license_type: The name of the license, which
            should be an Open Definition license ID if an ID exists
            for the license and otherwise may be the general license
            name or identifier.
        :param string url: The URL corresponding to the license. If
            license_type is a standard Open Definition license, then
            the URL will try to be inferred automatically.

        """
        licenses.add_license(self.descriptor, license_type, url)

    @property
    def datapackage_version(self):
        """The version of the data package specification this datapackage.json
        conforms to. It should follow the Semantic Versioning
        requirements (http://semver.org/).

        """
        version = self.descriptor.get("datapackage_version")
        if not version:
            raise KeyError("datapackage does not have a datapackage version")
        return version

    @datapackage_version.setter
    def datapackage_version(self, val):
        if not val:
            raise ValueError("datapackage version must be non-empty")
        self.descriptor['datapackage_version'] = verify_version(val)

    @property
    def title(self):
        """
        The title of the dataset as described by its descriptor.
        Default is an empty string if no title is present
        """

        return self.descriptor.get('title', u'')

    @title.setter
    def title(self, val):
        if not val:
            val = ""
        self.descriptor['title'] = str(val)

    @property
    def description(self):
        """
        The description of the dataset as described by its descriptor.
        Default is an empty string if no description is present
        """

        return self.descriptor.get('description', u'')

    @description.setter
    def description(self, val):
        if not val:
            val = ""
        self.descriptor['description'] = str(val)

    @property
    def homepage(self):
        """
        URL string for the data packages web site
        Default is an empty string if no homepage is present
        """
        return self.descriptor.get('homepage', u'')

    @homepage.setter
    def homepage(self, val):
        if not val:
            val = ""
        elif not is_url(val):
            raise ValueError("not a URL: {}".format(val))

        self.descriptor['homepage'] = str(val)

    @property
    def version(self):
        """A version string identifying the version of the package. It should
        conform to the Semantic Versioning requirements
        (http://semver.org/).

        Defaults to 0.0.1 if not specified.

        """
        return self.descriptor.get('version', u'0.0.1')

    @version.setter
    def version(self, val):
        self.descriptor['version'] = verify_version(val)

    def bump_major_version(self, keep_metadata=False):
        """Increases the major version by one, e.g. 1.0.0 --> 2.0.0

        Note that this sets the minor and patch versions to zero, and
        erases the prerelease and metadata information (unless
        `keep_metadata` is True, in which case the metadata will be
        preserved).

        """
        version = parse_version(self.version)
        major = version[0]
        if keep_metadata:
            metadata = version[-1]
        else:
            metadata = None
        new_version = format_version((major + 1, 0, 0, None, metadata))
        self.version = new_version

    def bump_minor_version(self, keep_metadata=False):
        """Increases the minor version by one, e.g. 1.0.0 --> 1.1.0

        Note that this sets the patch version to zero, and erases the
        prerelease and metadata information (unless `keep_metadata` is
        True, in which case the metadata will be preserved).

        """
        version = parse_version(self.version)
        major, minor = version[:2]
        if keep_metadata:
            metadata = version[-1]
        else:
            metadata = None
        new_version = format_version((major, minor + 1, 0, None, metadata))
        self.version = new_version

    def bump_patch_version(self, keep_metadata=False):
        """Increases the patch version by one, e.g. 1.0.0 --> 1.0.1

        Note that this erases the prerelease and metadata information
        (unless `keep_metadata` is True, in which case the metadata
        will be preserved).

        """
        version = parse_version(self.version)
        major, minor, patch = version[:3]
        if keep_metadata:
            metadata = version[-1]
        else:
            metadata = None
        new_version = format_version((major, minor, patch + 1, None, metadata))
        self.version = new_version

    @property
    def sources(self):
        """An array of source hashes. Each source hash may have name, web and
        email fields.

        Defaults to an empty list.

        """
        return sources.get_sources(self.descriptor)

    @sources.setter
    def sources(self, val):
        sources.set_sources(self.descriptor, val)

    def add_source(self, name, web=None, email=None):
        """Adds a source to the list of sources for this datapackage.

        :param string name: The human-readable name of the source.
        :param string web: A URL pointing to the source.
        :param string email: An email address for the contact of the
            source.

        """
        sources.add_source(self.descriptor, name, web, email)

    def remove_source(self, name):
        """Removes the source with the given name."""
        sources.remove_source(self.descriptor, name)

    @property
    def keywords(self):
        """An array of string keywords to assist users searching for the
        package in catalogs.

        Defaults to an empty list.

        """
        return self.descriptor.get('keywords', [])

    @keywords.setter
    def keywords(self, val):
        if not val:
            val = []
        self.descriptor['keywords'] = [str(x) for x in val]

    @property
    def image(self):
        """A link to an image to use for this data package.

        Defaults to an empty string.

        """
        return self.descriptor.get('image', u'')

    @image.setter
    def image(self, val):
        if not val:
            val = u''
        self.descriptor['image'] = str(val)

    @property
    def data(self):
        """
        An iterator that returns dictionary representation of the rows in
        all resources.
        """

        # Get all of the generators for the resources
        data_generators = [self.get_data(k) for k in self.resources.keys()]
        return itertools.chain.from_iterable(data_generators)

    def get_descriptor(self):
        """
        Get the descriptor for the data package (as defined by the standard)
        as a dictionary. This uses the URI provided by the constructor and
        performs a join with the descriptor URN. This follows the join rules
        of urlparse.urljoin which means for URLs that if the URI does
        not end with a slash the last piece of the URI will be replaced with
        the descriptor URN.
        """
        descriptor = self.open_resource('datapackage.json')

        # Load the descriptor json contents
        str_descriptor = descriptor.read().decode()
        json_descriptor = json.loads(str_descriptor)

        # Return the descriptor json contents (as the dict json.load returns
        return json_descriptor

    def get_resources(self):
        """
        Get the data package's resources as a dictionary. The key for each
        resource is the value of its name attribute. If no name is provided then
        the key is an empty string. This means that resources can be
        overwritten if they have the same (or no name).
        """

        # Initialise the empty dictionary
        sources = {}
        # Loop through the resources
        for resource in self.descriptor['resources']:
            # Create a resource dictionary
            source = {'location':
                          # Location is url path or None (in that order)
                          resource.get('url', resource.get('path', None)),
                      'encoding':
                        # The encoding of the file - defaults to utf-8
                          resource.get('encoding', 'utf-8'),
                      'fields':
                          # Fields are found in schema.fields
                          resource.get('schema', {}).get('fields', [])
                      }
            # Add the resource to the resource dictionary collection
            sources[resource.get('name', resource.get('id', u''))] = source

        # Return the resource collection
        return sources

    def get_data(self, name='', id=''):
        """
        Generator that yields the data for a given resource.
        The resource defaults to a resource identified by the empty string
        (no name attribute in descriptor)
        """
        # We support both name and id (id is an old deprecated field in the
        # data package standard). If user has used id and not name we assign
        # the id to the name.
        if not name and id:
            name = id

        # Check if the id can be found in the resources or throw a KeyError
        if name not in self.resources:
            raise KeyError("Source not found")

        # Get the resource dictionary representation
        resource_dict = self.resources[name]
        # Open the resource location
        resource_file = self.open_resource(resource_dict['location'])
        resource_file = (line.decode(resource_dict.get('encoding'))
                         for line in resource_file)
        # We assume CSV so we create the csv file
        reader = csv.reader(resource_file)
        # Throw away the first line (headers)
        next(reader)
        # For each row we yield it as a dictionary where keys are the field
        # names and the value the value in that row
        for row_idx, row in enumerate(reader):
            # Each row will be returned as a dictionary where the keys are
            # the field id
            row_dict = {}
            # Loop over fields in the schema and parse the values
            for field_idx, field in enumerate(resource_dict['fields']):
                # Again, id is an old deprecated word from the standard and
                # we use the name (but support the old id).
                field_name = field.get('name', field.get('id', ''))

                # Decode the field value
                value = row[field_idx]

                # We wrap this in a try clause so that we can give error
                # messages about specific fields in a row
                try:
                    row_dict[field_name] = self._field_parser(field)(value)
                except:
                    msg = u'Field "{field}" in row {row} could not be parsed.'
                    raise ValueError(msg.format(field=field_name, row=row_idx))

            yield row_dict
