# Security and exercise scope

Run this training lab only on dedicated virtual networks you control. The
hypervisor, firewall management and unrelated upstream systems are outside
student exercise scope. Keep the Docker build adapter disconnected during use.
For remote access, expose only the optional authenticated VPN listeners on the
firewall WAN; do not forward application or management ports.

Administrator credentials, VPN keys, generated `.env`, runtime state, snapshots
and configuration backups are private operator material. Never reuse exercise
accounts for administration or outside the lab. Do not publish generated VPN
profiles, database exports or raw traffic captures.

Detailed scenario information is in the optional
[instructor guide](exercises/instructor/guide.md), which contains spoilers.
Readers can choose whether to open it; public source also contains exercise details.

For an unintended security issue, use GitHub private vulnerability reporting if
enabled. Otherwise request a private contact channel without posting credentials
or detailed exploit evidence publicly.
