"""Wizard, WizardStep, StepInteraction, and WizardStepTranslation models.

Provides:
- InteractionType: StrEnum for supported wizard step interaction types
- Wizard: Model representing a configurable wizard flow
- WizardStep: Model representing a single step within a wizard
- StepInteraction: Model representing an interaction attached to a step
- WizardStepTranslation: Model for multilingual wizard step content

Uses SQLAlchemy 2.0 patterns with mapped_column and Mapped types.
Relationships use cascade delete for steps when wizard is deleted,
and for interactions when step is deleted.
"""

from enum import StrEnum
from uuid import UUID

from sqlalchemy import (
    JSON,
    Boolean,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from zondarr.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class InteractionType(StrEnum):
    """Supported wizard step interaction types.

    Each type defines a different user interaction pattern:
    - CLICK: Simple button confirmation
    - TIMER: Timed delay before proceeding
    - TOS: Terms of service acceptance with checkbox
    - TEXT_INPUT: Free-form text input collection
    - QUIZ: Multiple choice question with correct answer
    """

    CLICK = "click"
    TIMER = "timer"
    TOS = "tos"
    TEXT_INPUT = "text_input"
    QUIZ = "quiz"


class Wizard(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A configurable wizard flow for invitation redemption.

    Represents a sequence of steps that users must complete during
    invitation redemption. Wizards can be associated with invitations
    to run before and/or after account creation.

    Attributes:
        id: UUID primary key
        name: Human-readable name for the wizard
        description: Optional detailed description
        enabled: Whether the wizard is currently active
        created_at: Timestamp when the wizard was created
        updated_at: Timestamp of last modification
        steps: List of wizard steps in order
    """

    __tablename__: str = "wizards"

    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text, default=None)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationships - cascade delete for steps when wizard is deleted
    steps: Mapped[list[WizardStep]] = relationship(
        back_populates="wizard",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="WizardStep.step_order",
    )


class WizardStep(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A single step within a wizard.

    Represents one step in a wizard flow. Steps are content containers
    with zero or more interactions attached. Steps are ordered within
    their parent wizard and must have unique step_order values per wizard.

    Attributes:
        id: UUID primary key
        wizard_id: Foreign key to the parent wizard
        step_order: Position in the wizard sequence (0-indexed)
        title: Display title for the step
        content_markdown: Markdown content to display
        created_at: Timestamp when the step was created
        updated_at: Timestamp of last modification
        wizard: Reference to the parent wizard
        interactions: List of interactions attached to this step
    """

    __tablename__: str = "wizard_steps"

    wizard_id: Mapped[UUID] = mapped_column(
        ForeignKey("wizards.id", ondelete="CASCADE"),
    )
    step_order: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(255))
    content_markdown: Mapped[str] = mapped_column(Text)
    primary_language: Mapped[str] = mapped_column(String(10), default="en")

    # Relationships - use joined for single relations
    wizard: Mapped[Wizard] = relationship(
        back_populates="steps",
        lazy="joined",
    )

    # Interactions - cascade delete, ordered by display_order
    interactions: Mapped[list[StepInteraction]] = relationship(
        back_populates="step",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="StepInteraction.display_order",
    )

    # Translations - cascade delete
    translations: Mapped[list[WizardStepTranslation]] = relationship(
        back_populates="step",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    # Table constraints - unique step_order per wizard
    __table_args__: tuple[UniqueConstraint, ...] = (
        UniqueConstraint("wizard_id", "step_order", name="uq_wizard_step_order"),
    )


class StepInteraction(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """An interaction attached to a wizard step.

    Represents a composable interaction type that users must complete.
    Steps can have zero interactions (informational) or multiple
    interactions (AND logic: user completes all).

    Attributes:
        id: UUID primary key
        step_id: Foreign key to the parent step
        interaction_type: Type of interaction (click, timer, tos, etc.)
        config: JSON configuration specific to the interaction type
        display_order: Position for rendering multiple interactions
        created_at: Timestamp when the interaction was created
        updated_at: Timestamp of last modification
        step: Reference to the parent step
    """

    __tablename__: str = "step_interactions"

    step_id: Mapped[UUID] = mapped_column(
        ForeignKey("wizard_steps.id", ondelete="CASCADE"),
    )
    interaction_type: Mapped[InteractionType] = mapped_column(String(20))
    config: Mapped[dict[str, str | int | bool | list[str] | None]] = mapped_column(
        JSON, default=dict
    )
    display_order: Mapped[int] = mapped_column(Integer, default=0)

    # Relationships
    step: Mapped[WizardStep] = relationship(
        back_populates="interactions",
        lazy="joined",
    )

    # Table constraints - unique interaction type per step
    __table_args__: tuple[UniqueConstraint, ...] = (
        UniqueConstraint(
            "step_id", "interaction_type", name="uq_step_interaction_type"
        ),
    )


class WizardStepTranslation(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A translation of a wizard step's content into a specific language.

    Stores translated title and content_markdown for a wizard step,
    keyed by ISO 639-1 language code. Each step can have at most one
    translation per language.

    Attributes:
        id: UUID primary key
        step_id: Foreign key to the parent wizard step
        language_code: ISO 639-1 language code (e.g. "en", "da", "de")
        title: Translated step title
        content_markdown: Translated markdown content
        created_at: Timestamp when the translation was created
        updated_at: Timestamp of last modification
        step: Reference to the parent wizard step
    """

    __tablename__: str = "wizard_step_translations"

    step_id: Mapped[UUID] = mapped_column(
        ForeignKey("wizard_steps.id", ondelete="CASCADE"),
    )
    language_code: Mapped[str] = mapped_column(String(10))
    title: Mapped[str] = mapped_column(String(255))
    content_markdown: Mapped[str] = mapped_column(Text)

    # Relationships
    step: Mapped[WizardStep] = relationship(
        back_populates="translations",
        lazy="joined",
    )

    # Table constraints - unique language per step
    __table_args__: tuple[UniqueConstraint, ...] = (
        UniqueConstraint(
            "step_id", "language_code", name="uq_step_translation_language"
        ),
    )
