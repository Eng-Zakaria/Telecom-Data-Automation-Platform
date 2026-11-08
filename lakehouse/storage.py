"""Where each medallion layer lives, for the current CLOUDKIT_MODE.

local  -> Delta tables in Azurite containers (az://<layer>/<table>), emulator account
azure  -> Delta tables in ADLS Gen2 (abfss://<layer>@<account>.dfs.core.windows.net/<table>),
          Entra ID auth (managed identity in Azure, `az login` from a laptop)

Layer containers match infra/modules/storage/blob: bronze, silver, gold, quarantine.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from cloudkit import Settings, blob_service
from cloudkit.config import AZURITE_ACCOUNT, AZURITE_KEY

LAYERS = ("bronze", "silver", "gold", "quarantine")


@dataclass(frozen=True)
class Lake:
    settings: Settings
    prefix: str = ""  # isolates runs (tests, PR previews) inside the same containers

    @classmethod
    def from_env(cls, prefix: str | None = None) -> Lake:
        return cls(
            Settings.from_env(), prefix if prefix is not None else os.environ.get("LAKE_PREFIX", "")
        )

    def uri(self, layer: str, table: str) -> str:
        if layer not in LAYERS:
            raise ValueError(f"unknown layer {layer!r}; expected one of {LAYERS}")
        path = f"{self.prefix.strip('/')}/{table}".lstrip("/")
        if self.settings.is_local:
            return f"az://{layer}/{path}"
        account = self.settings.storage_account
        return f"abfss://{layer}@{account}.dfs.core.windows.net/{path}"

    @property
    def storage_options(self) -> dict[str, str]:
        if self.settings.is_local:
            return {
                "account_name": AZURITE_ACCOUNT,
                "account_key": AZURITE_KEY,
                "use_emulator": "true",
                "allow_http": "true",
                # object_store's emulator mode assumes 127.0.0.1:10000; honour overrides
                "azure_storage_endpoint": (
                    f"http://{self.settings.host}:{self.settings.blob_port}/{AZURITE_ACCOUNT}"
                ),
            }
        self.settings.require("storage_account")
        opts = {"account_name": self.settings.storage_account}
        if os.environ.get("LAKE_USE_AZURE_CLI", "").lower() == "true":
            opts["use_azure_cli"] = "true"
        return opts

    def ensure_containers(self) -> None:
        """Create layer containers in Azurite. In Azure, Terraform owns them."""
        if not self.settings.is_local:
            return
        svc = blob_service(self.settings)
        for layer in LAYERS:
            container = svc.get_container_client(layer)
            if not container.exists():
                container.create_container()

    def dataset_namespace(self) -> str:
        """OpenLineage dataset namespace for this lake (one per storage account)."""
        if self.settings.is_local:
            return f"azurite://{self.settings.host}:{self.settings.blob_port}/{AZURITE_ACCOUNT}"
        return f"abfss://{self.settings.storage_account}.dfs.core.windows.net"
