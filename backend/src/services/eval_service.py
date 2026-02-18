import uuid
from typing import List, Dict, Any
from datetime import datetime

from ..providers.base import LLMProvider, GenerationConfig, GenerationResult
from ..providers.openai_provider import OpenAIProvider
from ..providers.anthropic_provider import AnthropicProvider
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
            if provider_name == "openai":
                self._providers[provider_name] = OpenAIProvider(
                    api_key=self.settings.openai_api_key
                )
            elif provider_name == "anthropic":
                self._providers[provider_name] = AnthropicProvider(
                    api_key=self.settings.anthropic_api_key
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

            # Generate responses
            responses: List[str] = []
            generation_results: List[GenerationResult] = []

            for i, example in enumerate(eval_examples):
                result = await provider.generate(
                    prompt=example.prompt,
                    model=model,
                    config=config
                )
                responses.append(result.text)
                generation_results.append(result)

                # Update progress
                evaluation.progress = (i + 1) / len(eval_examples) * 0.7  # 70% for generation

            evaluation.responses = responses

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

        if self.settings.openai_api_key:
            openai = OpenAIProvider(api_key=self.settings.openai_api_key)
            providers.append({
                "id": "openai",
                "name": "OpenAI",
                "models": openai.available_models
            })

        if self.settings.anthropic_api_key:
            anthropic = AnthropicProvider(api_key=self.settings.anthropic_api_key)
            providers.append({
                "id": "anthropic",
                "name": "Anthropic",
                "models": anthropic.available_models
            })

        return providers
