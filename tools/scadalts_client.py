"""Small client for the pinned Scada-LTS REST and DWR interfaces."""
import http.cookiejar
import json
import re
import urllib.parse
import urllib.request


class ScadaClient:
    def __init__(self, base, username, password):
        self.base = base.rstrip('/') + '/'
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}),
            urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        data = urllib.parse.urlencode({'username': username, 'password': password}).encode()
        with self.opener.open(self.base + 'login.htm', data, timeout=30) as response:
            if 'login.htm' in response.url:
                raise RuntimeError('Scada-LTS login failed.')

    def get(self, path):
        with self.opener.open(self.base + path, timeout=30) as response:
            return response.read().decode('utf-8')

    def rest(self, path):
        return json.loads(self.get('api/' + path))

    def dwr(self, script, method, params=(), page='emport.shtm'):
        data = {'callCount': '1', 'page': '/Scada-LTS/' + page,
            'httpSessionId': '', 'scriptSessionId': 'RSB_RELEASE',
            'c0-scriptName': script, 'c0-methodName': method,
            'c0-id': '0', 'batchId': '0'}
        data.update({f'c0-param{i}': value for i, value in enumerate(params)})
        request = urllib.parse.urlencode(data).encode()
        with self.opener.open(self.base + f'dwr/call/plaincall/{script}.{method}.dwr',
                              request, timeout=60) as response:
            result = response.read().decode('utf-8')
        if '_remoteHandleException' in result or '_remoteHandleBatchException' in result:
            raise RuntimeError('Scada-LTS rejected the DWR request: ' + result[:500])
        return result

    @staticmethod
    def string(value):
        # DWR decodes a string after parsing its form body, so literal percent
        # signs in project labels require this additional encoding layer.
        return 'string:' + urllib.parse.quote(value, safe='')

    def set_fresh_admin_password(self, password):
        """Change only the fresh admin's password, preserving profile settings."""
        user = self.dwr('UsersDwr', 'getUser', ['number:1'], 'users.shtm')

        def value(name):
            match = re.search(r's\d+\.' + name + r'=([^;]+);', user)
            if not match:
                raise RuntimeError('Unexpected fresh-user schema: ' + name)
            return json.loads(match.group(1))

        if value('username') != 'admin':
            raise RuntimeError('Expected the fresh default administrator.')
        params = ['number:1', self.string(value('firstName')), self.string(value('lastName')),
            self.string(password), self.string(value('email')), self.string(value('phone')),
            'number:' + str(value('receiveAlarmEmails')),
            'boolean:' + str(value('receiveOwnAuditEvents')).lower(),
            'number:' + str(value('userProfile')), self.string(value('theme')),
            'boolean:' + str(value('enableFullScreen')).lower(),
            'boolean:' + str(value('hideShortcutDisableFullScreen')).lower()]
        result = self.dwr('UsersDwr', 'saveUser', params, 'users.shtm')
        if 'hasMessages:false' not in result:
            raise RuntimeError('SCADA administrator update failed; inspect the Users page.')
        ScadaClient(self.base, 'admin', password)  # Confirm a fresh login.
