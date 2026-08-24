# AGENT FLOW — Agents Decide, Envelope Protects

### Saksham IQ · Agentic Architecture & Complete Flow Specification

**Repo:** `D:\testcase`
**Version:** 1.0 · 2026-08-19
**Companions:** `docs/AI-100-PERCENT-AUTOMATION.md` · `docs/AI-ARCHITECTURE-DECISIONS.md`

---

## 0. Aapka faisla, aur maine kya kiya

Aapne kaha: **"Agents ko decision ke liye rakhunga."** Theek hai — aapka product hai, aapka call.

Toh maine yeh doc us tarah nahi likha ki aapko manaun. Maine yeh likha hai taaki agar agents
faisle le rahe hain, toh woh **theek se** lein. Iska matlab teen cheezein:

1. **Agents ko sach mein faisla dena.** Ek agent jo sirf template chunta hai, agent nahi hai.
   Yahan Planner Agent plan *banata* hai aur Teacher Agent branch, rung, variant, scaffold aur
   UI *chunta* hai. Yeh asli faisle hain.
2. **Ek Envelope banana jo veto kar sake.** Agent jo bhi chune, kuch invariants nahi tootenge.
   Yeh agent pe bharosa na hone ki baat nahi — yeh us cheez ka standard practice hai jahan
   user galti report nahi kar sakta.
3. **Deterministic engine ko fallback + baseline ke roop mein rakhna.** Agent timeout ho,
   invalid de, budget khatam ho — engine chal jaata hai. Aur usi engine ke against aap
   naap paoge ki agent sach mein behtar hai ya nahi.

**Ek line jo main abhi bhi bolunga, aur phir aage badh jaaunga:**

> Agent *pedagogy* decide kare — bilkul.
> Agent *correctness, stars, unlock, certificate* decide kare — nahi.
>
> Yeh meri pasand nahi hai, yeh aapke apne `CLAUDE.md` ka rule hai, aur yeh wo cheez hai
> jo parent ko bharosa deti hai. Agar kal ek parent poochhe *"mere bachche ko yeh star kyun
> mila?"* — aapke paas ek deterministic jawab hona chahiye, ek model ka mood nahi.

Baaki poora doc flow hai, jo aapne maanga.

---

## Contents

| § | Section |
|---|---|
| 1 | **Decision Boundary** — agent kya decide karega, kya nahi |
| 2 | **4-Layer Architecture** — Facts / Agents / Envelope / Render |
| 3 | **Agent 1: Planner** — tools, schema, envelope |
| 4 | **Agent 2: Teacher** — tools, schema, envelope |
| 5 | **THE FLOWS** — 9 flows, poore |
| 6 | **Envelope** — veto list, aur veto ke baad kya |
| 7 | **Contracts** — state, tools, schemas |
| 8 | **LangGraph** — verdict revised (ab haan) |
| 9 | **RAG** — verdict revised (tool lookup, vector nahi) |
| 10 | **Latency & Cost** — asli numbers, model choice |
| 11 | **Kaise pata chalega ki kaam kar raha hai** — A/B vs baseline |
| 12 | **Build order** |
| 13 | **Teen failure modes jo dekhni hain** |

---

## 1. Decision Boundary — teen buckets

Har faisla teen mein se ek bucket mein hai. Yeh table hi poore doc ka contract hai.

### 🟩 Bucket A — **Agent decide karega** (aapki demand, aur yeh sahi jagah hai)

| Faisla | Kaunsa agent | Kyun agent theek hai |
|---|---|---|
| Aaj kaunse 2 lessons | Planner | Composition problem hai, ek sahi jawab nahi hota |
| Lessons ka order | Planner | Context-dependent |
| Practice block ka shape | Planner | Trade-offs hain |
| Session kitni lambi | Planner | Bachche ka pattern padhna |
| Revise pehle ya baad mein | Planner | Judgement call |
| **Branch: aage badhun ya dobara samjhaun** | Teacher | **Aapki asli demand.** Yeh judgement hai. |
| **Kaunsa explanation rung (L1–L5)** | Teacher | Judgement |
| **Kaunsa analogy / example** | Teacher | Judgement |
| Scaffold ooncha ya neecha | Teacher | Judgement |
| Modality switch (voice→tap) | Teacher | Judgement |
| UI kitni simple ki jaaye | Teacher | Judgement |
| Kab kindly end karna hai | Teacher | Judgement |
| Prerequisite pe jaana hai ya nahi | Teacher | Judgement |
| Doubt ka jawab | Teacher | Open-ended |

**14 asli faisle agent ke paas hain.** Yeh cosmetic nahi hai — yeh poori teaching policy hai.

### 🟥 Bucket B — **Kabhi agent nahi** (deterministic facts)

| Faisla | Kahan | Kyun kabhi nahi |
|---|---|---|
| Jawab sahi hai ya galat | `activity_evaluators.py` | Ek sahi jawab hota hai. Judgement nahi hai. |
| Mastery ka number | EWMA (OP-05) | Arithmetic hai |
| Kitne stars mile | `learning_service` | Parent ko explain karna padta hai |
| Topic unlock hua ya nahi | `learning_service` | Wahi |
| Certificate eligible hai ya nahi | `child_service` | Wahi |
| Ownership (yeh bachcha is parent ka hai?) | `owned_child` | Security |
| Consent hai ya nahi | `consent_records` | Legal |

**Yeh saat cheezein hi wo hain jinpe poora product ka bharosa tika hai.** Baaki sab agent ke paas hai.

### 🟨 Bucket C — **Agent decide karta hai, Envelope veto kar sakta hai**

Agent ka faisla default hai. Envelope sirf tab bolti hai jab ek invariant toot raha ho.

| Invariant | Agent ne agar toda | Envelope kya karti hai |
|---|---|---|
| `attempts_on_current ≤ 4` | 5th baar wahi question | `END_KINDLY` force |
| Explanation mein answer nahi | "Circle tap karo" | Template se replace |
| Ek session mein rung repeat nahi | L2 dobara | Agla unused rung force |
| `choices_shown ≥ 2` | 1 option | 2 pe clamp |
| `touch_target ≥` band floor | 48px early mode mein | 96px pe clamp |
| Koi shaming shabd nahi | "Tumne galat kiya" | Template se replace |
| Locked / unavailable topic nahi | `available: false` topic plan mein | Plan reject, regenerate |
| Hindi topic pe Devanagari | Roman Hindi | Template se replace |
| Session ≤ target × 1.25 | 30 min plan 8 min ke bachche ko | Trim |
| AI budget ≤ 12/session | 15th call | Template |
| Deadline 2.5 s | Agent 4 s le raha hai | Deterministic engine |

**Note kijiye envelope kya *nahi* karti:** woh agent ko *sikhati* nahi, *argue* nahi karti,
aur kabhi bachche ko error nahi dikhati. Woh chup-chaap ek safe cheez pe clamp karti hai aur
**log karti hai**. Har veto ek metric hai — aur agar veto rate badh raha hai, toh yeh aapka
sabse zaroori signal hai ki prompt ya model badalna hai.

---

## 2. Architecture — 4 layers

```
┌─────────────────────────────────────────────────────────────────────┐
│  LAYER 4 — RENDER                                    Next.js / Expo │
│  Sirf dikhata hai. Kuch decide nahi karta. (R2)                     │
└────────────────────────────────▲────────────────────────────────────┘
                                 │ ConductorDirective
┌────────────────────────────────┴────────────────────────────────────┐
│  LAYER 3 — ENVELOPE                          app/agents/envelope.py │
│  Agent ka faisla lekar invariants check karti hai.                  │
│  Pass -> aage bhej do.   Fail -> clamp/replace + log.               │
│  DETERMINISTIC. Yeh khud ek agent NAHI hai.                         │
└────────────────────────────────▲────────────────────────────────────┘
                                 │ AgentDecision (structured)
┌────────────────────────────────┴────────────────────────────────────┐
│  LAYER 2 — AGENTS                                       app/agents/ │
│                                                                     │
│   ┌──────────────────┐              ┌──────────────────────┐        │
│   │ PLANNER AGENT    │              │  TEACHER AGENT       │        │
│   │ din mein 1 baar  │              │  har wrong answer /  │        │
│   │                  │              │  doubt / idle-3 pe   │        │
│   │ tools: 6         │              │  tools: 6            │        │
│   │ max steps: 8     │              │  max steps: 4        │        │
│   │ deadline: 8s     │              │  deadline: 2.5s      │        │
│   └────────┬─────────┘              └──────────┬───────────┘        │
│            │      LessonAssignment ───────────►│                    │
│            │◄──── LessonOutcome ───────────────┘                    │
│                                                                     │
│   FALLBACK (dono ke liye): deterministic engine.                    │
│   Timeout / invalid / budget-out -> engine chalta hai, chup-chaap.  │
└────────────────────────────────▲────────────────────────────────────┘
                                 │ tool calls (read-only)
┌────────────────────────────────┴────────────────────────────────────┐
│  LAYER 1 — FACTS                                  DETERMINISTIC     │
│                                                                     │
│  activity_evaluators · mastery EWMA · stars · unlock · certificate  │
│  curriculum_service · skill_graph · analogies · child_speech        │
│                                                                     │
│  Agents yahan se PADHTE hain. Agents yahan LIKH nahi sakte.         │
│  Postgres = sach.                                                   │
└─────────────────────────────────────────────────────────────────────┘
```

**Do rules jo yeh layering enforce karta hai:**

1. **Agent ke paas koi write tool nahi hai.** Agent padhta hai, faisla deta hai, structured
   output lautata hai. Likhna hamesha Envelope ke baad service karti hai. Iska matlab ek
   confused agent DB corrupt nahi kar sakta — worst case ek bekar teaching step de sakta hai,
   jo recoverable hai.
2. **Evaluate + mastery + commit agent ke chalne se PEHLE ho chuke hote hain.** Agent ko
   pehle se decided facts milte hain. Agent kabhi correctness ke beech mein nahi aata.

---

## 3. Agent 1 — PLANNER AGENT

> *"Aaj kya padhana hai, kis order mein, kitni der."*

### 3.1 Kab chalta hai

| Trigger | Frequency |
|---|---|
| Din ka pehla request (ya scheduled window) | **1 × per child per day** |
| Parent "regenerate" | max 1/day |
| Rest day | chalta hi nahi |

**Din mein ek baar. Isliye yeh agent ke liye sabse surakshit jagah hai** — latency budget
8 seconds hai, cost trivial hai, aur output frozen ho jaata hai.

### 3.2 Tools (sab read-only)

```python
get_child_state(child_id)      -> class, age_band, unlocked topics, current position, prefs
get_mastery(child_id)          -> [{skill_id, effective, band, attempts, last_at}]
get_revisit_queue(child_id)    -> [{skill_id, reason, due_on, interval_days}]
get_learner_profile(child_id)  -> avg_engaged_minutes, engagement_by_hour, avg_attempts
get_yesterday_plan(child_id)   -> plan + kaunse items incomplete the
get_candidate_lessons(child_id)-> SIRF unlocked + available + class-matched topics
                                  ← yahan hi lock enforce hoti hai. Agent locked topic
                                    dekh hi nahi sakta, isliye chun bhi nahi sakta.
```

**`get_candidate_lessons` sabse important tool hai.** Woh agent ko sirf legal choices deta hai.
Envelope se rokna behtar hai ki galat cheez pehle hi na dikhe. **Constrain the menu, not the diner.**

### 3.3 Output schema (forced structured output)

```json
{
  "reasoning": "Aditi ne kal shapes 2 attempts mein kiya, mastery 0.51 — learning band.
                circle revisit due hai. Toh revise pehle, phir shapes continue, phir naya
                letter. 8 min budget mein 3 blocks fit hote hain.",
  "target_minutes": 8,
  "items": [
    {"slot":1,"kind":"revise","skill_ids":["shape_circle"],"question_count":4,"reason":"due_revisit"},
    {"slot":2,"kind":"adventure","topic_id":"nur_maths_shapes","reason":"continue"},
    {"slot":3,"kind":"adventure","topic_id":"nur_eng_letter_b","reason":"new_skill"},
    {"slot":4,"kind":"practice","skill_ids":["shape_circle","letter_B"],"question_count":6}
  ],
  "copy": {"title":"Gol aur B ka din!","intro":"Kal humne shapes dekhe. Aaj B se milte hain!"}
}
```

`reasoning` field ko **log kiya jaata hai, bachche ko kabhi nahi dikhaya jaata.** Yeh aapka
debugging aur audit trail hai — agar plan ajeeb lage, aapke paas agent ki soch likhi hui hai.

### 3.4 Planner ki Envelope

| Check | Fail pe |
|---|---|
| Har `topic_id` `get_candidate_lessons` mein tha | Plan reject → retry once → deterministic plan |
| `plan_days` respect hua | Reject |
| `target_minutes` age band ke floor/ceiling mein | Clamp |
| Estimated time ≤ `target × 1.25` | End se trim |
| Kam se kam 1 adventure item | Deterministic plan |
| `copy.title ≤ 40`, `intro ≤ 120` | Truncate |
| Copy mein koi skill jo plan mein nahi | Template copy |
| Copy mein shaming / guilt / countdown | Template copy |
| Duplicate topic_id | Dedupe |
| Same child + same date | **Frozen** — dobara nahi chalega |

**Freeze rule sabse zaroori hai.** Ek agent har baar thoda alag plan dega. Agar plan har
refresh pe badla, bachche ko routine kabhi nahi milega. `UNIQUE (child_id, plan_date)` +
"generate once, then read" isko structurally rokta hai.

---

## 4. Agent 2 — TEACHER AGENT

> *"Yeh bachcha abhi atka hai. Ab kya karun?"*

### 4.1 Kab chalta hai — **aur kab bilkul nahi**

Yeh design ka sabse important faisla hai:

| Event | Agent chalta hai? | Kyun |
|---|---|---|
| **Correct, first try** | ❌ **NAHI** | 10 ms mein auto-advance. Sahi jawab pe bachche ko soch nahi, "haan!" chahiye. Yahan agent lagana app ko sust bana dega bina kuch faayde ke. |
| Correct, 2+ attempts | ⚠️ Optional | Teaching moment hai. Chahein toh chalao. |
| **Wrong answer** | ✅ **HAAN** | **Yahi asli kaam hai.** |
| Doubt / haath uthana | ✅ HAAN | Open-ended |
| Idle rung 3 | ✅ HAAN | Re-explain chahiye |
| Idle rung 1,2,4,5 | ❌ NAHI | Template ladder |
| Activity load | ❌ NAHI | Authored prompt + TTS |
| Lesson close | ⚠️ Optional | Recap copy |

**Natija:** ek 6-activity lesson mein agent typically **2–4 baar** chalega, 40 nahi.
Ek achha kar raha bachcha agent ko lagbhag kabhi trigger nahi karega — jo bilkul sahi hai.
**Agent atke hue bachche ke liye hai.**

### 4.2 Tools (sab read-only)

```python
get_turn_context()            -> phase, activity prompt/hint/options (ANSWER KE BINA),
                                 attempts, latency, scaffold, modality, minutes_in_session
get_skill_state(skill_id)     -> mastery, band, attempts_total, last_attempt_at
get_prerequisites(skill_id)   -> skill_graph se: requires[], unki mastery ke saath
get_explanation_history()     -> is session mein kaunse rungs/variants use ho chuke +
                                 exact text jo bola gaya (repeat rokne ke liye)
get_analogies(skill_id, lang) -> authored analogy bank, age band se filtered
get_recent_answers(n=6)       -> bachche ke pichhle jawab (patterns dekhne ke liye)
```

> **`get_turn_context` correct_answer aur accepted_answers kabhi nahi lautata.**
> Yeh R6 hai, aur aapke apne code mein `ANSWER_KEY_FIELDS` yeh already karta hai.
> Agent ko *pata* hai ki bachcha galat tha (fact diya gaya hai) — par sahi jawab kya tha,
> woh nahi. Isliye agent chahe toh bhi answer nahi bata sakta.

### 4.3 Output schema

```json
{
  "reasoning": "Do baar galat. Dono baar 'square' tap kiya — corner wali shape se confuse
                ho raha hai, ginti se nahi. L2 (concretise) ne pehle kaam nahi kiya kyunki
                woh abstract tha. L4 contrast use karun: gol vs kona side by side.",
  "diagnosis": "misconception:corners_vs_round",
  "decision": "RE_EXPLAIN",
  "rung": "L4",
  "variant_id": 2,
  "scaffold_level": 3,
  "modality": "tap",
  "presentation": {"choices_shown": 2, "touch_target_px": 120, "decoration": "off"},
  "message": "Yeh gol hai — koi kona nahi. Isme kone hain. Gol wale ko chhuo!",
  "visual_action": {"type": "dim_others", "targets": ["visual-item-1"]},
  "avatar_state": "encouraging"
}
```

**`diagnosis` field naya hai aur bahut kaam ka hai.** Agent ko ek misconception *naam* dena
padta hai. Yeh do cheezein deta hai: (a) agent ka reasoning grounded rehta hai, (b) aapko
aggregate data milta hai — "37% nursery bachche `corners_vs_round` pe atakte hain" ek
**curriculum insight** hai jo aapko aaj nahi milta.

### 4.4 Teacher ki Envelope

| Check | Fail pe |
|---|---|
| `decision` 6 mein se ek | `RE_EXPLAIN` default |
| `attempts_on_current ≥ 4` par decision `END_KINDLY` nahi | **`END_KINDLY` force** |
| `rung` `explanation_history` mein already hai | Agla unused rung force |
| Saare rungs khatam | `END_KINDLY` force |
| `variant_id` bank mein exist karta hai | Bank se pehla variant |
| `message` mein correct answer (normalised) | Template se replace |
| `message` mein shaming lexicon | Template se replace |
| `message` pichhle se >0.85 similar | Agla rung force |
| `message` word limit se lamba | Word boundary pe truncate |
| Language script topic se match | Template se replace |
| `scaffold_level` 2+ step jump | 1 step pe clamp |
| `choices_shown < 2` | 2 pe clamp |
| `touch_target_px <` band floor | Floor pe clamp |
| `visual_action.targets` allowlist mein | Drop kar do |
| `PREREQUISITE` chuna par koi prereq weak nahi | `RE_EXPLAIN` pe downgrade |
| Deadline 2.5 s | **Deterministic branch engine** |

**Sabse pehli line: attempt cap.** Chahe agent kitna bhi convinced ho ki "ek aur try se
ho jaayega" — 4 ke baad nahi. Ek 3-saal ka bachcha jo 5 baar fail hua hai, seekh raha hai
ki seekhna bura lagta hai. **Yeh ek aisi invariant hai jise agent kabhi override nahi karega.**

---
## 5. THE FLOWS

Nau flows. Yeh section hi aapka asli maanga hua hissa hai.

### 5.1 Flow 1 — Poora din

```
   ┌─ 16:30, parent ke study window mein ─────────────────────────────┐
   │  Notification: "Aditi ka learning time!"  (parent ke device pe)  │
   └──────────────────────────────┬───────────────────────────────────┘
                                  ▼
                         Bachcha app kholta hai
                                  ▼
                    GET /api/v1/conductor/{child_id}/open
                                  ▼
              ┌──────────────────────────────────────────┐
              │  Aaj ka plan already hai?                │
              └───────┬──────────────────────┬───────────┘
                  HAAN│                      │NAHI
                      │                      ▼
                      │        ╔═══════════════════════════════╗
                      │        ║   PLANNER AGENT chalta hai    ║
                      │        ║   6 tools, max 8 steps, 8s    ║
                      │        ║   → plan + copy               ║
                      │        ╚═══════════════╤═══════════════╝
                      │                        ▼
                      │              ENVELOPE (§3.4)
                      │              pass? → freeze karo
                      │              fail? → retry 1x → deterministic plan
                      │                        ▼
                      │              INSERT daily_plans
                      │              UNIQUE(child_id, plan_date)
                      ▼                        ▼
              ┌──────────────────────────────────────────┐
              │  GREET  — "Namaste Aditi! Kal humne      │
              │  shapes dekhe. Aaj gol aur B ka din!"    │
              │  ▶ (bada)      😴 (chhota)               │
              └──────────────────┬───────────────────────┘
                                 │ 5 s ya ▶ tap
                                 ▼
              ┌──────────────────────────────────────────┐
              │  slot 1 → LessonAssignment → CT          │
              └──────────────────┬───────────────────────┘
                                 ▼
                    ╔═══════════════════════════╗
                    ║   LESSON LOOP  (§5.2/5.3) ║ ◄──┐
                    ╚═════════════╤═════════════╝    │
                                  ▼                  │
                          LessonOutcome              │
                                  ▼                  │
                    ┌──────────────────────────┐     │
                    │ aur plan items bache?    │─YES─┘
                    └───────────┬──────────────┘   (slot 2, 3, 4)
                                │ NO
                                ▼
                    ┌──────────────────────────┐
                    │  CLOSE (§5.8)            │
                    │  recap · celebrate ·     │
                    │  "kal milte hain"        │
                    │  aur koi CTA nahi        │
                    └──────────────────────────┘
```

**Planner Agent din bhar mein exactly ek baar chala.** Plan frozen hai — refresh, re-login,
back button, kuch bhi use nahi badalta.

---

### 5.2 Flow 2 — Turn: **SAHI jawab** (agent chalta hi nahi)

Yeh sabse common path hai — ~70% turns. **Yahan koi agent nahi hai, aur yeh jaanboojh kar hai.**

```
  Bachcha "circle" tap karta hai
        │
        ▼  POST /conductor/sessions/{id}/input
  ┌─────────────────────────────────────────────────────┐
  │ 1. lesson_states SELECT ... FOR UPDATE      [D] 2ms │
  │ 2. activity_evaluators.evaluate()           [D] 1ms │  → correct
  │ 3. mastery EWMA update                      [D] 1ms │
  │ 4. stars += 3                               [D]     │
  │ 5. attempts row INSERT                      [D]     │
  │ 6. ═══ COMMIT ═══                               2ms │
  │ 7. attempts_on_current == 0 (first try)?            │
  │       HAAN → decision = ADVANCE, koi agent nahi [D] │
  │       NAHI → optional agent (§4.1)                  │
  │ 8. praise = static pool se pick             [D] <1ms│
  │ 9. agli activity load                       [D] 1ms │
  │10. scaffold −1 (fade)                       [D] <1ms│
  └─────────────────────────────────────────────────────┘
        │  TOTAL: ~9 ms
        ▼
  ConductorDirective { auto_advance_in_ms: 800, ... }
        │
        ▼
  Client: ⭐ star burst → 800 ms → agli activity
        │
        ▼
  Bachcha ne kuch tap nahi kiya. "Next" button hai hi nahi.
```

**Kyun yeh important hai:** agar aap correct path pe bhi agent chalate, toh har sahi jawab ke
baad 1.5 second ka silence aata. Ek 3-saal ka bachcha us silence mein screen se hat jaata hai.
**Agent ko wahan lagao jahan sochne ki zaroorat hai.**

---

### 5.3 Flow 3 — Turn: **GALAT jawab** ← **yeh main flow hai**

```
  Bachcha "square" tap karta hai (galat)
        │
        ▼  POST /conductor/sessions/{id}/input
┌───────────────────────────────────────────────────────────────────────┐
│ PHASE 1 — FACTS  (deterministic, agent se pehle)                      │
│                                                                       │
│  1. lesson_states LOCK                                    [D]    2 ms │
│  2. voice tha? → child_speech_service clean                [D]        │
│       0.30–0.80 band → enhancer (answer key ke bina)      [LLM] 300ms │
│  3. evaluate() → INCORRECT                                 [D]    1 ms │
│  4. mastery EWMA update (outcome 0.0)                      [D]    1 ms │
│  5. attempts_on_current += 1  → ab 2                       [D]        │
│  6. attempt row INSERT                                     [D]        │
│  7. ═══ COMMIT ═══   ← BACHCHE KA SACH SAVE HO GAYA           2 ms   │
└───────────────────────────────────┬───────────────────────────────────┘
                                    │
        ┌───────────────────────────┴──────────────────────────┐
        │  8. INSTANT ACK bhejo — agent ka intezaar mat karo   │
        │     "Hmm, chalo phir se dekhte hain..."       [D] 0ms │
        │     Client bolna shuru kar deta hai. Silence zero.   │
        └───────────────────────────┬──────────────────────────┘
                                    ▼
╔═══════════════════════════════════════════════════════════════════════╗
║ PHASE 2 — TEACHER AGENT              max 4 steps · deadline 2.5 s     ║
║                                                                       ║
║   step 1  get_turn_context()                                          ║
║           → "attempt 2, 'square' tap kiya, prompt 'Tap the circle',   ║
║              hint 'Round, no corners', options [circle, square,       ║
║              triangle], scaffold S2, mode tap"                        ║
║              (correct_answer NAHI diya gaya)                          ║
║                                                                       ║
║   step 2  get_explanation_history()                                   ║
║           → "L1 use ho chuka: 'Circle dhoondho, gol hota hai'"        ║
║                                                                       ║
║   step 3  get_recent_answers(6)                                       ║
║           → "dono baar 'square'. random nahi — pattern hai."          ║
║                                                                       ║
║   step 4  get_analogies("shape_circle", "hi")                         ║
║           → [गेंद, रोटी, चूड़ी]                                        ║
║                                                                       ║
║   AGENT DECIDES:                                                      ║
║     diagnosis  = "misconception:corners_vs_round"                     ║
║     decision   = RE_EXPLAIN                                           ║
║     rung       = L4  (contrast — kyunki L1 fail hua aur galti         ║
║                       systematic hai, random nahi)                    ║
║     scaffold   = S3  (S2 se ek step upar)                             ║
║     choices    = 2   (triangle hata do)                               ║
║     message    = "Yeh gol hai — koi kona nahi. Isme kone hain.        ║
║                   Gol wale ko chhuo!"                                 ║
╚═══════════════════════════════════╤═══════════════════════════════════╝
                                    ▼
┌───────────────────────────────────────────────────────────────────────┐
│ PHASE 3 — ENVELOPE                                          [D] 2 ms  │
│                                                                       │
│   attempts (2) ≤ 4 ..................................... ✅ pass      │
│   decision 6 mein se ek ................................ ✅ pass      │
│   rung L4 history mein nahi ............................ ✅ pass      │
│   message mein "circle"/"गोल" answer form? .............. ✅ pass*    │
│       (*"gol wale ko chhuo" ek instruction hai,                       │
│         answer reveal nahi — normalised compare pass)                 │
│   shame lexicon ........................................ ✅ pass      │
│   pichhle message se similarity 0.31 < 0.85 ............ ✅ pass      │
│   scaffold jump 1 step ................................. ✅ pass      │
│   choices 2 ≥ 2 ........................................ ✅ pass      │
│   touch target 120 ≥ 96 (early floor) .................. ✅ pass      │
│   Devanagari for hi .................................... ✅ pass      │
│                                                                       │
│   SAB PASS → agent ka faisla waisa ka waisa chalta hai                │
└───────────────────────────────────┬───────────────────────────────────┘
                                    ▼
┌───────────────────────────────────────────────────────────────────────┐
│ PHASE 4 — PERSIST + RENDER                                            │
│   lesson_states UPDATE: rung=L4, explanations_used += L4,             │
│                         scaffold=3, presentation cached               │
│   ConductorDirective bhejo                                            │
└───────────────────────────────────┬───────────────────────────────────┘
                                    ▼
   Bachcha dekhta hai: sirf 2 options (bade), triangle gaayab,
   square dim, Pip bolta hai "Yeh gol hai — koi kona nahi..."

   Total: ~1.4 s — jismein se PEHLA 0 ms silence tha (instant ack).
```

**Isme dhyan dene layak teen cheezein:**

1. **Truth commit ho chuka tha agent chalne se pehle.** Agent crash ho jaaye, timeout ho
   jaaye, kuch bhi — bachche ka attempt aur mastery safe hai.
2. **Instant ack ne latency ka problem khatam kar diya.** Bachcha 0 ms pe awaaz sunta hai.
   Agent 1.4 s mein aata hai, jab tak Pip filler bol chuka hai. Silence kabhi nahi.
3. **Agent ne sach mein faisla liya** — L4 chuna kyunki L1 fail hua tha aur galti systematic
   thi. Ek deterministic ladder `min(L1+attempts, L5)` se L3 chunta. Agent behtar chuna.
   **Yeh hai woh cheez jo aap maang rahe the.**

---

### 5.4 Flow 4 — Agent ka andar ka loop (bounded ReAct)

```
   ┌─────────────────────────────────────────────────────────┐
   │  ENTER: turn context + system prompt + tool schemas     │
   │  budget: max_steps=4 · deadline=2500ms · tokens=1200    │
   └───────────────────────┬─────────────────────────────────┘
                           ▼
              ┌────────────────────────┐
    ┌────────►│  MODEL: soch + action  │
    │         └───────────┬────────────┘
    │                     │
    │        ┌────────────┴───────────┐
    │        │                        │
    │    tool_call              final_answer
    │        │                        │
    │        ▼                        ▼
    │  ┌──────────────┐      ┌──────────────────┐
    │  │ tool allowed?│      │ schema valid?    │
    │  │  NAHI → err  │      │  NAHI → 1 retry  │
    │  │  HAAN → run  │      │  HAAN → EXIT ✅  │
    │  └──────┬───────┘      └──────────────────┘
    │         ▼
    │  ┌──────────────┐
    │  │ steps < 4?   │─── NAHI ─────┐
    │  └──────┬───────┘              │
    │      HAAN                      │
    └─────────┘                      ▼
                          ┌─────────────────────────┐
                          │  ABORT                  │
                          │  → deterministic engine │
                          │  → log agent_abort      │
                          │  Bachche ko farq nahi   │
                          │    dikhta               │
                          └─────────────────────────┘

   Har exit path pe deadline watchdog parallel chal raha hai:
   2500 ms → cancel → deterministic engine → log agent_timeout
```

**Chaar guardrails jo is loop ko safe rakhte hain:**

| Guard | Value | Kyun |
|---|---|---|
| `max_steps` | 4 | Ek stuck agent budget nahi kha sakta |
| `deadline` | 2500 ms | Bachcha intezaar nahi karega |
| Tool allowlist | 6 tools, sab read-only | Agent kuch tod nahi sakta |
| Schema retry | 1 | Ek retry theek hai, teen nahi |

**Aur fallback hamesha maujood hai.** Isliye deterministic branch engine banana **zaroori hai**,
chahe agents primary hon. Woh aapka floor hai.

---

### 5.5 Flow 5 — Two-Stage Response (latency ka asli hal)

Ek 3-saal ka bachcha 1.5 second silence mein screen se hat jaata hai. Yeh us problem ka hal
hai, aur yeh sabse practical trick है is poore doc mein.

```
   t=0 ms      Bachche ne galat tap kiya
                    │
   t=0 ms      ┌────▼────────────────────────────────────────┐
               │ STAGE 1 — INSTANT (deterministic, 0 LLM)    │
               │                                             │
               │  • Gentle "hmm" sound                        │
               │  • Pip "thinking" state pe jaata hai         │
               │  • Ek chhoti filler line, attempt-aware:     │
               │      attempt 1 → "Ohho, chalo phir se!"      │
               │      attempt 2 → "Hmm, saath dekhte hain..." │
               │      attempt 3 → "Koi baat nahi, aasan       │
               │                   karte hain..."             │
               │  • Galat option halke se dim ho jaata hai    │
               │                                             │
               │  Bachcha: turant response feel karta hai     │
               └─────────────────────────────────────────────┘
                    │
   t≈150 ms    Filler bolna shuru (TTS ~1.2 s chalega)
                    │
   t≈1400 ms   ┌────▼────────────────────────────────────────┐
               │ STAGE 2 — AGENT (filler ke khatam hote hi)   │
               │                                             │
               │  • Asli teaching step                        │
               │  • UI change (2 options, bade)               │
               │  • Visual action (dim_others)                │
               └─────────────────────────────────────────────┘

   Bachche ka anubhav: ek hi lagatar teacher. Koi ruk nahi.
```

**Filler lines rotate karti hain (`already_said` mein jaati hain) taaki woh khud repetitive
na lagein.** Aur agar agent 2.5 s se pehle aa gaya, filler beech mein kaat di jaati hai —
natural interruption, jaise ek asli teacher karta hai.

**Yeh pattern agents ko production mein possible banata hai.** Iske bina 1.4 s ka silence
har galat jawab pe aata, aur bachche ka focus toot jaata.

---

### 5.6 Flow 6 — Doubt / haath uthana

```
   Bachcha 🖐 tap karta hai ya bolta hai "yeh kya hai?"
        │
        ▼
   ┌────────────────────────────────────────────┐
   │ 1. lesson PAUSE — unmount NAHI      [D]    │
   │    lesson_states.paused_for = "doubt"      │
   │    resume_payload = { activity_index, ... }│
   └────────────────┬───────────────────────────┘
                    ▼
   ┌────────────────────────────────────────────┐
   │ 2. Pip: "Haan bolo, main sun raha hoon!"[D]│
   │    mic khulta hai (TTS band — barge-in lock)│
   └────────────────┬───────────────────────────┘
                    ▼
   ┌────────────────────────────────────────────┐
   │ 3. Speech → deterministic clean     [D]    │
   └────────────────┬───────────────────────────┘
                    ▼
   ╔════════════════════════════════════════════╗
   ║ 4. TEACHER AGENT — doubt mode              ║
   ║    Extra tool: get_curriculum_fact(topic)  ║
   ║    Rules jo prompt mein hard hain:          ║
   ║      • correct_answer nahi diya gaya       ║
   ║      • curriculum ke andar raho            ║
   ║      • ≤ 20 shabd                          ║
   ║      • bahar ka sawaal → gently wapas      ║
   ╚════════════════┬═══════════════════════════╝
                    ▼
   ┌────────────────────────────────────────────┐
   │ 5. ENVELOPE + extra doubt checks    [D]    │
   │    answer leak · off-curriculum · safety   │
   └────────────────┬───────────────────────────┘
                    ▼
   ┌────────────────────────────────────────────┐
   │ 6. Jawab bolo                              │
   │ 7. "Chalo wapas chalte hain!"              │
   │ 8. RESUME — resume_payload se EXACT wahi   │
   │    activity, wahi attempt, wahi scaffold   │
   └────────────────────────────────────────────┘

   Budget: max 3 doubt turns/session. Uske baad:
   "Bahut achhe sawaal! Pehle yeh khatam karein, phir baat karte hain."
```

**Doubt mode mein agent sabse khula hai — aur envelope sabse sakht.** Kyunki yahi ek jagah
hai jahan bachcha kuch bhi poochh sakta hai.

---

### 5.7 Flow 7 — Idle (bachcha chup hai)

Timers `experience_modes[*].idle_thresholds_seconds` se aate hain — manifest se, hardcoded nahi.

```
   next_input.timeout_ms se client timer chalata hai
   Har input pe reset

   ┌────────┬──────────────────────────────────┬─────────┐
   │ Rung   │ Kya hota hai                     │ Agent?  │
   ├────────┼──────────────────────────────────┼─────────┤
   │ 1  12s │ Instruction jaisi thi waisi      │  ❌ [D] │
   │ 2  25s │ Authored hint + target highlight │  ❌ [D] │
   │ 3  40s │ RE-EXPLAIN — nayi taraah se      │  ✅ AGENT│
   │ 4  60s │ demo_tap — "saath karte hain"    │  ❌ [D] │
   │ 5  80s │ "kuch aasan karein?" — offer     │  ❌ [D] │
   └────────┴──────────────────────────────────┴─────────┘

   Rung 5 ke baad koi bhi input nahi → END_KINDLY, warm close.
   Bachcha kabhi phansa nahi rehta. (R7)
```

**Paanch mein se sirf ek rung agent hai.** Yeh isliye ki idle ladder har screen pe chalta hai —
agar har rung agent hota, ek chup baitha bachcha 5 LLM call kha jaata aur session ka poora
budget khatam ho jaata.

---

### 5.8 Flow 8 — Lesson aur session close

```
   BRANCH → decision jo lesson khatam karta hai
   (ADVANCE + koi activity nahi bachi, ya END_KINDLY, ya time)
        │
        ▼
   ┌────────────────────────────────────────────┐
   │ 1. Score, stars, unlock compute      [D]   │
   │    ← AGENT KABHI NAHI. Bucket B.           │
   │ 2. Certificate eligibility check     [D]   │
   │ 3. revisit_queue mein skills daalo   [D]   │
   │ 4. learning_memory record            [D]   │
   │ 5. COMMIT                                  │
   └────────────────┬───────────────────────────┘
                    ▼
   ┌────────────────────────────────────────────┐
   │ 6. LessonOutcome → PLANNER                 │
   │ 7. Plan mein aur item bache?               │
   │      HAAN → agla LessonAssignment (§5.1)   │
   │      NAHI → session close                  │
   └────────────────┬───────────────────────────┘
                    ▼
   ┌────────────────────────────────────────────┐
   │ 8. RECAP — 3 cheezein jo aaj seekhi   [D]  │
   │    (mastery deltas se, agent se nahi)      │
   │ 9. Recap ke shabd                  [AGENT] │
   │    optional — template fallback hai        │
   │10. Celebrate — stars, badge          [D]   │
   │11. "Kal milte hain."                       │
   │                                            │
   │    ← AUR KUCH NAHI. Koi "ek aur?" nahi.    │
   │      Koi streak pressure nahi.             │
   │      Koi CTA nahi.                         │
   └────────────────────────────────────────────┘
```

**Step 8 aur 9 ka farq zaroori hai:** *kya* seekha yeh deterministic hai (mastery deltas).
*Kaise bolna hai* woh agent hai. Agent recap invent nahi kar sakta.

---

### 5.9 Flow 9 — Jab cheezein tootein (degradation)

```
   ┌──────────────────────────────────────────────────────────────┐
   │  AGENT TIMEOUT (>2.5s)                                       │
   │    → deterministic branch engine                             │
   │    → bachche ko farq nahi dikhta                             │
   │    → log agent_timeout_total{agent="teacher"}                │
   ├──────────────────────────────────────────────────────────────┤
   │  AGENT INVALID SCHEMA (1 retry ke baad)                      │
   │    → deterministic engine                                    │
   │    → log agent_invalid_total                                 │
   ├──────────────────────────────────────────────────────────────┤
   │  ENVELOPE VETO                                               │
   │    → clamp / replace, baaki faisla rakho                     │
   │    → log envelope_veto_total{rule="attempt_cap"}             │
   │    → yeh HEALTHY hai kam maatra mein. >5% = prompt problem.  │
   ├──────────────────────────────────────────────────────────────┤
   │  AI BUDGET KHATAM (12/session)                               │
   │    → deterministic engine baaki session ke liye              │
   │    → lesson poora chalta hai                                 │
   ├──────────────────────────────────────────────────────────────┤
   │  LLM PROVIDER DOWN (circuit open)                             │
   │    → dono agents band                                        │
   │    → deterministic plan + deterministic branch               │
   │    → PRODUCT POORA CHALTA HAI                                │
   ├──────────────────────────────────────────────────────────────┤
   │  TTS DOWN     → text + icon, early mode strict simplify      │
   │  STT DOWN     → tap-only, spoken activities tap-fallback pe  │
   │  DB DOWN      → read-only, naya session nahi, saaf message   │
   └──────────────────────────────────────────────────────────────┘
```

> **Isi wajah se deterministic engine banana optional nahi hai.**
> Woh agents ka competitor nahi — unka **floor** hai.
> Aur woh aapki **baseline** bhi hai (§11): uske bina aap kabhi prove nahi kar paoge ki
> agents sach mein behtar padha rahe hain.

---
## 6. Envelope — poori veto list

`app/agents/envelope.py`. **Deterministic. Yeh khud agent nahi hai** — ek agent ko guard karne
wala agent ka koi floor nahi hota.

### 6.1 Teen tarah ke veto

| Type | Kya karta hai | Example |
|---|---|---|
| **CLAMP** | Value ko legal range mein le aata hai, baaki faisla rakhta hai | `choices_shown: 1 → 2` |
| **REPLACE** | Ek field ko safe cheez se badalta hai | answer-leaking message → template |
| **OVERRIDE** | Poora decision badal deta hai | attempts 5 → `END_KINDLY` force |

### 6.2 Poori list, priority order mein

```
 #   RULE                                    TYPE       FAIL PE
───────────────────────────────────────────────────────────────────────────
 SAFETY — pehle, hamesha
 1   attempts_on_current ≤ 4                 OVERRIDE   END_KINDLY
 2   session_minutes ≤ target × 1.25         OVERRIDE   END_KINDLY
 3   shame lexicon absent                    REPLACE    template
 4   koi countdown / deadline / guilt copy   REPLACE    template
 5   koi PII solicitation                    REPLACE    template

 TRUTH — LLM ko star dene se rokna
 6   message mein correct_answer nahi        REPLACE    template
     (normalised, accepted_answers bhi)
 7   agent ne correctness override nahi ki   OVERRIDE   fact wapas
 8   agent ne stars/unlock nahi chhue        OVERRIDE   fact wapas

 PEDAGOGY — teaching ko theek rakhna
 9   rung explanation_history mein nahi      OVERRIDE   agla unused rung
10   message similarity < 0.85 vs already    OVERRIDE   agla rung
11   scaffold jump ≤ 1 step                  CLAMP      1 step
12   PREREQUISITE tabhi jab prereq weak      OVERRIDE   RE_EXPLAIN
13   rungs khatam                            OVERRIDE   END_KINDLY

 PRESENTATION — floors
14   choices_shown ≥ 2                       CLAMP      2
15   choices_shown ≤ band max                CLAMP      band max
16   touch_target ≥ band floor (96/64)       CLAMP      floor
17   text_density band se sakht nahi         CLAMP      band

 CONTENT — allowlists
18   variant_id bank mein exist karta hai    CLAMP      variant 0
19   visual_action.type approved list mein   REPLACE    none
20   visual_action.targets allowlist mein    CLAMP      drop
21   ui_action.target approved list mein     REPLACE    none
22   topic unlocked + available (planner)    OVERRIDE   plan reject

 LANGUAGE
23   script topic.language se match          REPLACE    template
24   word count ≤ band limit                 CLAMP      truncate

 BUDGET
25   AI calls ≤ 12/session, 200/child/day    OVERRIDE   deterministic
26   deadline ≤ 2500 ms                      OVERRIDE   deterministic
```

### 6.3 Har veto ek metric hai

```
envelope_veto_total{rule="attempt_cap",     agent="teacher"}
envelope_veto_total{rule="answer_leak",     agent="teacher"}
envelope_veto_total{rule="rung_repeat",     agent="teacher"}
envelope_veto_total{rule="locked_topic",    agent="planner"}
agent_timeout_total{agent="teacher"}
agent_invalid_total{agent="planner"}
```

**Yeh dashboard aapka sabse zaroori operational tool hai.** Padhne ka tareeka:

| Signal | Matlab | Karo |
|---|---|---|
| `answer_leak` > 1% | Prompt answer chupane pe kamzor hai | Prompt fix karo — **turant** |
| `attempt_cap` > 2% | Agent bachche ko phansa raha hai | Prompt mein exit ka zikr badhao |
| `rung_repeat` > 5% | Agent ko history dikh nahi rahi | Tool output ka format theek karo |
| `timeout` > 3% | Model bahut dheema | Chhota model, ya max_steps kam |
| Kuch bhi 0% hamesha | Rule dead ho sakta hai | Test se verify karo ki fire hota hai |

**Ek veto ek failure nahi hai** — woh system ka kaam karna hai. Par **trend** aapka sach hai.

---

## 7. Contracts

### 7.1 `lesson_states` — agent-aware version

`AI-100-PERCENT-AUTOMATION.md` §8.1 ke upar, agents ke liye chaar column:

```sql
-- agent decisions ka audit trail
last_agent_decision   JSONB      -- poora AgentDecision, reasoning ke saath
last_agent_source     TEXT       -- 'agent' | 'deterministic_fallback'
agent_calls_used      SMALLINT   -- session budget counter
envelope_vetoes       JSONB      -- [{rule, type, at}] — is session mein kya-kya veto hua
```

**`last_agent_source` bahut kaam ka hai:** aap analytics mein exactly alag kar sakte ho ki
agent-driven turns aur fallback turns mein learning outcome ka farq kya hai. **Yahi aapka
A/B ka natural experiment hai, bina alag se A/B banaye.**

### 7.2 `AgentDecision` — dono agents ke liye ek shape

```python
class AgentDecision(BaseModel):
    reasoning: str                          # logged, kabhi child ko nahi
    diagnosis: str | None = None            # "misconception:corners_vs_round"
    decision: Literal["ADVANCE","RE_EXPLAIN","SIMPLIFY",
                      "PREREQUISITE","SWITCH_MODALITY","END_KINDLY"]
    rung: Literal["L1","L2","L3","L4","L5"] | None
    variant_id: int | None
    scaffold_level: conint(ge=0, le=4)
    modality: Literal["tap","voice","trace"]
    presentation: Presentation
    message: str
    visual_action: VisualAction
    avatar_state: str
```

**Forced structured output** — Groq ka `response_format: {"type":"json_object"}` (aaj already
use ho raha hai) + Pydantic validation. Free text kabhi nahi.

### 7.3 Agents ke beech ka contract — badla nahi

```python
PLANNER ──LessonAssignment──► TEACHER
PLANNER ◄──LessonOutcome───── TEACHER
```

Shape wahi hai jo `AI-ARCHITECTURE-DECISIONS.md` §2.3 mein hai. **Agents andar se badal gaye,
unke beech ka contract nahi.** Yahi achhe contract ki nishaani hai.

### 7.4 File layout

```
backend/app/
├── agents/
│   ├── planner/
│   │   ├── agent.py          # loop
│   │   ├── tools.py          # 6 read-only tools
│   │   └── prompt.v1.txt
│   ├── teacher/
│   │   ├── agent.py
│   │   ├── tools.py          # 6 read-only tools
│   │   ├── prompt.v1.txt
│   │   └── prompt_doubt.v1.txt
│   ├── envelope.py           # 26 rules — DETERMINISTIC
│   ├── runtime.py            # bounded loop, deadline, retry, budget
│   └── schemas.py            # AgentDecision, PlanProposal
├── services/
│   ├── branch_engine.py      # DETERMINISTIC FALLBACK + BASELINE
│   ├── explanation_service.py# ladder, rungs, variants
│   ├── conductor_service.py  # state machine, agents ko call karta hai
│   └── plan_service.py       # deterministic plan fallback
```

**`branch_engine.py` abhi bhi bana raha hai, aur usme abhi bhi `app/agents/` ka import nahi
hai.** Woh ab primary nahi, fallback hai — par uski purity utni hi zaroori hai, kyunki woh
aapka floor aur baseline dono hai.

---

## 8. LangGraph — verdict revised

### 8.1 Maine apna jawab badla hai

Pichhle doc mein maine kaha tha "hot path pe nahi", aur us waqt wo sahi tha — kyunki design
mein ek 8-node deterministic machine thi.

**Aapne design badal diya. Ab agents sach mein tool-calling loops chala rahe hain, retry ho
rahe hain, multi-step reasoning ho rahi hai. Us duniya mein orchestration layer apni jagah
kamane lagta hai.**

**Naya verdict: HAAN, par sirf agent loop ke andar — poore Conductor pe nahi.**

### 8.2 Kahan haan, kahan nahi

```
┌──────────────────────────────────────────────────────────────┐
│ conductor_service.py — state machine                         │
│   → PLAIN PYTHON. LangGraph NAHI.                            │
│   Kyun: yeh transactional hai (SELECT FOR UPDATE ... COMMIT),│
│   iski state ek Postgres row hai, aur ise 150 ms mein        │
│   correct-answer path chalana hai. Yahan ek graph runtime    │
│   ghusane ka matlab hai transaction boundary ko ek framework │
│   ke andar chhupana. Woh galat trade hai.                    │
├──────────────────────────────────────────────────────────────┤
│ agents/teacher/agent.py — bounded ReAct loop                 │
│   → LangGraph THEEK HAI                                      │
│   4 steps, 6 tools, retry, deadline. Yeh sach mein graph hai.│
├──────────────────────────────────────────────────────────────┤
│ agents/planner/agent.py                                      │
│   → LangGraph THEEK HAI (aur behtar fit — 8 steps, offline)  │
├──────────────────────────────────────────────────────────────┤
│ tools/content_studio/ — authoring pipeline                   │
│   → LangGraph ka SABSE ACHHA use case                        │
└──────────────────────────────────────────────────────────────┘
```

### 8.3 Ek shart jo non-negotiable hai — checkpointer

Meri purani objection abhi bhi khadi hai, aur uska hal simple hai:

> **LangGraph ka checkpointer band rakho — ya use ephemeral rakho.**
>
> Ek turn ka agent loop **stateless** hai: state Postgres se aati hai, agent ek decision
> deta hai, decision Postgres mein jaata hai. Agent loop ke beech mein persist karne layak
> kuch hai hi nahi.
>
> ```python
> graph = builder.compile()            # ✅ koi checkpointer nahi
> graph = builder.compile(checkpointer=PostgresSaver(...))   # ❌ doosra sach
> ```
>
> Agar aap checkpointer laate ho, toh lesson ka sach do jagah ho jaata hai — `lesson_states`
> aur graph thread. Woh exactly wahi bug hai jo aap client se hata rahe ho
> (`TRACK-A` §2). **Ek turn = ek stateless agent invocation.**

### 8.4 Practical baat

| | |
|---|---|
| API service ke `requirements.txt` mein LangGraph? | Haan, par `langgraph` core hi — poora `langchain` nahi |
| Version pinning | Exact pin karo. Yeh tez badalta hai. |
| Kya aapko iski zaroorat hai? | **Nahi.** 4-step ReAct loop ~120 lines plain Python hai. |
| Kya isse madad milegi? | **Haan** — tracing, retry, streaming aur step limits mufт mein |
| Mera sujhav | **Plain Python se shuru karo (~120 lines). LangGraph tab lao jab teesra agent aaye ya loop 6+ steps ka ho jaaye.** Migration aasan hai; premature adoption ka undo mushkil hai. |

---

## 9. RAG — verdict revised

### 9.1 Agents ke saath ek cheez badal jaati hai

Deterministic design mein retrieval ki koi zaroorat hi nahi thi — pipeline ko exactly pata
tha usse kya chahiye.

**Ab agent khud decide karta hai usse kya jaanna hai.** Woh `get_analogies()` call karta hai,
`get_prerequisites()` call karta hai. **Yeh retrieval hai.**

Par yeh **tool-based lookup** hai, **vector search nahi**. Aur farq maayne rakhta hai:

| | Tool lookup | Vector RAG |
|---|---|---|
| Query | `get_analogies("shape_circle", "hi")` | embed("circle explanation") |
| Result | Exact bank entry | Approximate nearest neighbours |
| Galat ho sakta hai? | Nahi — key hai ya nahi hai | **Haan, chup-chaap** |
| Nursery query pe LKG content? | Namumkin | Mumkin |
| Debug | `KeyError` | "kyun yeh chunk aaya?" |
| Latency | 1 ms | 20–80 ms |
| Cost | 0 | embeddings + index |

### 9.2 Naya verdict

> **Child path pe: tool lookup HAAN, vector RAG NAHI.**
>
> Agent ke saare 6 tools deterministic lookups hain. Woh "retrieval" hain functional sense
> mein, aur woh 100% precise hain kyunki curriculum ke paas primary keys hain.
>
> Vector search **tabhi** justify hoti hai jab aapko na pata ho ki kaunsi key chahiye.
> Aapko hamesha pata hai — plan ne topic chuna, conductor ne activity chuni, skill graph ne
> prereq diya, analogy bank `skill_id` se keyed hai.

### 9.3 Kahan vector sach mein theek hai

| Use case | Vector? | Kyun |
|---|---|---|
| Agent ke 6 tools | ❌ | Primary keys hain |
| Doubt ka jawab | ⚠️ | Curated kids-FAQ set behtar hai. Poora **50–100 entries** ka hai — woh prompt mein fit ho jaata hai. Index ki zaroorat nahi. |
| Parent knowledge base | ✅ | Sach mein open-domain, adult reader |
| Author duplicate detection | ✅ | Internal tool, insaan reviewer |
| Cross-lingual content search | ✅ | Internal |

**Curriculum 100× bade hone tak (75 MB+) yeh nahi badlega.** Aur us waqt bhi pehla jawab
better indexing hoga, embeddings nahi.

---

## 10. Latency & Cost — asli numbers

### 10.1 Per-turn latency

| Turn type | % turns | Agent? | Latency | Budget | OK? |
|---|---|---|---|---|---|
| Correct, first try | ~55% | ❌ | **9 ms** | 150 ms | ✅ |
| Correct, 2+ attempts | ~15% | ⚠️ opt | 9 ms / 1.4 s | 2.5 s | ✅ |
| **Wrong answer** | ~20% | ✅ | **~1.4 s** | 2.5 s | ✅ |
| Doubt | ~5% | ✅ | ~1.6 s | 3.0 s | ✅ |
| Idle rung 3 | ~3% | ✅ | ~1.4 s | — | ✅ |
| Idle rung 1,2,4,5 | ~2% | ❌ | 5 ms | — | ✅ |
| **Perceived silence** | — | — | **0 ms** (§5.5 instant ack) | — | ✅ |

### 10.2 Model choice — yeh sabse important operational faisla hai

Teacher Agent 4 steps × ~250 tokens out chala sakta hai. Model ka farq:

| Model | Per step | 4 steps | Verdict |
|---|---|---|---|
| `llama-3.1-8b-instant` (Groq) — **aaj aapka** | ~180 ms | **~0.9 s** | ✅ **Isse shuru karo** |
| `llama-3.3-70b` (Groq) | ~450 ms | ~2.0 s | ⚠️ Deadline ke kinare |
| GPT-4o-mini / Claude Haiku class | ~700 ms | ~3.2 s | ❌ Deadline miss |
| GPT-4o / Sonnet class | ~1.5 s | ~6.5 s | ❌ Bahut dheema |

> **Groq pe rehna aapka sabse bada architectural fayda hai.** Ek 3-saal ke bachche ke liye
> tez chhota model dheeme bade model se **behtar** hai — kyunki teaching quality ka
> constraint hai *bachcha dhyan de raha hai ya nahi*, model ka reasoning depth nahi.
>
> Agar 8b se quality kam padti hai: pehle **tools ka output behtar karo** (agent ko zyada
> saaf context do), phir **prompt behtar karo**, aur **uske baad** hi bada model socho.
> 90% baar problem context ka hota hai, model ka nahi.

### 10.3 Cost

Maan lo `llama-3.1-8b-instant`, ~1,200 in / 250 out per step.

| | Value |
|---|---|
| Teacher agent calls/session | ~3 (avg) |
| Steps/call | ~3 |
| Planner calls/day/child | 1 (~6 steps) |
| **Tokens/session** | **~18,000** |
| Sessions/day (6k DAU) | 6,000 |
| **Tokens/day** | **~108 M** |
| Groq 8b pricing (approx) | ~$0.05–0.10 / M tokens |
| **Cost/day** | **~$6–11** |
| **Cost/month** | **~$180–330** |
| **Per child/month** | **~$0.03–0.06** |

**Yeh bilkul affordable hai.** Aur `backend-architecture.md` §1.4 ka
`ai_cost_estimate_usd_total` counter isko din 1 se track karega.

Comparison ke liye: agar aap yahi flow GPT-4o pe chalate, cost **~50×** hota
(~$9,000–16,000/mahina) **aur** latency deadline miss karti. Chhota-tez model yahan
do wajah se jeetta hai.

---

## 11. Kaise pata chalega ki agents sach mein behtar padha rahe hain

**Yeh section skip mat karna.** Agents ka poora point yeh hai ki woh deterministic ladder se
behtar padhaate hain. Agar aap woh naap nahi rahe, toh aapne sirf latency aur cost badhaya hai.

### 11.1 Natural experiment jo aapko mufт mein mil raha hai

`lesson_states.last_agent_source` (`'agent'` vs `'deterministic_fallback'`) har turn pe likha
jaata hai. Timeouts aur budget-exhaustion aapko **ek random-ish control group** de rahe hain.

Aur bhi behtar — ek explicit knob rakho:

```
AGENT_TRAFFIC_PCT = 90    # 10% children deterministic ladder pe (holdout)
```

Holdout `child_id` ke stable hash se, taaki ek bachcha roz flip na kare.

### 11.2 Metrics jo maayne rakhte hain

| Metric | Kaise | Agent jeetta hai agar |
|---|---|---|
| **Attempts-to-correct** | Ek skill pe pehle correct tak avg attempts | **Kam** |
| **Re-explains-to-mastery** | Mastery 0.75 tak kitne RE_EXPLAIN | **Kam** |
| **END_KINDLY rate** | % activities jo give-up pe khatam | **Kam** |
| **Session completion** | % plans jo poore hue | **Zyada** |
| **Next-day retention** | % bachche jo agle plan day pe aaye | **Zyada** |
| **7-day retention of skill** | Mastered skill 7 din baad pehli try mein sahi | **Zyada** ← **yeh sabse asli hai** |
| Envelope veto rate | §6.3 | **Kam** |
| p95 latency | — | Budget ke andar |

### 11.3 Trap jo aapko pakadna hai

> **Agent attempts-to-correct ko "jeet" sakta hai answer leak karke.**
>
> Isliye `answer_leak` veto rate hamesha attempts-to-correct ke saath padho.
> Agar attempts gir rahe hain **aur** leak vetoes badh rahe hain, toh agent behtar nahi
> padha raha — woh cheat kar raha hai aur envelope kuch pakad rahi hai (aur shayad sab nahi).
>
> Yeh RLHF wala reward-hack hai jo ek prompted agent mein bhi aa sakta hai, bas dheere.
> **Har week yeh do numbers saath dekho.**

### 11.4 Ship gate

Agents 100% traffic pe tab jayenge jab, 4 hafte ke data pe:

- [ ] Attempts-to-correct ≥10% behtar
- [ ] END_KINDLY rate nahi badha
- [ ] `answer_leak` veto rate < 0.5% **aur** trend flat/neeche
- [ ] p95 latency budget mein
- [ ] 7-day skill retention barabar ya behtar
- [ ] Zero safety incident (shame, PII, off-curriculum) 4 hafton mein

**Ek bhi fail = holdout 10% pe rehta hai aur aap prompt/tools theek karte ho.**

---

## 12. Build order

| # | Kya | Kyun is order mein |
|---|---|---|
| 1 | **Postgres + repositories** (OP-01) | `lesson_states`, `daily_plans` — sab yahin |
| 2 | **Auth + consent** (OP-02) | `mock_auth.py` sha256 hai |
| 3 | **Conductor state machine** (plain Python) | Woh dhaancha jisme agent baithega |
| 4 | **Deterministic branch engine + ladder** | **Fallback aur baseline. Agents se PEHLE.** Iske bina aap agent ship hi nahi kar sakte. |
| 5 | **`analogies.json` + `skill_graph.json`** | Agent ke tools ko data chahiye |
| 6 | **`envelope.py`** — 26 rules + metrics | **Agents se pehle.** Envelope ke bina agent = unguarded output. |
| 7 | **Agent runtime** — bounded loop, deadline, retry, budget | Dono agents ka common |
| 8 | **Teacher Agent** — tools, prompt, 10% traffic | Yahan asli value hai. Chhote se shuru. |
| 9 | **Two-stage response** (instant ack) | Iske bina 8 dheema mahsoos hoga |
| 10 | **Planner Agent** — 10% traffic | Kam risk (din mein 1 baar), baad mein |
| 11 | **Metrics + holdout + dashboard** | Iske bina 8/10 blind hai |
| 12 | Traffic 10% → 50% → 100%, gate ke saath (§11.4) | — |
| 13 | LangGraph migration (agar loop 6+ steps) | Optional |
| 14 | Content studio (LangGraph) | Jab variant bank chhota pade |

**Dhyan dijiye #4 aur #6, #8 se pehle hain.** Yeh sabse zaroori sequencing hai poore doc mein:

> **Deterministic engine aur Envelope agents se pehle bante hain.**
> Yeh agents ko rokne ke liye nahi hai — yeh unhe ship karne layak banane ke liye hai.
> Fallback ke bina ek agent timeout = toota hua lesson.
> Envelope ke bina ek agent hallucination = ek bachche ko galat jawab.
> Baseline ke bina aap kabhi jaan nahi paoge ki agents kaam kar rahe hain ya nahi.

---

## 13. Teen failure modes jo dekhni hain

### 13.1 Agent dheere-dheere answer leak karna seekh jaata hai

**Kaise dikhega:** attempts-to-correct shandaar. Bachche "seekh" rahe hain bahut tez.
Par 7-day retention girta hai.

**Kya ho raha hai:** agent aisi cheezein bol raha hai jo technically answer nahi hain par
usko de deti hain. "Gol wale ko chhuo" jab options `[circle, square]` hain — woh answer hai.
Bachcha task solve kar raha hai, concept nahi seekh raha.

**Bachav:** `answer_leak` veto rate weekly padho. Envelope ke check ko **semantic** karo,
sirf string match nahi — options ke against normalised compare, jo aaj `answer_resolution_service`
already achhi tarah karta hai. Us logic ko reuse karo.

### 13.2 Agent atke hue bachche pe zid karta hai

**Kaise dikhega:** `attempt_cap` veto rate badh raha hai. Session lambe ho rahe hain.

**Kya ho raha hai:** agent "helpful" hai. Woh maanta hai ek aur explanation kaam kar jaayegi.
LLMs har jagah give-up karne se hichkichaate hain.

**Bachav:** envelope pehle se hard-caps kar rahi hai (rule #1). Par prompt mein bhi likho:
*"Ek bachche ko jo nahi kar pa raha, chhod dena teaching ka failure nahi hai — woh teaching
hai."* Aur `END_KINDLY` ko decision list mein **pehla** rakho, aakhri nahi — ordering se
model ka prior badalta hai.

### 13.3 Plan har din alag "shape" ka ho jaata hai

**Kaise dikhega:** parent complain karta hai ki koi routine nahi hai. Session completion girta hai.

**Kya ho raha hai:** Planner Agent har din creative ho raha hai — kabhi revise pehle, kabhi
baad mein, kabhi 4 items kabhi 2. Bachchon ko **routine** chahiye. Variety content mein
chahiye, structure mein nahi.

**Bachav:** plan ka **shape** deterministic rakho (revise → adventure → adventure → practice),
aur agent ko sirf **content** chunne do us shape ke andar. Yeh envelope rule ban sakta hai:
"items ka `kind` sequence in-allowed-patterns mein ho." Do-teen allowed shapes rakho, agent
unme se ek chune.

---

## 14. Ek nazar mein

```
   ┌──────────────────────────────────────────────────────────────┐
   │  AGENT DECIDE KARTA HAI                                      │
   │    kaunse lessons · order · session length                   │
   │    branch · rung · variant · scaffold · modality · UI        │
   │    kab kindly end karna hai · doubt ka jawab                 │
   │                                     ← 14 asli faisle          │
   ├──────────────────────────────────────────────────────────────┤
   │  ENVELOPE VETO KAR SAKTI HAI              ← 26 rules, [D]    │
   │    attempt cap · answer leak · rung repeat · shame           │
   │    floors · allowlists · budget · deadline                   │
   ├──────────────────────────────────────────────────────────────┤
   │  AGENT KABHI NAHI CHHOOTA                 ← 7 facts, [D]     │
   │    correctness · mastery · stars · unlock · certificate      │
   │    ownership · consent                                       │
   ├──────────────────────────────────────────────────────────────┤
   │  DETERMINISTIC ENGINE HAMESHA PEECHE HAI                     │
   │    timeout · invalid · budget-out · provider down            │
   │    aur: aapki baseline, jiske against agent naapa jaayega    │
   └──────────────────────────────────────────────────────────────┘

   Agent chalta hai:  wrong answer · doubt · idle-3 · plan (1×/day)
   Agent nahi chalta: correct first-try (~55% turns) · idle 1,2,4,5 ·
                      activity load · scoring · unlock

   Perceived latency: 0 ms (instant ack) → asli teaching 1.4 s pe
   Cost: ~$0.03–0.06 per child per month on Groq 8b
```

**Teen line mein:**

> 1. **Agents 14 asli faisle lete hain** — plan, branch, rung, example, scaffold, UI, kab rukna hai.
>    Yeh cosmetic nahi, poori teaching policy hai.
> 2. **Envelope 26 invariants rakhti hai** aur veto kar sakti hai. Har veto ek metric hai.
>    Veto rate hi aapka prompt-quality signal hai.
> 3. **Deterministic engine agents se PEHLE banega** — fallback, floor aur baseline teeno ke roop mein.
>    Uske bina agent ship karna blind flying hai.

---

*Companions: `docs/AI-100-PERCENT-AUTOMATION.md` (poora automation spec, component verdicts) ·
`docs/AI-ARCHITECTURE-DECISIONS.md` (RLHF/LangGraph/RAG ka original analysis — §4 aur §5 ke
verdicts is doc ke §8 aur §9 se supersede hote hain, kyunki design agentic ho gaya hai).*
