// Run inside ics-nodered with the public training username/password as arguments.
// Exercises the authenticated inject node, then runs read-only identity/ACL
// checks through the intentionally exposed engineering job channel.
const fs = require('fs');
const http = require('http');
const mqtt = require('mqtt');
const [username, password] = process.argv.slice(2);
if (!username || !password) throw new Error('Supply the public Node-RED training login');
const credential = JSON.parse(fs.readFileSync('/data/flows_cred.json'))['rsb-mqtt-config'];
function request(path, body, headers = {}) {
  return new Promise((resolve, reject) => {
    const req = http.request({hostname: '127.0.0.1', port: 1880, path,
      method: 'POST', headers: {...headers, 'Content-Length': Buffer.byteLength(body)}}, res => {
      let data = ''; res.on('data', x => data += x);
      res.on('end', () => resolve({status: res.statusCode, body: data}));
    });
    req.on('error', reject); req.end(body);
  });
}
(async () => {
  const auth = await request('/auth/token', new URLSearchParams({client_id: 'node-red-admin',
    grant_type: 'password', scope: '*', username, password}).toString(),
    {'Content-Type': 'application/x-www-form-urlencoded'});
  if (auth.status !== 200) throw new Error('Node-RED training login failed');
  const token = JSON.parse(auth.body).access_token;
  const client = mqtt.connect('mqtt://10.0.20.21:1883', {username: credential.user,
    password: credential.password, clientId: 'rsb-validation-' + Date.now(), reconnectPeriod: 0});
  const timeout = setTimeout(() => {console.error('Engineering result timeout'); client.end(true); process.exit(1);}, 20000);
  client.on('error', () => {throw new Error('MQTT connection failed');});
  client.on('connect', () => client.subscribe('rsb/eng/ws03/result', async err => {
    if (err) throw err;
    const injected = await request('/inject/mqtt-job', '', {Authorization: 'Bearer ' + token});
    if (injected.status !== 200 && injected.status !== 204) throw new Error('Authenticated inject failed');
  }));
  client.on('message', (topic, bytes) => {
    const result = JSON.parse(bytes.toString());
    if (result.host !== 'RSB-WS03') throw new Error('Unexpected engineering host');
    if (result.job === 'shift_report') {
      console.log('Authenticated Node-RED inject reached the engineering agent.');
      client.publish('rsb/eng/ws03/cmd', JSON.stringify({job: 'exec',
        cmd: 'whoami & whoami /groups & type C:\\RSB-Lab\\LegacyConnections\\connect-engineering.cmd'}));
    } else if (result.job === 'exec') {
      const text = result.result.toLowerCase();
      if (!text.includes('rsb-ws03\\svc_engagent') || text.includes('s-1-5-32-544') ||
          !text.includes('access is denied')) throw new Error('Unexpected agent privileges or handoff ACL');
      console.log('Agent runs as the non-administrator svc_engagent; engineering handoff access is denied.');
      clearTimeout(timeout); client.end();
    }
  });
})().catch(err => {console.error(err.message); process.exit(1);});
