// RSB Engineering Agent — DMZ jump-host (RSB-WS03) MQTT agent.
//
// Lab-only component for the isolated RSB ICS training environment. Connects
// outbound to the DMZ MQTT broker, subscribes for engineering "jobs", and
// publishes results and a heartbeat. The connection is always initiated by
// this agent, so it works even though the broker/Node-RED side cannot initiate
// connections back toward this host.
//
// Dependency-free: uses only .NET Framework in-box assemblies so it compiles
// with the stock C# compiler (no NuGet / no internet). Minimal MQTT 3.1.1.
//
// Intentional weakness (easy tier): the "exec" job runs an arbitrary command
// and returns its output. This is the deliberate, documented foothold for the
// pivot scenario — it is NOT a production design.

using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Net.Sockets;
using System.ServiceProcess;
using System.Text;
using System.Threading;
using System.Web.Script.Serialization;

namespace RSB.Lab
{
    public static class Config
    {
        public static string Broker = "10.0.20.21";
        public static int    Port   = 1883;
        public static string User   = "rsb_broker";
        public static string Pass   = "";
        public static string TopicBase = "rsb/eng/ws03";
        public static string ClientId  = "ws03-engagent";
        public static readonly string InstallRoot = @"C:\ProgramData\RSB-Lab\EngAgent";

        public static void Load()
        {
            string cfg = Path.Combine(InstallRoot, "agent.config");
            if (!File.Exists(cfg)) return;
            foreach (string raw in File.ReadAllLines(cfg))
            {
                string line = raw.Trim();
                if (line.Length == 0 || line.StartsWith("#")) continue;
                int eq = line.IndexOf('=');
                if (eq <= 0) continue;
                string k = line.Substring(0, eq).Trim();
                string v = line.Substring(eq + 1).Trim();
                switch (k)
                {
                    case "broker":    Broker = v; break;
                    case "port":      int.TryParse(v, out Port); break;
                    case "user":      User = v; break;
                    case "password":  Pass = v; break;
                    case "topic_base":TopicBase = v; break;
                    case "client_id": ClientId = v; break;
                }
            }
        }
    }

    public static class Log
    {
        private static readonly object Gate = new object();
        public static void Write(string msg)
        {
            try
            {
                Directory.CreateDirectory(Config.InstallRoot);
                string line = DateTime.UtcNow.ToString("o") + " " + msg + Environment.NewLine;
                lock (Gate) File.AppendAllText(Path.Combine(Config.InstallRoot, "agent.log"), line);
            }
            catch { /* logging must never crash the agent */ }
        }
    }

    // Minimal MQTT 3.1.1 client (QoS 0). Just enough for the lab bus.
    public sealed class MqttClient : IDisposable
    {
        private TcpClient _tcp;
        private NetworkStream _s;
        private readonly object _wgate = new object();
        public Action<string, string> OnMessage; // (topic, payload)

        public void Connect(string host, int port, string clientId, string user, string pass, int keepalive)
        {
            _tcp = new TcpClient();
            _tcp.Connect(host, port);
            _tcp.NoDelay = true;
            _s = _tcp.GetStream();

            var vh = new List<byte>();
            WriteString(vh, "MQTT");
            vh.Add(0x04);                 // protocol level 4 (3.1.1)
            vh.Add((byte)0xC2);           // flags: username + password + clean session
            vh.Add((byte)(keepalive >> 8));
            vh.Add((byte)(keepalive & 0xFF));
            WriteString(vh, clientId);
            WriteString(vh, user);
            WriteString(vh, pass);
            SendPacket(0x10, vh.ToArray());

            byte[] connack = ReadPacket();
            // connack = [0x20][len][ackFlags][returnCode]
            if (connack == null || connack.Length < 4 || connack[0] != 0x20 || connack[3] != 0x00)
                throw new Exception("MQTT CONNECT refused (code " + (connack != null && connack.Length >= 4 ? connack[3].ToString() : "n/a") + ")");
        }

        public void Subscribe(string topic)
        {
            var p = new List<byte>();
            p.Add(0x00); p.Add(0x01);     // packet id
            WriteString(p, topic);
            p.Add(0x00);                  // qos 0
            SendPacket(0x82, p.ToArray());
        }

        public void Publish(string topic, string payload)
        {
            var p = new List<byte>();
            WriteString(p, topic);
            p.AddRange(Encoding.UTF8.GetBytes(payload));
            SendPacket(0x30, p.ToArray());
        }

        public void Ping() { SendPacket(0xC0, new byte[0]); }

        // Blocking receive loop; dispatches PUBLISH messages to OnMessage.
        public void ReceiveLoop(CancellationToken token)
        {
            while (!token.IsCancellationRequested)
            {
                byte[] pkt = ReadPacket();
                if (pkt == null) throw new IOException("broker closed the connection");
                int type = pkt[0] & 0xF0;
                if (type == 0x30) // PUBLISH
                {
                    int qos = (pkt[0] & 0x06) >> 1;
                    int idx = HeaderLen(pkt);               // start of variable header
                    int tlen = (pkt[idx] << 8) | pkt[idx + 1];
                    string topic = Encoding.UTF8.GetString(pkt, idx + 2, tlen);
                    int payStart = idx + 2 + tlen;
                    if (qos > 0) payStart += 2;              // skip packet id
                    string payload = Encoding.UTF8.GetString(pkt, payStart, pkt.Length - payStart);
                    var h = OnMessage;
                    if (h != null) h(topic, payload);
                }
                // 0xD0 PINGRESP and 0x90 SUBACK are ignored.
            }
        }

        private static void WriteString(List<byte> buf, string v)
        {
            byte[] b = Encoding.UTF8.GetBytes(v ?? "");
            buf.Add((byte)(b.Length >> 8));
            buf.Add((byte)(b.Length & 0xFF));
            buf.AddRange(b);
        }

        // Packet = fixed header byte + remaining-length + body. We prepend the
        // decoded remaining length in ReadPacket so index math is uniform:
        // returned array is [type][rl byte(s)][body]. HeaderLen finds body start.
        private int HeaderLen(byte[] pkt)
        {
            int i = 1;
            while ((pkt[i] & 0x80) != 0) i++;
            return i + 1;
        }

        private void SendPacket(byte header, byte[] body)
        {
            var frame = new List<byte>();
            frame.Add(header);
            frame.AddRange(EncodeLen(body.Length));
            frame.AddRange(body);
            byte[] bytes = frame.ToArray();
            lock (_wgate) { _s.Write(bytes, 0, bytes.Length); _s.Flush(); }
        }

        private static byte[] EncodeLen(int len)
        {
            var o = new List<byte>();
            do { int b = len % 128; len /= 128; if (len > 0) b |= 0x80; o.Add((byte)b); } while (len > 0);
            return o.ToArray();
        }

        private byte[] ReadPacket()
        {
            int first = _s.ReadByte();
            if (first < 0) return null;
            var lenBytes = new List<byte>();
            int mult = 1, rl = 0, enc;
            do
            {
                enc = _s.ReadByte();
                if (enc < 0) return null;
                lenBytes.Add((byte)enc);
                rl += (enc & 0x7F) * mult;
                mult *= 128;
            } while ((enc & 0x80) != 0);

            byte[] body = new byte[rl];
            int off = 0;
            while (off < rl)
            {
                int n = _s.Read(body, off, rl - off);
                if (n <= 0) return null;
                off += n;
            }
            var pkt = new byte[1 + lenBytes.Count + rl];
            pkt[0] = (byte)first;
            for (int i = 0; i < lenBytes.Count; i++) pkt[1 + i] = lenBytes[i];
            Array.Copy(body, 0, pkt, 1 + lenBytes.Count, rl);
            return pkt;
        }

        public void Dispose()
        {
            try { if (_s != null) _s.Dispose(); } catch { }
            try { if (_tcp != null) _tcp.Close(); } catch { }
        }
    }

    public sealed class Agent
    {
        private Thread _worker;
        private CancellationTokenSource _cts;
        private MqttClient _mqtt;
        private readonly JavaScriptSerializer _json = new JavaScriptSerializer();
        private const int Keepalive = 60;

        public void Start()
        {
            Config.Load();
            _cts = new CancellationTokenSource();
            _worker = new Thread(Run) { IsBackground = true };
            _worker.Start();
            Log.Write("agent starting; broker=" + Config.Broker + ":" + Config.Port);
        }

        public void Stop()
        {
            try { if (_cts != null) _cts.Cancel(); } catch { }
            try { if (_mqtt != null) _mqtt.Dispose(); } catch { }
            Log.Write("agent stopping");
        }

        private void Run()
        {
            while (!_cts.IsCancellationRequested)
            {
                try
                {
                    _mqtt = new MqttClient();
                    _mqtt.OnMessage = HandleMessage;
                    _mqtt.Connect(Config.Broker, Config.Port, Config.ClientId, Config.User, Config.Pass, Keepalive);
                    _mqtt.Subscribe(Config.TopicBase + "/cmd");
                    Log.Write("connected and subscribed to " + Config.TopicBase + "/cmd");
                    PublishStatus("online");

                    var reader = new Thread(() => { try { _mqtt.ReceiveLoop(_cts.Token); } catch (Exception ex) { Log.Write("receive loop ended: " + ex.Message); } }) { IsBackground = true };
                    reader.Start();

                    var started = DateTime.UtcNow;
                    while (!_cts.IsCancellationRequested && reader.IsAlive)
                    {
                        for (int i = 0; i < Keepalive / 2 && !_cts.IsCancellationRequested && reader.IsAlive; i++)
                            Thread.Sleep(1000);
                        if (!reader.IsAlive) break;
                        try { _mqtt.Ping(); PublishStatus("heartbeat"); } catch { break; }
                    }
                    _mqtt.Dispose();
                }
                catch (Exception ex)
                {
                    Log.Write("connection error: " + ex.Message);
                }
                if (_cts.IsCancellationRequested) break;
                Thread.Sleep(5000); // reconnect backoff
            }
        }

        private void PublishStatus(string state)
        {
            try
            {
                var payload = new Dictionary<string, object>
                {
                    { "agent", "RSB Engineering Agent" },
                    { "host", Environment.MachineName },
                    { "state", state },
                    { "version", "1.0" },
                    { "ts", DateTime.UtcNow.ToString("o") }
                };
                _mqtt.Publish(Config.TopicBase + "/status", _json.Serialize(payload));
            }
            catch (Exception ex) { Log.Write("status publish failed: " + ex.Message); }
        }

        private void HandleMessage(string topic, string payload)
        {
            Log.Write("cmd received: " + payload);
            string job = null; string result;
            try
            {
                var m = (Dictionary<string, object>)_json.DeserializeObject(payload);
                job = m != null && m.ContainsKey("job") ? Convert.ToString(m["job"]) : null;
                switch (job)
                {
                    case "plc_backup":
                        result = "plc_backup acknowledged for target " + (m.ContainsKey("target") ? m["target"] : "(none)");
                        break;
                    case "shift_report":
                        result = "shift_report generated at " + DateTime.UtcNow.ToString("o");
                        break;
                    case "exec":
                        // Intentional lab weakness: run an arbitrary command.
                        result = RunCommand(m.ContainsKey("cmd") ? Convert.ToString(m["cmd"]) : "");
                        break;
                    default:
                        result = "unknown job: " + (job ?? "(null)");
                        break;
                }
            }
            catch (Exception ex)
            {
                result = "job error: " + ex.Message;
            }
            PublishResult(job, result);
        }

        private void PublishResult(string job, string result)
        {
            try
            {
                const int max = 100 * 1024;
                if (result != null && result.Length > max) result = result.Substring(0, max) + "\n...[truncated]";
                var payload = new Dictionary<string, object>
                {
                    { "host", Environment.MachineName },
                    { "job", job },
                    { "result", result },
                    { "ts", DateTime.UtcNow.ToString("o") }
                };
                _mqtt.Publish(Config.TopicBase + "/result", _json.Serialize(payload));
            }
            catch (Exception ex) { Log.Write("result publish failed: " + ex.Message); }
        }

        private static string RunCommand(string cmd)
        {
            if (string.IsNullOrEmpty(cmd)) return "exec: empty command";
            var psi = new ProcessStartInfo("cmd.exe", "/c " + cmd)
            {
                RedirectStandardOutput = true,
                RedirectStandardError = true,
                RedirectStandardInput = true,   // close stdin so the child never blocks on it
                UseShellExecute = false,
                CreateNoWindow = true
            };
            var sb = new StringBuilder();
            using (var p = new Process())
            {
                p.StartInfo = psi;
                p.OutputDataReceived += (s, e) => { if (e.Data != null) lock (sb) sb.AppendLine(e.Data); };
                p.ErrorDataReceived  += (s, e) => { if (e.Data != null) lock (sb) sb.AppendLine(e.Data); };
                p.Start();
                try { p.StandardInput.Close(); } catch { }
                p.BeginOutputReadLine();
                p.BeginErrorReadLine();
                if (!p.WaitForExit(60000))
                {
                    try { p.Kill(); } catch { }
                    lock (sb) return sb.ToString().Trim() + "\n[timed out after 60s]";
                }
                p.WaitForExit(); // flush async buffers
            }
            lock (sb) return sb.ToString().Trim();
        }
    }

    public sealed class AgentService : ServiceBase
    {
        private Agent _agent;
        public AgentService() { ServiceName = "RSBEngineeringAgent"; }
        protected override void OnStart(string[] args) { _agent = new Agent(); _agent.Start(); }
        protected override void OnStop() { if (_agent != null) _agent.Stop(); }
    }

    public static class Program
    {
        public static void Main(string[] args)
        {
            if (args.Length > 0 && args[0] == "console")
            {
                var a = new Agent();
                a.Start();
                Console.WriteLine("RSB Engineering Agent running in console mode. Press Enter to stop.");
                Console.ReadLine();
                a.Stop();
            }
            else
            {
                ServiceBase.Run(new AgentService());
            }
        }
    }
}
