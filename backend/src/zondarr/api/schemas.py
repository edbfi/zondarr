"""API request/response schemas using msgspec Structs.

Provides:
- ErrorResponse: Standard error response structure
- MediaServerCreate/Response: Media server CRUD schemas
- LibraryResponse: Library response schema
- InvitationCreate/Response: Invitation CRUD schemas
- IdentityCreate/Response: Identity CRUD schemas
- UserResponse: User response schema
- HealthCheckResponse: Health endpoint response schema
- OAuthPinResponse/OAuthCheckResponse: OAuth flow schemas

Uses msgspec.Struct for high-performance serialization (10-80x faster than Pydantic).
Validation constraints are defined via Meta annotations.

Request structs use:
- kw_only=True: All fields must be passed as keyword arguments
- forbid_unknown_fields=True: Reject payloads with extra fields

Response structs use:
- omit_defaults=True: Exclude fields with default values from JSON output
"""

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

import msgspec
from msgspec import UNSET, UnsetType

from zondarr.core.languages import is_valid_language_code
from zondarr.media.provider import AuthFlowType

# =============================================================================
# Reusable Constrained Types
# =============================================================================

# Non-empty string with max length for names and identifiers
NonEmptyStr = Annotated[str, msgspec.Meta(min_length=1, max_length=255)]

# URL string with reasonable max length (HTTP(S) only)
UrlStr = Annotated[
    str, msgspec.Meta(min_length=1, max_length=2048, pattern=r"^https?://")
]

# API key string (may be longer for some services)
ApiKeyStr = Annotated[str, msgspec.Meta(min_length=1, max_length=512)]

# Invitation code (short, unique identifier, alphanumeric only)
InvitationCode = Annotated[
    str, msgspec.Meta(min_length=1, max_length=20, pattern=r"^[a-zA-Z0-9]+$")
]

# Email address (basic pattern validation)
EmailStr = Annotated[
    str, msgspec.Meta(pattern=r"^[\w.-]+@[\w.-]+\.\w+$", max_length=255)
]

# Positive integer for counts and limits
PositiveInt = Annotated[int, msgspec.Meta(gt=0)]

# Non-negative integer for use counts
NonNegativeInt = Annotated[int, msgspec.Meta(ge=0)]

# Username for redemption (lowercase, starts with letter)
Username = Annotated[
    str, msgspec.Meta(min_length=3, max_length=32, pattern=r"^[a-z][a-z0-9_]*$")
]

# Password for redemption (minimum 8 characters)
Password = Annotated[str, msgspec.Meta(min_length=8, max_length=128)]


# =============================================================================
# Error Response Schemas
# =============================================================================


class ErrorResponse(msgspec.Struct, kw_only=True):
    """Standard error response structure.

    All API errors return this structure for consistent client handling.

    Attributes:
        detail: Human-readable error description.
        error_code: Machine-readable error code for programmatic handling.
        timestamp: When the error occurred (UTC).
        correlation_id: Optional unique ID for tracing errors in logs.
    """

    detail: str
    error_code: str
    timestamp: datetime
    correlation_id: str | None = None


class FieldError(msgspec.Struct, kw_only=True):
    """Field-level validation error detail.

    Attributes:
        field: Name of the field that failed validation.
        messages: List of validation error messages for this field.
    """

    field: str
    messages: list[str]


class ValidationErrorResponse(msgspec.Struct, kw_only=True):
    """Validation error response with field-level details.

    Extends ErrorResponse with field-specific error information.

    Attributes:
        detail: Human-readable error description.
        error_code: Always "VALIDATION_ERROR" for this type.
        timestamp: When the error occurred (UTC).
        correlation_id: Optional unique ID for tracing errors in logs.
        field_errors: List of field-level validation errors.
    """

    detail: str
    error_code: str
    timestamp: datetime
    correlation_id: str | None = None
    field_errors: list[FieldError]


# =============================================================================
# Media Server Schemas
# =============================================================================


class MediaServerCreate(msgspec.Struct, kw_only=True, forbid_unknown_fields=True):
    """Request to create a media server.

    Note: server_type is validated as a non-empty string at the schema level.
    Valid provider type checking is deferred to the service layer's registry
    lookup, allowing new providers to be added without schema changes.

    Attributes:
        name: Human-readable name for the server.
        server_type: Type of media server (e.g., "plex", "jellyfin").
        url: Base URL for the media server API. Optional if use_env_credentials is True.
        api_key: Authentication token for the media server (optional if use_env_credentials is True).
        use_env_credentials: If True, resolve URL and api_key from environment variables on the server.
    """

    name: NonEmptyStr
    server_type: NonEmptyStr
    url: UrlStr | None = None
    api_key: ApiKeyStr | None = None
    use_env_credentials: bool = False


class EnvCredentialResponse(msgspec.Struct, kw_only=True):
    """A single detected provider credential from environment variables.

    The plaintext api_key is never sent to the client. Use
    ``use_env_credentials: true`` on create/test endpoints to have the
    server resolve the key from env vars.

    Attributes:
        server_type: Provider identifier string (e.g., "plex", "jellyfin").
        display_name: Human-readable provider name.
        has_url: Whether a URL was detected.
        has_api_key: Whether an API key was detected.
    """

    server_type: str
    display_name: str
    has_url: bool = False
    has_api_key: bool = False


class EnvCredentialsResponse(msgspec.Struct, kw_only=True):
    """Response listing all detected environment variable credentials.

    Attributes:
        credentials: List of detected provider credentials.
    """

    credentials: list[EnvCredentialResponse]


class CredentialLockStatusResponse(msgspec.Struct, kw_only=True):
    """Per-field lock status for media server credentials.

    Indicates which credential fields are overridden by environment
    variables and cannot be edited through the UI.

    Attributes:
        url_locked: True if the URL is set via environment variable.
        api_key_locked: True if the API key is set via environment variable.
    """

    url_locked: bool
    api_key_locked: bool


class MediaServerUpdate(msgspec.Struct, kw_only=True, forbid_unknown_fields=True):
    """Request to update a media server.

    All fields are optional - only provided fields will be updated.

    Attributes:
        name: Human-readable name for the server.
        url: Base URL for the media server API.
        api_key: Authentication token for the media server.
        enabled: Whether the server is active for user management.
    """

    name: NonEmptyStr | None = None
    url: UrlStr | None = None
    api_key: ApiKeyStr | None = None
    enabled: bool | None = None


class MediaServerResponse(msgspec.Struct, omit_defaults=True):
    """Media server response.

    Attributes:
        id: Unique identifier for the server.
        name: Human-readable name for the server.
        server_type: Type of media server (e.g., "plex", "jellyfin").
        url: Base URL for the media server API.
        enabled: Whether the server is active for user management.
        created_at: When the server was added.
        updated_at: When the server was last modified.
    """

    id: UUID
    name: str
    server_type: str
    url: str
    enabled: bool
    created_at: datetime
    updated_at: datetime | None = None
    supported_permissions: list[str] | None = None


class PublicMediaServerResponse(msgspec.Struct, omit_defaults=True):
    """Public-facing media server response for unauthenticated endpoints.

    Strips sensitive fields (id, url, enabled, timestamps) to prevent
    exposure of internal network topology.

    Attributes:
        name: Human-readable name for the server.
        server_type: Type of media server (e.g., "plex", "jellyfin").
        supported_permissions: List of supported permission types.
    """

    name: str
    server_type: str
    supported_permissions: list[str] | None = None


# =============================================================================
# Library Schemas
# =============================================================================


class LibraryResponse(msgspec.Struct, omit_defaults=True):
    """Library response.

    Attributes:
        id: Unique identifier for the library.
        name: Human-readable name of the library.
        library_type: Type of content (movies, tvshows, music, etc.).
        external_id: The library's ID on the media server.
        created_at: When the library was synced.
        updated_at: When the library was last synced.
    """

    id: UUID
    name: str
    library_type: str
    external_id: str
    created_at: datetime
    updated_at: datetime | None = None


class MediaServerWithLibrariesResponse(msgspec.Struct, omit_defaults=True):
    """Media server response including libraries.

    Attributes:
        id: Unique identifier for the server.
        name: Human-readable name for the server.
        server_type: Type of media server (e.g., "plex", "jellyfin").
        url: Base URL for the media server API.
        enabled: Whether the server is active for user management.
        created_at: When the server was added.
        updated_at: When the server was last modified.
        libraries: List of libraries on this server.
    """

    id: UUID
    name: str
    server_type: str
    url: str
    enabled: bool
    created_at: datetime
    libraries: list[LibraryResponse]
    updated_at: datetime | None = None
    supported_permissions: list[str] | None = None


class SyncChannelStatusResponse(msgspec.Struct, kw_only=True, omit_defaults=True):
    """Sync status details for a single sync channel."""

    in_progress: bool
    last_completed_at: datetime | None = None
    next_scheduled_at: datetime | None = None
    circuit_state: str | None = None
    consecutive_failures: int | None = None
    next_retry_at: datetime | None = None


class ServerSyncStatusResponse(msgspec.Struct, kw_only=True):
    """Sync status for all server sync channels."""

    libraries: SyncChannelStatusResponse
    users: SyncChannelStatusResponse


class MediaServerDetailResponse(msgspec.Struct, omit_defaults=True):
    """Detailed media server response including libraries and sync status."""

    id: UUID
    name: str
    server_type: str
    url: str
    enabled: bool
    created_at: datetime
    libraries: list[LibraryResponse]
    sync_status: ServerSyncStatusResponse
    updated_at: datetime | None = None
    supported_permissions: list[str] | None = None


# =============================================================================
# Wizard Schemas
# =============================================================================


class LanguageResponse(msgspec.Struct):
    """A single ISO 639-1 language entry.

    Attributes:
        code: Two-letter ISO 639-1 language code.
        name: Native language name.
    """

    code: str
    name: str


# Interaction type pattern for validation
InteractionTypeStr = Annotated[
    str, msgspec.Meta(pattern=r"^(click|timer|tos|text_input|quiz)$")
]

# Step order (non-negative integer)
StepOrder = Annotated[int, msgspec.Meta(ge=0)]

# Language code (ISO 639-1, exactly 2 lowercase letters, validated against standard)
LanguageCode = Annotated[
    str, msgspec.Meta(min_length=2, max_length=2, pattern=r"^[a-z]{2}$")
]


class TranslationData(msgspec.Struct, kw_only=True, forbid_unknown_fields=True):
    """Translation data for a wizard step.

    Attributes:
        language_code: ISO 639-1 language code (e.g., "en", "da", "de").
        title: Translated title for the step.
        content_markdown: Translated markdown content.
    """

    language_code: LanguageCode
    title: NonEmptyStr
    content_markdown: str

    def __post_init__(self) -> None:
        if not is_valid_language_code(self.language_code):
            msg = f"Invalid ISO 639-1 language code: {self.language_code!r}"
            raise ValueError(msg)


class TranslationResponse(msgspec.Struct, omit_defaults=True):
    """Translation response for a wizard step.

    Attributes:
        language_code: ISO 639-1 language code.
        title: Translated title for the step.
        content_markdown: Translated markdown content.
    """

    language_code: str
    title: str
    content_markdown: str


class WizardCreate(msgspec.Struct, kw_only=True, forbid_unknown_fields=True):
    """Request to create a wizard.

    Attributes:
        name: Human-readable name for the wizard.
        description: Optional detailed description.
        enabled: Whether the wizard is active. Defaults to True.
    """

    name: NonEmptyStr
    description: str | None = None
    enabled: bool = True


class WizardUpdate(msgspec.Struct, kw_only=True, forbid_unknown_fields=True):
    """Request to update a wizard.

    All fields are optional - only provided fields will be updated.

    Attributes:
        name: Human-readable name for the wizard.
        description: Optional detailed description.
        enabled: Whether the wizard is active.
    """

    name: NonEmptyStr | None = None
    description: str | None = None
    enabled: bool | None = None


class WizardStepCreate(msgspec.Struct, kw_only=True, forbid_unknown_fields=True):
    """Request to create a wizard step.

    Steps are created as bare content containers. Interactions
    are added separately via the interaction endpoints.

    Attributes:
        title: Display title for the step.
        content_markdown: Markdown content to display.
        step_order: Position in the wizard sequence. Auto-assigned if not provided.
        primary_language: Language code of the title/content_markdown fields.
        translations: Optional list of translations for other languages.
    """

    title: NonEmptyStr
    content_markdown: str
    step_order: StepOrder | None = None
    primary_language: LanguageCode = "en"
    translations: list[TranslationData] | None = None

    def __post_init__(self) -> None:
        if not is_valid_language_code(self.primary_language):
            msg = f"Invalid ISO 639-1 language code: {self.primary_language!r}"
            raise ValueError(msg)


class WizardStepUpdate(msgspec.Struct, kw_only=True, forbid_unknown_fields=True):
    """Request to update a wizard step.

    All fields are optional - only provided fields will be updated.

    Attributes:
        title: Display title for the step.
        content_markdown: Markdown content to display.
        primary_language: Language code of the title/content_markdown fields.
        translations: List of translations to upsert. Omit to leave unchanged.
    """

    title: NonEmptyStr | None = None
    content_markdown: str | None = None
    primary_language: LanguageCode | None = None
    translations: list[TranslationData] | None = None

    def __post_init__(self) -> None:
        if self.primary_language is not None and not is_valid_language_code(
            self.primary_language
        ):
            msg = f"Invalid ISO 639-1 language code: {self.primary_language!r}"
            raise ValueError(msg)


class StepReorderRequest(msgspec.Struct, kw_only=True, forbid_unknown_fields=True):
    """Request to reorder a wizard step.

    Attributes:
        new_order: The new position for the step (0-indexed).
    """

    new_order: StepOrder


class InteractionResponseData(msgspec.Struct, kw_only=True, forbid_unknown_fields=True):
    """Response data for a single interaction in a validation request.

    Attributes:
        interaction_id: The UUID of the interaction being validated.
        response: Type-specific response data (acknowledged, accepted, text, answer_index).
        started_at: When the interaction was started (required for timer validation).
    """

    interaction_id: UUID
    response: dict[str, str | int | bool | None]
    started_at: datetime | None = None


class StepValidationRequest(msgspec.Struct, kw_only=True, forbid_unknown_fields=True):
    """Request to validate a step completion.

    Sends all interaction responses for a step. Empty list means
    informational step (always valid).

    Attributes:
        step_id: The UUID of the step being validated.
        interactions: List of interaction responses. Empty for informational steps.
        progress_token: Signed progress token from prior step validation.
            Required for non-first steps to prove sequential completion.
    """

    step_id: UUID
    interactions: list[InteractionResponseData] = []
    progress_token: str | None = None


class StepInteractionResponse(msgspec.Struct, omit_defaults=True):
    """Step interaction response.

    Attributes:
        id: Unique identifier for the interaction.
        step_id: ID of the parent step.
        interaction_type: Type of interaction.
        config: Type-specific configuration.
        display_order: Position for rendering.
        created_at: When the interaction was created.
        updated_at: When the interaction was last modified.
    """

    id: UUID
    step_id: UUID
    interaction_type: str
    config: dict[str, str | int | bool | list[str] | None]
    display_order: int
    created_at: datetime
    updated_at: datetime | None = None


class StepInteractionCreate(msgspec.Struct, kw_only=True, forbid_unknown_fields=True):
    """Request to create a step interaction.

    Attributes:
        interaction_type: Type of interaction (click, timer, tos, text_input, quiz).
        config: Type-specific configuration.
        display_order: Position for rendering. Auto-assigned if not provided.
    """

    interaction_type: InteractionTypeStr
    config: dict[str, str | int | bool | list[str] | None] = {}
    display_order: StepOrder | None = None


class StepInteractionUpdate(msgspec.Struct, kw_only=True, forbid_unknown_fields=True):
    """Request to update a step interaction.

    Attributes:
        config: Type-specific configuration.
    """

    config: dict[str, str | int | bool | list[str] | None] | None = None


class WizardStepResponse(msgspec.Struct, omit_defaults=True):
    """Wizard step response.

    Attributes:
        id: Unique identifier for the step.
        wizard_id: ID of the parent wizard.
        step_order: Position in the wizard sequence.
        title: Display title for the step.
        content_markdown: Markdown content to display.
        primary_language: Language code of the title/content_markdown fields.
        interactions: List of interactions attached to this step.
        translations: List of translations for other languages.
        created_at: When the step was created.
        updated_at: When the step was last modified.
    """

    id: UUID
    wizard_id: UUID
    step_order: int
    title: str
    content_markdown: str
    primary_language: str
    interactions: list[StepInteractionResponse]
    translations: list[TranslationResponse]
    created_at: datetime
    updated_at: datetime | None = None


class WizardResponse(msgspec.Struct, omit_defaults=True):
    """Wizard response (without steps).

    Attributes:
        id: Unique identifier for the wizard.
        name: Human-readable name for the wizard.
        enabled: Whether the wizard is active.
        created_at: When the wizard was created.
        description: Optional detailed description.
        updated_at: When the wizard was last modified.
    """

    id: UUID
    name: str
    enabled: bool
    created_at: datetime
    description: str | None = None
    updated_at: datetime | None = None


class WizardDetailResponse(msgspec.Struct, omit_defaults=True):
    """Wizard response with steps.

    Attributes:
        id: Unique identifier for the wizard.
        name: Human-readable name for the wizard.
        enabled: Whether the wizard is active.
        created_at: When the wizard was created.
        steps: List of wizard steps in order.
        description: Optional detailed description.
        updated_at: When the wizard was last modified.
    """

    id: UUID
    name: str
    enabled: bool
    created_at: datetime
    steps: list[WizardStepResponse]
    description: str | None = None
    updated_at: datetime | None = None


class WizardListResponse(msgspec.Struct, kw_only=True):
    """Paginated wizard list response.

    Attributes:
        items: List of wizards for the current page.
        total: Total number of wizards matching the query.
        page: Current page number (1-indexed).
        page_size: Number of items per page.
        has_next: Whether there are more pages available.
    """

    items: list[WizardResponse]
    total: int
    page: int
    page_size: int
    has_next: bool


class StepValidationResponse(msgspec.Struct, kw_only=True):
    """Response from step validation endpoint.

    Attributes:
        valid: Whether the step completion was valid.
        completion_token: Token proving completion (only if valid).
        error: Error message (only if invalid).
    """

    valid: bool
    completion_token: str | None = None
    error: str | None = None


# =============================================================================
# Invitation Schemas
# =============================================================================


class CreateInvitationRequest(msgspec.Struct, kw_only=True, forbid_unknown_fields=True):
    """Request to create an invitation.

    Attributes:
        server_ids: List of media server IDs this invitation grants access to.
        code: Unique invitation code (if not provided, one will be generated).
        expires_at: Optional expiration timestamp.
        max_uses: Optional maximum number of redemptions.
        duration_days: Optional duration in days for user access after redemption.
        library_ids: Optional list of specific library IDs to grant access to.
        permissions: Optional permission overrides (can_download, can_stream, etc.).
        pre_wizard_id: Optional wizard ID to run before account creation.
        post_wizard_id: Optional wizard ID to run after account creation.
    """

    server_ids: Annotated[list[UUID], msgspec.Meta(min_length=1)]
    code: InvitationCode | None = None
    expires_at: datetime | None = None
    max_uses: PositiveInt | None = None
    duration_days: PositiveInt | None = None
    library_ids: list[UUID] | None = None
    permissions: dict[str, bool] | None = None
    pre_wizard_id: UUID | None = None
    post_wizard_id: UUID | None = None


# Alias for backwards compatibility
InvitationCreate = CreateInvitationRequest


class UpdateInvitationRequest(msgspec.Struct, kw_only=True, forbid_unknown_fields=True):
    """Request to update an invitation (mutable fields only).

    All fields are optional - only provided fields will be updated.
    Immutable fields (code, use_count, created_at, created_by) cannot be updated.

    Attributes:
        expires_at: Optional expiration timestamp.
        max_uses: Optional maximum number of redemptions.
        duration_days: Optional duration in days for user access after redemption.
        enabled: Whether the invitation is currently active.
        server_ids: List of media server IDs this invitation grants access to.
        library_ids: Optional list of specific library IDs to grant access to.
        permissions: Optional permission overrides (can_download, can_stream, etc.).
        pre_wizard_id: Optional wizard ID to run before account creation.
        post_wizard_id: Optional wizard ID to run after account creation.
    """

    expires_at: datetime | UnsetType | None = UNSET
    max_uses: PositiveInt | UnsetType | None = UNSET
    duration_days: PositiveInt | UnsetType | None = UNSET
    enabled: bool | UnsetType = UNSET
    server_ids: list[UUID] | UnsetType = UNSET
    library_ids: list[UUID] | UnsetType = UNSET
    permissions: dict[str, bool] | UnsetType = UNSET
    pre_wizard_id: UUID | UnsetType | None = UNSET
    post_wizard_id: UUID | UnsetType | None = UNSET


# Alias for backwards compatibility
InvitationUpdate = UpdateInvitationRequest


class InvitationResponse(msgspec.Struct, omit_defaults=True):
    """Invitation response with computed fields.

    Attributes:
        id: Unique identifier for the invitation.
        code: Unique invitation code.
        use_count: Current number of times the invitation has been redeemed.
        enabled: Whether the invitation is currently active.
        created_at: When the invitation was created.
        expires_at: Optional expiration timestamp.
        max_uses: Optional maximum number of redemptions.
        duration_days: Optional duration in days for user access after redemption.
        created_by: Optional identifier of who created the invitation.
        updated_at: When the invitation was last modified.
        is_active: Computed field: enabled AND not expired AND use_count < max_uses.
        remaining_uses: Computed field: max_uses - use_count if max_uses set.
    """

    id: UUID
    code: str
    use_count: int
    enabled: bool
    created_at: datetime
    is_active: bool
    expires_at: datetime | None = None
    max_uses: int | None = None
    duration_days: int | None = None
    created_by: str | None = None
    updated_at: datetime | None = None
    remaining_uses: int | None = None


class InvitationDetailResponse(msgspec.Struct, omit_defaults=True):
    """Detailed invitation response including related servers and libraries.

    Attributes:
        id: Unique identifier for the invitation.
        code: Unique invitation code.
        use_count: Current number of times the invitation has been redeemed.
        enabled: Whether the invitation is currently active.
        created_at: When the invitation was created.
        is_active: Computed field: enabled AND not expired AND use_count < max_uses.
        target_servers: List of media servers this invitation grants access to.
        allowed_libraries: List of specific libraries this invitation grants access to.
        expires_at: Optional expiration timestamp.
        max_uses: Optional maximum number of redemptions.
        duration_days: Optional duration in days for user access after redemption.
        created_by: Optional identifier of who created the invitation.
        updated_at: When the invitation was last modified.
        remaining_uses: Computed field: max_uses - use_count if max_uses set.
        pre_wizard: Optional wizard to run before account creation.
        post_wizard: Optional wizard to run after account creation.
    """

    id: UUID
    code: str
    use_count: int
    enabled: bool
    created_at: datetime
    is_active: bool
    target_servers: list[MediaServerResponse]
    allowed_libraries: list[LibraryResponse]
    expires_at: datetime | None = None
    max_uses: int | None = None
    duration_days: int | None = None
    created_by: str | None = None
    updated_at: datetime | None = None
    remaining_uses: int | None = None
    pre_wizard: WizardResponse | None = None
    post_wizard: WizardResponse | None = None


class InvitationListResponse(msgspec.Struct, kw_only=True):
    """Paginated invitation list response.

    Attributes:
        items: List of invitations for the current page.
        total: Total number of invitations matching the query.
        page: Current page number (1-indexed).
        page_size: Number of items per page.
        has_next: Whether there are more pages available.
    """

    items: list[InvitationResponse]
    total: int
    page: int
    page_size: int
    has_next: bool


# =============================================================================
# Invitation Validation/Redemption Schemas
# =============================================================================


class InvitationValidationResponse(msgspec.Struct, omit_defaults=True):
    """Response from invitation validation endpoint.

    Attributes:
        valid: Whether the invitation code is valid for redemption.
        failure_reason: Specific reason if invalid (not_found, disabled, expired, max_uses_reached).
        target_servers: List of media servers the invitation grants access to (if valid).
        allowed_libraries: List of specific libraries the invitation grants access to (if valid).
        duration_days: Duration in days for user access after redemption (if valid).
        pre_wizard: Optional wizard to run before account creation (if valid).
        post_wizard: Optional wizard to run after account creation (if valid).
    """

    valid: bool
    failure_reason: str | None = None
    target_servers: list[PublicMediaServerResponse] | None = None
    allowed_libraries: list[LibraryResponse] | None = None
    duration_days: int | None = None
    pre_wizard: WizardDetailResponse | None = None
    post_wizard: WizardDetailResponse | None = None


class RedeemInvitationRequest(msgspec.Struct, kw_only=True, forbid_unknown_fields=True):
    """Request to redeem an invitation.

    Attributes:
        username: Username for the new accounts (3-32 chars, lowercase, starts with letter).
        password: Password for the new accounts (minimum 8 characters).
        email: Optional email address for the identity.
        redemption_token: One-time OAuth redemption token from the PIN check endpoint.
            Resolved server-side to the provider's auth_token.
        pre_wizard_token: Signed wizard completion token proving the pre-wizard
            was completed. Required when the invitation has a pre_wizard_id configured.
    """

    username: Username
    password: Password
    email: EmailStr | None = None
    redemption_token: str | None = None
    pre_wizard_token: str | None = None


# =============================================================================
# Identity Schemas
# =============================================================================


class IdentityCreate(msgspec.Struct, kw_only=True, forbid_unknown_fields=True):
    """Request to create an identity.

    Attributes:
        display_name: Human-readable name for the identity.
        email: Optional email address for notifications.
        expires_at: Optional expiration timestamp.
    """

    display_name: NonEmptyStr
    email: EmailStr | None = None
    expires_at: datetime | None = None


class IdentityUpdate(msgspec.Struct, kw_only=True, forbid_unknown_fields=True):
    """Request to update an identity.

    All fields are optional - only provided fields will be updated.

    Attributes:
        display_name: Human-readable name for the identity.
        email: Optional email address for notifications.
        expires_at: Optional expiration timestamp.
        enabled: Whether the identity is currently active.
    """

    display_name: NonEmptyStr | None = None
    email: EmailStr | None = None
    expires_at: datetime | None = None
    enabled: bool | None = None


class IdentityResponse(msgspec.Struct, omit_defaults=True):
    """Identity response.

    Attributes:
        id: Unique identifier for the identity.
        display_name: Human-readable name for the identity.
        email: Optional email address for notifications.
        expires_at: Optional expiration timestamp.
        enabled: Whether the identity is currently active.
        created_at: When the identity was created.
        updated_at: When the identity was last modified.
    """

    id: UUID
    display_name: str
    enabled: bool
    created_at: datetime
    email: str | None = None
    expires_at: datetime | None = None
    updated_at: datetime | None = None


# =============================================================================
# User Schemas
# =============================================================================


class UserResponse(msgspec.Struct, omit_defaults=True):
    """User response.

    Attributes:
        id: Unique identifier for the user.
        identity_id: ID of the parent identity.
        media_server_id: ID of the media server.
        external_user_id: The user's ID on the media server.
        username: The username on the media server.
        email: Email captured for the parent identity (OAuth-supplied or
            user-entered), or None if unknown.
        expires_at: Optional expiration timestamp.
        enabled: Whether the user account is currently active.
        created_at: When the user was created.
        updated_at: When the user was last modified.
    """

    id: UUID
    identity_id: UUID
    media_server_id: UUID
    external_user_id: str
    username: str
    enabled: bool
    created_at: datetime
    email: str | None = None
    external_user_type: str | None = None
    expires_at: datetime | None = None
    updated_at: datetime | None = None


class UserDetailResponse(msgspec.Struct, omit_defaults=True):
    """Detailed user response with relationships.

    Includes identity info, media server info, and invitation source.

    Attributes:
        id: Unique identifier for the user.
        identity_id: ID of the parent identity.
        media_server_id: ID of the media server.
        external_user_id: The user's ID on the media server.
        username: The username on the media server.
        email: Email captured for the parent identity (OAuth-supplied,
            user-entered, or provider-supplied), or None if unknown.
        enabled: Whether the user account is currently active.
        created_at: When the user was created.
        identity: The parent identity with all linked users.
        media_server: The media server this user belongs to.
        expires_at: Optional expiration timestamp.
        updated_at: When the user was last modified.
        invitation_id: ID of the invitation used to create this user.
        invitation: The source invitation if available.
    """

    id: UUID
    identity_id: UUID
    media_server_id: UUID
    external_user_id: str
    username: str
    enabled: bool
    created_at: datetime
    identity: IdentityResponse
    media_server: MediaServerResponse
    email: str | None = None
    external_user_type: str | None = None
    expires_at: datetime | None = None
    updated_at: datetime | None = None
    invitation_id: UUID | None = None
    invitation: InvitationResponse | None = None


class RemoveSharesResponse(msgspec.Struct, kw_only=True):
    """Response for the remove-shares endpoint.

    Attributes:
        user: Updated user details with relationships.
        libraries_removed: Number of shared libraries removed (0 or 1).
        message: Human-readable description of what happened.
    """

    user: UserDetailResponse
    libraries_removed: int
    message: str


class UserListResponse(msgspec.Struct, kw_only=True):
    """Paginated user list response.

    Attributes:
        items: List of users for the current page.
        total: Total number of users matching the query.
        page: Current page number (1-indexed).
        page_size: Number of items per page.
        has_next: Whether there are more pages available.
    """

    items: list[UserDetailResponse]
    total: int
    page: int
    page_size: int
    has_next: bool


# Sort field options for user listing
UserSortField = Annotated[
    str, msgspec.Meta(pattern=r"^(created_at|username|expires_at)$")
]

# Sort order options
SortOrder = Annotated[str, msgspec.Meta(pattern=r"^(asc|desc)$")]

# Page number (1-indexed, positive)
PageNumber = Annotated[int, msgspec.Meta(ge=1)]

# Page size (1-100, with default 50)
PageSize = Annotated[int, msgspec.Meta(ge=1, le=100)]


class UserListFilters(msgspec.Struct, kw_only=True, forbid_unknown_fields=True):
    """Filters for user listing.

    Supports filtering by media_server_id, invitation_id, enabled status,
    and expiration status. Supports sorting by created_at, username, and
    expires_at.

    Attributes:
        media_server_id: Filter by media server ID.
        invitation_id: Filter by invitation ID.
        enabled: Filter by enabled status.
        expired: Filter by expiration status (True = expired, False = not expired).
        sort_by: Field to sort by (created_at, username, expires_at).
        sort_order: Sort direction (asc, desc).
        page: Page number (1-indexed).
        page_size: Number of items per page (max 100, default 50).
    """

    media_server_id: UUID | None = None
    invitation_id: UUID | None = None
    enabled: bool | None = None
    expired: bool | None = None
    sort_by: UserSortField = "created_at"
    sort_order: SortOrder = "desc"
    page: PageNumber = 1
    page_size: PageSize = 50


class UpdatePermissionsRequest(
    msgspec.Struct, kw_only=True, forbid_unknown_fields=True
):
    """Request to update user permissions on the media server.

    Maps to universal permission names that are translated to server-specific
    settings by the media client implementations.

    Attributes:
        can_download: Whether the user can download content.
        can_stream: Whether the user can stream/play content.
        can_sync: Whether the user can sync content for offline use.
        can_transcode: Whether the user can use transcoding.
    """

    can_download: bool | None = None
    can_stream: bool | None = None
    can_sync: bool | None = None
    can_transcode: bool | None = None


class IdentityWithUsersResponse(msgspec.Struct, omit_defaults=True):
    """Identity response including linked users.

    Attributes:
        id: Unique identifier for the identity.
        display_name: Human-readable name for the identity.
        email: Optional email address for notifications.
        expires_at: Optional expiration timestamp.
        enabled: Whether the identity is currently active.
        created_at: When the identity was created.
        updated_at: When the identity was last modified.
        users: List of media server accounts linked to this identity.
    """

    id: UUID
    display_name: str
    enabled: bool
    created_at: datetime
    users: list[UserResponse]
    email: str | None = None
    expires_at: datetime | None = None
    updated_at: datetime | None = None


# =============================================================================
# Join Health Check Schemas
# =============================================================================


class ServerHealthStatus(msgspec.Struct):
    """Health status of a single target server.

    Attributes:
        name: Human-readable name for the server.
        server_type: Type of media server (e.g., "plex", "jellyfin").
        reachable: Whether the server is reachable and responding.
    """

    name: str
    server_type: str
    reachable: bool


class JoinHealthResponse(msgspec.Struct):
    """Response from join health check endpoint.

    Attributes:
        all_reachable: Whether all target servers are reachable.
        servers: Per-server health status.
    """

    all_reachable: bool
    servers: list[ServerHealthStatus]


# =============================================================================
# Redemption Response Schemas
# =============================================================================


class RedemptionResponse(msgspec.Struct, omit_defaults=True):
    """Response from successful invitation redemption.

    Attributes:
        success: Always True for successful redemption.
        identity_id: ID of the created identity.
        users_created: List of users created on each target server.
        message: Optional success message.
    """

    success: bool
    identity_id: UUID
    users_created: list[UserResponse]
    message: str | None = None


class RedemptionErrorResponse(msgspec.Struct, kw_only=True):
    """Response from failed invitation redemption.

    Attributes:
        success: Always False for failed redemption.
        error_code: Machine-readable error code (e.g., USERNAME_TAKEN, SERVER_ERROR).
        message: Human-readable error description.
        failed_server: Name of the server that failed (if applicable).
        partial_users: List of users that were created before failure (for rollback info).
    """

    success: bool = False
    error_code: str
    message: str
    correlation_id: str | None = None
    failed_server: str | None = None
    partial_users: list[UserResponse] | None = None


# =============================================================================
# Health Check Schemas
# =============================================================================


class HealthCheckResponse(msgspec.Struct, kw_only=True):
    """Health check response.

    Attributes:
        status: Overall health status ("healthy" or "degraded").
        checks: Individual dependency check results.
    """

    status: str
    checks: dict[str, bool]


class LivenessResponse(msgspec.Struct, kw_only=True):
    """Liveness probe response.

    Attributes:
        status: Always "alive" if the process is running.
    """

    status: str


class ReadinessResponse(msgspec.Struct, kw_only=True):
    """Readiness probe response.

    Attributes:
        status: "ready" if the application can serve traffic, "not ready" otherwise.
    """

    status: str


# =============================================================================
# Settings Schemas
# =============================================================================

# Origin URL (must start with http:// or https://)
OriginUrl = Annotated[
    str, msgspec.Meta(min_length=1, max_length=2048, pattern=r"^https?://[^/?#]+$")
]


class CsrfOriginResponse(msgspec.Struct, kw_only=True):
    """CSRF origin setting response.

    Attributes:
        csrf_origin: The configured CSRF origin URL, or null if not set.
        is_locked: True if the value is set via environment variable and cannot
            be changed through the API.
        secure_cookies_auto_enabled: True when secure cookies were automatically
            enabled because the CSRF origin was set to an HTTPS URL.
    """

    csrf_origin: str | None
    is_locked: bool
    secure_cookies_auto_enabled: bool = False


class CsrfOriginUpdate(msgspec.Struct, kw_only=True, forbid_unknown_fields=True):
    """Request to update the CSRF origin setting.

    Attributes:
        csrf_origin: The origin URL to set, or null to clear.
    """

    csrf_origin: OriginUrl | None = None


class CsrfOriginTestRequest(msgspec.Struct, kw_only=True, forbid_unknown_fields=True):
    """Request to test a CSRF origin against the browser's actual Origin header.

    Attributes:
        origin: The origin URL to test.
    """

    origin: OriginUrl


class CsrfOriginTestResponse(msgspec.Struct, kw_only=True):
    """Response from CSRF origin test.

    Attributes:
        success: Whether the provided origin matches the request's Origin header.
        message: Human-readable result description.
        request_origin: The Origin header extracted from the request, if available.
    """

    success: bool
    message: str
    request_origin: str | None = None


class SecureCookiesResponse(msgspec.Struct, kw_only=True):
    """Secure cookies setting response.

    Attributes:
        secure_cookies: Whether secure cookies are enabled.
        is_locked: True if the value is set via environment variable and cannot
            be changed through the API.
    """

    secure_cookies: bool
    is_locked: bool


class SecureCookiesUpdate(msgspec.Struct, kw_only=True, forbid_unknown_fields=True):
    """Request to update the secure cookies setting.

    Attributes:
        secure_cookies: Whether to enable secure cookies.
    """

    secure_cookies: bool


# =============================================================================
# Connection Test Schemas
# =============================================================================


class ConnectionTestRequest(msgspec.Struct, kw_only=True, forbid_unknown_fields=True):
    """Request to test a media server connection.

    If server_type is omitted, the backend will auto-detect
    by probing all registered providers concurrently.

    Attributes:
        url: Base URL for the media server API. Optional if use_env_credentials is True.
        api_key: Authentication token for the media server (optional if use_env_credentials is True).
        server_type: Optional type of media server. Auto-detected if omitted.
        use_env_credentials: If True, resolve URL and api_key from environment variables on the server.
    """

    url: UrlStr | None = None
    api_key: ApiKeyStr | None = None
    server_type: NonEmptyStr | None = None
    use_env_credentials: bool = False


class ConnectionTestResponse(msgspec.Struct, kw_only=True):
    """Response from a media server connection test.

    Attributes:
        success: Whether the connection test succeeded.
        message: Human-readable result message.
        server_type: Detected or confirmed server type.
        server_name: Name of the server (if connection succeeded).
        version: Server version (if connection succeeded).
    """

    success: bool
    message: str
    server_type: str | None = None
    server_name: str | None = None
    version: str | None = None


# =============================================================================
# Authentication Schemas
# =============================================================================

# Admin username: 3-32 chars, lowercase, starts with letter
AdminUsername = Annotated[
    str, msgspec.Meta(min_length=3, max_length=32, pattern=r"^[a-z][a-z0-9_]*$")
]

# Admin password: 15+ chars for strong security
AdminPassword = Annotated[str, msgspec.Meta(min_length=15, max_length=128)]

# Onboarding flow steps for initial installation.
OnboardingStep = Literal["account", "security", "server", "complete"]


class AuthFieldInfo(msgspec.Struct, kw_only=True):
    """Auth field descriptor for frontend form rendering.

    Attributes:
        name: Field key (e.g., "server_url").
        label: Display label (e.g., "Server URL").
        field_type: HTML input type ("text", "password", "url").
        placeholder: Placeholder text for the input.
        required: Whether the field is required.
    """

    name: str
    label: str
    field_type: str
    placeholder: str = ""
    required: bool = True


class ProviderAuthInfo(msgspec.Struct, kw_only=True):
    """Auth method metadata for a provider.

    Mirrors ``AdminAuthDescriptor`` from ``media.provider`` for the HTTP layer.

    Attributes:
        method_name: Auth method identifier (e.g., "plex").
        display_name: Human-readable name (e.g., "Plex").
        flow_type: Auth flow type ("oauth" or "credentials").
        fields: Field descriptors for credential-based flows.
    """

    method_name: str
    display_name: str
    flow_type: AuthFlowType
    fields: list[AuthFieldInfo] = []


class AuthMethodsResponse(msgspec.Struct, kw_only=True):
    """Response listing available authentication methods.

    Attributes:
        methods: List of available auth method names ("local" plus any configured external providers).
        setup_required: True if no admin accounts exist yet.
        onboarding_required: True if setup/admin onboarding is not yet complete.
        onboarding_step: Current onboarding step to resume.
        provider_auth: Metadata for each external auth provider.
    """

    methods: list[str]
    setup_required: bool
    onboarding_required: bool
    onboarding_step: OnboardingStep
    provider_auth: list[ProviderAuthInfo] = []


class OnboardingStatusResponse(msgspec.Struct, kw_only=True):
    """Onboarding status response.

    Attributes:
        onboarding_required: True if onboarding is still in progress.
        onboarding_step: Current onboarding step to resume.
    """

    onboarding_required: bool
    onboarding_step: OnboardingStep


class AdminSetupRequest(msgspec.Struct, kw_only=True, forbid_unknown_fields=True):
    """Request to create the first admin account.

    Attributes:
        username: Admin username (3-32 chars, lowercase).
        password: Admin password (15+ chars).
        email: Optional email address.
        bootstrap_token: Bootstrap token required for initial admin setup.
    """

    username: AdminUsername
    password: AdminPassword
    email: EmailStr | None = None
    bootstrap_token: str


class LoginRequest(msgspec.Struct, kw_only=True, forbid_unknown_fields=True):
    """Local username/password login request.

    Attributes:
        username: Admin username.
        password: Admin password.
    """

    username: str
    password: str


class ExternalLoginRequest(msgspec.Struct, kw_only=True, forbid_unknown_fields=True):
    """External provider login request.

    Accepts arbitrary credential fields as a dict. The provider's
    AdminAuthProvider validates the required fields.

    Attributes:
        credentials: Provider-specific credential key-value pairs.
    """

    credentials: dict[str, str]


class AdminMeResponse(msgspec.Struct, kw_only=True):
    """Current admin info response.

    Attributes:
        id: Admin account UUID.
        username: Admin username.
        email: Optional email address.
        auth_method: Authentication method used.
        totp_enabled: Whether TOTP two-factor authentication is active.
        onboarding_required: True if onboarding is still in progress.
        onboarding_step: Current onboarding step to resume.
    """

    id: UUID
    username: str
    onboarding_required: bool
    onboarding_step: OnboardingStep
    totp_enabled: bool = False
    email: str | None = None
    auth_method: str = "local"


class AuthSuccessResponse(msgspec.Struct, kw_only=True):
    """Authentication success response.

    Attributes:
        success: Indicates the operation completed successfully.
    """

    success: bool = True


class LoginResponse(msgspec.Struct, kw_only=True, omit_defaults=True):
    """Login response that may require TOTP verification.

    When totp_required is True, the client must call the TOTP verify
    endpoint with the challenge_token. No access token cookie is set.

    When totp_required is False (or absent), login is complete and
    the access token cookie is set normally.

    Attributes:
        totp_required: True if TOTP verification is needed.
        challenge_token: Short-lived JWT for TOTP verification step.
    """

    totp_required: bool = False
    challenge_token: str | None = None


# TOTP 6-digit code
TOTPCode = Annotated[str, msgspec.Meta(min_length=6, max_length=6, pattern=r"^\d{6}$")]


class TOTPVerifyRequest(msgspec.Struct, kw_only=True, forbid_unknown_fields=True):
    """Request to verify a TOTP code during login.

    Attributes:
        challenge_token: The challenge JWT from the login response.
        code: The 6-digit TOTP code from the authenticator app.
    """

    challenge_token: str
    code: TOTPCode


class TOTPBackupCodeRequest(msgspec.Struct, kw_only=True, forbid_unknown_fields=True):
    """Request to verify a backup code during login.

    Attributes:
        challenge_token: The challenge JWT from the login response.
        code: The backup code in XXXX-XXXX format.
    """

    challenge_token: str
    code: Annotated[str, msgspec.Meta(min_length=1, max_length=20)]


class TOTPSetupResponse(msgspec.Struct, kw_only=True):
    """Response from TOTP setup initiation.

    Attributes:
        provisioning_uri: OTPAuth URI for authenticator apps.
        qr_code_svg: QR code as inline SVG.
        backup_codes: List of plaintext backup codes.
    """

    provisioning_uri: str
    qr_code_svg: str
    backup_codes: list[str]


class TOTPConfirmSetupRequest(msgspec.Struct, kw_only=True, forbid_unknown_fields=True):
    """Request to confirm TOTP setup with a code from the authenticator app.

    Attributes:
        code: The 6-digit TOTP code from the authenticator app.
    """

    code: TOTPCode


class TOTPConfirmSetupResponse(msgspec.Struct, kw_only=True):
    """Response after successful TOTP setup confirmation.

    Attributes:
        backup_codes: List of plaintext backup codes to save.
    """

    backup_codes: list[str]


class TOTPDisableRequest(msgspec.Struct, kw_only=True, forbid_unknown_fields=True):
    """Request to disable TOTP two-factor authentication.

    Attributes:
        password: Current password for verification.
        code: A valid 6-digit TOTP code to authorize disabling.
    """

    password: Annotated[str, msgspec.Meta(min_length=1)]
    code: TOTPCode


class TOTPRegenerateBackupCodesRequest(
    msgspec.Struct, kw_only=True, forbid_unknown_fields=True
):
    """Request to regenerate backup codes.

    Attributes:
        code: A valid 6-digit TOTP code to authorize regeneration.
    """

    code: TOTPCode


class TOTPBackupCodesResponse(msgspec.Struct, kw_only=True):
    """Response containing backup codes.

    Attributes:
        backup_codes: List of plaintext backup codes.
    """

    backup_codes: list[str]


class LinkProviderRequest(msgspec.Struct, kw_only=True, forbid_unknown_fields=True):
    """Request to link an external auth provider to the current admin.

    Attributes:
        method: The auth method name (e.g., "plex", "jellyfin").
        credentials: Provider-specific credential key-value pairs.
    """

    method: NonEmptyStr
    credentials: dict[str, str]


class LinkProviderResponse(msgspec.Struct, kw_only=True):
    """Response after linking an external auth provider.

    Attributes:
        method: The linked auth method.
        external_id: The external service identifier.
    """

    method: str
    external_id: str


class AdminProfileResponse(msgspec.Struct, kw_only=True):
    """Admin profile response for settings page.

    Attributes:
        id: Admin account UUID.
        username: Admin username.
        email: Optional email address.
        auth_method: Authentication method used.
    """

    id: UUID
    username: str
    email: str | None = None
    auth_method: str = "local"


class AdminEmailUpdate(msgspec.Struct, kw_only=True, forbid_unknown_fields=True):
    """Request to update admin email.

    Attributes:
        email: New email address, or None to clear.
    """

    email: EmailStr | None = None


class AdminPasswordChange(msgspec.Struct, kw_only=True, forbid_unknown_fields=True):
    """Request to change admin password.

    Attributes:
        current_password: Current password for verification.
        new_password: New password (15+ chars).
    """

    current_password: Annotated[str, msgspec.Meta(min_length=1)]
    new_password: AdminPassword


class PasswordChangeResponse(msgspec.Struct, kw_only=True):
    """Response after password change.

    Attributes:
        success: Whether the password was changed.
        message: Human-readable result message.
    """

    success: bool
    message: str


# =============================================================================
# Settings Schemas
# =============================================================================


class SettingValue(msgspec.Struct, kw_only=True):
    """A single setting value with lock status.

    Attributes:
        value: Current setting value.
        is_locked: True if set via environment variable.
    """

    value: str | None
    is_locked: bool


class AllSettingsResponse(msgspec.Struct, kw_only=True):
    """Bundle of all application settings.

    Attributes:
        csrf_origin: CSRF origin setting.
        secure_cookies: Secure cookies setting.
        sync_interval_seconds: Sync interval setting.
        expiration_check_interval_seconds: Expiration check interval setting.
    """

    csrf_origin: SettingValue
    secure_cookies: SettingValue
    sync_interval_seconds: SettingValue
    expiration_check_interval_seconds: SettingValue


class SyncIntervalUpdate(msgspec.Struct, kw_only=True, forbid_unknown_fields=True):
    """Request to update the sync interval.

    Attributes:
        sync_interval_seconds: New interval in seconds (60-86400).
    """

    sync_interval_seconds: Annotated[int, msgspec.Meta(ge=60, le=86400)]


class ExpirationIntervalUpdate(
    msgspec.Struct, kw_only=True, forbid_unknown_fields=True
):
    """Request to update the expiration check interval.

    Attributes:
        expiration_check_interval_seconds: New interval in seconds (60-86400).
    """

    expiration_check_interval_seconds: Annotated[int, msgspec.Meta(ge=60, le=86400)]


class AboutResponse(msgspec.Struct, kw_only=True):
    """System information response.

    Attributes:
        app_version: Application version string.
        python_version: Python runtime version.
        db_engine: Database engine type.
        os_info: Operating system information.
    """

    app_version: str
    python_version: str
    db_engine: str
    os_info: str


# =============================================================================
# Sync Schemas
# =============================================================================


class SyncRequest(msgspec.Struct, kw_only=True, forbid_unknown_fields=True):
    """Request to sync a server (optional parameters).

    Attributes:
        dry_run: If True, only report discrepancies without making changes.
            Defaults to True for safety.
    """

    dry_run: bool = True


class SyncResult(msgspec.Struct, kw_only=True):
    """Result of a server sync operation.

    Reports discrepancies between local user records and the actual
    state of users on the media server.

    Attributes:
        server_id: ID of the media server that was synced.
        server_name: Name of the media server.
        synced_at: Timestamp when the sync was performed.
        orphaned_users: Usernames that exist on the server but not locally.
        stale_users: Usernames that exist locally but not on the server.
        matched_users: Count of users that match between local and server.
        imported_users: Count of orphaned users imported into local DB.
    """

    server_id: UUID
    server_name: str
    synced_at: datetime
    orphaned_users: list[str]
    stale_users: list[str]
    matched_users: int
    imported_users: int = 0


class LibrarySyncResult(msgspec.Struct, kw_only=True):
    """Result of a manual library synchronization operation."""

    server_id: UUID
    server_name: str
    synced_at: datetime
    total_libraries: int
    added_count: int
    updated_count: int
    removed_count: int


# =============================================================================
# Provider Metadata Schemas
# =============================================================================


class ProviderMetadataResponse(msgspec.Struct, kw_only=True, omit_defaults=True):
    """Provider metadata for frontend rendering.

    Attributes:
        server_type: Provider identifier string.
        display_name: Human-readable name.
        color: Brand hex color.
        icon_svg: SVG path data for the provider icon.
        api_key_help_text: Help text for the "add server" form.
        capabilities: List of supported capability strings.
        supported_permissions: List of supported permission keys.
        join_flow_type: Join flow type ("oauth_link" or "credential_create").
    """

    server_type: str
    display_name: str
    color: str
    icon_svg: str
    api_key_help_text: str = ""
    capabilities: list[str] = []
    supported_permissions: list[str] = []
    join_flow_type: str | None = None


# =============================================================================
# OAuth Schemas
# =============================================================================


class OAuthPinResponse(msgspec.Struct, omit_defaults=True, kw_only=True):
    """Response from OAuth PIN creation.

    Attributes:
        handle: Opaque session handle for status checking (replaces pin_id).
        code: The PIN code to display to the user.
        auth_url: URL where user authenticates.
        expires_at: When the PIN expires.
    """

    handle: str
    code: str
    auth_url: str
    expires_at: datetime


class OAuthCheckResponse(msgspec.Struct, omit_defaults=True, kw_only=True):
    """Response from OAuth PIN status check.

    The raw provider auth_token is never exposed. On successful authentication,
    a one-time ``redemption_token`` is returned instead, which the frontend
    passes to the redemption endpoint to prove OAuth completion.

    Attributes:
        authenticated: Whether the PIN has been authenticated.
        redemption_token: One-time token for redeeming the auth credential (only if authenticated).
        email: User's email (only if authenticated).
        error: Error message (only if failed).
    """

    authenticated: bool
    redemption_token: str | None = None
    email: str | None = None
    error: str | None = None


# =============================================================================
# Dashboard Schemas
# =============================================================================


class RecentActivityItem(msgspec.Struct, kw_only=True):
    """A single recent activity event for the dashboard.

    Attributes:
        type: Event type identifier (e.g., "user_created", "invitation_created").
        description: Human-readable description of the event.
        timestamp: When the event occurred.
    """

    type: str
    description: str
    timestamp: datetime


class DashboardStatsResponse(msgspec.Struct, kw_only=True):
    """Aggregated dashboard statistics.

    Attributes:
        total_invitations: Total number of invitations.
        active_invitations: Invitations that are enabled, not expired, and have uses remaining.
        total_users: Total number of media server user accounts.
        active_users: Users that are enabled and not expired.
        total_servers: Total number of configured media servers.
        enabled_servers: Media servers that are currently enabled.
        pending_invitations: Active invitations with zero redemptions so far.
        recent_activity: Last 10 activity events across all entity types.
    """

    total_invitations: int
    active_invitations: int
    total_users: int
    active_users: int
    total_servers: int
    enabled_servers: int
    pending_invitations: int
    recent_activity: list[RecentActivityItem]
