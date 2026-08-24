# AI ARCHITECTURE DECISIONS — Brutal Answers

### Two agents · RLHF · LangGraph · RAG · aur asli workflow

**Repo:** `D:\testcase`
**Version:** 1.0 · 2026-08-19
**Companion:** `docs/AI-100-PERCENT-AUTOMATION.md` (yeh doc uske §3/§4/§10 ko implement-level pe kholta hai)

> Aapne "brutal answer" maanga hai. Toh main taareef se shuru nahi karunga.
> **Aapke 4 sawaalon ka scorecard:**
>
> | Sawaal | Verdict |
> |---|---|
> | 1. Do AI — Scheduler/Guide + Class Teacher | ✅ **HAAN.** Yeh split bilkul sahi hai. Par "agent" ka matlab badalna padega. |
> | 2. RLHF use karein? | ❌ **NAHI.** Aur agar kiya, toh aap ek *cheating teacher* train kar loge. §3 padho — yeh sabse zaroori section hai. |
> | 3. LangGraph use karein? | ⚠️ **CLASSROOM MEIN NAHI. BACK OFFICE MEIN HAAN.** §4 |
> | 4. RAG use karein? | ❌ **NAHI.** Aapke paas retrieve karne ko kuch hai hi nahi. Aapke paas primary key hai. §5 |
>
> Do "nahi" aur ek "aadha nahi" hain — par teeno ke saath **iske badle kya karna hai** likha hai,
> aur woh cheez aap jo chahte ho woh 80–90% de deti hai, bina risk ke.

---

## Contents

| § | Section |
|---|---|
| 1 | Pehle ek baat saaf kar lein: "agent" ka matlab kya hai |
| 2 | **Do AI ka split** — Planner-Guide vs Class Teacher, ownership aur contract |
| 3 | **RLHF ka brutal jawab** — aur uski jagah kya (Variant Bandit) |
| 4 | **LangGraph ka brutal jawab** — kahan haan, kahan nahi |
| 5 | **RAG ka brutal jawab** — aur retrieval kahan sach mein chahiye |
| 6 | **"Different different examples"** — asli tareeka |
| 7 | **Workflow** — hot path, offline path, authoring path (teeno) |
| 8 | Kya build karna hai, kis order mein |
| 9 | Numbers — cost, latency, data volume |
| 10 | Ek nazar mein: kya karo / kya mat karo |

---

## 1. Pehle ek baat saaf: "agent" ka matlab kya hai

Aap "agent" bol rahe ho, aur usse do bilkul alag cheezein samjhi ja sakti hain:

| Meaning A — **Ownership boundary** | Meaning B — **Autonomous LLM loop** |
|---|---|
| Ek service jiski apni zimmedari hai, apna state, apna contract | Ek LLM jo khud decide karta hai kaunsa tool call karna hai, kitni baar, aur kab rukna hai |
| Deterministic ho sakta hai | Non-deterministic by definition |
| Test ho sakta hai | Sirf sample kiya ja sakta hai |
| 150 ms | 2–8 s |
| Fail hone pe predictable | Fail hone pe kuch bhi |

**Aapko Meaning A chahiye. Bilkul chahiye. Do agents banao.**
**Aapko Meaning B child path pe nahi chahiye.**

Kyun — ek line mein: *ek 3-saal ka bachcha uss galti ko report nahi kar sakta jo autonomous
loop ne ki hai.* Jab ek adult developer ke saath agent galat tool call karta hai, developer
dekh leta hai. Jab ek pre-literate bachche ke saath karta hai, koi nahi dekhta. Aap teen
mahine baad mastery data mein dekhoge ki kuch galat tha.

**Toh iss doc mein "agent" ka matlab:** ek zimmedari ki seema. Uske andar core deterministic
hai, aur LLM ek *renderer* hai — decision maker nahi.

Ek jagah Meaning B chalega: **content authoring pipeline (offline)**. Wahan output ek
insaan review karta hai ship karne se pehle. §7.3.

---

## 2. Do AI ka split — HAAN, aur exactly aise

Aapka instinct sahi hai. Aur woh accidentally software architecture ka ek purana sahi rule
pakad raha hai: **"kya padhana hai" aur "kaise padhana hai" do alag concerns hain.**
Aaj aapke code mein ye ghula-mila hai — `guide_agent_service.py` (924 lines) dono karta hai,
aur isiliye woh dono theek se nahi karta.

### 2.1 Agent 1 — **Planner-Guide (PG)**

> *"Aaj kya padhana hai, kab padhana hai, aur bachche ko kahan le jaana hai."*

| | |
|---|---|
| **Kab chalta hai** | Din mein ek baar (plan) + har navigation event pe |
| **State ka malik** | `daily_plans`, `revisit_queue`, `learner_profiles`, child ka route |
| **Faisle** | Kaunse 2 lessons · practice block · order · session length · auto-open · rest day · carry-over |
| **LLM ka kaam** | Sirf `plan.copy.title` (≤40 char) aur `copy.intro` (≤120 char) + GREET line |
| **LLM band ho toh** | Template. Plan bilkul same. |
| **Latency budget** | 300 ms (plan generation), 150 ms (navigation) |
| **Lesson ke andar** | **Kabhi nahi jhaankta.** Ek activity kaise padhai gayi, PG ko nahi pata. |
| **Code** | `services/plan_service.py` · `services/navigation_service.py` |

### 2.2 Agent 2 — **Class Teacher (CT)**

> *"Yeh ek activity kaise padhani hai. Samjhao → karwao → jawab lo → decide karo."*

| | |
|---|---|
| **Kab chalta hai** | Lesson ke andar har child input pe (tap / voice / trace / silence / doubt) |
| **State ka malik** | `lesson_states` (§8.1 of the automation spec) |
| **Faisle** | Phase · scaffold level · branch (6 options) · ladder rung · UI presentation · idle rung |
| **LLM ka kaam** | Chune hue rung ko *shabd* dena. Rung khud nahi chunta. |
| **LLM band ho toh** | Template. Har rung fir bhi chalta hai. |
| **Latency budget** | 150 ms (no LLM) / 2.5 s p95 (LLM) |
| **Kaunsa lesson** | **Kabhi khud nahi chunta.** PG deta hai. |
| **Code** | `services/conductor_service.py` · `services/branch_engine.py` · `services/explanation_service.py` |

### 2.3 Contract — sirf do messages. Poora interface yahi hai.

```python
# PG ──────────────► CT      (lesson shuru karte waqt, ek baar)
@dataclass(frozen=True)
class LessonAssignment:
    child_id: str
    plan_item_slot: int
    topic_id: str
    skill_ids: tuple[str, ...]
    mode: Literal["adventure", "practice", "revise"]
    target_minutes: float          # PG ne attention window se nikala
    scaffold_hint: int             # mastery band se initial S-level
    resume_from: dict | None       # carry-over / doubt-pause ke liye

# CT ──────────────► PG      (lesson khatam hone pe, ek baar)
@dataclass(frozen=True)
class LessonOutcome:
    session_id: str
    completed: bool
    skills_practised: dict[str, float]     # skill_id -> mastery delta
    end_reason: Literal["completed", "end_kindly", "time", "child_stopped"]
    minutes_spent: float
    revisit: tuple[str, ...]               # revisit_queue mein daalne wale skills
    parent_flags: tuple[str, ...]          # 3-din stuck skill, etc.
```

**Ye contract itna chhota isliye hai ki wahi uski taakat hai.**

- CT ko `daily_plans` ka schema nahi pata → plan engine badlo, CT ko chhoona nahi padta
- PG ko `scaffold_level` ka matlab nahi pata → pedagogy badlo, plan engine safe
- Dono ko `activity_evaluators` pata hai, aur **koi bhi correctness decide nahi karta**
- Dono LLM ke bina poore chalte hain

### 2.4 Ek teesri cheez jo agent **nahi** hai

**Evaluator.** `activity_evaluators.py` — 37 registered types, pure functions, zero LLM.
Yeh already production-grade hai. Ise agent mat banao, LLM mat do, "smart" mat banao.
Yeh product ki sabse bharosemand file hai. **Haath mat lagao.**

### 2.5 Aaj se kal ka mapping

| Aaj | Kal |
|---|---|
| `guide_agent_service.py` (924 lines, sab kuch) | **Split** → PG ka copy layer + CT ka voice layer + `ai/validate.py` |
| `daily_recommendation_service.py` | **PG ka core ban jaata hai** |
| `companion.py` router | **PG ka HTTP face** |
| `learning_service.py` attempt loop | **CT ko** (scoring/stars/unlock `learning_service` mein hi rahenge) |
| `practice_service.py` | **CT** — same loop, `sessions.mode = "practice"` |
| `guided_navigation_service.py` allowlist | **PG** (aur `guide_agent_service` ke allowlist ke saath merge — aaj **do alag allowlists hain**, do alag sach) |

---

## 3. RLHF — brutal jawab

### 3.1 Seedha jawab: **NAHI.** Aur yeh close call nahi hai.

Main aapko char wajah de raha hoon. Pehli teen practical hain. **Chauthi wajah wo hai jiske
liye yeh section likha gaya hai** — usse mat chhodna.

### 3.2 Wajah 1 — Aapke paas data hi nahi hai

RLHF ka matlab: ek **reward model** train karna human preference pairs pe, phir base model ko
uske against PPO/GRPO se optimize karna.

| Cheez | Chahiye | Aapke paas |
|---|---|---|
| Ranked preference pairs | 10,000–100,000 | **0** |
| Live users | Thousands | **0** — abhi prototype hai |
| Labelling budget | Domain experts (nursery teachers), months | — |
| Training infra | GPU cluster, eval harness, rollback | — |
| Serving infra | Apne weights host karne padenge | Aap Groq API pe ho (`llama-3.1-8b-instant`) |

Aapka `config.py` `groq_api_key` + hosted model use karta hai. RLHF ke baad aap **apna model
serve** kar rahe honge. Woh ek alag company hai, alag cost structure, alag on-call.

### 3.3 Wajah 2 — Jise aap "feedback" keh rahe ho, woh RLHF ka feedback hai hi nahi

Yeh sabse common confusion hai aur isse saaf karna zaroori hai:

| Aapke paas jo signal hai | RLHF ko jo signal chahiye |
|---|---|
| "Bachche ne sahi jawab diya" | "Insaan ne output A ko output B se behtar bataya" |
| Yeh **bachche ke baare mein** data hai | Yeh **model ke output ki quality** ke baare mein data hai |
| Isse **mastery** update hoti hai | Isse **model weights** update hote hain |
| Confounded: bachcha shayad pehle se jaanta tha | Direct comparison |

Bachche ka right/wrong ek **learning signal** hai, ek **preference signal** nahi. Aap already
usse sahi jagah use kar rahe ho — `skill_mastery` EWMA (OP-05). Usi signal ko LLM weights pe
lagana category error hai.

### 3.4 Wajah 3 — Reward sparse, delayed aur confounded hai

Maan lo aap phir bhi karna chahte ho. Reward kya hoga? "Bachche ne sahi jawab diya."

- **Sparse** — ek lesson mein 6 activities. 6 reward signals. Ek epoch ke liye kitne lesson chahiye?
- **Delayed** — asli reward "kya bachche ko *kal* yaad hai" hai. Woh 24 ghante baad aata hai.
- **Confounded** — bachcha sahi bola kyunki explanation achha tha? Ya kyunki woh pehle se jaanta
  tha? Ya kyunki sirf 2 options the? Ya kyunki mummy paas baithi thi? Aapke paas isko alag
  karne ka koi tareeka nahi.
- **Noisy** — 3-saal ka bachcha random tap karta hai. Aapka apna `child_speech_service` isi
  wajah se poora likha gaya hai.

### 3.5 Wajah 4 — **Aap ek cheating teacher train kar loge.** Yeh sabse important hai.

Yeh soch ke padho. RLHF ka reward: *"bachche ne sahi jawab diya."*

Model ke liye us reward ko maximise karne ka sabse aasan, sabse reliable, sabse tez raasta
kya hai?

> **Bachche ko jawab bata dena.**

Bas. Reward-hacking ka classic case. Policy gradient isko **hazaaron baar tez** dhoondh lega
bajaye "achha analogy dhoondhna" ke, kyunki jawab batane ka reward ~1.0 hai aur variance ~0 hai.
Aap literally ek aisa model optimize kar rahe honge jo cheat karna seekhe.

Aur ab dekhiye aapka apna code kya kehta hai — `guide_agent_service.py` mein yeh comment
pehle se likha hua hai, aur yeh bilkul sahi hai:

> *"The model is never shown the answer key… 'what is the answer?', which is the first thing a
> four-year-old asks the guide, could be answered. The child then taps it and the deterministic
> scorer awards the star, which makes the LLM the thing that decided the star."*

Jis insaan ne yeh likha, usne yeh problem samajh li thi. **RLHF-on-child-correctness us
poori suraksha ko ulta kar deta hai** — aap model ko woh karne ke liye *train* kar rahe ho
jisse rokne ke liye aapne architecture banaya tha.

Aur mitigation bhi kaam nahi karega: "answer leak pe penalty laga do" → model paraphrase
seekh lega. "Circle wala"→"gol wala"→"jo ball jaisa hai" — semantically leak, lexically clean.
Aap ek adversary train kar rahe ho apne hi safety filter ke against.

### 3.6 Toh phir feedback loop banega kaise? — **Variant Bandit**

Aap jo *asli* cheez chahte ho woh yeh hai:

> "System seekhe ki kaunsa explanation kis bachche pe kaam karta hai, aur agli baar wahi use kare."

Uske liye RLHF ki zaroorat **bilkul nahi** hai. Uske liye **contextual bandit** chahiye.
Farq yeh hai:

| RLHF | Contextual Bandit |
|---|---|
| Model **naya text** likhna seekhta hai | System **pehle se likhe hue** options mein se chunna seekhta hai |
| Action space: infinite | Action space: **finite, authored, reviewed** |
| Unsafe output invent ho sakta hai | **Ho hi nahi sakta** — har arm ek insaan ne likha hai |
| 10k+ labels chahiye | **30 observations per bucket** se kaam shuru |
| GPU training | ~200 lines Python, ek table |
| Rollback = redeploy weights | Rollback = ek row |
| Audit: impossible | Audit: "Aditi ko L2-variant-3 mila kyunki uska posterior sabse ooncha tha" |

**Yeh 80–90% woh de deta hai jo log RLHF se ummeed karte hain, aur risk ~0 hai.**

### 3.7 Bandit ka design — implementable

**Arms** — sirf *variant*, kabhi *rung* nahi:

```
arm = (skill_family, rung, variant_id)

skill_family : "counting" | "letters" | "shapes" | "colours" | "phonics" | "tracing" | "hindi_oral"
rung         : L1 | L2 | L4          # L3 aur L5 template-only hain, unme variant nahi
variant_id   : analogies.json / templates se authored variant ka index
```

> **Sabse zaroori guardrail:** bandit **kabhi rung nahi chunta.** Rung pedagogy hai —
> woh `min(L1 + attempts, L5)` se deterministic aata hai (automation spec §4.2).
> Bandit sirf *us rung ke andar* ka variant chunta hai. Yeh ek line hai jo poore
> pedagogy ko bandit ke experiment se bachati hai.

**Context** — chhota rakho. Neural mat banao.

```
age_band          4   (playgroup / nursery / lkg / ukg)
mastery_band      3   (weak / learning / mastered)
attempt_index     3   (1 / 2 / 3+)
modality          3   (tap / voice / trace)
frustration       2   (<0.5 / >=0.5)
language          2   (en / hi)
─────────────────────
                432 buckets — realistically ~120 populated
```

Har bucket mein per-arm ek `Beta(α, β)`. Bas. **Ek `bandit_arms` table:**

```sql
CREATE TABLE bandit_arms (
    skill_family  TEXT NOT NULL,
    rung          TEXT NOT NULL,
    variant_id    SMALLINT NOT NULL,
    context_key   TEXT NOT NULL,     -- "nursery|weak|2|tap|calm|en"
    alpha         NUMERIC NOT NULL DEFAULT 1.0,
    beta          NUMERIC NOT NULL DEFAULT 1.0,
    pulls         INTEGER NOT NULL DEFAULT 0,
    updated_at    TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (skill_family, rung, variant_id, context_key)
);
```

**Reward** — explanation ke *baad* ka outcome, session ka nahi:

```python
def reward(next_attempt_correct: bool, attempts_after: int, ended_kindly: bool) -> float:
    if ended_kindly:            return 0.0     # explanation ne bachao nahi kiya
    if not next_attempt_correct: return 0.0
    if attempts_after == 1:     return 1.0     # explanation ke turant baad sahi
    if attempts_after == 2:     return 0.6
    return 0.3
```

**Selection** — Thompson sampling:

```python
def choose(arms, context_key, rng):
    if total_pulls(context_key) < 30:            # cold start
        return rng.choice(arms)                  # seeded by (child_id, date)
    return max(arms, key=lambda a: rng.betavariate(a.alpha, a.beta))
```

**Update** — nightly ARQ job, real-time nahi. Kyun: real-time update ka matlab hai ki ek
bachche ka ek jawab doosre bachche ko dikhne wala content badal de. Nightly batch reproducible
hai aur debug ho sakta hai.

**Chaar guardrails jo non-negotiable hain:**

1. **Bandit rung nahi chunta.** Sirf variant.
2. **Har arm ek insaan ka likha hua content hai.** Bandit text generate nahi karta.
3. **Floor: har arm ko har 100 pulls mein kam se kam 1 pull.** Warna ek variant permanently
   mar jaayega aur aapko kabhi nahi pata chalega ki woh kisi doosre cohort ke liye behtar tha.
4. **Kill switch.** `BANDIT_ENABLED=false` → seeded deterministic choice, jaisa aaj hai.
   Poora product waise ka waisa chalta hai.

**Offline eval** — ship karne se pehle:
- Replay 4 hafte ke attempt logs
- Baseline: seeded random variant choice
- Metric: **attempts-to-correct**, aur **END_KINDLY rate**
- Bandit tabhi ship hoga jab attempts-to-correct me ≥10% sudhaar ho **aur** END_KINDLY rate na badhe

### 3.8 Asli "HF" — Human Feedback, bina RL ke

Human feedback aapko chahiye. Bas usse gradient mat banao — usse **content ka faisla** banao:

| Source | Kaun | Kya hota hai |
|---|---|---|
| Parent 👎 kisi explanation pe | Parent | Woh variant review queue mein jaata hai. 3 flags = auto-disable, insaan dekhega. |
| Teacher review queue | Nursery teacher (contractor, part-time) | Naye variants approve/reject karta hai. Yahi content pipeline ka gate hai. |
| Bandit ka posterior | System | Kaunsa variant kaam kar raha hai ka evidence |
| Golden transcript eval | CI | Prompt version regression |
| END_KINDLY spike per skill | System | Ek **curriculum** problem ka signal, teaching ka nahi |

**Yeh sasta hai, safe hai, audit ho sakta hai, aur kal shuru ho sakta hai.**
RLHF na sasta hai, na safe, na audit ho sakta, aur 12 mahine door hai.

### 3.9 Kab RLHF/DPO revisit karein — likhit trigger

`backend-architecture.md` §0.4 ke style mein, taaki yeh faisla decision rahe, omission nahi:

> **Revisit preference tuning (DPO, RLHF nahi) tab jab:**
> - 50,000+ real lessons ka data ho, **aur**
> - ek nursery teacher ne 5,000+ explanation pairs rank kiye hon, **aur**
> - Variant Bandit apna saturate kar chuka ho (naye variants se koi sudhaar nahi), **aur**
> - offline eval harness itna bharosemand ho ki regression pakad le
>
> Tab bhi: **DPO, PPO nahi** (sasta, stable, rollback aasan), aur ship se pehle **offline
> eval gate + shadow mode + human review**.
>
> Yeh realistically **12–18 mahine** door hai. Aaj bandit banao.

---
## 4. LangGraph — brutal jawab

### 4.1 Seedha jawab

> **Classroom hot path pe: NAHI.**
> **Back office (authoring, reports, evals) pe: HAAN, achha fit hai.**

Yeh "LangGraph bura hai" nahi hai. LangGraph ek theek library hai. Yeh **is jagah galat tool
hai**, aur wajahein specific hain.

### 4.2 Class Teacher mein kyun nahi — paanch concrete wajahein

**Wajah 1 — Do sources of truth ban jaayenge.**

LangGraph ka model: graph state + ek checkpointer (`MemorySaver`, `PostgresSaver`) jo use
persist karta hai. Aapka Class Teacher ka state ek **Postgres row** hai (`lesson_states`) jo:
- transactional hona chahiye (attempt + mastery + state, ek commit mein)
- ownership-checked hona chahiye (`owned_child` dependency, R3)
- 3 stateless FastAPI replicas ke beech share hona chahiye

LangGraph checkpointer laane ka matlab hai **ek doosra state store**. Ab lesson ka sach do
jagah hai. Aapke apne `docs/TRACK-A-experience-first.md` §2 ka title hi yeh hai:
*"The one rule that must not bend — Volatile is fine. Two sources of truth is not."*
Aap us bug ko client se hata rahe ho; graph runtime se wapas mat le aao.

**Wajah 2 — Aapko determinism chahiye, aur uska test likhna hai.**

Automation spec ka DoD kehta hai: *same `BranchInput` → same decision, 100 runs*, aur
*`branch_engine.py` `app/ai/` se kuch import nahi karta — AST test se.*

`branch_engine.decide()` ek **pure function** hai. Ek pure function ko graph runtime mein
wrap karne se:
- koi nayi capability nahi milti
- ek dependency, ek serialization format, aur ek version-to-upgrade mil jaata hai
- AST-level "yeh module LLM ko nahi chhoota" ka test **mushkil** ho jaata hai, kyunki ab
  aapka module ek runtime ke andar chal raha hai jo LLM providers ko import karta hai

**Wajah 3 — Latency budget.**

`backend-architecture.md` §1.1: `POST /learning/sessions/{id}/answer` (no LLM) → **p95 150 ms**.

Bachche ke tap se leke Pip ke bolne tak ka poora path — evaluate, mastery, commit, branch,
rung, presentation — deterministic Python mein **~15–30 ms** hai. Graph runtime ka overhead
us budget ke against maayne rakhta hai. Par asli khatra overhead nahi hai:

> **LangGraph laane se log LLM nodes hot path pe daal denge.** Kyunki library isi ke liye
> hai. Ek `should_reexplain` node jo LLM se poochhta hai — dekhne mein bahut natural lagta
> hai, aur woh R1 ko chupke se maar deta hai.

**Wajah 4 — Graph itna chhota hai ki library justify nahi hoti.**

Aapka poora Class Teacher graph:

```
8 nodes   : greet, set, i_do, we_do, you_do, check, branch, close
edges     : linear, plus branch se 6 deterministic outcomes
cycles    : ek (branch → we_do/you_do)
LLM nodes : ek (voice), aur woh bhi commit ke *baad*
```

Yeh ek `match` statement hai. Napkin pe ban jaata hai. Framework tab laate hain jab graph
itna bada ho ki usko dekhna mushkil ho — yeh nahi hai.

**Wajah 5 — Dependency tax.**

Aaj `backend/requirements.txt` chhota hai: FastAPI, pydantic, httpx, psycopg. LangChain ka
dependency tree isse kai guna bada hai, tez chalta hai, aur breaking changes deta hai.
6k DAU ke product mein woh maintenance ek asli laagat hai — aur `backend-architecture.md` §0.3
ka poora thesis hi yahi hai: *"infrastructure you maintain instead of product you ship."*

### 4.3 Iske badle kya — 60 lines

```python
# services/conductor_service.py — poora "graph runtime" itna hi hai

Phase = Literal["greet","set","i_do","we_do","you_do","check","branch","close"]

HANDLERS: dict[Phase, Callable[[LessonState, ChildInput], StepResult]] = {
    "greet":  handle_greet,   "set":    handle_set,
    "i_do":   handle_i_do,    "we_do":  handle_we_do,
    "you_do": handle_you_do,  "check":  handle_check,
    "branch": handle_branch,  "close":  handle_close,
}

async def step(session_id: str, child_input: ChildInput) -> ConductorDirective:
    async with uow.begin() as tx:                       # SELECT ... FOR UPDATE
        state = await repo.lock_lesson_state(session_id)
        result = HANDLERS[state.phase](state, child_input)   # pure, testable
        await repo.persist(state.apply(result))
        await tx.commit()                               # ← TRUTH COMMITTED

    # AI sirf yahan, commit ke baad, timeout + fallback ke saath
    voice = await ai.voice(result.decision, result.rung, result.variant, timeout=2.5)
    return build_directive(result, voice)
```

- State ownership: **ek** Postgres row
- Determinism: har handler pure hai, seedha test hota hai
- LLM: commit ke baad, ek jagah, guaranteed fallback
- Graph badalna: dict mein ek entry
- Dependency: zero nayi

**Yeh boring hai. Boring hi point hai.** Bachchon ke learning ka core loop woh jagah nahi
hai jahan aap architectural novelty kharcho.

### 4.4 LangGraph kahan sach mein achha hai — teen jagah

| Kahan | Kyun fit hai |
|---|---|
| **Content authoring pipeline** (§7.3) | Sach mein multi-step aur branching: draft → age critic → safety critic → pedagogy critic → duplicate check → human queue. Offline. Latency maayne nahi rakhti. Output insaan review karta hai. LLM ka non-determinism yahan **feature** hai. |
| **Parent weekly report** (ARQ worker) | fetch stats → draft → critique → revise → validate. Offline, adult reader, low stakes. |
| **Eval harness** | Golden transcripts pe judge chalana, multi-criteria scoring. Offline. |

Teeno mein common: **offline, adult-facing ya human-reviewed, aur latency-insensitive.**
Teeno mein se koi bhi bachche ko live text nahi bhejta.

### 4.5 Faisla, likhit roop mein

> **`app/ai/` aur `services/conductor_service.py` mein koi orchestration framework nahi.**
> Revisit tab jab: Class Teacher graph 20+ nodes ka ho jaaye, ya multi-agent negotiation
> chahiye ho, ya human-in-the-loop pauses hot path pe chahiye hon.
> Aaj teeno mein se ek bhi sach nahi hai.
>
> **`tools/content_studio/` mein LangGraph theek hai.** Woh alag process hai, alag
> `requirements`, alag deploy. API ke dependency tree mein nahi aayega.

---

## 5. RAG — brutal jawab

### 5.1 Seedha jawab: **NAHI.** Aur yeh sabse aasan "nahi" hai.

Aapka apna spec yeh pehle se keh chuka hai. `docs/backend-architecture.md` §0.4:

> | Not building | Revisit when |
> | RAG / vector DB | Curriculum exceeds what fits in a prompt — **not before** |

Woh line sahi thi. Main use dohra raha hoon, aur numbers de raha hoon.

### 5.2 Numbers

| | |
|---|---|
| Poora curriculum | **758 KB JSON**, 4 classes |
| Ek class | 80–298 KB |
| Ek topic | ~2–8 KB |
| **CT ko ek waqt pe kitna chahiye** | **ek activity — ~400 bytes** |
| LLM prompt budget | 1,200 tokens (§1.4) |
| Ek activity + hint + options + analogies | **~150 tokens** |

Aapko retrieval nahi chahiye. Aapko **`dict[topic_id]`** chahiye. Aur woh aapke paas
already hai — `curriculum_service.get_topic()`, `get_activities()`.

### 5.3 Asli baat: retrieval ek **problem** solve karta hai jo aapko hai hi nahi

Retrieval ka sawaal: *"mujhe nahi pata kaunsa document relevant hai, semantic similarity se
dhoondh do."*

Class Teacher ki position:
- Plan ne topic **deterministically** chuna (W3 S3)
- Conductor ne activity **index se** chuna
- Skill graph ne prerequisite **explicit edge se** diya
- Analogy bank `skill_id` se **directly** keyed hai

**Har cheez ka primary key aapke paas hai.** "Kya relevant hai" ka koi sawaal hi nahi hai.
Vector search laana ek O(1) dictionary lookup ko ek approximate nearest-neighbour search se
replace karna hai. Yeh sirf slower nahi — **galat** hai.

### 5.4 Aur ek failure mode jo yahan sach mein khatarnaak hai

Vector search "kuch nahi mila" nahi bolta. Woh **sabse nazdeek** cheez lauta deta hai.

| Kya hota hai | Nateeja |
|---|---|
| Nursery ke bachche ke liye "counting" query | LKG ka subtraction explanation retrieve ho gaya |
| Hindi topic pe query | English chunk retrieve ho gaya (embeddings cross-lingual leak karte hain) |
| "circle" pe query | "cycle" ka chunk retrieve ho gaya |

Yeh galat jawab **plausible dikhta hai**, silent hai, aur ek 4-saal ke bachche ke saamne hai
jo ise report nahi kar sakta. `curriculum_service.get_topic(topic_id)` yeh **kar hi nahi sakta**.
Woh ya sahi topic deta hai ya `KeyError` deta hai.

Aur aapka loader already `TOPIC_NOT_READY` (409) aur startup fail-fast se yeh discipline
enforce karta hai. RAG us discipline ka ulta hai.

### 5.5 Retrieval kahan sach mein justify hoti hai

| Use case | Justified? | Kyun |
|---|---|---|
| Child path pe explanation dhoondhna | ❌ | Primary key hai |
| Analogy chunna | ❌ | `analogies.json[skill_id]` — dict lookup |
| Prerequisite dhoondhna | ❌ | `skill_graph.json` — explicit edges |
| Doubt ka jawab ("aasman neela kyun hai?") | ⚠️ **Shayad** | Open-domain. Par jawab **safe, short, curated** hona chahiye — toh curated kids-FAQ set behtar hai, open RAG nahi |
| **Parent knowledge base** ("mera bachcha hakla raha hai") | ✅ **HAAN** | Sach mein open-domain, adult reader, curated parenting content pe RAG sahi hai |
| **Author tool** — "isse milti-julti activity kahan hai?" | ✅ **HAAN** | Internal, insaan reviewer, duplicate detection ke liye |
| Cross-lingual content search (authors ke liye) | ✅ **HAAN** | Internal |

**Pattern saaf hai:** RAG **adult, internal, ya low-stakes** surfaces pe theek hai.
Child ke learning path pe kabhi nahi.

### 5.6 Faisla, likhit roop mein

> **Child path pe koi vector DB, koi embedding search, koi RAG nahi.**
> Curriculum access hamesha primary key se — `curriculum_service` ke through.
>
> **Revisit tab jab:** curriculum 100× bada ho jaaye (75 MB+) **aur** ek naya use case ho
> jahan sahi content ka id pata na ho. Aaj dono galat hain.
>
> **Alag se allowed (child path ko chhue bina):** parent knowledge base, authoring
> duplicate-detection. Alag service, alag index, child API se koi shared code nahi.

---

## 6. "Different different examples" — asli tareeka

Yeh aapka sabse achha instinct tha, aur ise theek se karna zaroori hai.

### 6.1 Galat tareeka (jo aasan lagta hai)

> "LLM se bolo naya example generate kare."

Kya galat ho sakta hai, aur asli examples:

| Model kya bol sakta hai | Problem |
|---|---|
| "Circle sikke jaisa hota hai" | Bachche ne sikka dekha hi nahi (digital payments) |
| "Circle pizza jaisa hota hai" | Culturally off, aur bahut bachchon ne nahi dekha |
| "B is for Balloon" jab lesson "B is for Ball" hai | Curriculum sequence tod diya |
| "गोल मतलब round" | Hindi lesson mein English ghusa diya |
| "Yeh bilkul bandook ki nali jaisa gol hai" | Safety filter ke through nikal sakta hai |
| Wahi analogy 4 baar alag shabdon mein | Bachche ko lagta hai teacher sun hi nahi raha |

Aur ek aisi baat jo aksar miss hoti hai: **ek galat analogy sirf bekar nahi hoti, woh
misconception paida karti hai.** "Circle ek pahiya hai" wale bachche ko oval bhi circle
lagega. Aap ek galti sikha rahe ho jise baad mein *un-teach* karna padega.

### 6.2 Sahi tareeka — Authored Variant Bank + Bandit

```json
// backend/app/data/curriculum/analogies.json
{
  "shape_circle": {
    "en": [
      {"id": 0, "text": "a ball",     "concrete": true,  "bands": ["playgroup","nursery","lkg","ukg"]},
      {"id": 1, "text": "a roti",     "concrete": true,  "bands": ["playgroup","nursery","lkg","ukg"]},
      {"id": 2, "text": "the sun",    "concrete": false, "bands": ["lkg","ukg"]},
      {"id": 3, "text": "a bangle",   "concrete": true,  "bands": ["nursery","lkg","ukg"]}
    ],
    "hi": [
      {"id": 0, "text": "गेंद",  "concrete": true, "bands": ["playgroup","nursery","lkg","ukg"]},
      {"id": 1, "text": "रोटी",  "concrete": true, "bands": ["playgroup","nursery","lkg","ukg"]},
      {"id": 2, "text": "चूड़ी", "concrete": true, "bands": ["nursery","lkg","ukg"]}
    ]
  }
}
```

**Har rung ke liye variety kahan se aati hai:**

| Rung | Variety ka source | Kitne variants |
|---|---|---|
| L1 Restate | Sentence-frame templates × hint | 3–4 |
| L2 Concretise | **Analogy bank** — bandit chunta hai | 3–5 per skill per language |
| L3 Demonstrate | Visual action (highlight / trace / co-count) | 2–3 (template-only) |
| L4 Contrast | Activity ke apne options se generate | options ki count jitne |
| L5 Do together | `demo_tap` | 1 (template-only) |

**Ek skill pe realistic combinations: 3 × 4 × 2 × 3 × 1 ≈ 72 alag teaching paths.**
Ek bachche ko ek session mein max 4 milte hain. **Repeat practically zero hai** —
bina ek bhi shabd LLM ke invent kiye.

### 6.3 LLM ka role yahan — aur uski hadd

LLM **analogy nahi chunta**. Woh chuni hui analogy ko *bolna* seekhata hai:

```
Input to model:
  analogy_chosen : "गेंद"              ← bandit ne chuna, bank se
  skill_display  : "गोल आकार"
  age_band       : "nursery"
  language       : "hi"
  word_limit     : 10
  already_said   : ["देखो — यह गोल है।"]

Valid output:  "गेंद जैसा गोल! अब गोल वाले को छुओ।"
Invalid:       कोई और analogy laana (bank mein nahi hai → validate.py reject → template)
```

**Yeh farq hi sab kuch hai.** LLM ek *translator* hai chuni hui pedagogy se bachche ki bhasha
mein. Woh pedagogy ka *author* nahi hai.

### 6.4 Naye variants aate kahan se hain

Yahan LLM sach mein value deta hai — **offline, human review ke saath** (§7.3):

```
LLM 20 candidate analogies draft karta hai
      → age-band critic (yeh 3-saal ke bachche ke liye theek hai?)
      → safety critic
      → culture/locale critic (India, tier-2/3, 2026)
      → duplicate check (yahan embeddings theek hain — internal tool)
      → HUMAN REVIEW QUEUE  ← gate. bina iske kuch ship nahi hota.
      → analogies.json
      → loader validate karta hai
      → bandit ka naya arm ban jaata hai
```

**Insaan production tak pahunchne se pehle har variant dekhta hai.** Ek nursery teacher
20 candidates 10 minute mein review kar leti hai. Yeh scale karta hai, aur yeh audit hota hai.

---
## 7. Workflow — teeno, poore

### 7.1 Hot path — bachcha ek jawab deta hai

Yeh woh flow hai jo din mein ~70,000 baar chalega (`backend-architecture.md` §1.2).
**Har step ka owner likha hai. Sirf ek step LLM hai.**

```
┌── CHILD ────────────────────────────────────────────────────────────────┐
│  taps "circle"  /  says "gol"  /  traces  /  12s chup rehta hai         │
└────────────────────────────────┬────────────────────────────────────────┘
                                 ▼
                POST /api/v1/conductor/sessions/{id}/input
                                 │
┌── CLASS TEACHER (CT) ───────────┼───────────────────────────────────────┐
│                                 ▼                                       │
│  1. LOAD + LOCK      SELECT lesson_states ... FOR UPDATE      [D]  2 ms │
│                      ownership check (R3)                              │
│                                 ▼                                       │
│  2. RESOLVE INPUT    voice? -> child_speech_service (deterministic)[D]  │
│                              -> 0.30–0.80 band? AI enhancer   [LLM*] 300ms
│                              -> enhancer ko correct answer NAHI (R6)   │
│                      tap?   -> as-is                                    │
│                      idle?  -> koi answer nahi, idle rung ++            │
│                                 ▼                                       │
│  3. EVALUATE         activity_evaluators.evaluate()           [D]  1 ms │
│                      ← YAHI SACH HAI. LLM yahan kabhi nahi.            │
│                                 ▼                                       │
│  4. MASTERY          EWMA + lazy decay (OP-05)                [D]  1 ms │
│  5. PERSIST          attempts row + skill_mastery + lesson_state  [D]   │
│  6. ═══ COMMIT ═══   ← TRUTH SAVED. Yahan se aage sab kuch fail        │
│                        ho sakta hai, bachche ki progress safe hai.     │
│                                 ▼                                       │
│  7. BRANCH           decide(BranchInput) -> 6 mein se 1        [D]  <1ms│
│                      ADVANCE|RE_EXPLAIN|SIMPLIFY|                      │
│                      PREREQUISITE|SWITCH_MODALITY|END_KINDLY           │
│                                 ▼                                       │
│  8. RUNG             min(L1+attempts, L5), used rungs skip    [D]  <1ms│
│  9. VARIANT          bandit.choose(rung, context)             [D]  1 ms │
│                      ← arms sab authored. invent kuch nahi hota.       │
│ 10. SCAFFOLD         S-level ±1                               [D]  <1ms│
│ 11. PRESENTATION     UI autopilot (choices, target, decoration)[D] <1ms│
│                                 ▼                                       │
│ 12. VOICE            rung L3/L5      -> template              [D]  <1ms│
│                      rung L1/L2/L4   -> LLM(context)          [LLM] 800ms
│                      budget khatam / circuit open -> template  [D]      │
│                                 ▼                                       │
│ 13. VALIDATE         11-step ladder (spec §10.3)              [D]  2 ms │
│                      answer-leak · shame · repeat · script · allowlist │
│                      koi bhi fail -> template. Kabhi raw text nahi.    │
│                                 ▼                                       │
│ 14. DIRECTIVE        ConductorDirective                                │
└─────────────────────────────────┬───────────────────────────────────────┘
                                  ▼
                     activity · scaffold · presentation · speech
                     visual_action · next_input.on_timeout
                                  ▼
┌── CLIENT ───────────────────────────────────────────────────────────────┐
│  render karta hai. TTS bolta hai. timer chalata hai. KUCH DECIDE NAHI  │
│  KARTA. (R2)                                                           │
└─────────────────────────────────────────────────────────────────────────┘

  branch == END_KINDLY / lesson complete ho gaya:
       CT ──LessonOutcome──► PG ──► agla plan item ya CLOSE
```

**Latency:** LLM ke bina **~10 ms** (150 ms budget ke andar aaram se).
LLM ke saath **~1.1 s** (2.5 s p95 budget ke andar).
`LLM_PROVIDER=none` pe: **~10 ms, har baar, har rung**, aur poora lesson chalta hai.

**Steps 1–6 aur 7–11 mein LLM zero hai.** Bachche ki poori progress LLM ke bina decide hoti
hai. Step 12 hi ekmatra jagah hai, aur uska fallback tested hai.

### 7.2 Planner-Guide ka flow — din mein ek baar + navigation pe

```
Din ka pehla request (ya scheduled window)
      │
      ▼
┌── PLANNER-GUIDE (PG) ──────────────────────────────────────────────────┐
│  P1  plan_days check      -> rest day? -> warm rest state, ruk jao [D] │
│  P2  aaj ka plan hai?     -> haan -> return frozen plan            [D] │
│                              (refresh/re-login pe REGENERATE NAHI)     │
│  P3  CARRY-OVER           kal ka ek incomplete adventure item      [D] │
│  P4  REVISE BLOCK         revisit_queue where due_on <= today      [D] │
│                           + weak-skill rule R3                         │
│  P5  ADVENTURE ×2         R1–R7 compose (naya spec nahi likhna)    [D] │
│  P6  PRACTICE BLOCK       P5 ke skills ka union, 6 questions,      [D] │
│                           weak×3 learning×2 mastered×1,                │
│                           seed = (child_id, plan_date)                 │
│  P7  FIT TO TIME          attention window se trim (end se)        [D] │
│  P8  FREEZE               persist. UNIQUE(child_id, plan_date)     [D] │
│  P9  COPY                 title <=40, intro <=120           [LLM/tmpl] │
│                           model ko sirf skill display names milte hain │
│ P10  AUTO-OPEN            5s baad pehla item                       [D] │
└───────────────────────────────┬────────────────────────────────────────┘
                                ▼
                        LessonAssignment ──► CT
                                             │
                        LessonOutcome  ◄─────┘
                                ▼
                 plan item status update, agla item ya CLOSE
```

**Poora plan deterministic hai except P9.** LLM band karo → plan **byte-identical** rehta
hai, sirf `copy` template ka hota hai. Yeh W3 ka already-declared DoD hai; yeh doc sirf
usko do-agent shape mein rakh raha hai.

### 7.3 Authoring pipeline — **yahan LangGraph theek hai**

Yeh **offline** chalta hai, bachche ke path se poori tarah alag. `tools/content_studio/` —
alag process, alag `requirements.txt`, alag deploy. API ke dependency tree mein nahi.

```
     AUTHOR / SYSTEM: "shape_circle ke liye 20 nayi analogies chahiye, hi + en"
                                    │
    ┌───────────────────────────────▼──────────────────────────────┐
    │  LangGraph (yahan iska non-determinism ek FEATURE hai)       │
    │                                                              │
    │   [draft]  20 candidates generate                            │
    │      │                                                       │
    │      ├──► [age critic]      "3-saal ka bachcha jaanta hai?"  │
    │      ├──► [safety critic]   violence/fear/PII/brand          │
    │      ├──► [culture critic]  India, tier-2/3, 2026            │
    │      ├──► [language critic] hi = Devanagari, koi mixing nahi │
    │      └──► [dup check]       embeddings — INTERNAL TOOL, ok   │
    │      │                                                       │
    │   koi bhi critic fail -> [revise] -> max 2 loops             │
    └───────────────────────────────┬──────────────────────────────┘
                                    ▼
    ╔═══════════════════════════════════════════════════════════════╗
    ║  HUMAN REVIEW QUEUE — nursery teacher                        ║
    ║  approve / reject / edit.  ISKE BINA KUCH SHIP NAHI HOTA.    ║
    ╚═══════════════════════════════╤═══════════════════════════════╝
                                    ▼
              analogies.json  /  activities/*.json  (git commit, reviewed diff)
                                    ▼
              curriculum loader startup pe validate (fail-fast)
                                    ▼
              bandit ka naya arm (Beta(1,1), cold start)
```

**Yahan LLM khul ke chalta hai — kyunki output ke aur bachche ke beech ek insaan khada hai.**
Yeh poora doc isi ek line pe ghoomta hai.

### 7.4 Nightly jobs (ARQ worker)

| Job | Kya |
|---|---|
| `bandit_update` | Kal ke attempts se Beta posteriors update. Real-time nahi — reproducible aur debuggable. |
| `revisit_schedule` | Mastered skills ko 1/3/7/21 day intervals pe `revisit_queue` mein daalo |
| `parent_digest` | Daily digest bhejo (quiet hours respect karke) |
| `parent_weekly` | Weekly narrative (LangGraph optional yahan) |
| `eval_harness` | 200 golden transcripts current prompt versions pe. Regression = CI fail. |
| `content_gaps` | Skills without activities · activities without `skill_id` · orphan graph nodes |
| `certificate_render` | Async, kabhi inline nahi (§1.4) |

### 7.5 Poora system — ek nazar mein

```
                     ┌──────────────────────────────────┐
                     │        CHILD (2–6 saal)          │
                     └───────────────┬──────────────────┘
                                     │ tap / voice / trace / silence
                 ┌───────────────────▼───────────────────┐
                 │   Next.js / Expo  — RENDER ONLY       │
                 │   kuch decide nahi karta (R2)         │
                 └───────────────────┬───────────────────┘
                                     │ HTTPS
        ┌────────────────────────────▼────────────────────────────┐
        │                   FastAPI (3 replicas)                  │
        │                                                         │
        │   ┌─────────────────┐        ┌────────────────────┐     │
        │   │  PLANNER-GUIDE  │───────►│   CLASS TEACHER    │     │
        │   │  kya padhana    │ Lesson │   kaise padhana    │     │
        │   │                 │◄───────│                    │     │
        │   │ plan · route    │Outcome │ phase · scaffold   │     │
        │   │ revisit · open  │        │ branch · rung      │     │
        │   └────────┬────────┘        └────────┬───────────┘     │
        │            │                          │                 │
        │            │      ┌───────────────────▼──────────────┐  │
        │            │      │  EVALUATOR  (agent NAHI)         │  │
        │            │      │  pure functions · LLM zero       │  │
        │            │      │  ← YAHI SACH HAI                 │  │
        │            │      └───────────────────┬──────────────┘  │
        │            │                          │                 │
        │   ┌────────▼──────────────────────────▼──────────────┐  │
        │   │  ai/  —  context · policy · validate · templates │  │
        │   │  LLM SIRF SHABD DETA HAI. FAISLA KABHI NAHI.     │  │
        │   └────────────────────────┬─────────────────────────┘  │
        └────────────────────────────┼────────────────────────────┘
                                     │
              ┌──────────────────────┼──────────────────────┐
              ▼                      ▼                      ▼
        ┌───────────┐         ┌───────────┐         ┌──────────────┐
        │ Postgres  │         │   Redis   │         │  Groq API    │
        │ ← SACH    │         │ cache /   │         │  optional    │
        │           │         │ ratelimit │         │  down ho toh │
        │ 21 tables │         │           │         │  app chalta  │
        └───────────┘         └───────────┘         └──────────────┘
              ▲
              │  nightly
        ┌─────┴──────────────────────────────────────┐
        │  ARQ worker: bandit · revisit · digest ·   │
        │  eval · gaps · certificates                │
        └────────────────────────────────────────────┘

        ══════ OFFLINE, alag process ══════
        ┌────────────────────────────────────────────┐
        │ tools/content_studio/  (LangGraph OK)      │
        │ draft → critics → HUMAN REVIEW → git       │
        └────────────────────────────────────────────┘
```

---

## 8. Build order

| # | Kya | Kyun is order mein | Effort |
|---|---|---|---|
| 1 | **Postgres + repositories** (OP-01) | `mock_storage.py` ke rehte hue kuch bhi durable nahi. `lesson_states`, `bandit_arms`, `revisit_queue` — sabko DB chahiye. | L |
| 2 | **Auth + consent** (OP-02) | `mock_auth.py` sha256 hai. Iske bina production illegal. | M |
| 3 | **Agent split** — PG aur CT alag modules, `LessonAssignment`/`LessonOutcome` contract | Baaki sab ka structure. Behaviour abhi same rakho — sirf seemayein khींcho. | M |
| 4 | **Branch engine** (pure function + 100-run determinism test) | CT ka dil. Sabse chhota, sabse zyada leverage. | S |
| 5 | **Explanation ladder L1–L5** + `analogies.json` + `skill_graph.json` | "Dobara samjhao" — aapki asli demand. | M |
| 6 | **`ai/validate.py`** 11-step ladder | Answer-leak + repeat-guard. Iske bina 5 unsafe hai. | S |
| 7 | **UI autopilot** `presentation` block | "UI easy kardo" | M |
| 8 | **Zero-tap** — auto-open, auto-advance, graceful exit | "AI hi class khole" | M |
| 9 | **Plan engine** (W3) + `revisit_queue` | PG ka core | L |
| 10 | **Variant Bandit** | **Yahan aata hai. #5 ke bina arms hi nahi hain.** | S |
| 11 | Speech enhancer (0.30–0.80 band) | Aaj ka sabse bada silent failure | M |
| 12 | Eval harness + golden transcripts | #10 ko ship karne ke liye zaroori | M |
| 13 | Content studio (LangGraph) | Jab variant bank chhota padne lage | M |
| 14 | Parent knowledge base (RAG, agar chahiye) | Optional, child path se poori tarah alag | M |

**Bandit #10 pe hai, #3 pe nahi.** Kyun: bandit ko *arms* chahiye. Arms `analogies.json` se
aate hain, jo #5 mein banti hai. Aur reward ko `lesson_states` chahiye, jo #3–#4 mein banta hai.
Bandit pehle banana matlab ek aisi cheez optimize karna jiske paas chunne ko kuch hai hi nahi.

**RLHF is list mein nahi hai.** Woh 12–18 mahine door hai (§3.9).
**LangGraph #13 pe hai**, aur woh alag process hai.
**RAG #14 pe hai**, optional, aur child path ko chhoota bhi nahi.

---

## 9. Numbers

### 9.1 Latency (`backend-architecture.md` §1.1 ke against)

| Path | LLM? | Estimate | Budget p95 |
|---|---|---|---|
| CT input — tap, ADVANCE | Nahi | ~10 ms | 150 ms ✅ |
| CT input — RE_EXPLAIN L3/L5 (template) | Nahi | ~12 ms | 150 ms ✅ |
| CT input — RE_EXPLAIN L1/L2/L4 | Haan | ~1.1 s | 2.5 s ✅ |
| CT input — voice, enhancer band | Haan | ~1.4 s | 2.5 s ✅ |
| PG plan generate | Haan (copy) | ~1.2 s | 3 s ✅ |
| PG plan read (frozen) | Nahi | ~15 ms | 300 ms ✅ |
| Bandit choose | Nahi | ~1 ms | — |
| **Har cheez `LLM_PROVIDER=none` pe** | — | **~10–15 ms** | ✅ |

### 9.2 LLM calls per session

| Kahan | Calls |
|---|---|
| PG greet + plan copy | 2 |
| CT rung L1/L2/L4 | ≤4 |
| Idle rung 3 | ≤2 |
| Doubt | ≤3 |
| CLOSE recap | 1 |
| **Total** | **≈12** — budget exactly (§1.4) |

**Zero calls:** first-try correct · auto-advance · L3/L5 · idle 1/2/4/5 · branch · autopilot ·
plan selection · mastery · unlock · certificate · bandit.

### 9.3 Data — bandit ko kitna chahiye

| | |
|---|---|
| Context buckets (realistic) | ~120 |
| Arms per bucket | 3–5 |
| Cold start threshold | 30 pulls/bucket |
| **Signal se pehle chahiye** | **~4,000 explanation events** |
| 6,000 DAU pe (~2 re-explains/child/day) | **~1 din** |
| 100 pilot children pe | **~3 hafte** |

**Yahi wajah hai ki bandit realistic hai aur RLHF nahi.** Bandit 3 hafte ke pilot pe kaam karta
hai. RLHF ko 10,000+ human-ranked pairs chahiye — woh 100 children se **kabhi nahi** aayenge.

### 9.4 RAG jo bachaya

| | |
|---|---|
| Vector DB (managed) | $70–200/mo |
| Embedding calls | $20–50/mo |
| Re-index pipeline | ~1 din/mahina eng time |
| **Kya milta** | Ek dict lookup ka slower, galat-ho-sakne wala version |
| **Bachaya** | **~$1,500/saal + ek poora failure mode** |

---

## 10. Ek nazar mein

### ✅ KARO

| | Kyun |
|---|---|
| **Do agents banao** — Planner-Guide + Class Teacher | Aapka instinct sahi tha. Concerns alag hain. |
| Dono ka core **deterministic** rakho | Testable, reproducible, safe |
| **Branch engine ek pure function** | 6 outcomes, fixed priority, 100-run determinism test |
| **Explanation ladder L1–L5**, ek session mein rung repeat nahi | "Dobara samjhao" ka asli implementation |
| **Authored variant bank** (analogies, sentence frames) | Variety bina invention ke |
| **Contextual bandit** variants pe | Aapka "feedback se seekho" — safe version |
| **Human review** har naye variant pe | Poora doc isi ek line pe khada hai |
| **11-step validation** har LLM output pe | Answer-leak + repeat-guard + shame |
| LangGraph **content studio mein** | Offline, human-gated — sahi fit |
| RAG **parent KB mein** (agar chahiye) | Adult, open-domain, low stakes |

### ❌ MAT KARO

| | Kyun |
|---|---|
| **RLHF child-correctness pe** | Aap cheating teacher train kar loge. §3.5 |
| LLM se **rung ya branch chunwana** | Non-deterministic pedagogy = untestable product |
| LLM se **live analogy invent karwana** | Culturally galat, misconception paida karta hai |
| **LangGraph hot path pe** | Do sources of truth, latency, aur LLM ko hot path pe bulawa |
| **RAG child path pe** | Aapke paas primary key hai. Silent wrong retrieval khatarnaak hai. |
| **Bandit se rung chunwana** | Pedagogy experiment ka subject nahi hai |
| **Real-time bandit update** | Ek bachche ka jawab doosre ka content badal dega. Nightly. |
| **Evaluator ko "smart" banana** | `activity_evaluators.py` sabse bharosemand file hai. Haath mat lagao. |

### Teen line ka jawab

> 1. **Do agents — haan**, par woh *ownership boundaries* hain, autonomous LLM loops nahi.
> 2. **RLHF — nahi.** Aapko **Contextual Bandit over authored variants** chahiye. Woh 90%
>    faayda deta hai, 3 hafte mein kaam karta hai, aur cheat nahi kar sakta.
> 3. **LangGraph aur RAG — classroom mein nahi, back office mein haan.** Bachche ke path pe
>    boring, deterministic, aur testable jeet ta hai. Woh 3-saal ka bachcha aapki galti
>    report nahi kar sakta — isliye galti hone hi mat do.

---

*Companion: `docs/AI-100-PERCENT-AUTOMATION.md`. Yeh doc uske §3 (Conductor), §4 (Explanation
Engine) aur §10 (LLM Contract) ko implement-level pe kholta hai, aur RLHF / LangGraph / RAG ke
faisle unke saath consistent hain.*
