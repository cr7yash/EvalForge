"""
Catalog of models reachable through the Portkey AI gateway.

Portkey exposes models as ``@<route>/<remote_id>`` (e.g.
``@zotgpt-api-azure/gpt-5.5``). This module maps those onto short, stable
slugs grouped by vendor family, and records which generation parameters each
model actually accepts.

The parameter capabilities below are not guesses — they were measured by
calling every model on the gateway. They matter: the OpenAI-compatible
surface is *not* uniform across routes, and sending an unsupported parameter
is a hard 400, not a silently ignored field. Notably:

* Reasoning models reject ``max_tokens`` outright and require
  ``max_completion_tokens``. ``max_completion_tokens`` is accepted by every
  model on every route, so it is what we always send.
* ``temperature`` / ``top_p`` / ``stop`` support varies model by model, and
  not along route lines — ``claude-opus-5`` rejects temperature while
  ``claude-sonnet-4-6`` on the same route accepts it.
* Reasoning models spend the output budget on hidden thinking before emitting
  any text, so a budget that is fine for a normal model can yield an empty
  string. ``min_output_tokens`` guards against that.
"""

from dataclasses import dataclass
from typing import Dict, List


@dataclass(frozen=True)
class ParamCaps:
    """Which generation parameters a model accepts."""
    temperature: bool = True
    top_p: bool = True
    stop: bool = True
    reasoning_effort: bool = False
    min_output_tokens: int = 0


# Ordinary chat models: everything works, no hidden reasoning budget.
FULL = ParamCaps()

# Accepts all sampling params but thinks before answering, so it needs headroom.
FULL_THINKING = ParamCaps(min_output_tokens=4000)

# Sampling is fine, but the backend rejects stop sequences.
NO_STOP = ParamCaps(stop=False)

# Reasoning models that still honour temperature/top_p (gpt-5.1 .. gpt-5.4).
REASONING_SAMPLED = ParamCaps(
    stop=False, reasoning_effort=True, min_output_tokens=4000
)

# Reasoning models that reject every sampling knob (gpt-5, gpt-5.5, o-series).
REASONING_STRICT = ParamCaps(
    temperature=False, top_p=False, stop=False,
    reasoning_effort=True, min_output_tokens=4000,
)

# Newer Claude models: no temperature/top_p, but stop sequences still work.
# They reject reasoning_effort ("thinking.type.enabled is not supported").
NO_SAMPLING = ParamCaps(
    temperature=False, top_p=False, stop=True, min_output_tokens=4000
)


@dataclass(frozen=True)
class ModelSpec:
    """A single model as exposed through the gateway."""
    slug: str                       # UI + database value, e.g. "claude-opus-5"
    route: str                      # gateway route, e.g. "@zotgpt-api-bedrock"
    remote_id: str                  # id within the route
    family: str                     # vendor family key
    caps: ParamCaps = FULL
    pricing: Dict[str, float] | None = None   # USD per 1K tokens; None = unknown

    @property
    def model_id(self) -> str:
        """Fully qualified model identifier sent to the gateway."""
        return f"{self.route}/{self.remote_id}"


FAMILY_LABELS: Dict[str, str] = {
    "openai": "OpenAI",
    "anthropic": "Anthropic",
    "google": "Google",
    "mistral": "Mistral",
    "other": "Other",
}

AZURE = "@zotgpt-api-azure"
BEDROCK = "@zotgpt-api-bedrock"
MANTLE = "@zotgpt-api-bedrock-mantle"
GEMINI = "@zotgpt-api-gemini"
VERTEX = "@zotgpt-api-vertex"

# Pricing is deliberately partial. Where a model's public list price is not
# known with confidence it is left as None, and the cost evaluator reports it
# as unpriced rather than quoting a misleading $0.00.
CATALOG: List[ModelSpec] = [
    # ---- OpenAI (Azure route) --------------------------------------------
    ModelSpec("gpt-4o", AZURE, "gpt-4o", "openai", FULL,
              {"input": 0.0025, "output": 0.01}),
    ModelSpec("gpt-4o-mini", AZURE, "gpt-4o-mini", "openai", FULL,
              {"input": 0.00015, "output": 0.0006}),
    ModelSpec("gpt-4.1", AZURE, "gpt-4.1", "openai", FULL,
              {"input": 0.002, "output": 0.008}),
    ModelSpec("gpt-4.1-mini", AZURE, "gpt-4.1-mini", "openai", FULL,
              {"input": 0.0004, "output": 0.0016}),
    ModelSpec("gpt-4.1-nano", AZURE, "gpt-4.1-nano", "openai", FULL,
              {"input": 0.0001, "output": 0.0004}),
    ModelSpec("gpt-5", AZURE, "gpt-5", "openai", REASONING_STRICT,
              {"input": 0.00125, "output": 0.01}),
    ModelSpec("gpt-5-mini", AZURE, "gpt-5-mini", "openai", REASONING_STRICT,
              {"input": 0.00025, "output": 0.002}),
    ModelSpec("gpt-5-nano", AZURE, "gpt-5-nano", "openai", REASONING_STRICT,
              {"input": 0.00005, "output": 0.0004}),
    ModelSpec("gpt-5.1", AZURE, "gpt-5.1", "openai", REASONING_SAMPLED,
              {"input": 0.00125, "output": 0.01}),
    ModelSpec("gpt-5.2", AZURE, "gpt-5.2", "openai", REASONING_SAMPLED),
    ModelSpec("gpt-5.4", AZURE, "gpt-5.4", "openai", REASONING_SAMPLED),
    ModelSpec("gpt-5.4-mini", AZURE, "gpt-5.4-mini", "openai", REASONING_SAMPLED),
    ModelSpec("gpt-5.4-nano", AZURE, "gpt-5.4-nano", "openai", REASONING_SAMPLED),
    ModelSpec("gpt-5.5", AZURE, "gpt-5.5", "openai", REASONING_STRICT),
    ModelSpec("gpt-5.6-luna", AZURE, "gpt-5.6-luna", "openai", REASONING_STRICT),
    ModelSpec("gpt-5.6-sol", AZURE, "gpt-5.6-sol", "openai", REASONING_STRICT),
    ModelSpec("gpt-5.6-terra", AZURE, "gpt-5.6-terra", "openai", REASONING_STRICT),
    ModelSpec("o3-full", AZURE, "o3-full", "openai", REASONING_STRICT,
              {"input": 0.002, "output": 0.008}),
    ModelSpec("o4-mini", AZURE, "o4-mini", "openai", REASONING_STRICT,
              {"input": 0.0011, "output": 0.0044}),

    # ---- Anthropic (Bedrock route) ---------------------------------------
    # claude-3-5-sonnet / claude-3-5-haiku are advertised by the gateway but
    # are end-of-life on Bedrock and return 404, so they are omitted.
    ModelSpec("claude-haiku-4-5", BEDROCK,
              "us.anthropic.claude-haiku-4-5-20251001-v1:0", "anthropic", FULL,
              {"input": 0.001, "output": 0.005}),
    ModelSpec("claude-sonnet-4", BEDROCK,
              "us.anthropic.claude-sonnet-4-20250514-v1:0", "anthropic", FULL,
              {"input": 0.003, "output": 0.015}),
    ModelSpec("claude-sonnet-4-5", BEDROCK,
              "us.anthropic.claude-sonnet-4-5-20250929-v1:0", "anthropic", FULL,
              {"input": 0.003, "output": 0.015}),
    ModelSpec("claude-sonnet-4-6", BEDROCK,
              "us.anthropic.claude-sonnet-4-6", "anthropic", FULL),
    ModelSpec("claude-opus-4-5", BEDROCK,
              "us.anthropic.claude-opus-4-5-20251101-v1:0", "anthropic", FULL,
              {"input": 0.005, "output": 0.025}),
    ModelSpec("claude-opus-4-6", BEDROCK,
              "us.anthropic.claude-opus-4-6-v1", "anthropic", FULL),
    ModelSpec("claude-opus-4-7", BEDROCK,
              "us.anthropic.claude-opus-4-7", "anthropic", NO_SAMPLING),
    ModelSpec("claude-opus-4-8", BEDROCK,
              "us.anthropic.claude-opus-4-8", "anthropic", NO_SAMPLING),
    ModelSpec("claude-sonnet-5", BEDROCK,
              "us.anthropic.claude-sonnet-5", "anthropic", NO_SAMPLING),
    ModelSpec("claude-opus-5", BEDROCK,
              "us.anthropic.claude-opus-5", "anthropic", NO_SAMPLING),

    # ---- Google ----------------------------------------------------------
    ModelSpec("gemini-2.5-pro", VERTEX, "gemini-2.5-pro", "google", FULL,
              {"input": 0.00125, "output": 0.01}),
    ModelSpec("gemini-2.5-flash", VERTEX, "gemini-2.5-flash", "google", FULL,
              {"input": 0.0003, "output": 0.0025}),
    ModelSpec("gemini-2.5-flash-lite", VERTEX, "gemini-2.5-flash-lite", "google",
              FULL, {"input": 0.0001, "output": 0.0004}),
    ModelSpec("gemini-3.1-flash-lite", GEMINI, "gemini-3.1-flash-lite", "google",
              FULL_THINKING),
    ModelSpec("gemini-3.5-flash", GEMINI, "gemini-3.5-flash", "google",
              FULL_THINKING),
    ModelSpec("gemini-3.5-flash-lite", GEMINI, "gemini-3.5-flash-lite", "google",
              FULL_THINKING),
    ModelSpec("gemini-3.6-flash", GEMINI, "gemini-3.6-flash", "google",
              FULL_THINKING),
    ModelSpec("gemini-3.7-flash", GEMINI, "gemini-3.7-flash", "google",
              FULL_THINKING),
    ModelSpec("gemma-4-31b", MANTLE, "google.gemma-4-31b", "google", FULL),
    ModelSpec("gemma-4-26b-a4b", MANTLE, "google.gemma-4-26b-a4b", "google", FULL),
    ModelSpec("gemma-4-e2b", MANTLE, "google.gemma-4-e2b", "google", FULL),

    # ---- Mistral ---------------------------------------------------------
    ModelSpec("mistral-large-2407", BEDROCK, "mistral.mistral-large-2407-v1:0",
              "mistral", FULL, {"input": 0.002, "output": 0.006}),
    ModelSpec("mistral-large-3", BEDROCK, "mistral.mistral-large-3-675b-instruct",
              "mistral", NO_STOP),
    ModelSpec("mixtral-8x7b", BEDROCK, "mistral.mixtral-8x7b-instruct-v0:1",
              "mistral", FULL, {"input": 0.00045, "output": 0.0007}),

    # ---- Other -----------------------------------------------------------
    ModelSpec("deepseek-r1", BEDROCK, "us.deepseek.r1-v1:0", "other",
              FULL_THINKING, {"input": 0.00135, "output": 0.0054}),
    ModelSpec("kimi-k2.5", BEDROCK, "moonshotai.kimi-k2.5", "other", NO_STOP),
    # Same model, different route — needs a distinct slug to stay addressable.
    ModelSpec("kimi-k2.5-mantle", MANTLE, "moonshotai.kimi-k2.5", "other", FULL),
]


_BY_FAMILY: Dict[str, List[ModelSpec]] = {}
for _spec in CATALOG:
    _BY_FAMILY.setdefault(_spec.family, []).append(_spec)


def families() -> List[str]:
    """Family keys that actually have models, in FAMILY_LABELS order."""
    return [f for f in FAMILY_LABELS if f in _BY_FAMILY]


def models_for_family(family: str) -> List[ModelSpec]:
    """All models belonging to a vendor family."""
    return list(_BY_FAMILY.get(family, []))


def find(family: str, slug: str) -> ModelSpec | None:
    """Look up a model by family and slug."""
    for spec in _BY_FAMILY.get(family, []):
        if spec.slug == slug:
            return spec
    return None
