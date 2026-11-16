"""Render native cloud-init and Compose inputs without running local commands."""

import base64
import json
from pathlib import Path
from typing import Final

import pulumi

from settings import Settings, checked

MAX_USER_DATA_BYTES: Final = 32 * 1024


def cloud_config(settings: Settings, secrets: list[str], source: Path) -> str:
    """Render one secret user-data document; every application image is preloaded."""
    postgres, n8n, receipts, encryption, webhook = [
        checked(value, r"[a-f0-9]{64}", "application secret") for value in secrets[:5]
    ]
    enrollment = secrets[5]
    environment = {
        "N8N_IMAGE": settings.n8n_image,
        "POSTGRES_IMAGE": settings.postgres_image,
        "TAILSCALE_IMAGE": settings.tailscale_image,
        "N8N_FQDN": settings.fqdn,
        "TS_HOSTNAME": settings.name,
        "POSTGRES_PASSWORD": postgres,
        "N8N_DB_PASSWORD": n8n,
        "N8N_ENCRYPTION_KEY": encryption,
    }
    credentials = [
        {
            "id": "privateReceiptDb",
            "name": "Private receipts database",
            "type": "postgres",
            "data": {
                "host": "postgres",
                "database": "receipts",
                "user": "receipt_writer",
                "password": receipts,
                "port": 5432,
                "ssl": "disable",
            },
        },
        {
            "id": "privateReceiptHeader",
            "name": "Private receipt webhook",
            "type": "httpHeaderAuth",
            "data": {"name": "X-Receipt-Token", "value": webhook},
        },
    ]
    init_sql = (source / "postgres-init.sql").read_text().replace(
        "@@N8N_PASSWORD@@", n8n,
    ).replace("@@RECEIPTS_PASSWORD@@", receipts)
    files = [
        ("compose.yaml", (source / "compose.yaml").read_text(), "0600", "root:root"),
        (
            ".env",
            "\n".join(f"{key}={value}" for key, value in environment.items()) + "\n",
            "0600",
            "root:root",
        ),
        ("enrollment.key", enrollment, "0600", "root:root"),
        ("postgres-init.sql", init_sql, "0444", "root:root"),
        ("serve.json", (source / "serve.json").read_text(), "0444", "root:root"),
        ("workflow.json", (source / "workflow.json").read_text(), "0444", "root:root"),
        ("credentials.json", json.dumps(credentials), "0444", "root:root"),
    ]
    write_files = [
        {
            "path": f"/opt/private-n8n/{name}",
            "permissions": mode,
            "owner": owner,
            "encoding": "b64",
            "content": base64.b64encode(content.encode()).decode(),
        }
        for name, content, mode, owner in files
    ]
    write_files.append({
        "path": "/etc/systemd/system/private-n8n.service",
        "permissions": "0644",
        "content": (source / "private-n8n.service").read_text(),
    })
    document = {
        "ssh_pwauth": False,
        "write_files": write_files,
        "runcmd": [
            ["chmod", "0700", "/opt/private-n8n"],
            ["systemctl", "daemon-reload"],
        ],
    }
    result = "#cloud-config\n" + json.dumps(document)
    if len(result.encode()) > MAX_USER_DATA_BYTES:
        message = "Rendered cloud-init exceeds Hetzner's 32 KiB limit"
        raise pulumi.RunError(message)
    return result
