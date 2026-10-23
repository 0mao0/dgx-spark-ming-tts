# Third-party notices

This repository contains configuration, scripts, and documentation. It does not
redistribute model weights or engine source code.

| Component | Use | License |
|---|---|---|
| [inclusionAI/Ming-3.0-tts-tiny](https://huggingface.co/inclusionAI/Ming-3.0-tts-tiny) | model weights, downloaded by the user | MIT |
| [vLLM](https://github.com/vllm-project/vllm) 0.32.0 | inference runtime, installed with pip | Apache-2.0 |
| [vLLM-Omni](https://github.com/vllm-project/vllm-omni) PR #9119 / #9198 | pipeline and serving overlay, downloaded by the user | Apache-2.0 |
| [nginx](https://nginx.org/) | streaming proxy, configuration only | BSD-2-Clause |
| [matplotlib](https://matplotlib.org/) / [Pillow](https://python-pillow.org/) | chart scripts | PSF-based / HPND |

The Ming-3.0-tts tiny checkpoint is a Ling V3 MoE model (7.9B total, 1.3B
active) with a flow-matching decoder. It is not a small dense model; the 0.5B
sibling is a different architecture branch and does not run on this pipeline.
