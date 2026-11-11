# OCR on a Cloud GPU with vLLM: Deployment Plan & Cost Report

**Status:** Draft for review · **Prices as of:** 7 Nov 2026 (third-party trackers, see Sources; re-check before committing spend) · **FX assumption:** ₹95 = $1

---

## 1. Summary

- **Recommendation:** run `Qwen/Qwen2.5-VL-3B-Instruct-AWQ` with **vLLM** on **one NVIDIA L4 (24 GB)** in **GCP `asia-south1` (Mumbai)**, `g2-standard-8`. Start and stop it on a **school-hours schedule**, and let requests outside those hours wake it.
- **Pilot cost:** about **$266/month (≈ ₹25k)** for one L4 at 260 h/month. Running 24/7 would cost about $684/month (≈ ₹65k).
- **Throughput target:** about 2,000 pages/hour per L4. The current setup does 1 page at a time at about 4 s/page, which is about 900/h. This target is an **assumption**. Phase 1 benchmarks it before any money is committed.
- **Second choice:** AWS `g6.xlarge` (L4) in `ap-south-1`. It works the same way and costs about 9% more. OCI fits only if you already have Oracle credits.
- **Urgent and unrelated to cost:** `Bodhan.ipynb` contains a hardcoded Hugging Face token. Revoke it and remove it from git history.

---

## 2. Current state (what we're migrating from)

| Item | Today |
|---|---|
| Model | `Qwen/Qwen2.5-VL-3B-Instruct-AWQ` (4-bit), env `QWEN_VL_MODEL_ID` |
| Runtime | HF `transformers` loaded **inside the FastAPI process** (`backend/app/services/ocr_service.py`) |
| Concurrency | Global `threading.Lock`, so **one page at a time** and no batching |
| Settings | `min_pixels=512·28²`, `max_pixels=2048·28²`, `max_new_tokens=2048`, greedy |
| Limits | 15 MB/file, 50 files/request, 25 pages/PDF. A worst-case request can take more than 1 h |
| Hardware seen | Dev RTX 5060 8 GB: about 4 s/image, about 5 GB VRAM. Colab T4: 3–121 s/image, up to 9.6 GB peak |
| Deployability | `infrastructure/Dockerfile` has no CUDA, so OCR **cannot run in the current deploy** |
| Batch grading | Hard-coded to the `simulated` provider (`batch_grading_service.py:316`) |
| Dependency risk | AutoAWQ 0.2.9 is deprecated. It needs a workaround for `lm_head` |

The main problems are that OCR is tied to whichever machine runs the backend and that it processes one page at a time.

---

## 3. Target architecture

```
Browser ──► FastAPI backend (existing CPU host / container)
               │  OpenAI-compatible HTTPS, private network + API key
               ▼
           GPU VM (L4, Mumbai) ── vLLM: Qwen2.5-VL-3B-Instruct-AWQ
               ▲
           Redis queue (already in docker-compose): batch grading and off-hours jobs
```

Example vLLM launch on the GPU VM:

```bash
vllm serve Qwen/Qwen2.5-VL-3B-Instruct-AWQ \
  --max-model-len 8192 \
  --limit-mm-per-prompt '{"image":1}' \
  --mm-processor-kwargs '{"min_pixels":401408,"max_pixels":1605632}' \
  --gpu-memory-utilization 0.90 \
  --api-key "$OCR_VLLM_API_KEY"
```

Why vLLM:
- **Continuous batching.** Many pages are decoded at once on a single GPU, which replaces the serial lock.
- **OpenAI-compatible `/v1/chat/completions`.** The backend becomes a small HTTP client, and torch is no longer needed in the backend image.
- **Native AWQ loading.** This removes the deprecated AutoAWQ dependency and the `lm_head` workaround.
- **Model headroom.** The 24 GB L4 also fits **Qwen2.5-VL-7B-AWQ**, worth A/B testing for handwriting, which has not been tested yet.

---

## 4. GPU options (India regions, on-demand, 1 GPU)

| Cloud / region | Instance | GPU | On-demand $/h | ₹/h | Spot $/h | Notes |
|---|---|---|---|---|---|---|
| **GCP asia-south1** | **g2-standard-8** | **L4 24 GB** | **~0.89** | **~84** | ~0.45 | **Recommended** |
| AWS ap-south-1 | g6.xlarge | L4 24 GB | ~0.97 | ~92 | ~0.50 | Equivalent, about 9% dearer |
| GCP asia-south1 | n1-standard-4 + T4 | T4 16 GB | ~0.60 | ~57 | ~0.25 | Budget option, older architecture, slower |
| AWS ap-south-1 | g4dn.xlarge | T4 16 GB | ~0.58 | ~55 | ~0.25 | Budget option |
| OCI Mumbai/Hyderabad | VM.GPU.A10.1 | A10 24 GB | ~1.27–2.00 | ~120–190 | n/a | Generous free egress. Only worth it with Oracle credits |

T4 figures are approximate. OCI's official rate could not be confirmed. A 1-year commitment (GCP CUD / AWS Savings Plan) on an L4 costs about **$0.56/h (−37%)** and only pays off for an always-on base GPU.

**Why L4 over T4:** the T4 is about 35% cheaper per hour, but it is a much older GPU (Turing, no FP8, less bandwidth). The Colab T4 numbers (up to 121 s on one page) show it struggling. The L4 should give a much lower **cost per page**.

---

## 5. Throughput planning figure

- Each page is about 1–2k image tokens of prefill plus about 500–1,000 output tokens.
- **Planning figure: 2,000 pages/hour per L4** with vLLM batching. Phase 1 must confirm it.
- GPU-hours needed ≈ pages/day ÷ 2,000.

| Pages/day | GPU-hours/day | L4s needed in a 10 h window |
|---|---|---|
| 2,000 | 1 | 1 (mostly idle) |
| 20,000 | 10 | 2 (1 would be at 100%, with no peak headroom) |
| 100,000 | 50 | 6 (5 + 1 headroom) |

---

## 6. Uptime models explained

Every option uses the same GPU. They differ only in **when it is switched on**, because the cloud bills for every hour the VM is running, busy or idle.

### A. School hours (scheduled start/stop)
- A scheduler (GCP **Cloud Scheduler** + a start/stop function, or AWS **EventBridge Scheduler**) **starts the VM at about 07:30 IST and stops it at about 17:30, Monday to Saturday**.
- That is 10 h × 26 days ≈ **260 h/month**, against 730 h for 24/7, so it costs **about 64% less**.
- Teachers see **no waiting** during school hours because the model is already loaded.
- Outside those hours, a request is **queued in Redis** and runs at 07:30, or it triggers a wake-up (option D).
- Idle scheduled hours are still billed.

### B. Scale to zero (on demand)
- The VM is **off by default**. The first request starts it: VM boot, then container start, then model load. That takes **about 2–4 minutes**. The VM shuts itself down after about 30 minutes with no requests.
- You pay only for busy time plus those idle tails, which makes it **the cheapest option at very low volume**.
- The drawbacks:
  - The first teacher after every quiet spell waits minutes.
  - The backend needs "wake and wait" logic.
  - GPUs in Mumbai sometimes run out of stock, so a start can fail exactly when someone is waiting.
- Once usage is spread across the day, the VM is on most of the day anyway, and the savings over A disappear.

### C. 24/7
- No waiting at any time, at about **2.8× the cost of A**. It makes sense only at Scale tier, or if work arrives overnight. At that point, buy a 1-year commitment for the always-on base.

### D. Recommended: hybrid (A + on-demand wake)
- Use the school-hours schedule, plus outside-hours requests wake the VM, which then auto-stops after 30 minutes idle.
- Daytime use is instant, evening and Sunday use still works, and the cost is close to A.

---

## 7. Monthly expense model (GCP L4 Mumbai, on-demand $0.89/h, ₹95/$)

Fixed costs: per GPU VM, 100 GB SSD + static IP + logging ≈ **$25/month**. Shared items (network/egress/monitoring) ≈ **$10/month**. So fixed = $10 + $25 × GPUs: Pilot $35, Growth (2 VMs) $60, Scale (6 VMs) $160.

| Tier | Pages/day | L4s | **School hours** (260 h/GPU) | Scale-to-zero | 24/7 (730 h/GPU) |
|---|---|---|---|---|---|
| **Pilot** | ≤ 2k | 1 | **$266 (₹25k)** | $80–130 (₹8–12k)¹ | $684 (₹65k) |
| **Growth** | 2k–20k | 1–2 | **$266–522 (₹25–50k)** | ≈ same as school hours² | $1,358 (₹1.29L) for 2 GPUs |
| **Scale** | 20k–100k | 2–6 | **$522–1,547 (₹50k–1.47L)** | n/a³ | $2,032 (₹1.93L) for 3 GPUs with an overnight queue, up to $4,054 (₹3.85L) for 6 |

¹ Assumes 2–4 h/day of uptime (busy time plus idle tails) × 26 days.
² About 10–12 GPU-hours/day of busy time is already most of the school day, so there's nothing left to save.
³ A fleet that is busy all day never reaches zero.

**How the numbers are built:** GPUs × hours × $0.89 + fixed. For example, Pilot school hours = 1 × 260 × 0.89 + 35 = $266. Growth peak = 2 × 260 × 0.89 + 60 = $522. Scale peak = 6 × 260 × 0.89 + 160 = $1,547. (Exact rate used: $0.889/h.)

### Cost per 1,000 pages (school-hours mode, at the top of each tier)
| Tier | Pages/month (×26 days) | Monthly | **$/1k pages** | ₹/1k pages |
|---|---|---|---|---|
| Pilot (2k/day) | 52,000 | $266 | **$5.12** | ₹486 |
| Growth (20k/day) | 520,000 | $522 | **$1.00** | ₹95 |
| Scale (100k/day) | 2,600,000 | $1,547 | **$0.60** | ₹57 |

The theoretical floor, with an L4 100% busy, is about $0.45 per 1k pages.

### Ways to cut cost further
- **Spot/preemptible L4 (about $0.45/h, −49%)** for **batch grading**. Those jobs are already queued, so a preemption only causes a retry. Keep interactive Scan Review on on-demand.
- A **1-year commitment (−37%)** on the base GPU, but only once Scale tier runs 24/7.
- **On AWS instead of GCP:** multiply every GPU figure by about 1.09.

---

## 8. Backend integration (follow-up work, not part of this report)

1. New provider `qwen-vllm` in `backend/app/services/ocr_service.py`. It sends `POST {OCR_VLLM_BASE_URL}/v1/chat/completions` with the existing prompt and a base64 image per page (PDFs keep the current PyMuPDF rendering). Pages run concurrently with `httpx`/`asyncio`, and the global lock goes away.
2. Add config `OCR_PROVIDER` (`qwen-local` | `qwen-vllm`), `OCR_VLLM_BASE_URL` and `OCR_VLLM_API_KEY` in `backend/app/core/config.py` and `.env.example`.
3. `requirements-ocr.txt` becomes **dev-only**. The production backend image stays CPU-only.
4. Switch `batch_grading_service.py:316` from `simulated` to the configured provider, fed through the Redis queue.
5. Add `infrastructure/gpu/` with the vLLM container/compose file, a VM startup script and the scheduler (start/stop) definitions.
6. Isolate errors per page. Today one bad file fails the whole request.
7. Health check plus a "GPU waking up" status in the Scan Review UI for the scale-to-zero/hybrid path.

---

## 9. Risks & security

| Risk | Mitigation |
|---|---|
| **Leaked HF token in `Bodhan.ipynb`** | Revoke it now and purge it from git history (`git filter-repo`) |
| Student data protection (DPDP Act 2023) | Keep the GPU VM in an India region, on a private VPC with no public IP, require an API key, and keep no images on the GPU VM |
| L4 stock-outs in Mumbai | Allow a second zone (asia-south2 Delhi), with AWS g6 as a fallback |
| The 2,000 pages/h assumption is wrong | Phase 1 benchmark. The tier tables scale linearly with the measured figure |
| Handwriting accuracy (untested) | A/B test 3B vs 7B-AWQ on real answer sheets during the pilot |
| Cost overrun | Billing budget alerts at 50/90/100%, plus scheduled stop as a safety net |

---

## 10. Rollout

| Phase | What | Duration | Est. cost |
|---|---|---|---|
| 1. Benchmark | A spot L4 VM in Mumbai running vLLM on about 100 real pages. Measure pages/h, p95 latency and VRAM. Compare 3B vs 7B | 1–2 days | ~$5–10 |
| 2. Pilot | 1 on-demand L4, hybrid schedule, Scan Review behind a feature flag | 4–6 weeks | ~$266/month |
| 3. Batch grading | Switch grading to real OCR via the Redis queue. Consider spot for queued jobs | — | per tier |
| 4. Re-tier | Size the fleet from observed pages/day and the measured throughput | ongoing | — |

---

## Sources (price checks, 7 Nov 2026)
- GCP g2-standard-8, asia-south1: [Spare Cores](https://sparecores.com/server/gcp/g2-standard-8), [DevZero](https://www.devzero.io/instances/gcp/g2-standard-8), [Google Cloud accelerator pricing](https://cloud.google.com/products/compute/pricing/accelerator-optimized)
- AWS g6.xlarge, ap-south-1: [Spare Cores](https://sparecores.com/server/aws/g6.xlarge), [DevZero](https://www.devzero.io/instances/aws/g6.xlarge), [Vantage](https://instances.vantage.sh/aws/ec2/g6.xlarge)
- OCI GPU shapes: [OCI price list](https://www.oracle.com/cloud/price-list/), [third-party SKU summary](https://oraclelicensingexperts.com/blog/oracle-cloud-gpu-skus-pricing/)
- FX: [Pluang USD/INR](https://pluang.com/en/tools/currency-converter/usd-inr) (≈ ₹96.5, July 2026). This report uses ₹95.
