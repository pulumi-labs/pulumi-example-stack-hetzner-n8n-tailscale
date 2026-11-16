"""Read the stack boundary once, with immutable, explicit artifact inputs."""

import ipaddress
import re
from dataclasses import dataclass
from typing import Final

import pulumi

N8N_IMAGE: Final = (
    "docker.io/n8nio/n8n:2.47.6@sha256:"
    "3566fc1c340d8888a2e02c0dfbf7558fe4e3b300a9da892b1223e223404c5828"
)
POSTGRES_IMAGE: Final = (
    "docker.io/library/postgres:17.12-bookworm@sha256:"
    "40865bc877a289da75963d97d72b59633f639fc5af7a4e856bfa3714cae5b536"
)
TAILSCALE_IMAGE: Final = (
    "docker.io/tailscale/tailscale:v1.104.4@sha256:"
    "ed6480b33c6eb67c9cbd203ed42b9fb57e361986725b6856def71b7a3d9e276c"
)


def checked(value: str, pattern: str, key: str) -> str:
    """Reject invalid input without including its value in an exception."""
    if re.fullmatch(pattern, value) is None:
        message = f"Invalid configuration format: {key}"
        raise pulumi.RunError(message)
    return value


@dataclass(frozen=True, slots=True)
class Settings:
    """Single parsed stack configuration, including deferred Pulumi secrets."""

    name: str
    location: str
    image_id: int
    operator_cidr: str
    ssh_public_key: str
    tailnet: str
    tag: str
    fqdn: str
    n8n_image: str
    postgres_image: str
    tailscale_image: str
    hcloud_token: pulumi.Output[str]
    oauth_client_id: str
    oauth_client_secret: pulumi.Output[str]
    postgres_password: pulumi.Output[str]
    n8n_password: pulumi.Output[str]
    receipts_password: pulumi.Output[str]
    encryption_key: pulumi.Output[str]
    webhook_token: pulumi.Output[str]

    @classmethod
    def load(cls) -> "Settings":
        """Require scanned immutable images and a single operator source address."""
        config = pulumi.Config()
        name = checked(config.require("name"), r"[a-z][a-z0-9-]{2,39}", "name")
        fqdn = checked(
            config.require("fqdn"),
            re.escape(name) + r"\.[a-z0-9-]+\.ts\.net",
            "fqdn",
        )
        network = ipaddress.IPv4Network(config.require("operatorCidr"), strict=True)
        if network.prefixlen != network.max_prefixlen:
            message = "operatorCidr must be one IPv4 /32"
            raise pulumi.RunError(message)
        image_id = config.require_int("dockerHostImageId")
        if image_id <= 0:
            message = "dockerHostImageId must be a verified numeric image ID"
            raise pulumi.RunError(message)
        return cls(
            name=name,
            location=config.get("location") or "nbg1",
            image_id=image_id,
            operator_cidr=str(network),
            ssh_public_key=config.require("sshPublicKey"),
            tailnet=config.require("tailnet"),
            tag=checked(config.require("tag"), r"tag:[a-z][a-z0-9-]+", "tag"),
            fqdn=fqdn,
            n8n_image=N8N_IMAGE,
            postgres_image=POSTGRES_IMAGE,
            tailscale_image=TAILSCALE_IMAGE,
            hcloud_token=config.require_secret("hcloudToken"),
            oauth_client_id=config.require("tailscaleOAuthClientId"),
            oauth_client_secret=config.require_secret("tailscaleOAuthClientSecret"),
            postgres_password=config.require_secret("postgresPassword"),
            n8n_password=config.require_secret("n8nPassword"),
            receipts_password=config.require_secret("receiptsPassword"),
            encryption_key=config.require_secret("encryptionKey"),
            webhook_token=config.require_secret("webhookToken"),
        )
