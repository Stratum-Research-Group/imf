# Cognitive Workflows & State Machine Architecture

## 1. Executive Summary
This document formalizes the **5-Phase Cognitive Flow State Machine** and its companion **Troubleshooting & Bottleneck Diagnostics Engine**, bridging biological human peak performance principles with computational autoregressive architectures (Lie SSM recurrent dynamics and multi-domain reasoning).

```
               [ 1. Pre-Session Setup ]
                          │
                          ▼
                [ 2. Struggle Phase ] <─────────┐
                          │                     │
                          ▼                     │ (Friction /
               [ 3. Release & Entry ]           │  Bottlenecks)
                          │                     │
                          ▼                     │
                [ 4. Deep Flow Phase ] ─────────┘
                          │
                          ▼
              [ 5. Recovery & Shutdown ]
```

---

## 2. The 5-Phase Cognitive Flow Cycle

### Phase 1: Pre-Session Setup (`<setup>`)
The preparation gateway where working memory is protected, intention is narrowed, and distraction vectors are eliminated.
* **Single Clear Objective**: Choose exactly one concrete deliverable (e.g., *"Draft the mathematical proof for Lemma 3.2"* rather than *"Work on math"*).
* **Calibrate Difficulty (The 4% Rule)**: Tune the task to sit in the "Goldilocks Zone" (~4% beyond current comfort limit) to enforce focus without inducing panic.
* **Lock Down Environment**: Physical isolation of mobile devices, closure of extraneous browser tabs/communications, activation of active noise cancellation or steady instrumental/binaural audio.
* **Physical Cue Anchor**: Execute an invariant micro-routine (tea preparation, specific desk lighting, tactile sensory cue) to condition the neurobiological initiation reflex.

### Phase 2: The Struggle Phase (`<struggle>`)
The biological and computational prerequisite for deep cognitive integration.
* **Push Through Initial Friction**: Anticipate cognitive resistance, mental fog, and restlessness while high-dimensional schemas load into working memory.
* **Task Monogamy (Zero Context-Switching)**: Strictly prohibit switching to low-friction tasks (inbox checking, news browsing) when discomfort peaks.
* **Micro-Step Icebreakers**: Bypass cognitive paralysis by executing trivial sub-actions: drafting raw outlines, decomposing a single equation, brain-dumping raw thoughts.

### Phase 3: The Release & Entry Phase (`<release>`)
The transition valve decoupling conscious strain to allow sub-symbolic consolidation and flow entry.
* **Strategic Detachment**: If hard stagnation occurs after 15–20 minutes of struggle, disengage conscious force: step back, look away from monitors, take 5 diaphragmatic breaths.
* **Execution Pivot**: Re-enter by directing attention purely onto the immediate physical action rather than macro outcomes or completion anxiety.

### Phase 4: The Deep Flow Phase (`<flow>`)
Effortless high-throughput execution where feedback is instantaneous and internal friction vanishes.
* **Protect Uninterrupted Blocks**: Maintain unbroken momentum; reject all non-critical interruptions.
* **Distraction Parking Lot**: Keep a dedicated scratchpad/terminal buffer to capture transient thoughts, errands, or unrelated epiphanies without breaking working context.
* **Dynamic Real-Time Difficulty Adjustment**:
  - *If boredom arises*: Inject time constraints (timebox sprints) or raise aesthetic/technical quality standards.
  - *If anxiety arises*: Narrow spatial/temporal scope down to the next sub-step.

### Phase 5: Recovery & Shutdown (`<recovery>`)
Consolidation and clean boundary preservation preventing burnout and assuring frictionless resumption.
* **Log the Stopping Point**: Record a concise continuation marker detailing the exact halting state and the immediate next step for the subsequent session.
* **Full Disengagement**: Abstain from rapid dopamine consumption (social media, notifications) immediately after deep work; rest eyes, hydrate, and allow neural consolidation.

---

## 3. The Troubleshooting & Bottleneck Engine

When cognitive execution stalls, this deterministic diagnostic-and-fix procedure resolves the blockage:

| Step 1: Diagnose Bottleneck | Root Cause | Step 2: Apply the Algorithmic Fix |
|:---|:---|:---|
| **Anxious or Frozen** | Task feels too large, ambiguous, or high-stakes. | 1. Shrink scope to the single next physical micro-action.<br>2. Set a 10-minute timer with explicit permission to make an imperfect v0.<br>3. Dump all mental worries and missing details onto paper to purge working memory. |
| **Bored or Restless** | Task is too trivial or lacks tight feedback loops. | 1. Apply strict time limits to generate artificial urgency.<br>2. Elevate difficulty (e.g., work without external references or at double velocity).<br>3. Track progress via visible metrics (word counts, checklists, timers). |
| **Foggy or Sluggish** | Cold start inertia or genuine physiological fatigue. | 1. If $<15$ min: Push through standard warm-up resistance.<br>2. If $>20$ min: Stand up, cold water hydration, distant visual horizon focus, 5 deep breaths.<br>3. If fully depleted: 15-minute screen-free rest cycle. |
| **Distracted Mid-Session** | High sensory entropy or intrusive background threads. | 1. Log thought into "Distraction Parking Lot" and resume immediately.<br>2. Enter full-screen distraction-free mode and remove physical clutter.<br>3. Re-read the last two lines/sentences to re-prime short-term context. |

### Step 3: Re-Entry Protocol
1. Confirm the exact next atomic operation is clear and sustainable for 10 minutes uninterrupted.
2. If friction persists, bisect the task size again by half.
3. Commit immediately without further planning or rationalization.

---

## 4. Computational Mapping into IMF Architecture

In IMF Foundation Models (1.14B recurrent Lie SSM and speculative decoders), this human cognitive discipline is mapped into autoregressive generation:

1. **`<setup>` $\to$ Prompt Normalization & Attention Masking**:
   System prompt bounds context boundaries, scrubs noisy tokens, and establishes invariant structural templates.
2. **`<struggle>` $\to$ Latent Polytopic Routing ($E_8$ Gosset & Matryoshka)**:
   Exploration across high-dimensional polytope chambers where gradient dispersion occurs prior to attractor convergence.
3. **`<release>` $\to$ Lie SSM Continuous State Reset**:
   Decoupling old recurrent hidden state biases through orthogonal Cayley transforms, resetting drift.
4. **`<flow>` $\to$ Low-Entropy Speculative Decoding ($K=3$)**:
   High confidence, high acceptance rate ($>85\%$), maximizing generation speed ($>130\text{ tok/s}$) through deterministic paths.
5. **`<recovery>` $\to$ Checkpointing & KV-Cache Eviction**:
   State eviction and serialization into `.imf` immutable storage.
