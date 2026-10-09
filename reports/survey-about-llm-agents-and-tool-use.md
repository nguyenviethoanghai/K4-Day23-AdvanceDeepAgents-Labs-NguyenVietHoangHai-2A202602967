# A Comprehensive Survey on LLM Agents and Tool Use: Architectures, Reasoning, and Benchmarks

## TL;DR (3-5 bullets, each citing [n])
- **Tool-Augmented Reasoning & Efficiency**: Modern LLM agents extend model capabilities by invoking external APIs and functions, where techniques like Chain-of-Abstraction [1] and parallel function execution pipelines [2] significantly reduce execution latency and improve multi-step planning accuracy.
- **Context Management & Tool Space Scaling**: As toolsets expand, challenges such as redundancy and context overload are mitigated via intelligent context-aware filtering, description rewriting, and merging systems like ToolScope [3], alongside sparse inference optimizations [4].
- **Adaptive Decision-Making & Learning**: Recent breakthroughs reveal that LLMs possess latent awareness of tool necessity, enabling lightweight probes to eliminate redundant calls [5], while interactive benchmarks like Learn2Play Bench [6] evaluate online experience-driven adaptation in unfamiliar environments.
- **Standardization & Comprehensive Benchmarking**: Frameworks such as UniToolCall [7] and Model Context Protocol (MCP) evaluation suites (MCP-RADAR [8] and MCPAgentBench [9]) establish unified representations, standardized data pipelines, and multi-dimensional evaluation metrics for real-world agentic systems.

## Background (definitions and foundational citations [n])
Large language model (LLM) agents represent systems where autoregressive models act as the core reasoning engine, augmented with perception, memory, and action spaces. In these architectures, tool use—often referred to as function calling or API invocation—allows models to bridge the gap between static parametric knowledge and dynamic, real-time external capabilities. 

Foundational studies established the paradigm of tool-augmented generation, where text generation is interleaved with structured action tokens that invoke calculators, web search engines, interpreters, and enterprise databases. However, scaling these systems introduces acute challenges: bloated prompt contexts, redundant tool descriptions, inefficient serial execution, and hallucinated API parameters. To address these hurdles, recent research has transitioned toward rigorous formalisms. UniToolCall [7] establishes unified data and evaluation representations for agentic tool use, while API-level graph datasets such as In-N-Out [10] model parameter dependencies to ensure robust multi-step API execution. Furthermore, automated testing frameworks like ToolFuzz [11] safeguard runtime reliability by uncovering discrepancies in natural language tool documentation.

## Tool Selection, Description Optimization, and Context Scaling
Managing large and evolving tool repositories remains a critical bottleneck for deploying robust LLM agents. Real-world enterprise and developer ecosystems often expose hundreds of overlapping tools with similar descriptions, leading to selection ambiguity and severe context window exhaustion.

To overcome these barriers, ToolScope [3] introduces a dual-module architecture comprising a tool merger with auto-correction to eliminate redundancy and a context-aware retriever that dynamically filters and ranks relevant tools for each user query. Complementing retrieval-time pruning, instruction-tuning strategies such as Trace-Free+ optimize and rewrite tool descriptions through curriculum learning, ensuring high reliability across diverse agent configurations [12]. When dealing with complex task graphs, planning algorithms inspired by Monte Carlo tree search, such as ToolTree [13], employ bidirectional pruning and dual-stage evaluation to systematically navigate expansive action spaces without drifting into irrelevant sub-routines.

## Latent Tool Awareness and Execution Optimization
A fundamental question in agentic computing is when and how LLMs decide to invoke tools versus relying on internal parametric generation. Recent investigations demonstrate that LLMs possess latent internal representations of tool necessity even prior to explicit reasoning generation [5]. 

Leveraging this insight, lightweight probes and latent estimators (such as the Probe&Prefill method) can predict tool necessity and suppress redundant calls, achieving up to a 48% reduction in unnecessary API invocations while maintaining task accuracy [5]. Once a tool call is deemed necessary, execution efficiency becomes paramount. Sequential invocation introduces compounding latency in multi-turn dialogues. Innovations like the LLM Compiler framework parallelize independent function calls [2], while reasoning paradigms such as Chain-of-Abstraction (CoA) utilize abstract planning tokens to structure computational workflows before invoking execution engines [1].

## Experience-Driven Adaptation and Interactive Environments
While static evaluations test single-turn tool accuracy, real-world deployments require agents to operate in dynamic, unfamiliar environments where rules are not explicitly known beforehand. 

To bridge this evaluation gap, Learn2Play Bench introduces text-based game environments designed specifically to assess how effectively LLM agents acquire and adapt through direct interaction rather than relying on pre-existing training familiarity [6]. In parallel, multi-agent embodied settings require synchronized ego-stream generation and fine-grained interaction modeling, as explored in multi-agent egocentric world models [14]. For multimodal deep research, unified frameworks like OneSearch-VL synthesize images and videos by constructing Visually Grounded Evidence Graphs (VGEG), serving as shared task-level references for retrieval, grounding, and fact composition [15].

## Benchmarking, Reliability, and Future Challenges
Evaluating agentic tool use demands rigorous, multi-dimensional benchmarks that reflect real-world deployment conditions. Traditional coding test evaluations often rely on a single reference solution, which can overstate test quality by ignoring alternative valid implementations. TestPrism addresses this by introducing a Joint Success Function evaluated across thousands of candidate implementations [16].

Within the Model Context Protocol (MCP) ecosystem, benchmarks such as MCP-RADAR provide five-dimensional evaluations of tool utilization capabilities [8], while MCPAgentBench scales assessment to complex real-world enterprise tasks [9]. Furthermore, as interaction histories accumulate over long-horizon tasks, KV-cache memory overhead strains standard serving engines. Infrastructure innovations like SparseEngine introduce sparse-first inference contracts to manage memory and attention overhead efficiently [4]. Open challenges remain in robust error recovery, dynamic API discovery, security against malicious tool injections, and cross-platform agentic coordination.

## References
[1] Efficient Tool Use with Chain-of-Abstraction Reasoning. arxiv. https://huggingface.co/papers/2401.17464 (2024-01-30)
[2] An LLM Compiler for Parallel Function Calling. arxiv. https://huggingface.co/papers/2312.04511 (2023-12-07)
[3] ToolScope: Enhancing LLM Agent Tool Use through Tool Merging and Context-Aware Filtering. hf-search. https://huggingface.co/papers/2510.20036 (2026-05-08)
[4] SparseEngine: Sparse-First Inference Engine. hf-daily. https://huggingface.co/papers/2609.39068 (2026-09-30)
[5] LLM Agents Already Know When to Call Tools -- Even Without Reasoning. arxiv. https://huggingface.co/papers/2605.09252 (2026-05-10)
[6] Learn2Play Bench: How Well Do LLM Agents Learn from Experience in Unfamiliar Environments?. hf-daily. https://huggingface.co/papers/2610.08215 (2026-10-08)
[7] UniToolCall: Unifying Tool-Use Representation, Data, and Evaluation for LLM Agents. arxiv. https://huggingface.co/papers/2604.11557 (2026-04-13)
[8] MCP-RADAR: A Multi-Dimensional Benchmark for Evaluating Tool Use Capabilities in Large Language Models. hf-search. https://huggingface.co/papers/2505.16700 (2025-05-22)
[9] MCPAgentBench: A Real-world Task Benchmark for Evaluating LLM Agent MCP Tool Use. hf-search. https://huggingface.co/papers/2512.24565 (2025-12-28)
[10] In-N-Out: A Parameter-Level API Graph Dataset for Tool Agents. arxiv. https://huggingface.co/papers/2509.01560 (2025-12-30)
[11] ToolFuzz -- Automated Agent Tool Testing. arxiv. https://huggingface.co/papers/2503.04479 (2025-03-11)
[12] Learning to Rewrite Tool Descriptions for Reliable LLM-Agent Tool Use. hf-search. https://huggingface.co/papers/2602.20426 (2026-02-23)
[13] ToolTree: Efficient LLM Agent Tool Planning via Dual-Feedback Monte Carlo Tree Search and Bidirectional Pruning. hf-search. https://huggingface.co/papers/2603.12740 (2026-03-13)
[14] Multi-Agent Egocentric World Model with Fine-Grained Embodied Interaction. hf-daily. https://huggingface.co/papers/2610.12299 (2026-10-08)
[15] OneSearch-VL: Unified Multimodal Deep Research Agent for Image and Video. hf-daily. https://huggingface.co/papers/2610.12419 (2026-10-08)
[16] TestPrism: Rethinking Test Evaluation Beyond a Single Reference. hf-daily. https://huggingface.co/papers/2610.12289 (2026-10-08)
