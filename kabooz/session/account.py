# kabooz/session/account.py
"""
Account management for QobuzSession.

Profile and password operations against the authenticated user's
Qobuz account. Thin wrappers over QobuzClient, plus the pool-mode
guard that client methods already enforce.

Extracted from session/__init__.py. Mixin composition — methods
operate on a QobuzSession instance with access to self.client.

Public import path unchanged.
"""
from __future__ import annotations

from typing import Any

from ..models.user import UserProfile


class AccountMixin:
    """Mixin providing profile and password management.
    Composed into QobuzSession via class inheritance."""

    def get_profile(self) -> UserProfile:
        return self.client.get_user_info()

    def update_profile(self, **kwargs: Any) -> UserProfile:
        return self.client.update_user(**kwargs)

    def change_password(
        self, current_password: str, new_password: str,
    ) -> None:
        self.client.update_password(current_password, new_password)
