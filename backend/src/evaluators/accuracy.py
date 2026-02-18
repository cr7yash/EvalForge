import numpy as np
from typing import List
from nltk.translate.bleu_score import sentence_bleu, SmoothingFunction
from rouge_score import rouge_scorer
from sklearn.metrics.pairwise import cosine_similarity
from sentence_transformers import SentenceTransformer

from .base import BaseEvaluator, EvalExample, EvalResult, EvaluatorResult


class AccuracyEvaluator(BaseEvaluator):
    """Evaluates accuracy using multiple NLP metrics."""

    def __init__(self, embedding_model: str = "all-MiniLM-L6-v2"):
        """
        Initialize accuracy evaluator.

        Args:
            embedding_model: Sentence transformer model for semantic similarity
        """
        self.embedder = SentenceTransformer(embedding_model)
        self.rouge = rouge_scorer.RougeScorer(['rougeL'], use_stemmer=True)
        self.smoothing = SmoothingFunction().method1

    @property
    def name(self) -> str:
        return "accuracy"

    @property
    def metrics(self) -> List[str]:
        return ["exact_match", "semantic_similarity", "bleu", "rouge_l", "f1"]

    async def evaluate(
        self,
        examples: List[EvalExample],
        responses: List[str],
        **kwargs
    ) -> EvaluatorResult:
        """Evaluate accuracy metrics for all examples."""
        results = []

        for example, response in zip(examples, responses):
            if not example.expected_output:
                continue

            expected = example.expected_output

            # Exact match
            exact = 1.0 if response.strip().lower() == expected.strip().lower() else 0.0

            # Semantic similarity
            emb_response = self.embedder.encode([response])
            emb_expected = self.embedder.encode([expected])
            semantic_sim = cosine_similarity(emb_response, emb_expected)[0][0]

            # BLEU score
            reference = [expected.split()]
            candidate = response.split()
            bleu = sentence_bleu(reference, candidate, smoothing_function=self.smoothing)

            # ROUGE-L
            rouge_scores = self.rouge.score(expected, response)
            rouge_l = rouge_scores['rougeL'].fmeasure

            # F1 score
            f1 = self._calculate_f1(expected, response)

            results.append(EvalResult(
                example_id=example.id,
                metrics={
                    "exact_match": exact,
                    "semantic_similarity": float(semantic_sim),
                    "bleu": bleu,
                    "rouge_l": rouge_l,
                    "f1": f1
                }
            ))

        # Aggregate metrics
        if results:
            aggregated = {
                metric: np.mean([r.metrics[metric] for r in results])
                for metric in self.metrics
            }
        else:
            aggregated = {metric: 0.0 for metric in self.metrics}

        return EvaluatorResult(
            evaluator_name=self.name,
            results=results,
            aggregated_metrics=aggregated
        )

    def _calculate_f1(self, expected: str, response: str) -> float:
        """Calculate F1 score based on token overlap."""
        expected_tokens = set(expected.lower().split())
        response_tokens = set(response.lower().split())

        if not expected_tokens or not response_tokens:
            return 0.0

        common = expected_tokens & response_tokens
        precision = len(common) / len(response_tokens)
        recall = len(common) / len(expected_tokens)

        if precision + recall == 0:
            return 0.0
        return 2 * (precision * recall) / (precision + recall)
