"""
Nashat Clone Configuration Schema
=================================

Pydantic models that define the structure of nashat_*.yaml files.
This is the source of truth for what's valid in agent configs.

Loaded by: shared/config_loader.py
"""
from __future__ import annotations
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


# ============================================================================
# ENUMS
# ============================================================================

class Visibility(str, Enum):
    private = "private"
    public = "public"


class ResponseLength(str, Enum):
    intelligent = "intelligent"
    concise = "concise"
    explanatory = "explanatory"
    custom = "custom"


class Creativity(str, Enum):
    strict = "strict"
    adaptive = "adaptive"
    creative = "creative"


class ModelProvider(str, Enum):
    anthropic = "anthropic"
    openai = "openai"
    google = "google"


# ============================================================================
# PERSONA
# ============================================================================

class SocialLink(BaseModel):
    model_config = ConfigDict(extra="forbid")
    platform: str = Field(..., max_length=50)
    url: str = Field(..., max_length=500)


class Persona(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(..., max_length=100)
    handle: str = Field(..., max_length=50)
    organization: Optional[str] = Field(None, max_length=100)
    role: Optional[str] = Field(None, max_length=100)
    headline: Optional[str] = Field(None, max_length=200)
    bio: Optional[str] = Field(None, max_length=2000)
    avatar_url: Optional[str] = Field(None, max_length=500)
    social_links: list[SocialLink] = Field(default_factory=list, max_length=10)
    pinned_questions: list[str] = Field(default_factory=list, max_length=5)
    disclaimer_text: Optional[str] = Field(None, max_length=400)
    disclaimer_enabled: bool = True
    visibility: Visibility = Visibility.private
    initial_message: str = Field("Hi, how can I help?", max_length=400)


# ============================================================================
# BEHAVIOR
# ============================================================================

class Mode(BaseModel):
    model_config = ConfigDict(extra="forbid")
    label: str = Field(..., max_length=100)
    description: Optional[str] = Field(None, max_length=300)
    collections: list[str] = Field(default_factory=list)
    coaching_n: int = Field(0, ge=0, le=20)
    reference_n: int = Field(0, ge=0, le=20)
    published_n: int = Field(0, ge=0, le=20)
    prompt_overlay: Optional[str] = Field(None, max_length=3000)


class Behavior(BaseModel):
    model_config = ConfigDict(extra="forbid")
    purpose: str = Field(..., max_length=6000)
    speaking_style: str = Field(..., max_length=5000)
    custom_instructions: list[str] = Field(default_factory=list, max_length=20)
    response_length: ResponseLength = ResponseLength.intelligent
    response_length_custom_value: Optional[int] = Field(None, ge=1)
    creativity: Creativity = Creativity.adaptive
    no_answer_message: str = Field(..., max_length=400)
    show_citations: bool = True
    model_provider: ModelProvider = ModelProvider.anthropic
    model_name: str = Field("claude-sonnet-4-6", max_length=100)
    temperature: float = Field(0.4, ge=0.0, le=2.0)
    max_tokens: int = Field(1500, ge=100, le=8192)
    default_mode: str = Field(..., max_length=100)
    modes: dict[str, Mode] = Field(default_factory=dict)


# ============================================================================
# GUARDRAILS
# ============================================================================

class Guardrails(BaseModel):
    model_config = ConfigDict(extra="forbid")
    never_do: list[str] = Field(default_factory=list)
    always_do: list[str] = Field(default_factory=list)
    character_rules: list[str] = Field(default_factory=list)
    domain_knowledge_rules: list[str] = Field(default_factory=list)
    escalation_rules: list[str] = Field(default_factory=list)
    sales_directives: list[str] = Field(default_factory=list)


# ============================================================================
# KNOWLEDGE & RETRIEVAL
# ============================================================================

class RetrievalConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    embedding_model: str = Field("text-embedding-3-large", max_length=100)
    top_k: int = Field(8, ge=1, le=50)
    similarity_threshold: float = Field(0.65, ge=0.0, le=1.0)
    reranker_enabled: bool = False
    reranker_model: Optional[str] = Field(None, max_length=100)


class Knowledge(BaseModel):
    model_config = ConfigDict(extra="forbid")
    knowledge_collections: list[str] = Field(default_factory=list)
    staff_exclusions: list[str] = Field(default_factory=list)
    retrieval_config: RetrievalConfig = Field(default_factory=RetrievalConfig)


# ============================================================================
# AUDIENCE (forward-looking — not enforced yet)
# ============================================================================

class AudienceTier(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message_limit: Optional[int] = Field(None, ge=0)
    voice_minute_limit: Optional[int] = Field(None, ge=0)
    resets_monthly: bool = True


class Audience(BaseModel):
    model_config = ConfigDict(extra="forbid")
    just_me: AudienceTier = Field(default_factory=AudienceTier)
    insiders: AudienceTier = Field(default_factory=AudienceTier)
    public: AudienceTier = Field(default_factory=AudienceTier)
    anonymous: AudienceTier = Field(default_factory=AudienceTier)


# ============================================================================
# ROOT
# ============================================================================

class AgentConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: str = Field("1.0", max_length=20)
    agent_id: str = Field(..., max_length=100)
    persona: Persona
    behavior: Behavior
    guardrails: Guardrails = Field(default_factory=Guardrails)
    knowledge: Knowledge = Field(default_factory=Knowledge)
    audience: Audience = Field(default_factory=Audience)


def validate_default_mode_exists(config: AgentConfig) -> None:
    if config.behavior.default_mode not in config.behavior.modes:
        raise ValueError(
            f"default_mode '{config.behavior.default_mode}' "
            f"not found in modes: {list(config.behavior.modes.keys())}"
        )
