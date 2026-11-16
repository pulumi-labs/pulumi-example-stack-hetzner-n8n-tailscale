"""Provision one private automation VM; execute only in the approved sandbox."""

from pathlib import Path

import pulumi
import pulumi_hcloud as hcloud
import pulumi_tailscale as tailscale

from settings import Settings
from startup import cloud_config

settings = Settings.load()
cloud = hcloud.Provider("hetzner", token=settings.hcloud_token)
tailnet = tailscale.Provider(
    "tailnet",
    tailnet=settings.tailnet,
    oauth_client_id=settings.oauth_client_id,
    oauth_client_secret=settings.oauth_client_secret,
)
labels = {"app": "private-n8n", "instance": settings.name}
ssh_key = hcloud.SshKey(
    "operator",
    name=settings.name,
    public_key=settings.ssh_public_key,
    labels=labels,
    opts=pulumi.ResourceOptions(provider=cloud),
)
firewall = hcloud.Firewall(
    "private-app",
    name=settings.name,
    labels=labels,
    rules=[
        hcloud.FirewallRuleArgs(
            direction="in",
            protocol="tcp",
            port="22",
            source_ips=[settings.operator_cidr],
            description="Operator SSH only; application ports remain closed",
        ),
    ],
    opts=pulumi.ResourceOptions(provider=cloud),
)
enrollment = tailscale.TailnetKey(
    "enrollment",
    description=settings.name.replace("-", ""),
    tags=[settings.tag],
    expiry=86400,
    reusable=False,
    ephemeral=False,
    preauthorized=True,
    recreate_if_invalid="never",
    opts=pulumi.ResourceOptions(provider=tailnet),
)
source = Path(__file__).parent
user_data = pulumi.Output.all(
    settings.postgres_password,
    settings.n8n_password,
    settings.receipts_password,
    settings.encryption_key,
    settings.webhook_token,
    enrollment.key,
).apply(lambda secrets: cloud_config(settings, secrets, source))
server = hcloud.Server(
    "automation",
    name=settings.name,
    server_type="cx23",
    location=settings.location,
    image=str(settings.image_id),
    ssh_keys=[ssh_key.id],
    firewall_ids=[firewall.id.apply(int)],
    public_nets=[hcloud.ServerPublicNetArgs(ipv4_enabled=True, ipv6_enabled=False)],
    user_data=pulumi.Output.secret(user_data),
    labels=labels,
    backups=False,
    delete_protection=False,
    rebuild_protection=False,
    shutdown_before_deletion=True,
    opts=pulumi.ResourceOptions(provider=cloud, delete_before_replace=True),
)
pulumi.export("serverId", server.id)
pulumi.export("publicIpv4", server.ipv4_address)
pulumi.export("privateUrl", f"https://{settings.fqdn}")
pulumi.export("hostname", settings.name)
pulumi.export("tag", settings.tag)
pulumi.export("enrollmentId", enrollment.id)
pulumi.export("enrollmentUrn", enrollment.urn)
pulumi.export("serverUrn", server.urn)
