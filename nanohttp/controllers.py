
import time
import os
import logging
from os.path import isdir, join, relpath, pardir, exists
from mimetypes import guess_type

from .exceptions import HttpNotFound, HttpMethodNotAllowed, HttpForbidden
from .contexts import context
from .constants import HTTP_DATETIME_FORMAT


logging.basicConfig(level=logging.INFO)

UNLIMITED = -1

class Controller(object):
    __nanohttp__ = dict(
        verbs='any',
        encoding='utf8',
        default_action='index'
    )

    def _get_default_handler(self, remaining_paths):
        default_action = self.__nanohttp__['default_action']
        handler = getattr(self, default_action, None)
        if not handler:
            raise HttpNotFound()

        return handler, remaining_paths

    def _find_handler(self, remaining_paths):
        if not remaining_paths or not hasattr(self, remaining_paths[0]):
            # Handler is not found, trying default handler
            return self._get_default_handler(remaining_paths)

        return getattr(self, remaining_paths[0], None), remaining_paths[1:]

    # noinspection PyMethodMayBeStatic
    def _validate_handler(self, handler, remaining_paths):
        if not callable(handler) or not hasattr(handler, '__nanohttp__'):
            raise HttpNotFound()

        # noinspection PyUnresolvedReferences
        manifest = handler.__nanohttp__
        positionals = manifest.get('positional_arguments', UNLIMITED)
        optionals = manifest.get('optional_arguments', UNLIMITED)
        available_arguments = len(remaining_paths)
        verbs = manifest.get('verbs', 'any')

        if UNLIMITED not in (optionals, positionals) and \
                (positionals > available_arguments or available_arguments > (positionals + optionals)):
            raise HttpNotFound()

        if verbs is not 'any' and context.method not in verbs:
            raise HttpMethodNotAllowed()

        return handler, remaining_paths

    # noinspection PyMethodMayBeStatic
    def _serve_handler(self, handler, remaining_paths):
        context.response_encoding = handler.__nanohttp__.get('encoding', None)
        context.response_content_type = handler.__nanohttp__.get('content_type', None)
        return handler(*remaining_paths)

    def __call__(self, *remaining_paths):
        handler, remaining_paths = self._find_handler(list(remaining_paths))
        handler, remaining_paths = self._validate_handler(handler, remaining_paths)
        return self._serve_handler(handler, remaining_paths)


class RestController(Controller):

    def _find_handler(self, remaining_paths):
        if remaining_paths and hasattr(self, remaining_paths[0]):
            return getattr(self, remaining_paths[0], None), remaining_paths[1:]

        # Handler is not found, trying verb
        if not hasattr(self, context.method):
            raise HttpMethodNotAllowed()

        return getattr(self, context.method), remaining_paths


class Static(Controller):
    __nanohttp__ = dict(
        verbs='any',
        encoding=None,
        default_action='index'
    )

    __chunk_size__ = 0x4000

    def __init__(self, directory='.', default_document='index.html'):
        self.default_document = default_document
        self.directory = directory

    def __call__(self, *remaining_paths):

        # Find the physical path of the given path parts
        physical_path = join(self.directory, *remaining_paths)

        # Check to do not access the parent directory of root and also we are not listing directories here.
        if pardir in relpath(physical_path, self.directory):
            raise HttpForbidden()

        if isdir(physical_path):
            if self.default_document:
                physical_path = join(physical_path, self.default_document)
                if not exists(physical_path):
                    raise HttpForbidden
            else:
                raise HttpForbidden()

        context.response_headers.add_header('Content-Type', guess_type(physical_path)[0] or 'application/octet-stream')

        try:
            f = open(physical_path, mode='rb')
            stat = os.fstat(f.fileno())
            context.response_headers.add_header('Content-Length', str(stat[6]))
            context.response_headers.add_header(
                'Last-Modified',
                time.strftime(HTTP_DATETIME_FORMAT, time.gmtime(stat.st_mtime))
            )

            with f:
                while True:
                    r = f.read(self.__chunk_size__)
                    if not r:
                        break
                    yield r

        except OSError:
            raise HttpNotFound()
