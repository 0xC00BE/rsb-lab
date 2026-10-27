# Contributing

Start with the topology and porting guide. Submit platform adapters separately
from common guest changes where possible. Describe your host platform, guest
versions, changes, verification, and remaining manual steps.

Never commit `.env`, live passwords, VPN profiles, keys, private database state,
VM disks or conversation histories. Public training credentials must be clearly
identified and consistent with the provisioning scripts. Do not silently change
an intended weakness into a production recommendation.

Run `python3 tools/validate_release.py` before proposing a change. On Linux, also
run Compose validation with your private local `.env`. For simulator changes,
install the relevant `requirements.txt` into a disposable environment and run
the included tests. For platform support, complete `docs/acceptance.md` and attach
a sanitized report. Mark untested configurations as experimental.

Contributions are provided under the repository's MIT license for original work;
retain attribution and compatible notices for any external source you introduce.
