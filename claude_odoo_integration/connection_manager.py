# Copyright 2026 M&H Services
"""
Connection manager for Claude Code + Odoo.sh integration.

Handles multiple Odoo.sh environments (production, staging, dev).
Loads credentials from environment variables or .env file.
"""
import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv
from .odoo_client import OdooRPCClient, OdooConfig

dotenv_path = Path(__file__).parent.parent / ".env"
if dotenv_path.exists():
    load_dotenv(dotenv_path)


class ConnectionManager:
    """Manages connections to multiple Odoo.sh environments."""

    def __init__(self):
        self._clients: dict[str, OdooRPCClient] = {}
        self._setup_connections()

    def _setup_connections(self):
        """Initialize connections from environment variables."""
        for env in ["dev", "staging", "production"]:
            url = os.getenv(f"ODOO_{env.upper()}_URL")
            db = os.getenv(f"ODOO_{env.upper()}_DB")
            user = os.getenv(f"ODOO_{env.upper()}_USER")
            password = os.getenv(f"ODOO_{env.upper()}_PASSWORD")

            if all([url, db, user, password]):
                config = OdooConfig(url=url, db=db, username=user, password=password)
                client = OdooRPCClient(config)
                if client.connect():
                    self._clients[env] = client

    def get_client(self, environment: str = "dev") -> OdooRPCClient:
        """Get or create a connection to the specified environment."""
        if environment not in self._clients:
            raise ValueError(f"Unknown environment: {environment}. Configured: {list(self._clients.keys())}")
        return self._clients[environment]

    def list_environments(self) -> list[str]:
        """Return list of configured environments."""
        return list(self._clients.keys())