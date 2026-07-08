#!/usr/bin/env bash
# Example 3: Full paper-writing pipeline
# Use case: produce a complete survey paper with the 5-sub-skill task pack.
# Runs background with auto-synthesis — check progress with zhuri status.

zhuri "write a survey paper: 'A Survey of Post-Training Techniques for \
Large Language Models in HPC'.

Core topics:
1. Supervised Fine-Tuning (SFT) — domain adaptation for HPC workloads
2. Reinforcement Learning: RLHF, PPO, GRPO and their variants
3. Preference Alignment: DPO, IPO, KTO, ORPO and derivatives
4. Cross-cutting comparison: training stability, compute cost, alignment quality

Key papers to cover:
- HPC-GPT (Qin et al., SC'24) and related HPC+LLM work
- CodeRL, DeepSeekMath-GRPO, and other code-generation post-training methods

Requirements:
- Chapters organized by technique evolution: SFT → RLHF/PPO → DPO → GRPO
- Each chapter: method principles, HPC applicability analysis, representative papers
- Comparison tables: data needs, compute resources, performance by method
- At least 30 citations from recent top-tier venues
- Open problems and future directions section" \
  --yes --synthesize --max-iters 50
