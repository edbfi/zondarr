"""Database models - SQLAlchemy 2.0 async models."""

from zondarr.models.admin import AdminAccount, AuthSession, RefreshToken
from zondarr.models.app_setting import AppSetting
from zondarr.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from zondarr.models.identity import Identity, User
from zondarr.models.invitation import (
    Invitation,
    invitation_libraries,
    invitation_servers,
)
from zondarr.models.media_server import Library, MediaServer
from zondarr.models.oauth_session import OAuthSessionModel
from zondarr.models.sync_run import SyncRun
from zondarr.models.wizard import (
    InteractionType,
    StepInteraction,
    Wizard,
    WizardStep,
    WizardStepTranslation,
)

__all__ = [
    "AdminAccount",
    "AppSetting",
    "AuthSession",
    "Base",
    "Identity",
    "InteractionType",
    "Invitation",
    "Library",
    "MediaServer",
    "OAuthSessionModel",
    "RefreshToken",
    "StepInteraction",
    "SyncRun",
    "TimestampMixin",
    "UUIDPrimaryKeyMixin",
    "User",
    "Wizard",
    "WizardStep",
    "WizardStepTranslation",
    "invitation_libraries",
    "invitation_servers",
]
