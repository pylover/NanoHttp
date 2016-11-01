import re
from os.path import join

from nanohttp import Controller, action, context
from tests.helpers import WsgiAppTestCase, STUFF_DIR


class FormTestCase(WsgiAppTestCase):
    class Root(Controller):
        @action(methods='post')
        def index(self):
            return ', '.join('%s: %s' % (k, v) for k, v in sorted(context.form.items(), key=lambda x: x[0]))

    def test_simple_query_string(self):
        self.assert_post('/?a=1&b=&c=2', "a: 1, b: , c: 2")
        self.assert_post('/?a=1&b=2&b=3', "a: 1, b: ['2', '3']")

    def test_url_encoded(self):
        self.assert_post(
            '/',
            fields={
                'a': 1,
                'b': [2, 3],
            },
            resp='a: 1, b: [2, 3]'
        )

    def test_multipart(self):
        self.assert_post(
            '/',
            fields={
                'a': 1,
                'b': [2, 3],
            },
            files={'c': join(STUFF_DIR, 'cat.jpg')},
            resp=re.compile("a: 1, b: \[2, 3\], c: FieldStorage\('c', 'cat\.jpg.*")
        )
