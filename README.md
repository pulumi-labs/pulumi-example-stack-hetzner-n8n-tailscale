# Private n8n order automation on Hetzner with Tailscale

Build a private automation service for a small team. You send a sample order to
n8n, it calculates the total, saves a receipt in PostgreSQL, and sends the receipt
back. The sample order below should produce **3000 cents**.

n8n is a visual workflow editor. Hetzner supplies one virtual machine (VM), Docker
Compose runs the app and database on that VM, and Tailscale provides private
HTTPS access. Python Pulumi creates and connects the infrastructure. You do not
need Kubernetes for this example.

**Validation on November 16, 2026: live deployment, owner setup, webhook execution,
network denial, persistence and restart are UNRUN.** The installed Hetzner and
Tailscale SDK contracts, complete infrastructure hash lock, native syntax, strict
lint and type checks passed in an approved disposable VM. Source and reviewed
SDK artifacts passed malware scans. Application image layers remain unacquired;
the fresh security-fixed image age gates and dedicated account access are
unresolved. These source checks do not prove a working automation service.

## Before you begin

This is a private, experimental source example, not a tested installer. You need:

- A dedicated Hetzner Cloud project and a token with Read & Write access.
- A personal or dedicated Tailscale network, called a **tailnet**, with the
  access rules and HTTPS settings described in step 2.
- A dedicated SSH key to administer the VM, plus the exact official Docker image
  ID from your Hetzner account. An image ID identifies the VM's starting OS.
- An approved isolated deployment environment with Python 3.12, the pinned Pulumi
  tools and encrypted state storage. Pulumi state tracks the resources it creates.

Read cleanup before creating the VM: deleting it also deletes this example's
local database. There is no tested backup or restore procedure.

## 1. Get the example

```sh
git clone https://github.com/pulumi-labs/pulumi-example-stack-hetzner-n8n-tailscale.git
cd pulumi-example-stack-hetzner-n8n-tailscale
```

## How it works

Pulumi owns a `hcloud.Server`, its inline public network, `hcloud.Firewall`,
`hcloud.SshKey`, and one `tailscale.TailnetKey`, using explicit provider instances.
The VM is the standard `cx23` shape, 2 shared x86 vCPUs / 4 GiB RAM, in `nbg1`.
Confirm its current availability, specifications and quote before applying.
The image is a verified numeric ID of Hetzner's official `docker-ce` app image,
Ubuntu 24.04 with Docker Engine and the Compose plugin preinstalled.
No custom runner or image build is needed.

The VM has one public IPv4 for outbound traffic and operator SSH. Its cloud
firewall permits only TCP 22 from the configured operator IPv4 `/32`. IPv6 is
disabled. There are no Docker published ports. PostgreSQL is only on an internal
Compose network. n8n shares the Tailscale container's network namespace and binds
only `127.0.0.1:5678`. Tailscale uses userspace networking, without host networking,
`/dev/net/tun`, extra capabilities, subnet routing or an exit node.

Native Tailscale Serve proxies private HTTPS 443 to that loopback endpoint.
`serve.json` explicitly has no Funnel destinations. The daemon substitutes its
actual `${TS_CERT_DOMAIN}`; the configured n8n URL must match the enrolled device's
actual name. The cloud firewall has no 443, 80, 5678 or 5432 ingress. Outbound HTTPS
and DNS remain available; restrictive inbound rules can force DERP relay.

Three Compose named volumes store PostgreSQL data, n8n local settings, and
Tailscale node state on the VM boot disk. They survive container restarts, not VM
replacement/deletion. This is a single failure domain, with no backup, HA or
restore claim. Destruction intentionally deletes its synthetic data. There is no
separate Hetzner volume, snapshot, backup, load balancer or network.

The n8n database login owns only `n8n`. The workflow login can connect to
`receipts` and SELECT/INSERT into `automation.receipts`; it cannot create tables,
update/delete receipts or connect to the private n8n database. The n8n credential
uses plaintext PostgreSQL transport only within this VM's internal bridge.
The VM and its administrators are trusted with all application data and secrets.

## 2. Prepare your accounts and private network

Use accounts you are authorized to administer. The live trial was blocked by
missing Hetzner and personal Tailscale credentials; the source checks do not
establish account access. Store tokens in your secret manager, not in Git.

Use a dedicated/personal tailnet and approved test devices. Do not reuse or
modify an unrelated corporate tailnet. An OAuth client lets Pulumi request a
one-use device enrollment key without giving the VM your management secret.

<details>
<summary>Tailscale administrator checklist: tags, access rules and test devices</summary>

A tag identifies this app's device; a grant says which users or devices may reach
it. MagicDNS gives it a private name. Before creating a VM, the tailnet owner
must verify all of the following:

- An existing dedicated tag, for example `tag:private-n8n`, whose owners include
  the provisioning OAuth client. Its client is restricted to that tag.
- Existing grants allow only the selected operator/automation identities to
  `tag:private-n8n` on `tcp:443`. A distinct negative-test identity has no matching
  grant, including broad pre-existing wildcard grants. A default allow-all policy
  cannot prove denial. No grant to 5678 or 5432 is required.
- MagicDNS and HTTPS certificates are already enabled. Enabling HTTPS can expose
  the machine name in public certificate transparency logs. Use a non-sensitive
  unique hostname. Confirm the exact `<name>.<tailnet-dns-name>.ts.net` name.
- The tailnet permits this tagged, preauthorized device; any device-approval or
  Tailnet Lock signing requirements are settled before deployment.
- Two existing test clients and their positive/negative identities are approved,
  with an outside client available for the internet denial check.

The program creates no ACL, grants, DNS preferences, tailnet settings, OAuth
clients or shared tags. If those prerequisites are absent, record a blocker.
Do not replace the global policy or silently weaken it.

</details>

Use a project-scoped Hetzner **Read & Write** API token in a dedicated project;
the API token permission boundary is the project, not a per-server IAM policy.
It must create/read/delete servers, auto primary IPs, firewalls and SSH keys.
Keep it in the provisioning sandbox only. The Tailscale provider uses OAuth
client ID/secret with **auth_keys** write permission restricted to the existing
tag. It creates a one-use, preauthorized, non-ephemeral tagged enrollment key
with a one-day expiry (the documented minimum), never auto-recreated after use.
The application receives only that enrollment key, not the provisioning OAuth
secret. Key expiry/revocation does not remove the enrolled device; tagged node
key expiry is normally disabled. Cleanup separately requires a scoped
**devices:core** read/write token for the owned tag/device.

SSH uses a dedicated ephemeral operator keypair. Configure only its public key;
the private key stays outside the VM and repository. Verify the host fingerprint
through the authenticated Hetzner console before SSH. Do not disable host-key
checking. State and user-data contain secrets: use an encrypted Pulumi backend,
restrict Hetzner project membership, never emit decrypted state/user-data or
`docker compose config` into retained logs. Cloud-init keeps root-readable
copies on the VM. Host administrators and providers can see bootstrap secrets.

## 3. Prepare the pinned software

Use Python 3.12, `pulumi==3.273.0`, `pulumi-hcloud==1.43.4` and
`pulumi-tailscale==0.29.0`. The providers are the libraries that let Pulumi
manage Hetzner and Tailscale. Their installed SDK contracts passed the recorded
source checks. Keep the checked-in `requirements.lock` rather than resolving
new versions during this walkthrough.

Runtime pins in `settings.py` are real publisher index digests:

| Input | Selected acquisition target | Present status |
| --- | --- | --- |
| n8n | `docker.io/n8nio/n8n:2.47.6@sha256:3566fc1c340d8888a2e02c0dfbf7558fe4e3b300a9da892b1223e223404c5828` | Publisher metadata verified; layers unacquired |
| PostgreSQL | `docker.io/library/postgres:17.12-bookworm@sha256:40865bc877a289da75963d97d72b59633f639fc5af7a4e856bfa3714cae5b536` | Registry manifest hash verified; layers unacquired |
| Tailscale | `docker.io/tailscale/tailscale:v1.104.4@sha256:ed6480b33c6eb67c9cbd203ed42b9fb57e361986725b6856def71b7a3d9e276c` | Publisher metadata verified; layers unacquired |
| Host | Numeric ID of official x86 `docker-ce` image | Account inventory required |

The native pins have no floating override. Compose uses `pull_policy: never`.
Acquire, inspect, scan and preload the exact selected Linux/amd64 images before
starting the service. A digest string alone does not prove registry provenance
or scan coverage. Match the actual loaded image digest to the reviewed index
and platform manifest mapping inside the sandbox.

<details>
<summary>Dated security notes and release-age requirements</summary>

The mature Tailscale 1.104.4 image was pushed October 28 and includes the
TS-2026-014 through TS-2026-017 fixes. Newer TS-2026-018 concerns the Kubernetes
operator, absent here. Later 1.104.5/6 client releases have no corresponding
official Docker tag; 1.104.7 is unnecessary for this source's Serve path.

The current n8n advisory **GHSA-h59h-rf6m-7jp5** permits workflow activation with
credentials inaccessible to the publisher; it requires **2.47.6**, released
November 13 at 08:24:14 UTC. GHSA-c772-hjfp-gfc2, GHSA-q8rc-7m84-mfvj and
GHSA-g333-hr44-g82p also have that security floor. Mature 2.47.4 is therefore
rejected. The fixed n8n image reaches four days on **November 17 at 08:24:14 UTC**
using the later source release timestamp conservatively.

PostgreSQL 17.12 fixes current security issues including CVE-2026-120151
(PL/pgSQL type confusion enabling arbitrary code execution). Its selected
index was published November 12 at 22:16:18 UTC and reaches four days
on **November 16 at 22:16:19 UTC** (rounded up); confirm publication at acquisition.
Downgrading to 17.11 retains these fixes'
vulnerabilities. These are concrete security-driven age blockers, not a request
to wait for the latest releases. **No fresh-artifact waiver exists.** Wait for
the fixed artifacts' age threshold unless your execution policy explicitly permits early use.
All current advisories still need rechecking when layers are acquired.

</details>

The checked-in `requirements.lock` records exact Python packages and hashes.
Keep a record of the downloaded package and tool hashes in your approved
deployment environment. Scan all wheel contents including
native libraries, images including every layer/whiteout and nested archive,
provider binaries, tools and generated cloud-init/bootstrap outputs **before**
execution. Scanner coverage errors, skipped files or unresolved malware findings
block execution. Keep scanner payloads, credentials and logs out of this tree.
Use the existing trusted scanner and approved VM boundary; do not reconstruct or
scan the official OS disk. Inspect preinstalled Docker/Compose versions and
their actual behavior in the guest before loading workloads.

## 4. Configure and create the VM

Run Pulumi commands in your approved isolated deployment environment, not on
an unisolated workstation. Copy the reviewed source there, prepare Pulumi CLI
3.273.0 and the matching hcloud 1.43.4 / tailscale 0.29.0 plugins, and install the
scanned Python packages using `--require-hashes -r requirements.lock`.
Use an encrypted Pulumi backend and keep state outside Git.

The next block creates a **stack**, a named copy of your deployment. Replace the
shell variables with values from your accounts before running it:

| Variable | Where the value comes from |
| --- | --- |
| `DEDICATED_HOSTNAME` | A unique, non-sensitive name you choose for the VM |
| `VERIFIED_DOCKER_CE_IMAGE_ID` | Numeric ID of the official x86 Docker app image in Hetzner |
| `APPROVED_OPERATOR_IPV4_CIDR` | Your approved SSH source IPv4 followed by `/32` |
| `DEDICATED_SSH_PUBLIC_KEY` | The public half of your dedicated SSH key |
| `DEDICATED_TAILNET_ID`, `EXISTING_APP_TAG` | Your tailnet and the existing app tag from step 2 |
| `VERIFIED_PRIVATE_FQDN` | Full device name such as `name.your-tailnet.ts.net` |
| `DEDICATED_OAUTH_CLIENT_ID` | The dedicated Tailscale OAuth client's ID |

Keep the matching secret values for the interactive prompts below.

```sh
pulumi stack init private-n8n
pulumi config set name "$DEDICATED_HOSTNAME"
pulumi config set location nbg1
pulumi config set dockerHostImageId "$VERIFIED_DOCKER_CE_IMAGE_ID"
pulumi config set operatorCidr "$APPROVED_OPERATOR_IPV4_CIDR"
pulumi config set sshPublicKey "$DEDICATED_SSH_PUBLIC_KEY"
pulumi config set tailnet "$DEDICATED_TAILNET_ID"
pulumi config set tag "$EXISTING_APP_TAG"
pulumi config set fqdn "$VERIFIED_PRIVATE_FQDN"
pulumi config set tailscaleOAuthClientId "$DEDICATED_OAUTH_CLIENT_ID"
```

Use interactive `pulumi config set --secret <key>` for `hcloudToken`,
`tailscaleOAuthClientSecret`, `postgresPassword`, `n8nPassword`,
`receiptsPassword`, `encryptionKey`, and `webhookToken`. Generate each application
secret independently as exactly 64 lowercase hex characters in the approved
secret facility. Do not pass secret values as shell arguments. No value or
credential reference is supplied by this example.

```sh
pulumi preview --diff --save-plan reviewed-plan.json
# Inspect actual resources, public ingress, numeric image, costs and replacements.
pulumi up --plan reviewed-plan.json
pulumi stack output serverId
pulumi stack output publicIpv4
```

### Start the app on the new VM

After `pulumi up` succeeds, note the server ID and public IP. Connect over SSH
using the dedicated key and verify the host fingerprint as described in step 2.
The following commands run **on the new Hetzner VM**, as its administrator.

Provisioning writes native configuration under `/opt/private-n8n`; it deliberately
does not download or start unscanned application images. In the VM, after the
administrator stages the reviewed archives:

```sh
cloud-init status --wait
docker version
docker compose version
docker load --input /var/tmp/reviewed-n8n.tar
docker load --input /var/tmp/reviewed-postgres.tar
docker load --input /var/tmp/reviewed-tailscale.tar
# Verify RepoDigests and selected platform against the acquisition manifest.
systemctl enable --now private-n8n
cd /opt/private-n8n
docker compose ps
docker compose exec -T tailscale tailscale status --json
docker compose exec -T tailscale tailscale serve status --json
```

Complete first enrollment within one day. Confirm `Self.DNSName` exactly matches
the configured URL before owner setup. A colliding hostname can gain a suffix;
stop and correct the name/config rather than accepting a certificate mismatch.
No `--insecure`, Funnel, public host bind or tailnet-wide change is a remedy.
Provider success is VM creation, not application readiness.

## 5. Create your n8n account and try an order

From the authorized dedicated-tailnet client, visit the private HTTPS URL and
complete n8n's native first-owner setup with a unique password. Enable available
MFA. Do not expose setup to other tailnet members; the grant must be scoped
before boot. n8n account authentication remains required for editor/API access;
Tailscale identity headers are not an n8n SSO configuration. Legacy basic-auth
environment variables are not used. No n8n API key or paid registration is needed.

After the owner exists, run these native commands inside the guest:

```sh
cd /opt/private-n8n
docker compose exec -T --user node n8n n8n import:credentials --input=/bootstrap/credentials.json
docker compose exec -T --user node n8n n8n import:workflow --input=/bootstrap/workflow.json
docker compose exec -T --user node n8n n8n publish:workflow --id=privateOrderReceipt
docker compose restart n8n
```

CLI imports default to the owner's personal project; this is a single-owner,
fresh instance. Do not import into an unrelated existing instance. Imported
credential IDs are stable and the workflow references them explicitly.
The native import encrypts credentials in PostgreSQL with `encryptionKey`;
the initial root-protected bootstrap files remain sensitive on the boot disk.
CLI commands bypass UI permissions and are reserved for the VM operator.

The workflow accepts POST `/webhook/order-receipt` with the separate secret
`X-Receipt-Token` header. It passes the body as a PostgreSQL bound JSON parameter,
calculates integer cents, INSERTs a receipt, and returns the persisted row.
It uses only Webhook and PostgreSQL built-in nodes, no Code node or custom code
runner. Example synthetic body:

```json
{
  "order_id": "synthetic-order-unique",
  "items": [
    {"sku": "training-seat", "quantity": 2, "unit_cents": 1250},
    {"sku": "workbook", "quantity": 1, "unit_cents": 500}
  ]
}
```

Expected receipt: `item_count=3`, `total_cents=3000`, with a PostgreSQL timestamp.
Use a new order ID for each call. The primary key rejects duplicate IDs.
This is a focused valid synthetic workflow, not a general order API: arbitrary
malformed inputs are not promised 4xx responses, and some invalid/no-item
requests may return an empty successful result or an internal error. No
malformed-input or idempotency pass is claimed.

Send the JSON above as a POST request to your private URL plus
`/webhook/order-receipt`, using `Content-Type: application/json` and your
`X-Receipt-Token` header. Use an HTTP client that keeps the token out of logs.
Success means the response contains the expected receipt and the same row exists
in PostgreSQL. Also try a missing/wrong token and a device without a matching
Tailscale grant; neither should reach the useful workflow.

The live receipt, database readback, denied-client and restart-persistence checks
are all **UNRUN** in the recorded trial. Capture sanitized results before cleanup;
never retain headers containing credentials or private n8n logs.

## 6. Check costs and clean up

Budget for the Hetzner VM, its public IPv4, storage and network traffic, plus any
Tailscale plan charges that apply to your account. Check your current quote before
creating resources. This example does not enforce a spending cap. Set a deadline
for a trial and reserve time to remove it; powered-off VMs remain billable.

Secrets and cloud-init are creation inputs. Changes can replace the VM and lose
all three volumes. Before replacement, export allowed evidence/data, capture and
remove the old exact device, and explicitly replace both the enrollment key and
server using their exported URNs in the reviewed Pulumi plan. A consumed key is
not auto-recreated. Never use broad device/tag deletion. Retaining the Tailscale
volume permits normal container restarts without a new enrollment key; don't
remove it while the VM is retained.

For cleanup, first capture `Self.ID` from this VM's `tailscale status --json`
and verify the matching device through the Tailscale API using its exact ID,
hostname, tag and private DNS name. Keep that identifier in your private cleanup
record. The following commands delete the local application volumes and their
data. After accepting that data loss, run them on the VM:

```sh
cd /opt/private-n8n
docker compose exec -T tailscale tailscale logout
systemctl disable --now private-n8n
docker compose down --volumes
```

Logout may already remove the device. Check the Tailscale admin console or API
for the exact device ID you recorded. If it remains, remove that device after
matching its hostname, full DNS name and tag, then verify that it is absent.
Do not delete every device with the tag. A missing resource response is evidence
of absence; an authentication failure is not.

```sh
pulumi destroy --preview-only
# Review targets, then:
pulumi destroy
```

Pulumi deletes only its own VM, auto primary IPv4, firewall, SSH public-key
resource and enrollment key. The provider does not own the enrolled device;
the explicit native device cleanup is required, not assumed from key deletion.
Independently inspect Hetzner servers, primary IPs, volumes, snapshots/backups,
firewalls and SSH keys by recorded IDs, and Tailscale device/key IDs. Expect no
remaining billable resources. An exact resource NotFound/HTTP 404 is absence;
authentication errors/timeouts are unresolved. Revoke dedicated provisioning
credentials and remove copied archives, bootstrap material and temporary
operator credentials after reconciliation. Retain encrypted state until cleanup
is independently verified. Never remove pre-existing grants, tags, DNS settings,
OAuth clients or other shared resources as part of this stack.

## Attribution and sources

This composes official deployment features; it does not redistribute upstream
images. n8n's Sustainable Use License permits internal business/personal uses
subject to its terms and excludes separately licensed enterprise components.
It is fair-code, not an unrestricted hosted-service license. Reselling n8n
access or embedding it for customers requires separate license review. No paid
enterprise feature or subscription is used here.

This example's authored code is licensed under the [MIT License](LICENSE) and
is provided as-is, without warranty or a support commitment. Third-party
components retain their own licenses and notices.

For more detail, start with these official references:

- https://docs.hetzner.com/cloud/apps/list/docker-ce/
- https://github.com/pulumi/pulumi-hcloud/tree/v1.43.4/sdk/python/pulumi_hcloud
- https://github.com/pulumi/pulumi-tailscale/tree/v0.29.0/sdk/python/pulumi_tailscale
- https://docs.n8n.io/hosting/installation/docker/
- https://docs.n8n.io/hosting/cli-commands/
- https://github.com/n8n-io/n8n/blob/n8n%402.47.6/LICENSE.md
- https://tailscale.com/docs/features/containers/docker/docker-params
- https://tailscale.com/kb/1312/serve
- https://tailscale.com/kb/1085/auth-keys
- https://docs.docker.com/compose/compose-file/05-services/
