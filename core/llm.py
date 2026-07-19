"""
LLM Integration Module

Handles communication with Ollama for local LLM inference.
"""

import asyncio
import logging
from dataclasses import dataclass
from typing import Any, Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from core.agent_base import AgentConfig, DiagnosticResult, LLMResponse, RemediationAction

logger = logging.getLogger(__name__)


@dataclass
class LLM InferenceRequest:
    """Request for LLM inference."""

    prompt: str
    system_prompt: str | None = None
    temperature: float = 0.7
    max_tokens: int = 2048
    context_window: int = 8192


class LLMClient:
    """
    Client for Ollama LLM API.

    Provides structured interfaces for:
    - Direct inference
    - Diagnostic analysis
    - Remediation planning
    - Decision making
    """

    def __init__(self, config: AgentConfig):
        self.config = config
        self.base_url = config.ollama_url
        self.model = config.ollama_model
        self._client: httpx.AsyncClient | None = None

    async def initialize(self) -> None:
        """Initialize the HTTP client."""
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(60.0, connect=10.0),
        )

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()

    @property
    def logger(self) -> logging.Logger:
        return logging.getLogger("llm_client")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    async def generate(self, request: LLMInferenceRequest) -> LLMResponse:
        """
        Generate a response from the LLM.

        Args:
            request: Inference request with prompt and parameters

        Returns:
            LLMResponse with generated content and metadata
        """
        if not self._client:
            await self.initialize()

        system_prompt = request.system_prompt or self._get_default_system_prompt()

        full_prompt = f"{system_prompt}\n\n{request.prompt}"

        try:
            response = await self._client.post(
                "/api/generate",
                json={
                    "model": self.model,
                    "prompt": full_prompt,
                    "temperature": request.temperature,
                    "num_predict": request.max_tokens,
                    "stream": False,
                },
            )
            response.raise_for_status()
            data = response.json()

            return LLMResponse(
                content=data.get("response", ""),
                confidence=0.8,  # Ollama doesn't provide confidence
                reasoning=None,
            )

        except httpx.HTTPStatusError as e:
            self.logger.error(f"LLM HTTP error: {e.response.status_code} - {e.response.text}")
            return LLMResponse(
                content="",
                confidence=0.0,
                error=f"HTTP {e.response.status_code}: {e.response.text}",
            )
        except Exception as e:
            self.logger.error(f"LLM inference error: {e}")
            return LLMResponse(content="", confidence=0.0, error=str(e))

    def _get_default_system_prompt(self) -> str:
        """Get the default system prompt for agents."""
        return """You are an expert AIOps assistant for Kubernetes clusters.

Your role is to help diagnose issues, plan remediations, and make decisions
about cluster operations.

Guidelines:
- Be precise and factual
- Consider multiple hypotheses
- Prioritize safety and stability
- Explain your reasoning
- When uncertain, say so

Respond in the requested format with clear, actionable information."""

    async def analyze_diagnostic(
        self,
        symptoms: list[str],
        metrics: dict[str, Any],
        logs: list[str],
    ) -> DiagnosticResult:
        """
        Analyze symptoms and metrics to diagnose an issue.

        Args:
            symptoms: Observed symptoms
            metrics: Relevant metrics
            logs: Relevant log entries

        Returns:
            DiagnosticResult with diagnosis and recommendations
        """
        prompt = self._build_diagnostic_prompt(symptoms, metrics, logs)

        request = LLMInferenceRequest(
            prompt=prompt,
            system_prompt="""You are an expert SRE diagnosing Kubernetes issues.
Analyze the provided symptoms, metrics, and logs to identify the root cause.

Provide a structured diagnosis with:
1. Most likely issue
2. Root cause (if identifiable)
3. Confidence level (0-1)
4. Recommended actions
5. Affected components

Be specific and actionable.""",
            temperature=0.3,  # Lower temp for more deterministic responses
            max_tokens=1024,
        )

        response = await self.generate(request)

        if response.error:
            return DiagnosticResult(
                issue="Analysis failed",
                root_cause=None,
                confidence=0.0,
                recommendations=[f"Error: {response.error}"],
                affected_components=[],
                severity="unknown",
            )

        return self._parse_diagnostic_response(response.content)

    def _build_diagnostic_prompt(
        self,
        symptoms: list[str],
        metrics: dict[str, Any],
        logs: list[str],
    ) -> str:
        """Build a diagnostic prompt from collected data."""
        prompt = "## Symptoms Observed\n"
        for s in symptoms:
            prompt += f"- {s}\n"

        prompt += "\n## Metrics\n"
        for k, v in metrics.items():
            prompt += f"- {k}: {v}\n"

        prompt += "\n## Relevant Logs\n"
        for log in logs[-20:]:  # Limit to last 20 log entries
            prompt += f"```\n{log}\n```\n"

        prompt += "\n## Analysis\n"
        prompt += "Based on the above information, provide your diagnosis:"

        return prompt

    def _parse_diagnostic_response(self, content: str) -> DiagnosticResult:
        """Parse LLM response into DiagnosticResult."""
        # Simple parsing - in production, use structured outputs
        lines = content.split("\n")
        issue = "Unknown issue"
        root_cause = None
        confidence = 0.5
        recommendations = []
        affected = []
        severity = "medium"

        for line in lines:
            line_lower = line.lower()
            if "issue:" in line_lower or "problem:" in line_lower:
                issue = line.split(":", 1)[-1].strip()
            elif "root cause:" in line_lower:
                root_cause = line.split(":", 1)[-1].strip()
            elif "confidence:" in line_lower:
                try:
                    conf_str = line.split(":", 1)[-1].strip().replace("%", "")
                    confidence = float(conf_str) / 100 if "%" in line else float(conf_str)
                except ValueError:
                    pass
            elif "recommend" in line_lower or "action" in line_lower:
                recommendations.append(line.split(":", 1)[-1].strip())
            elif "affected" in line_lower or "component" in line_lower:
                affected.append(line.split(":", 1)[-1].strip())
            elif "severity:" in line_lower or "priority:" in line_lower:
                severity = line.split(":", 1)[-1].strip().lower()

        return DiagnosticResult(
            issue=issue,
            root_cause=root_cause,
            confidence=confidence,
            recommendations=recommendations if recommendations else ["Manual investigation required"],
            affected_components=affected,
            severity=severity,
        )

    async def plan_remediation(
        self,
        diagnostic: DiagnosticResult,
        available_actions: list[str],
        constraints: dict[str, Any],
    ) -> list[RemediationAction]:
        """
        Plan remediation actions based on diagnostic.

        Args:
            diagnostic: Result from diagnostic analysis
            available_actions: List of available remediation actions
            constraints: Constraints like risk tolerance, time limits

        Returns:
            List of RemediationAction to execute
        """
        prompt = f"""## Issue to Remediate
{diagnostic.issue}

## Root Cause
{diagnostic.root_cause or 'Unknown'}

## Confidence
{diagnostic.confidence:.0%}

## Available Actions
"""
        for action in available_actions:
            prompt += f"- {action}\n"

        prompt += f"""
## Constraints
"""
        for k, v in constraints.items():
            prompt += f"- {k}: {v}\n"

        prompt += """
## Plan
Based on the issue and available actions, create a remediation plan.
For each action, specify:
1. Description
2. Action type (restart, scale, configure, notify, etc.)
3. Target resource
4. Risk level (low, medium, high)
5. Whether approval is required

Be conservative with high-risk actions."""

        request = LLMInferenceRequest(
            prompt=prompt,
            system_prompt="""You are an expert DevOps engineer planning remediation actions.
Create a clear, safe remediation plan.""",
            temperature=0.3,
            max_tokens=1024,
        )

        response = await self.generate(request)

        if response.error:
            return []

        return self._parse_remediation_response(response.content, diagnostic)

    def _parse_remediation_response(
        self, content: str, diagnostic: DiagnosticResult
    ) -> list[RemediationAction]:
        """Parse LLM response into RemediationAction list."""
        actions = []
        lines = content.split("\n")

        for i, line in enumerate(lines):
            line_lower = line.lower()
            if "action:" in line_lower or "step:" in line_lower or "1." in line_lower:
                desc = line.split(":", 1)[-1].strip() or line.split(".", 1)[-1].strip()

                action = RemediationAction(
                    id=f"action-{i}",
                    description=desc,
                    action_type="unknown",
                    target="",
                    parameters={},
                    estimated_impact="Unknown",
                    risk_level="medium",
                    requires_approval=diagnostic.confidence < 0.8,
                    auto_execute=diagnostic.confidence >= 0.9,
                )

                # Try to parse additional details
                for j in range(i + 1, min(i + 5, len(lines))):
                    next_line = lines[j].lower()
                    if "type:" in next_line:
                        action.action_type = lines[j].split(":", 1)[-1].strip()
                    elif "target:" in next_line:
                        action.target = lines[j].split(":", 1)[-1].strip()
                    elif "risk:" in next_line:
                        risk = lines[j].split(":", 1)[-1].strip().lower()
                        if "low" in risk:
                            action.risk_level = "low"
                        elif "high" in risk:
                            action.risk_level = "high"
                    elif "approve" in next_line:
                        action.requires_approval = "yes" in next_line or "true" in next_line

                actions.append(action)

        return actions

    async def make_decision(
        self,
        context: dict[str, Any],
        options: list[str],
        criteria: dict[str, float],
    ) -> tuple[str, float]:
        """
        Make a decision from options based on criteria.

        Args:
            context: Context information
            options: Available options
            criteria: Criteria with weights (sum to 1.0)

        Returns:
            Tuple of (selected option, confidence)
        """
        prompt = "## Decision Context\n"
        for k, v in context.items():
            prompt += f"- {k}: {v}\n"

        prompt += "\n## Options\n"
        for i, opt in enumerate(options):
            prompt += f"{i + 1}. {opt}\n"

        prompt += "\n## Criteria (weights)\n"
        for c, w in criteria.items():
            prompt += f"- {c}: {w:.0%}\n"

        prompt += "\n## Decision\n"
        prompt += "Analyze the options against the criteria and select the best one.\n"
        prompt += "Provide your selection and confidence (0-100%)."

        request = LLMInferenceRequest(
            prompt=prompt,
            system_prompt="""You are an expert decision-making system.
Analyze options against criteria and make optimal decisions.
Consider trade-offs and provide clear reasoning.""",
            temperature=0.4,
            max_tokens=512,
        )

        response = await self.generate(request)

        if response.error:
            return options[0], 0.0

        # Parse response
        for opt in options:
            if opt.lower() in response.content.lower():
                return opt, 0.7

        return options[0], 0.5
