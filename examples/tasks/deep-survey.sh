#!/usr/bin/env bash
# Example 2: Deep iterative research survey
# Use case: complex open-ended topic needing multi-perspective exploration.
# Runs up to 30 orchestrator ticks with live monitor and auto-synthesis.

zhuri "write a comprehensive survey on LLM-based autonomous agents, covering:
1. Architecture patterns (ReAct, Plan-and-Solve, multi-agent orchestration)
2. Memory and context management
3. Tool use and API integration
4. Evaluation benchmarks and metrics
5. Open problems and future directions

Requirements:
- At least 50 citations from top venues (NeurIPS, ICML, ICLR, ACL, EMNLP)
- Comparison tables for architecture patterns and benchmarks
- Critical assessment of each approach's limitations" \
  --yes --synthesize --max-iters 30
