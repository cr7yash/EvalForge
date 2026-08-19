import asyncio
import uuid
from typing import List, Dict, Any
from datetime import datetime

from ..providers.base import LLMProvider, GenerationConfig, GenerationResult
from ..providers.openai_provider import OpenAIProvider
from ..providers.anthropic_provider import AnthropicProvider
from ..providers.portkey_provider import PortkeyProvider
from ..providers.portkey_catalog import FAMILY_LABELS, families, models_for_family
from ..evaluators.base import EvalExample, BaseEvaluator
from ..evaluators.accuracy import AccuracyEvaluator
from ..evaluators.performance import PerformanceEvaluator
from ..evaluators.cost import CostEvaluator
from ..models.evaluation import Evaluation, EvaluationStatus
from ..core.config import get_settings


class EvaluationService:
    """Service for running LLM evaluations."""

    def __init__(self):
        self.settings = get_settings()
        self._providers: Dict[str, LLMProvider] = {}
        self._evaluators: Dict[str, BaseEvaluator] = {}

    def _get_provider(self, provider_name: str) -> LLMProvider:
        """Get or create provider instance."""
        if provider_name not in self._providers:
            # Portkey vendor families are the primary path. The "-direct" ids
            # bypass the gateway and need their own vendor API key.
            if provider_name in FAMILY_LABELS and self.settings.portkey_api_key:
                self._providers[provider_name] = PortkeyProvider(
                    family=provider_name,
                    api_key=self.settings.portkey_api_key,
                    base_url=self.settings.portkey_base_url,
                )
            elif provider_name == "openai-direct":
                self._providers[provider_name] = OpenAIProvider(
                    api_key=self.settings.openai_api_key
                )
            elif provider_name == "anthropic-direct":
                self._providers[provider_name] = AnthropicProvider(
                    api_key=self.settings.anthropic_api_key
                )
            elif provider_name in FAMILY_LABELS:
                raise ValueError(
                    f"Provider '{provider_name}' requires PORTKEY_API_KEY to be set"
                )
            else:
                raise ValueError(f"Unknown provider: {provider_name}")
        return self._providers[provider_name]

    def _get_evaluator(self, evaluator_name: str, provider: LLMProvider, model: str) -> BaseEvaluator:
        """Get or create evaluator instance."""
        key = f"{evaluator_name}_{provider.name}_{model}"
        if key not in self._evaluators:
            if evaluator_name == "accuracy":
                self._evaluators[key] = AccuracyEvaluator()
            elif evaluator_name == "performance":
                self._evaluators[key] = PerformanceEvaluator()
            elif evaluator_name == "cost":
                self._evaluators[key] = CostEvaluator(provider, model)
            else:
                raise ValueError(f"Unknown evaluator: {evaluator_name}")
        return self._evaluators[key]

    async def _generate_all(
        self,
        provider: LLMProvider,
        model: str,
        config: GenerationConfig,
        eval_examples: List[EvalExample],
        evaluation: Evaluation,
    ) -> List[GenerationResult]:
        """
        Generate a response for every example concurrently.

        Requests are bounded by a semaphore so a large dataset does not open
        hundreds of simultaneous connections and trip provider rate limits.
        ``asyncio.gather`` preserves input order, so results stay aligned with
        their examples regardless of completion order.
        """
        semaphore = asyncio.Semaphore(self.settings.max_concurrent_requests)
        total = len(eval_examples)
        completed = 0

        async def generate_one(example: EvalExample) -> GenerationResult:
            nonlocal completed
            async with semaphore:
                result = await provider.generate(
                    prompt=example.prompt,
                    model=model,
                    config=config
                )
            completed += 1
            evaluation.progress = completed / total * 0.7  # 70% for generation
            return result

        return await asyncio.gather(
            *(generate_one(example) for example in eval_examples)
        )

    @staticmethod
    def _collect_warnings(
        eval_examples: List[EvalExample],
        generation_results: List[GenerationResult],
    ) -> List[str]:
        """
        Flag generations that cannot be scored meaningfully.

        An empty or truncated response scores as a zero on accuracy, which is
        indistinguishable from a genuinely wrong answer. Recording why keeps a
        token-budget problem from being read as poor model quality.
        """
        warnings: List[str] = []
        for example, result in zip(eval_examples, generation_results):
            if result.is_empty:
                detail = (
                    f" — all {result.reasoning_tokens} output tokens went to "
                    f"reasoning; raise max_tokens"
                    if result.reasoning_tokens
                    else ""
                )
                warnings.append(
                    f"Example {example.id}: model returned no text{detail}"
                )
            elif result.truncated:
                warnings.append(
                    f"Example {example.id}: response was cut off at the "
                    f"token limit ({result.output_tokens} tokens)"
                )
        return warnings

    async def run_evaluation(
        self,
        name: str,
        provider_name: str,
        model: str,
        examples: List[Dict[str, Any]],
        evaluator_names: List[str],
        config_dict: Dict[str, Any] | None = None
    ) -> Evaluation:
        """
        Run a complete evaluation.

        Args:
            name: Evaluation name
            provider_name: Provider identifier
            model: Model identifier
            examples: List of example dicts
            evaluator_names: List of evaluator names to run
            config_dict: Generation config dict

        Returns:
            Evaluation model with results
        """
        # Create evaluation record
        eval_id = str(uuid.uuid4())
        evaluation = Evaluation(
            id=eval_id,
            name=name,
            provider=provider_name,
            model=model,
            evaluators=evaluator_names,
            examples=examples,
            config=config_dict or {},
            status=EvaluationStatus.RUNNING,
            progress=0.0
        )

        try:
            # Parse examples
            eval_examples = [
                EvalExample(
                    id=ex.get("id", str(i)),
                    prompt=ex["prompt"],
                    expected_output=ex.get("expected_output"),
                    context=ex.get("context"),
                    metadata=ex.get("metadata", {})
                )
                for i, ex in enumerate(examples)
            ]

            # Get provider and config
            provider = self._get_provider(provider_name)
            config = GenerationConfig(**config_dict) if config_dict else GenerationConfig()

            # Generate responses concurrently
            generation_results = await self._generate_all(
                provider, model, config, eval_examples, evaluation
            )
            responses = [r.text for r in generation_results]

            evaluation.responses = responses
            evaluation.warnings = self._collect_warnings(
                eval_examples, generation_results
            ) or None

            # Run evaluators
            evaluator_results = {}
            for i, evaluator_name in enumerate(evaluator_names):
                evaluator = self._get_evaluator(evaluator_name, provider, model)

                result = await evaluator.evaluate(
                    examples=eval_examples,
                    responses=responses,
                    generation_results=generation_results
                )

                evaluator_results[evaluator_name] = result.model_dump()

                # Update progress
                evaluation.progress = 0.7 + (i + 1) / len(evaluator_names) * 0.3

            evaluation.results = evaluator_results
            evaluation.status = EvaluationStatus.COMPLETED
            evaluation.progress = 1.0
            evaluation.completed_at = datetime.utcnow()

        except Exception as e:
            evaluation.status = EvaluationStatus.FAILED
            evaluation.error = str(e)
            raise

        return evaluation

    def get_available_providers(self) -> List[Dict[str, Any]]:
        """Get list of available providers and their models."""
        providers = []

        # Portkey exposes every vendor family behind one gateway key.
        if self.settings.portkey_api_key:
            for family in families():
                providers.append({
                    "id": family,
                    "name": FAMILY_LABELS[family],
                    "models": [s.slug for s in models_for_family(family)]
                })

        # Direct vendor access, only when explicitly configured.
        if self.settings.openai_api_key:
            openai = OpenAIProvider(api_key=self.settings.openai_api_key)
            providers.append({
                "id": "openai-direct",
                "name": "OpenAI (direct)",
                "models": openai.available_models
            })

        if self.settings.anthropic_api_key:
            anthropic = AnthropicProvider(api_key=self.settings.anthropic_api_key)
            providers.append({
                "id": "anthropic-direct",
                "name": "Anthropic (direct)",
                "models": anthropic.available_models
            })

        return providers
