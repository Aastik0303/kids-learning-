# SAKSHAM IQ — 100% AI-Automated Classroom

### Production Specification: The Zero-Tap Teacher

**Repo:** `D:\testcase` — `backend/` (FastAPI) · `frontend/` (Next.js 16) · `mobile/` (Expo RN) · `docs/`
**Version:** 1.0 · 2026-08-19
**Learner:** 2–6 saal, pre-literate, zero tech knowledge, akela baitha hua
**Companions:** `docs/backend-architecture.md` · `docs/frontend-architecture.md` · `docs/upgrade-plan.md` · `docs/TRACK-A-experience-first.md` · `docs/ops/OP-01`…`OP-07`

> Yeh doc un docs ko **replace nahi** karta. Woh *infrastructure* specify karte hain
> (Postgres, auth, responsive, plan engine). Yeh doc **teaching automation** specify karta hai —
> app ko ek asli nursery teacher kaise banaya jaaye jo class **khud chalaye**, aur us
> automation ko 100% tak kaise le jaaya jaaye.

**Doc bhasha:** Hinglish prose, English technical terms/tables/prompts (baaki `docs/` family se match).
**Teaching bhasha:** English + Hindi dono — language *content* se aati hai (`Subject.language` /
`Topic.language` manifest mein), UI toggle se nahi. Yeh already sahi banaya hua hai; isse todna nahi.

---

## Contents

| § | Section | Kya milega |
|---|---|---|
| 0 | Executive Summary | 3 minute mein poori baat, aaj ka honest scorecard, 4 core gaps |
| 1 | Non-Negotiables | R1–R10, jo kabhi nahi tootenge |
| 2 | Pedagogy | I Do/We Do/You Do · scaffolding S0–S4 · Model-Lead-Test · 4 age bands |
| 3 | **AI Class Conductor** | State machine · **Branch Decision Engine** · prerequisite · graceful exit · idle & frustration watchers |
| 4 | **Explanation Engine** | Ladder L1–L5 · analogy bank · skill graph · answer-leak rule |
| 5 | **Zero-Tap Flow** | AI schedule · AI auto-open · session ke andar zero navigation · doubt · close |
| 6 | **Adaptive UI Autopilot** | Live UI simplification, thresholds, pointing layer |
| 7 | **Automation Register** | Aaj ka har manual step → automator. **Coverage math yahan hai.** |
| 8 | Data Model | 4 naye tables/files |
| 9 | API | Conductor endpoints + `ConductorDirective` shape |
| 10 | LLM Contract | Model ko kya milta hai, 11-step validation ladder, budget, degrade |
| 11 | Phase Plan | P0–P14 + copy-paste agent prompts |
| 12 | **Kya manual rahega** | Aur kyun. Yeh section skip mat karna. |
| 13 | Definition of Done | CI test names, prose nahi |
| 14 | Risks | 10 risks + mitigation |
| 15 | **Component Verdicts** | Repo ki har file: KEEP / EXTEND / REFACTOR / REPLACE / DELETE |
| 16 | Aage kya karna hai | — |

**Sabse pehle padho:** §0.3 (aaj ka scorecard) → §0.4 (4 gaps) → §3.4 (branch engine) → §7 (coverage) → §12 (limits).

## 0. Executive Summary — 3 minute mein poori baat

### 0.1 Aap kya maang rahe ho

> "Ab ye demo nahi. 100% AI automation. AI hi schedule kare, class khole, UI easy kare, class
> handle kare, explain kare, bacche ka response le, us response ke aadhaar pe decide kare —
> aage badhna hai ya dobara samjhana hai. Ek bahut friendly teacher ki tarah padhaye."

Iska technical naam: **Zero-Tap Classroom.** Bachcha app kholta hai (ya app khud khulta hai
scheduled time pe) — aur uske baad **poora session bina kisi navigation ke chalta hai.**
Bachche ka kaam sirf ek hai: seekhna. Baaki sab AI chalata hai.

### 0.2 "100% automation" ka exact matlab (aur limit)

100% ka matlab **child surface pe zero manual decisions** — yeh achievable hai aur yahi target hai.
Parent surface pe 100% automation **galat** hoga, aur yeh doc us par honest hai (§12).

| Surface | Automation target | Kyun |
|---|---|---|
| **Child** | **100%** — zero navigation, zero menu, zero "next" button, zero choice about what to study | 3 saal ka bachcha navigate nahi kar sakta. Har manual step ek dead-end hai. |
| **Parent — daily** | **100%** — digest, alerts, plan, reports sab khud aate hain | Parent ko roz app kholne ki zaroorat nahi honi chahiye |
| **Parent — control** | **Deliberately manual** — consent, daily goal, study days, class override, data delete | Consent automate karna illegal hai (DPDP/COPPA). Yeh limitation nahi, requirement hai. |
| **Ops** | **100%** — content validation, budget, circuit break, rollups, degrade ladder | 6k DAU pe koi raat ko jaag ke server nahi dekhega |

### 0.3 Aaj ka honest scorecard

Maine repo ka har component padha. Yeh raha sach:

| Layer | Aaj kya hai | Automation % aaj |
|---|---|---|
| Curriculum | Manifest-driven, 4 classes / 20 subjects, 758 KB authored activities, **37 registered activity types** (akele nursery 25 use karta hai), loader startup pe fail-fast karta hai | **90%** — authoring manual hai (sahi hai), serving automated |
| Correctness | `activity_evaluators.py` — pure functions, LLM zero | **100%** — yeh already production-grade hai |
| Speech cleanup | `child_speech_service.py` — deterministic phonetics, `kid_phonetics.json` | **70%** — 0.30–0.80 confidence band ka enhancer khaali hai |
| Guide | `guide_agent_service.py`, 924 lines, event→response, Groq + full fallback | **40%** — *react* karta hai, *conduct* nahi karta |
| Session flow | `learning_service.py` — activity index, attempts, stars, unlock | **50%** — client ko "next" karna padta hai |
| Scheduling | `daily_recommendation_service.py` — next unlocked topic | **20%** — sirf suggest karta hai, khud kholta nahi |
| UI adaptation | `experience.ts` + manifest `experience_modes` | **30%** — class se aata hai, bachche ke *behaviour* se nahi badalta |
| Persistence | `mock_storage.py` — in-memory dicts | **0%** — restart pe sab gaya |
| Auth | `mock_auth.py` — sha256 | **0%** — production mein nahi ja sakta |
| **Overall child-surface automation** | | **≈35%** |

### 0.4 Chaar gaps jo "demo" ko "product" banne se rok rahe hain

**Gap 1 — Koi class chal hi nahi rahi.**
`guide_agent_service.guide()` ek *stateless event responder* hai. Client event bhejta hai,
woh ek message deta hai. Kisi ke paas "abhi lesson kis phase mein hai" ka concept nahi.
Yeh teacher nahi, commentator hai. → **Class Conductor (§3)**

**Gap 2 — "Explain" ka matlab abhi "sawaal dohrana" hai.**
`_question_teaching_message()` padhiye: zyadatar branches `question.hint` ya `question.prompt`
wapas bol dete hain. Jis bachche ko samajh nahi aaya, use *wahi* baat dubara mil rahi hai.
→ **Explanation Ladder L1–L5 (§4)**

**Gap 3 — Wrong answer pe teaching nahi badalti, sirf taareef badalti hai.**
attempt 1 → `HINT_RESPONSES_ATTEMPT_1`, attempt 2 → `_2`, attempt 3 → `_3_PLUS`.
Teen alag *encouragements*, zero nayi *samajh*. → **Branch Decision Engine (§3.4) + Model-Lead-Test (§2.3)**

**Gap 4 — Bachche ko app chalana padta hai.**
`/adventure` → subject card → topic card → start. Teen taps, teen padhne wali screens,
ek 3-saal ke bachche ke liye. → **Auto-Open + Zero-Tap flow (§5)**

### 0.5 Yeh doc kya deta hai

1. **§2 Pedagogy** — 2-6 saal ke liye asli method (I Do/We Do/You Do, scaffolding fade,
   Model-Lead-Test correction, 4 age bands).
2. **§3 AI Class Conductor** — woh state machine jo class **chalati** hai. Doc ka dil.
3. **§4 Explanation Engine** — 5-rung ladder, "dobara samjhana" ka asli matlab.
4. **§5 Zero-Tap flow** — schedule → auto-open → teach → close, bina ek bhi navigation tap ke.
5. **§6 Adaptive UI Autopilot** — UI bachche ke *struggle* ke hisaab se live badalti hai.
6. **§7 Automation Register** — aaj ka har manual step, aur usko kya automate karega.
   Coverage math yahi hai: **child surface 47/47 steps automated = 100%**.
7. **§8–§13** — data model, API, LLM contract, phase plan, DoD, aur kya jaanboojh kar manual rahega.

### 0.6 Ek rule jo poore doc ko hold karta hai

> **Plan computed hai. Branch decision computed hai. Sirf *awaaz* generated hai.**

`CLAUDE.md` kehta hai: *"Do not use an LLM for deterministic correctness, scoring, stars,
unlocking, or certificate eligibility."* Yeh doc us rule ko **todta nahi, badhata hai**:

| Faisla | Kaun leta hai |
|---|---|
| Aaj kya padhana hai | **Deterministic** — plan engine (§5.1) |
| Bachche ka jawab sahi hai ya nahi | **Deterministic** — `activity_evaluators.py` (already) |
| Aage badhna hai ya dobara samjhana hai | **Deterministic** — branch engine (§3.4) |
| Kaunsa explanation rung chalega | **Deterministic** — ladder policy (§4.2) |
| UI kitni simple karni hai | **Deterministic** — autopilot thresholds (§6) |
| **Us sab ke shabd kya honge** | **LLM** — validated, capped, template-fallback |

**Isliye:** "100% AI automation" ka matlab "100% LLM" **nahi** hai. Automation 100% hai,
LLM dependency ~15% hai. Product **LLM permanently band hone par bhi poora chalta hai** —
sirf teacher ki awaaz template ki ho jaati hai. Yeh `docs/backend-architecture.md` §1.3 ka
already-declared rule hai ("AI availability is explicitly NOT in the SLA") aur hum use rakhenge.

---

## 1. Non-Negotiables

`CLAUDE.md` ke prototype rules ab production rules ban rahe hain, paanch naye ke saath.

| # | Rule | Kahan enforce hoga |
|---|---|---|
| R1 | LLM kabhi source of truth nahi — correctness, score, stars, mastery, unlock, certificate, **plan, branch decision** | `tests/contract/test_llm_never_decides.py` |
| R2 | Client kabhi trusted nahi — attempt, score, index, unlock server se re-derive | `core/deps.py` + session row |
| R3 | Har child-scoped request ownership-checked | `owned_child` dependency |
| R4 | Raw model text kabhi client tak nahi — schema + action allowlist + safety, warna template | `ai/validate.py` |
| R5 | No process-local mutable state | `mock_storage.py` delete (OP-01) |
| **R6** | **Answer key kabhi model ko nahi jaata.** Aaj `ANSWER_KEY_FIELDS` sirf `guide_agent_service._payload_for_model()` mein hai — ab har AI call pe, ek hi jagah | `ai/context.py` — single builder |
| **R7** | **Bachcha kabhi phansega nahi.** Har question se izzat ke saath nikalne ka raasta | Graceful Exit Ladder (§3.6) |
| **R8** | **Child surface pe zero shaming, zero guilt, zero countdown, zero streak-break copy** | `validate.py` shame-lexicon |
| **R9** | **Har screen guide khud bolta hai** — bachche ko padhna ya dhoondhna nahi padega | OP-04 rule 1 + §5.3 |
| **R10** | **Child surface pe zero required navigation.** Har tap optional ho, mandatory nahi | Zero-Tap audit (§7) |

---

## 2. Pedagogy — 2 se 6 saal ko padhaya kaise jaata hai

> Iske bina "AI teacher" sirf ek chatbot hai jo quiz de raha hai.

### 2.1 Method: I Do → We Do → You Do

Aapka curriculum **already isi shape mein authored hai**. `nursery.json` ka `method` field khud
kehta hai: *"Every item is taught before it is asked… meet it, find it, match it, say it, write it."*
Aur `activity_evaluators.answer_kind()` ke teen kinds exactly in phases pe map hote hain:

| Phase | Teacher kya karta hai | Activity types (jo already exist karte hain) | `answer_kind()` |
|---|---|---|---|
| **I DO** — Model | Dikhata hai, bolta hai, naam deta hai. **Koi sawaal nahi.** | `introduce`, `introduce_letter`, `introduce_number`, `introduce_colour`, `introduce_shape`, `introduce_topic`, `story_listen`, `rhyme_listen`, `action_song` | `presentational` |
| **WE DO** — Guided | Saath karta hai: point, co-count, demo-tap, watch-me trace | koi bhi `choice` type, **scaffold ON** | `choice` |
| **YOU DO** — Independent | Chup. Bachcha akela karta hai. | wahi type, **scaffold OFF** | `choice` / `spoken` |

**Aaj ka structural bug:** `learning_service._lesson_activities()` teaching cards ko sampling se
bachata hai (achha) — par **WE DO phase exist hi nahi karta.** Bachcha `introduce_shape` dekhta
hai, phir seedha `select_shape` akela. Beech ka guided step gaayab hai. Yeh sabse badi
pedagogical galti hai jo abhi code mein hai. §3.3 isse theek karta hai — **bina naya content
likhe**, kyunki WE DO wahi activity hai jo scaffold ON ke saath chalti hai.

### 2.2 Scaffolding fade — madad har baar kam hoti hai

```
S4 FULL     teacher answer dikhata AUR bolta hai, bachcha copy karta hai   (pehla exposure)
S3 STRONG   teacher sahi option pe point karta hai, bachcha tap karta hai
S2 LIGHT    teacher 2 options pe simaa deta hai, bachcha chunta hai
S1 CUE      teacher ek shabd ka cue deta hai ("gol wala")
S0 NONE     teacher chup
```

**Rules:**
- Ek session mein scaffold **ek waqt pe ek hi step move** karega. Correct → ek step niche.
  Wrong → ek step upar. Do step kabhi nahi.
- Starting level `skill_mastery` band se: `weak → S3`, `learning → S1`, `mastered → S0`.
- Scaffold level **server pe** rehta hai (session row mein), client pe nahi. R2.

### 2.3 Error correction: Model → Lead → Test → Retest

Yeh Direct Instruction ka classic correction loop hai. Aaj ke code se comparison:

| Attempt | Aaj (`learning_service.answer_learning`) | Naya |
|---|---|---|
| 1st galat | `generator.hint(activity.hint)` — wahi authored hint | **MODEL** — sahi jawab dikhao aur bolo, bina dobara poochhe: *"Yeh circle hai. Circle gol hota hai, koi kona nahi."* Scaffold → S4. |
| 2nd galat | `WRONG_ATTEMPT_2 + activity.hint` | **LEAD** — saath karo: `demo_tap`, co-count, watch-me trace. Bachcha teacher ke saath karta hai. Scaffold S4 hold. |
| 3rd galat | `WRONG_ATTEMPT_3_PLUS`, mark weak | **TEST** — options 2 pe le aao (§6.2), phir wahi sawaal. Ab bachcha jeetega. Scaffold → S3. |
| 4th galat | question rotate karo, mark weak | **RETEST later** — prerequisite micro-lesson (§3.5) ya kindly end (§3.6). Aaj is skill pe aur nahi. |

**Kabhi 4 se zyada attempt nahi.** Attempt 3 ke baad **question ki difficulty girti hai,
bachche ka self-concept nahi.**

### 2.4 Chaar age bands — ek app, chaar alag teachers

Manifest mein aaj 2 experience modes hain: `early` (96 px target, 3 choices, `text_density: none`,
playgroup+nursery) aur `standard` (64 px, 4 choices, `short_words`, lkg+ukg).
Pedagogically 4 chahiye. Yeh **manifest edit hai, code edit nahi** — `ExperienceMode` schema
already ye saare fields carry karta hai, aur `curriculum_service.experience_mode_for_class()`
class se mode uthata hai, isliye chaar modes add karna zero code change hai.

| Class | Age | Attention | Session length | Max choices | Text | Answer mode | Teacher tone | Idle ladder (sec) |
|---|---|---|---|---|---|---|---|---|
| `playgroup` | 2–3 | 3–5 min | 3–4 activities | **2** | none | **tap only**, voice optional | Sing-song, ≤6 words, sab celebrate | 12/25/40/60/80 |
| `nursery` | 3–4 | 5–8 min | 4–6 | **2–3** | none | tap primary, voice optional | Warm, ≤10 words, naming-heavy | 12/22/35/50/70 |
| `lkg` | 4–5 | 8–12 min | 6–8 | **3–4** | short_words | tap + voice | Friendly, ≤15 words, "kyun" explain karta hai | 8/18/30/45/60 |
| `ukg` | 5–6 | 12–18 min | 8–10 | **4** | short_words | tap + voice + trace | Coach, ≤20 words, sochne ka prompt deta hai | 8/16/28/40/55 |

**2–3 ke liye hard rule:** spoken answer *kabhi* mandatory nahi. `EARLY_MODE_SYSTEM_PROMPT` mein
yeh already likha hai — par abhi woh ek *prompt hint* hai, jo model ignore kar sakta hai.
Ab yeh **policy layer mein enforce** hoga: agar mode `early` hai aur activity `spoken` kind ki hai,
server tap-fallback options ke bina activity serve hi nahi karega.

### 2.5 Mastery, spaced retrieval, aur continuity

- **Mastery gate** — agla topic tab khule jab skill *mastered* ho (`effective ≥ 0.75` aur
  `attempts_total ≥ 4`, OP-05 ke constants), sirf `passing_score ≥ 80` se nahi. Aaj unlock
  attempt-based hai, knowledge-based nahi.
- **Spaced retrieval** — har mastered skill **1 / 3 / 7 / 21 din** baad ek baar wapas aayegi.
  Forgetting curve ka jawab repetition nahi, *spaced* repetition hai.
- **Continuity** — har session ki pehli line pichhle session ko naam se yaad kare:
  *"Kal humne A seekha tha. Aaj B se milte hain."* `learning_memory_service.get_latest_learning_memory()`
  yeh data **already deta hai** — aaj sirf `companion.py` mein ek jagah use hota hai. Isko
  Conductor ke GREET state mein le jao.

### 2.6 Taareef: mehnat ki, kaabiliyat ki nahi

Growth-mindset rule — `avatar_service.py` ke `CORRECT_MESSAGES`, `learning_service.CORRECT_FEEDBACK`,
aur `guide_agent_service.STATIC_PRAISE` teeno pools pe lagega:

| Kabhi nahi | Hamesha |
|---|---|
| "You're so smart!" | "Tumne dhyaan se ginaa!" |
| "Good boy / good girl" | "Achhi koshish — dobara try kiya, wahi badi baat hai" |
| har correct pe confetti | confetti sirf milestone pe |

Aur: **first-try correct pe LLM call nahi hogi.** `mobile/src/ai/guideEvents.ts` ka
`shouldCallAgent()` yeh already sahi karta hai (`ANSWER_CORRECT` → `attempt >= 2`).
Web pe port karna hai (W4d). Yeh latency + paisa dono bachata hai, aur pedagogically bhi sahi
hai: sahi jawab pe bachche ko lecture nahi, sirf "haan!" chahiye.

---
## 3. The AI Class Conductor — woh cheez jo class *chalati* hai

> Yeh doc ka dil hai. Baaki sab iske around hai.

### 3.1 Aaj vs kal

**Aaj:** client event bhejta hai → `guide_agent_service.guide(payload)` → ek message wapas.
Server ko yaad nahi ki lesson kis phase mein hai, bachche ne pichhle 3 min mein kya kiya,
kaunsa explanation pehle try ho chuka hai. Har call ek nayi zindagi hai.

**Kal:** server ke paas ek **live lesson state** hai. Har child input us state ko aage badhata
hai. Server decide karta hai next action kya hai aur client ko batata hai. Client sirf
render karta hai aur input bhejta hai. Client kuch decide nahi karta.

```
                            ┌──────────────────────────────┐
   child input  ──────────► │   CLASS CONDUCTOR (server)   │
   (tap / voice / silence)  │                              │
                            │  lesson_state row  (source   │
                            │  of truth, R2)               │
                            │      │                       │
                            │      ▼                       │
                            │  ┌────────────────────────┐  │
                            │  │ 1. EVALUATE            │  │  deterministic
                            │  │ 2. UPDATE MASTERY      │  │  deterministic
                            │  │ 3. COMMIT              │  │  ← truth persisted HERE
                            │  ├────────────────────────┤  │
                            │  │ 4. BRANCH DECIDE       │  │  deterministic  §3.4
                            │  │ 5. PICK LADDER RUNG    │  │  deterministic  §4.2
                            │  │ 6. SET SCAFFOLD        │  │  deterministic  §2.2
                            │  │ 7. ADAPT UI            │  │  deterministic  §6
                            │  ├────────────────────────┤  │
                            │  │ 8. VOICE THE STEP      │  │  LLM (or template)
                            │  │ 9. VALIDATE            │  │  deterministic  R4/R6/R8
                            │  └────────────────────────┘  │
                            └──────────────┬───────────────┘
                                           ▼
                                 ConductorDirective
                            (what to show, say, point at,
                             and what to do if child is silent)
```

**Steps 1–3 pehle commit hote hain, phir 8 chalta hai.** `backend-architecture.md` §1.1 ka
already-declared rule: *"Persist the attempt and mastery update, commit, then call the AI.
An AI timeout degrades the teaching voice, never the child's progress."* Conductor us rule ko
poori tarah maanta hai.

### 3.2 State machine

```
                    ┌─────────┐
                    │  GREET  │  continuity line, kal ka zikr, aaj ka plan
                    └────┬────┘
                         ▼
                    ┌─────────┐
                    │   SET   │  "aaj hum circle se milenge" — objective, 1 line
                    └────┬────┘
                         ▼
     ┌──────────────►┌─────────┐
     │               │  I_DO   │  teach card. koi sawaal nahi. presentational activity.
     │               └────┬────┘
     │                    ▼
     │               ┌─────────┐
     │               │  WE_DO  │  same activity, scaffold S4/S3. teacher point karta hai.
     │               └────┬────┘
     │                    ▼
     │               ┌─────────┐
     │               │ YOU_DO  │  scaffold S1/S0. teacher chup.
     │               └────┬────┘
     │                    ▼
     │               ┌─────────┐
     │               │  CHECK  │  evaluate (deterministic) + mastery update + COMMIT
     │               └────┬────┘
     │                    ▼
     │               ┌─────────┐
     └───────────────│ BRANCH  │  §3.4 — 6 outcomes
       re_explain    └────┬────┘
       simplify           │ advance / end
       prerequisite       ▼
       modality      ┌─────────┐
                     │  CLOSE  │  recap, celebrate, "kal milte hain"
                     └─────────┘

  Har state pe parallel: IDLE WATCHER (§3.7) aur FRUSTRATION WATCHER (§3.8)
```

**Naya table:** `lesson_states`. Poora shape §8.1 mein.

| Column | Kya rakhta hai |
|---|---|
| `phase` | `greet\|set\|i_do\|say_it\|we_do\|you_do\|check\|branch\|close` |
| `scaffold_level` | `0..4` (§2.2) |
| `ladder_rung` | `0..5` — is skill pe abhi tak kaunsa explanation chala (§4) |
| `attempts_on_current` | `0..4` |
| `explanations_used` | `["L1","L3"]` — dobara wahi rung nahi chalega |
| `consecutive_correct` | boredom detection ke liye |
| `frustration_score` | 0.0–1.0, §3.8 |
| `last_input_at` | idle ladder ke liye |
| `modality` | `tap\|voice\|trace` — switch hone pe badalta hai |

### 3.3 WE DO phase — bina naya content likhe

Yeh sabse zyada value dene wala change hai, aur ismein **zero naya authored content** chahiye.

WE DO wahi activity hai jo YOU DO mein hai — bas `scaffold_level ≥ 3` ke saath serve hoti hai.
Server activity ke saath ek `scaffold` block bhejta hai:

```json
{
  "activity": { "...same authored activity..." },
  "scaffold": {
    "level": 3,
    "point_at": ["visual-item-0"],
    "dim_others": true,
    "demo_tap": false,
    "co_narrate": "Dekho — yeh gol hai. Yahi circle hai.",
    "options_shown": ["circle", "square"]
  }
}
```

- `point_at` / `dim_others` → `GuideVisualAction` ke `highlight` aur `dim_others` types
  **already approved hain** (`APPROVED_VISUAL_ACTIONS` mein). Naya action type nahi chahiye.
- `demo_tap` → naya visual action, sirf S4 pe. Answer ko tap hote **dikhata** hai, submit nahi
  karta. Yeh OP-04 §3 ke idle-ladder rung 45s mein already specified hai.
- `options_shown` → server-side trim (§6.2). Client ko choice trim karne ki permission nahi.

**Ek exception jo galat hoga agar miss kiya:** `lesson_flow: "complete"` topics (jaise letter
levels — meet it, find it, say it, write it) already ek designed sequence hain. Unme WE DO
insert karna method ko tod dega. Rule: **`lesson_flow == "complete"` pe WE DO inject nahi hoga**;
woh sequence khud apna I-do/You-do carry karta hai. Sirf `lesson_flow == "sample"` topics pe
WE DO inject hoga.

### 3.4 Branch Decision Engine — "aage badhun ya dobara samjhaun"

Yeh **exactly** woh cheez hai jo aapne maangi. Aur yeh **pura deterministic** hai.

**Input** (sab trusted server state se, client se kuch nahi):

```python
@dataclass(frozen=True)
class BranchInput:
    is_correct: bool
    attempts_on_current: int          # 0-based, is question pe
    response_latency_ms: int          # server-measured, client-reported nahi
    skill_mastery: float              # effective, decay ke baad
    skill_attempts_total: int
    consecutive_correct: int
    frustration_score: float          # §3.8
    ladder_rungs_used: tuple[str, ...]
    scaffold_level: int
    minutes_in_session: float
    target_minutes: float
    modality: str
    prerequisite_mastery: float | None   # concept graph se, §4.5
    age_band: str
```

**Output** — chhe mein se ek. Kabhi saatvan nahi:

| Decision | Kab | Conductor kya karta hai |
|---|---|---|
| `ADVANCE` | correct, aur (first-try **ya** mastery ≥ 0.60) | Agli activity. Koi "next" button nahi. Praise chhota (§2.6). |
| `RE_EXPLAIN` | galat, `attempts ≤ 2`, prerequisite theek hai | **Agla ladder rung** (§4.2). Scaffold +1. Wahi question. |
| `SIMPLIFY` | galat, `attempts == 3` | Options 2 pe (§6.2), touch target bada, distractions off. Wahi question. |
| `PREREQUISITE` | `prerequisite_mastery < 0.40` | Is question ko rok do. Prereq ka micro-lesson chalao (§3.5). Phir wapas. |
| `SWITCH_MODALITY` | `modality == "voice"` aur 2 consecutive `unresolved` speech results | Tap pe switch. Bachche ki galti nahi — mic ki hai. |
| `END_KINDLY` | `attempts ≥ 4` **ya** `frustration ≥ 0.75` **ya** `minutes > target × 1.25` | Skill ko `revisit_queue` mein daalo, warm close, koi guilt nahi (§3.6). |

**Priority order** — pehla jo match kare wahi jeetega. Order fixed hai aur testable hai:

```
1. END_KINDLY        (safety pehle — bachcha kabhi phansega nahi, R7)
2. SWITCH_MODALITY   (input problem ko learning problem mat samjho)
3. PREREQUISITE      (aisi cheez mat sikhao jiski neev nahi hai)
4. SIMPLIFY
5. RE_EXPLAIN
6. ADVANCE
```

**Yahan LLM ka role: zero.** LLM sirf chune hue decision ko *shabd* deta hai.

**Test jo yeh sab pakadta hai:** `tests/unit/test_branch_engine.py` — har `BranchInput`
combination pe decision assert hoga, aur `test_branch_is_llm_free.py` assert karega ki
branch module `ai/` se kuch import hi nahi karta.

### 3.5 Prerequisite micro-lesson (drop-in)

Agar bachcha "gino 5 tak" pe fail ho raha hai aur "gino 3 tak" ki mastery 0.40 se kam hai —
toh problem 5 nahi hai, 3 hai. Conductor:

1. Current lesson ko **pause** karta hai (unmount nahi — exact activity index yaad rehta hai)
2. Prereq skill ka sabse chhota teaching set chalata hai — max **3 activities**
3. Wapas exact us jagah aata hai jahan ruka tha
4. Bachche ko iska pata bhi nahi chalta: *"Ek chhoti cheez pehle dekhte hain!"*

Concept graph (§4.5) ek **authored data file** hai, LLM output nahi:
`backend/app/data/curriculum/skill_graph.json`. Curriculum loader ise startup pe validate karega
(har `skill_id` manifest mein exist kare, koi cycle na ho) — bilkul waise hi jaise aaj
`activity_evaluators.is_registered()` unknown activity types ko startup pe reject karta hai.

### 3.6 Graceful Exit Ladder (R7)

Ek 3-saal ke bachche ko aise sawaal ke saamne bithana jo woh nahi kar sakta — yeh use sikhata
hai ki seekhna bura lagta hai. Yeh product ka sabse bada risk hai.

| Rung | Kab | Bachcha kya sunta hai | Guilt? |
|---|---|---|---|
| 1 | attempts 4 | "Yeh thoda mushkil tha. Koi baat nahi! Kuch aur try karein?" | nahi |
| 2 | frustration ≥ 0.75 | "Chalo thodi der kuch aasan karte hain 😊" | nahi |
| 3 | time > target×1.25 | "Aaj bahut achha kaam kiya! Kal phir milte hain." | nahi |
| 4 | 3 din se same skill fail | Skill ko `parent_support_queue` mein daalo, parent ko real-world activity card do (§7 P-06) | nahi |

Har rung pe skill `revisit_queue` mein jaati hai — **delete nahi hoti**. Woh 1/3/7 din wale
spaced schedule pe wapas aayegi, tab tak jab tak ban na jaaye.

**Ek cheez jo kabhi nahi hogi:** bachche ko yeh batana ki woh fail hua. `learning_service` ka
aaj ka `TOPIC_COMPLETE_NEEDS_PRACTICE` pool ("Let us practise this one a little more") already
achha hai — usi tone ko poore ladder pe extend karo.

### 3.7 Idle Watcher

OP-04 §3 ka ladder already specified hai. Conductor use **server-side** chalata hai (aaj koi
nahi chalata). Timers `experience_modes[*].idle_thresholds_seconds` se aate hain — manifest se,
hardcoded nahi.

| Rung | Guide kya karta hai | LLM? |
|---|---|---|
| 1 | Instruction jaisi thi waisi dohrata hai | Nahi — template |
| 2 | Authored hint + target highlight | Nahi — template |
| 3 | **Aasan shabdon mein dobara samjhata hai** (ladder rung +1) | **Haan** |
| 4 | "Saath karte hain" — `demo_tap`, answer tap hote dikhata hai, submit nahi karta | Nahi — template |
| 5 | Kuch aasan pe jaane ka offer. Kabhi phansata nahi. | Nahi — template |

**Sirf ek rung LLM use karta hai.** Isi wajah se yeh har screen pe chal sakta hai bina AI
budget (`backend-architecture.md` §1.4: 12 calls/session) khatam kiye.

### 3.8 Frustration & Boredom Watchers

Dono deterministic scores hain, dono session state se compute hote hain.

```python
# 0.0 = khush, 1.0 = ab bas karo
frustration = clamp(
      0.30 * (attempts_on_current / 4)
    + 0.25 * (1 - recent_correct_rate)          # pichhle 6 answers
    + 0.20 * retry_burst_ratio                  # 3s se kam mein tap
    + 0.15 * silence_ratio                      # idle rungs hit / rungs available
    + 0.10 * modality_failure_ratio             # unresolved speech
)
```

- `frustration ≥ 0.50` → UI autopilot simplify karta hai (§6)
- `frustration ≥ 0.75` → `END_KINDLY`
- `consecutive_correct ≥ 5` **aur** `avg_latency < 40% of band median` → **boredom**:
  scaffold S0, agla topic jaldi khol do, distractors badhao

**Kyun deterministic:** ek model ka "yeh bachcha frustrated lag raha hai" reproducible nahi hai
aur test nahi ho sakta. Ek formula ho sakta hai. Aur jab yeh galat ho, aap ek number badalte ho,
ek prompt nahi.

### 3.9 Kya Conductor **nahi** karta

| Nahi karta | Kyun |
|---|---|
| Correctness decide | `activity_evaluators.py` karta hai (already sahi) |
| Stars / score / unlock decide | `learning_service` karta hai (already sahi) |
| Curriculum content generate | Content authored hai. AI-generated curriculum 2-saal ke bachche ko nahi dikhaya jaayega. |
| Client pe chalna | Poora server-side. Client ke paas lesson state ki copy nahi hogi (R2, aur TRACK-A §2 ka "one source of truth") |

---

## 4. Explanation Engine — "dobara samjhana" ka asli matlab

### 4.1 Aaj ki problem, code se

`guide_agent_service._question_teaching_message()` ka aakhri branch:

```python
return (
    f"Look at what is shown. {question.hint or question.prompt}",
    ...
)
```

Aur `learning_service.answer_learning()` attempt 1 pe:

```python
feedback = generator.hint(activity.hint, topic.language)
```

Dono `activity.hint` hi hain. Toh jis bachche ko hint samajh nahi aaya, use **wahi hint**
dobara mil raha hai — bas ek alag taareef ke saath aage laga ke. Yeh re-explaining nahi hai.

Counting aur trace branches iska exception hain — woh sach mein co-count aur watch-me karte
hain, aur woh **sahi shape** hain. Ladder unko generalise karta hai.

### 4.2 The Explanation Ladder — L1 se L5

Ek concept ke liye paanch alag *tarike*, ek hi baat ke paanch *repeat* nahi.

| Rung | Naam | Kya hota hai | Example (circle) | Content source |
|---|---|---|---|---|
| **L1** | **Restate** | Wahi baat, chhote shabdon mein, dheere | "Circle dhoondho. Circle gol hota hai." | `activity.hint` + simplification template |
| **L2** | **Concretise** | Bachche ki duniya ki cheez se jodo | "Circle ball jaisa hai. Roti jaisa. 🍪" | Analogy bank (§4.4) |
| **L3** | **Demonstrate** | Dikhao, batao mat | Circle pulse karta hai, ungli uske around ghumti hai, baaki dim | `GuideVisualAction`: `trace_shape` + `dim_others` |
| **L4** | **Contrast** | Sahi vs galat side by side | "Yeh gol hai ✅. Isme kone hain ❌. Gol wale ko chhuo." | Options ke andar se, deterministic |
| **L5** | **Do together** | Hand-over-hand — teacher answer tap karta hai, phir bachcha karta hai | `demo_tap`, phir wahi sawaal S3 pe | Scaffold system |

**Policy (deterministic):**
```
rung = min(L1 + attempts_on_current, L5)
agar rung already `explanations_used` mein hai  → agla unused rung lo
agar saare rungs use ho gaye                    → BRANCH ko END_KINDLY force karo
```

`explanations_used` `lesson_states` mein rehta hai. **Ek session mein ek skill pe koi rung
dobara nahi chalega.** Yeh ek line ka rule hai jo poore "AI apni baat dohra raha hai" problem
ko khatam kar deta hai.

### 4.3 Kaunsa hissa LLM likhta hai

| Rung | Structure | Shabd |
|---|---|---|
| L1 | deterministic | LLM (validated) ya template |
| L2 | deterministic (analogy bank se pick) | LLM analogy ko wording deta hai; **bank se hi analogy chunni hai** |
| L3 | **poora deterministic** — visual action ki koi model wording nahi | template narration |
| L4 | deterministic (options se contrast bana) | LLM |
| L5 | **poora deterministic** | template |

Toh 5 rungs mein **2 poore template hain**, 3 hybrid. Agar LLM down hai, 5 ke 5 rungs
chalte hain — sirf wording template ki hoti hai. R10 satisfied.

### 4.4 Analogy Bank

`backend/app/data/curriculum/analogies.json` — authored, LLM-generated nahi.

```json
{
  "shape_circle": {
    "en": ["a ball", "a biscuit", "the sun", "a wheel"],
    "hi": ["गेंद", "रोटी", "सूरज", "पहिया"],
    "age_bands": ["playgroup", "nursery", "lkg", "ukg"]
  }
}
```

**Kyun authored:** ek model "circle is like a coin" bol sakta hai ek aise bachche ko jisne
sikka dekha hi nahi, ya culturally galat cheez utha sakta hai. Bank locale-aware hai aur
review ho sakta hai. Loader startup pe validate karega ki har `skill_id` manifest mein exist karta hai.

### 4.5 Skill Graph

`backend/app/data/curriculum/skill_graph.json` — `PREREQUISITE` branch ise use karta hai.

```json
{
  "count_to_5":   { "requires": ["count_to_3"], "teaches_before": ["count_to_10"] },
  "letter_B":     { "requires": ["letter_A"] },
  "shape_square": { "requires": ["shape_circle"] }
}
```

**Loader rules (startup pe fail-fast, jaise aaj curriculum karta hai):**
- Har `skill_id` kisi authored activity ke `skill_id` field mein exist kare
- Koi cycle na ho
- Depth ≤ 4 (isse zyada matlab curriculum hi galat structured hai)

### 4.6 Answer leak — R6, ab poore system pe

`guide_agent_service._payload_for_model()` mein already yeh comment hai, aur woh bilkul sahi hai:

> *"The model is never shown the answer key… 'what is the answer?', which is the first thing a
> four-year-old asks the guide, could be answered. The child then taps it and the deterministic
> scorer awards the star, which makes the LLM the thing that decided the star."*

Ab yeh **ek hi jagah** rahega — `ai/context.py` ka context builder — aur har LLM call
(conductor, ladder, plan copy, parent digest) usi se guzregi. Aaj yeh sirf ek function mein hai;
koi bhi naya AI call site ise bypass kar sakta hai.

**Exception jo declare karna zaroori hai:** L4 (Contrast) aur L5 (Do together) ko answer
**chahiye**. Isliye woh dono **template-rendered hain, LLM-worded nahi**. Yahi wajah hai ki
woh ladder pe template-only mark kiye gaye hain.

---
## 5. Zero-Tap Flow — AI schedule karta hai, AI class kholta hai

### 5.1 Scheduling — plan computed hota hai

`docs/upgrade-plan.md` W3 aur `docs/ops/OP-05` already ek deterministic daily plan generator
(S1–S6) specify karte hain. **Wo spec sahi hai. Use dobara mat likho.** Yeh doc uske upar
sirf teen cheezein add karta hai:

**Addition A — `plan_days` ke saath *time* bhi.**
`children.preferences` mein: `{ "study_window": {"start":"16:00","end":"19:00"}, "tz":"Asia/Kolkata" }`.
Plan window ke andar kholne ke liye ready rehta hai; window ke bahar app kholne pe bhi kaam karta
hai (kabhi mana nahi karta), par notification window mein hi jaata hai.

**Addition B — best-slot learning.**
`learner_profiles.engagement_by_hour` (24 buckets, EWMA of completed-activities-per-minute).
14 din baad system parent ko **suggest** karta hai: "Aditi 5 baje sabse achha karti hai."
**Parent hi confirm karta hai** — yeh consent-adjacent hai, silently badalna galat hoga.

**Addition C — session length attention-window se.**
`target_minutes = min(parent_goal, learner_profiles.avg_engaged_minutes × 1.15)`,
age band ke floor/ceiling ke andar clamp (§2.4). Yaani ek 2-saal ka bachcha 12-minute plan
nahi paayega sirf isliye ki parent ne 12 set kiya tha.

### 5.2 Auto-Open — "AI hi class khole"

Aaj: bachcha `/home` pe aata hai → `HomeExperience` do badi cards dikhata hai
(Practice / Continue Adventure) → tap → `/adventure` → subject card → topic card → start.
**Ek 3-saal ke bachche ke liye teen navigation decisions.**

Kal — `/home` **teen second** ka ek warm handshake hai, phir class khud shuru:

```
t=0.0s   Pip wave karta hai. Bolta hai: "Namaste Aditi! Kal humne A seekha tha."
t=2.0s   "Aaj B se milte hain. Chalein?"
t=2.0s   Ek bada glowing button: ▶ (icon-only, koi text nahi). 96px+.
         Ek chhota, kam glowing button: 😴 (abhi nahi)
t=5.0s   Agar koi tap nahi hua → auto-start. Countdown nahi dikhta (R8: no countdowns),
         Pip bas bolta hai "Chalo shuru karte hain!" aur lesson khul jaata hai.
```

**Design rules jo yahan matter karte hain:**
- ▶ tap karna **optional** hai, required nahi. Wahi "zero-tap" hai (R10).
- 😴 hamesha maujood hai. Bachche ko rukne ka haq hai. Ek bhi guilt shabd nahi.
- Auto-start **sirf tab** jab plan ka pehla item pending ho **aur** aaj plan day ho.
  Rest day pe ek warm rest state — khaali screen nahi.
- Guest / no-child pe auto-start nahi. Woh path parent ka hai.

**Yeh kahan banega:** `HomeExperience.tsx` — jo already `startCompanionSession()` call karta hai
aur `guidance.target_id` se highlight karta hai. Server ek naya field jodega:
`auto_open: { enabled: true, after_ms: 5000, route: "/adventure/nur_maths/nur_maths_shapes" }`.
Client sirf obey karta hai. Route safety wahi purani double-check hai — `isSafeGuideTarget` +
server-side allowlist (`guided_navigation_service.APPROVED_GUIDE_TARGETS`), aur mobile ka
double-checked pattern (W4 §"Two things worth copying verbatim") web pe port hoga.

### 5.3 Session ke andar — ek bhi navigation tap nahi

| Aaj bachcha kya tap karta hai | Kal kaun karta hai |
|---|---|
| "Continue Adventure" | Auto-open (§5.2) |
| Subject card | Plan ne chuna |
| Topic card | Plan ne chuna |
| "Start" | Conductor ne GREET → SET → I_DO chala diya |
| **"Next" har correct answer ke baad** | **Conductor auto-advance** (correct pe 800ms delay, taaki celebration dikh sake) |
| "Try again" | Conductor ne RE_EXPLAIN chala diya, wahi question dobara serve ho gaya |
| "Hint" | Idle watcher ne rung 2 pe khud de diya |
| "Back to subjects" lesson ke baad | Conductor CLOSE → agla plan item ya "kal milte hain" |
| "Practice" | Plan ka slot 4 — khud chalta hai |

**Bache hue optional taps** (yeh sab *offered* hain, *required* nahi):
▶ start · 😴 stop · 🖐 haath uthana (doubt) · 🔊 dobara suno · answer tap.
**Answer tap hi ekmatra tap hai jo learning hai.** Baaki sab escape hatch hain.

### 5.4 Doubt / haath uthana

`mobile/src/features/guide/` mein `DoubtOverlay` + `useHandRaise` already exist karte hain.
Web pe port hoga (W4d). Conductor ke saath integration:

- Haath uthana lesson ko **pause** karta hai, **unmount nahi**. `lesson_states.phase` waisa hi rehta hai.
- Bachcha bolta hai ya tap karta hai. Backend `GUIDE_HELP_REQUESTED` handle karta hai
  (already implemented, `_help_message()`).
- Jawab ke baad Conductor **exact usi step pe** resume karta hai.
- Doubt turns AI budget mein count hote hain (`backend-architecture.md` §1.4: 12/session).
- **Doubt ke jawab mein answer key kabhi nahi** — R6. `_is_contextual_mismatch()` already
  is direction mein kaam karta hai; usi ko ladder ke saath jodo.

### 5.5 Class close

CLOSE state:
1. **Recap** — 3 cheezein jo aaj seekhi (deterministic, mastery deltas se)
2. **Celebrate** — stars, badge agar mile (already `learning_service` deta hai)
3. **Stop** — "Aaj bas! Kal phir milte hain." **Aur aage kuch offer nahi.**

`upgrade-plan.md` W3 mein yeh already likha hai aur bilkul sahi hai:
*"A child-learning product that always asks for one more is a dark pattern."*
Yeh doc us rule ko dohrata hai aur enforce karta hai: CLOSE ke baad child surface pe
**koi CTA nahi**. Bonus round sirf parent shuru kar sakta hai.

---

## 6. Adaptive UI Autopilot — "UI AI ke hisaab se easy kardo"

### 6.1 Aaj

`experience.ts` + manifest `experience_modes` se UI *class* ke hisaab se set hoti hai:
`touch_target_px`, `max_choices_per_screen`, `text_density`. Yeh **achha design hai** — server
authoritative hai, frontend ke paas apne numbers nahi hain (`FALLBACK_MODE` sirf pehle response
se pehle ka safety net hai, aur woh strict side pe hai — sahi choice).

**Problem:** yeh static hai. Ek bachcha jo struggle kar raha hai wahi 4 options dekhta rehta hai.

### 6.2 Autopilot — live UI adaptation

Server har response ke saath ek `presentation` block bhejta hai. **Client kuch decide nahi
karta** — R2, aur isliye bhi ki do jagah decide karne se do alag UI ban jaayenge.

```json
{
  "presentation": {
    "choices_shown": 2,
    "touch_target_px": 120,
    "text_density": "none",
    "decoration": "off",
    "motion": "reduced",
    "narration_speed": 0.85,
    "highlight": ["visual-item-0"],
    "dim_others": true
  }
}
```

**Deterministic rules — sab session state se:**

| Signal | Threshold | UI kya karta hai |
|---|---|---|
| `frustration ≥ 0.50` | | choices −1 (min 2), touch target ×1.25, decoration off |
| `attempts_on_current ≥ 3` | | choices → 2, distractors sabse alag wale rakho |
| 2 mis-taps < 400ms apart | | touch target ×1.4, gap ×1.5 (ungli ka issue hai, samajh ka nahi) |
| `consecutive_correct ≥ 5` **aur** latency < band median × 0.4 | boredom | choices +1 (max band cap), scaffold S0 |
| `unresolved` speech × 2 | | voice UI collapse, tap UI promote (`SWITCH_MODALITY`) |
| `prefers-reduced-motion` | | `day-sky-backdrop` off, celebration static |
| session minutes > target | | decoration off, narration +10% dheemi, close ki taraf |

**Do hard floors jo kabhi break nahi honge:**
- `touch_target_px` kabhi manifest ke band value se kam nahi (`early` = 96, `standard` = 64).
  Autopilot sirf **bada** kar sakta hai.
- `choices_shown` kabhi 2 se kam nahi. Ek choice choice nahi hai.

### 6.3 Distraction Reduction Mode

`frontend/app/globals.css` (aaj **3,029 lines** — `upgrade-plan.md` W2 ne 2,172 measure kiya tha, tab se badha hai) mein `day-sky-backdrop` — sun, 3 clouds, 2 bird layers —
**har route pe render hota hai.** Jab bachcha struggle kar raha hai, chidiyaan udd rahi hain.

Rule: `decoration: "off"` pe backdrop, ambient animation, aur non-essential colour sab band.
Screen pe sirf question, options, aur Pip. `upgrade-plan.md` W2 already yeh keh raha hai
(decoration `md:` se upar aur `prefers-reduced-motion: no-preference` pe hi) — yeh doc ek
**teesri condition** jodta hai: *aur tab jab bachcha struggle na kar raha ho.*

### 6.4 Pointing layer

`APPROVED_VISUAL_ACTIONS` already yeh sab carry karta hai:
`pulse`, `highlight`, `highlight_sequence`, `dim_others`, `group_objects`, `trace_shape`, `show_example`.
**Yeh ek achha, tight allowlist hai.** Ek naya chahiye: `demo_tap` (S4 scaffold ke liye, §3.3).

Aur `allowed_visual_targets` ka `visual-item-` / `visual-example-` prefix rule
(`validate_guide_request()`) exactly wahi shape hai jo chahiye — target space bandha hua hai,
model usse bahar point nahi kar sakta. `demo_tap` bhi usi allowlist se guzregi.

### 6.5 Web ↔ Mobile parity

`upgrade-plan.md` W4 already poora parity matrix carry karta hai. Yeh doc usme kuch add nahi
karta except: **`presentation` block dono clients ek jaise consume karenge**, kyunki woh server
se aata hai. Mobile ke `components/responsive/` aur `theme/` tokens already isi shape mein hain.

---
## 7. The Automation Register — 100% tak kaise pahunchte hain

> Yeh section hi "100%" ka proof hai. Har woh manual step jo aaj app mein hai, yahan list hai,
> uske code location ke saath, aur uska automator.
>
> **Owner column:** `D` = fully deterministic · `H` = hybrid (deterministic decision + LLM voice)
> · `L` = LLM-authored copy (validated, template fallback).

### 7.1 Child surface — entry & navigation (C-01 … C-10)

| # | Aaj bachche ko kya karna padta hai | Kahan | Kaun automate karega | Owner |
|---|---|---|---|---|
| C-01 | App khol ke home tak pahunchna | `app/page.tsx` | Scheduled session + parent's device notification window ke andar deep-link seedha auto-open pe (§5.1–5.2) | D |
| C-02 | Apni profile chunni | `app/child/select/page.tsx` | Single-child households (majority) pe auto-select; multi-child pe **photo-only** picker, koi naam padhna nahi | D |
| C-03 | "Practice ya Adventure" decide karna | `HomeExperience.tsx` — 2 cards | **Yeh choice hat jaayegi.** Plan decide karta hai. Home ab ek greeting + ▶ hai. | D |
| C-04 | "Continue Adventure" tap | wahi | Auto-open, 5s baad (§5.2) | D |
| C-05 | Subject chunna | `app/adventure/page.tsx` → `SubjectGrid` | Plan ne slot 2/3 mein chun liya (W3 S3) | D |
| C-06 | Topic chunna | `app/adventure/[subjectId]` → `TopicList` | wahi | D |
| C-07 | Topic page pe "start" tap | `app/adventure/[subjectId]/[topicId]` | Conductor GREET→SET→I_DO khud chalata hai (§3.2) | D |
| C-08 | Screen ka instruction padhna | har page | **R9** — guide har screen pe khud bolta hai, arrival pe auto-TTS | H |
| C-09 | Samajhna ki yeh screen kis liye hai | har page | SET state ek line mein objective bolta hai | H |
| C-10 | Pehli activity shuru karna | `ActivityView.tsx` | Conductor auto-serve | D |

### 7.2 Child surface — lesson ke andar (C-11 … C-28)

| # | Aaj bachche ko kya karna padta hai | Kahan | Kaun automate karega | Owner |
|---|---|---|---|---|
| C-11 | Question padhna | `LearningQuestion.tsx` | Auto-narration; `early` mode mein text hai hi nahi (`text_density: none`) | H |
| C-12 | Samajhna ki ab uski baari hai | — | YOU_DO phase pe explicit cue: chime + Pip ka "ab tum!" + mic/options glow | D |
| C-13 | "Dobara suno" tap karna | — | Idle rung 1 khud dohrata hai (§3.7). Manual 🔊 optional rehta hai. | D |
| C-14 | "Hint" tap karna | — | Idle rung 2 khud deta hai | D |
| C-15 | **Correct ke baad "Next" tap karna** | `learning.ts` continue call | **Conductor auto-advance**, 800ms celebration ke baad | D |
| C-16 | Wrong ke baad "Try again" tap karna | wahi | `RE_EXPLAIN` khud chalta hai, wahi question re-serve hota hai | D |
| C-17 | Decide karna ki madad maangni hai | `GuideCoach.tsx` | Frustration watcher pehle offer karta hai (§3.8). 🖐 optional rehta hai. | D |
| C-18 | Mic kholna / press-to-talk | `VoiceRecorder.tsx` | Conductor voice window khud kholta hai jab uski baari ho; barge-in lock (§7.4 C-40) | D |
| C-19 | Speech na samjhe toh dobara bolna | `child_speech_service` `retry` status | AI Speech Enhancer 0.30–0.80 band bharta hai (§7.4); 2 fail pe modality switch | H |
| C-20 | Voice fail pe tap pe switch karna | manual today | `SWITCH_MODALITY` branch (§3.4) | D |
| C-21 | Yaad rakhna kitni activity bachi hain | `activity_index/total` | Non-numeric progress: bharti hui bag/stars ki lakeer. **Ginti kabhi nahi dikhegi** — 3 saal ka bachcha ginti ko pressure padhta hai | D |
| C-22 | Phanse hue se nikalna | **aaj koi raasta nahi** | Graceful Exit Ladder (§3.6) — **R7** | D |
| C-23 | Decide karna ki sawaal chhodna hai | `attempt_number >= 4` pe rotate | `END_KINDLY`, skill `revisit_queue` mein | D |
| C-24 | Bore hone pe kuch karna | **aaj koi raasta nahi** | Boredom watcher (§3.8) — scaffold S0, difficulty up, agla topic jaldi | D |
| C-25 | Break lene ka decide karna | — | Time governor: `minutes > target×1.25` pe warm close | D |
| C-26 | Lesson complete tap karna | `_complete_topic` | Conductor CLOSE khud chalata hai | D |
| C-27 | Subjects pe wapas jaana | `open-subjects` target | Plan ka agla item khud khulta hai | D |
| C-28 | Agla lesson chunna | manual | Plan | D |

### 7.3 Child surface — practice, rewards, recovery (C-29 … C-38)

| # | Aaj bachche ko kya karna padta hai | Kahan | Kaun automate karega | Owner |
|---|---|---|---|---|
| C-29 | "Practice" karne ka decide karna | `HomeExperience` | Plan slot 4 — un dono lessons ke skills se jo aaj hue (W3 S4) | D |
| C-30 | Practice subject chunna | `app/practice/page.tsx` | Plan ne chuna | D |
| C-31 | Practice topic chunna | `app/practice/[topic]` | wahi | D |
| C-32 | Practice questions tap karke aage badhna | `practice_service` | Conductor practice mode ko bhi chalata hai — same loop, `sessions.mode` alag | D |
| C-33 | Rewards kholna | `app/rewards` | Milestone pe khud dikhta hai; browse optional rehta hai | D |
| C-34 | Certificate kholna | `app/certificate` | Unlock pe khud offer hota hai (`CERTIFICATE_UNLOCKED` already exist karta hai) | D |
| C-35 | Aaj ke liye rukne ka decide karna | — | Plan complete → CLOSE → koi aur CTA nahi (§5.5) | D |
| C-36 | Kal sahi jagah se resume karna | **aaj possible hi nahi (in-memory)** | Postgres (OP-01) + plan carry-over (W3 S1) + `lesson_states` resume | D |
| C-37 | Server error se recover karna | `ApiUnreachableError` | Offline banner + cached plan + local queue; jo pehle se load hai woh chalta rahega | D |
| C-38 | Expired session se recover karna | `EXPIRED_LEARNING_SESSION` 404 | Server-side session resume `lesson_states` se; bachche ko error hi nahi dikhega | D |

### 7.4 Child surface — modality & edge cases (C-39 … C-47)

| # | Aaj bachche ko kya karna padta hai | Kahan | Kaun automate karega | Owner |
|---|---|---|---|---|
| C-39 | Offline handle karna | koi handling nahi | Service worker + prefetched audio + queued attempts (`OfflineBanner` mobile mein already hai) | D |
| C-40 | Awaaz ka overlap sambhalna | `speech.ts` | **Barge-in lock**: jab tak Pip bol raha hai, mic band. Jab mic khula, TTS band. Ek hardware-level mutex. | D |
| C-41 | Galat class level jhelna | parent override manual | System 14 din ka evidence dekh ke parent ko **suggest** karta hai. Auto-move nahi — yeh parent ka faisla hai (§12) | H |
| C-42 | Trace mein: kahan se shuru karna hai jaanna | `TraceCanvas.tsx` (713 lines) | Watch-me demo + blue start dot + directional narration. `_question_teaching_message` ka trace branch **already sahi hai** — usko L3 ladder rung bana do | D |
| C-43 | Free draw: kab khatam hua jaanna | `FREE_DRAW_TARGETS` | Time-boxed (45s) + "ho gaya?" gentle check. Accuracy target zero — yeh already sahi hai | D |
| C-44 | `parent_activity` samajhna (nursery mein 14 hain!) | `_presentational_evaluator` | Parent ko card notification pe jaata hai; child surface pe woh activity **skip** hoti hai jab tak parent confirm na kare. Aaj yeh fake tap ban jaata hai. | D |
| C-45 | `story_listen` / `rhyme_listen` / `action_song`: sirf sunna hai, jaanna | wahi | I_DO phase explicitly "sirf dekho aur suno" bolta hai; koi answer UI hi nahi render hoti | D |
| C-46 | `available: false` topic pe pahunch jaana | `TOPIC_NOT_READY` 409 | Plan aise topics chunta hi nahi. Deep link pe warm redirect, error nahi. | D |
| C-47 | Backend path na hone wale features (`words`, `sentences`, `speaking`, `drawing`, `tracing`, `stories`) | `mobile/src/features/catalog.ts` | Honest "practice activity today, full levels coming" state (W4c) — kabhi failure screen nahi | D |

### 7.5 Child surface coverage

| | Count |
|---|---|
| Manual steps aaj | **47** |
| Automated after this spec | **47** |
| **Child-surface automation** | **100%** |
| Owner split | D: 41 · H: 6 · L: 0 |

**Bache hue optional taps (required nahi):** ▶ start · 😴 stop · 🖐 doubt · 🔊 repeat · answer tap.
Inme se sirf **answer tap** learning hai. Baaki chaar escape hatches hain, aur ek escape hatch
ka maujood hona automation ki kami nahi — child-safety requirement hai (R7).

**L column zero hai, aur yeh jaanboojh kar hai.** Child surface pe koi bhi *faisla* LLM nahi
leta. LLM sirf un 6 hybrid rows ki *wording* deta hai, aur woh bhi validated + template-fallback.

### 7.6 Parent surface (P-01 … P-14)

| # | Manual step | Kaun automate karega | Owner | Manual rahega? |
|---|---|---|---|---|
| P-01 | Roz app khol ke dekhna bachche ne kya kiya | Daily digest push/email, plan complete hone pe | H | — |
| P-02 | Progress report banana | Weekly narrative — numbers deterministic, prose LLM | L | — |
| P-03 | Weak areas dhoondhna | `skill_mastery` bands se auto-surface | D | — |
| P-04 | Practice plan banana | Plan engine | D | — |
| P-05 | Yaad rakhna ki study time hai | Scheduled notification, quiet hours ke saath | D | — |
| P-06 | `parent_activity` cards manage karna | Auto-queue + reminder + one-tap "ho gaya" | D | — |
| P-07 | Class level sahi hai ya nahi decide karna | System evidence-based suggestion deta hai | H | **Haan — parent confirm karega** |
| P-08 | Certificate generate karna | Auto-issue on eligibility, async render (`backend-architecture.md` §1.4) | D | — |
| P-09 | Streak dekhna | Auto — **aur break hone pe chup, celebrate tab jab ho** (R8) | D | — |
| P-10 | Bachche ke frustration ka pata lagana | Distress escalation alert (3 din se stuck skill) | H | — |
| P-11 | Daily goal set karna | — | — | **Haan — parent ka faisla** |
| P-12 | Study days set karna | — | — | **Haan — parent ka faisla** |
| P-13 | Consent dena | — | — | **Haan — legally must be human (DPDP/COPPA)** |
| P-14 | Data delete karna | — | — | **Haan — must be human** |

**Parent daily-work automation: 10/10 = 100%.** Control decisions (P-07, P-11–P-14)
jaanboojh kar manual hain. §12 mein iski wajah likhi hai.

### 7.7 Ops & content (O-01 … O-12)

| # | Manual step | Automator | Owner |
|---|---|---|---|
| O-01 | Content valid hai ya nahi check karna | Startup fail-fast loader — **already exists**, `skill_graph.json` + `analogies.json` tak extend karo | D |
| O-02 | Unknown activity type pakadna | `activity_evaluators.is_registered()` — **already exists** | D |
| O-03 | AI cost monitor karna | `ai_cost_estimate_usd_total` counter + per-child/session budget | D |
| O-04 | LLM outage handle karna | Circuit breaker → template. Product 100% usable rehta hai (R10) | D |
| O-05 | Prompt regression pakadna | Golden-transcript suite: 200 fixed (event, state) → assert shape, ban words, ban answer-leak | D |
| O-06 | Bad AI output pakadna | `validate.py` — schema + action allowlist + safety + shame-lexicon + answer-leak | D |
| O-07 | Teaching quality measure karna | Metrics: first-try-correct %, re-explains-to-mastery, END_KINDLY rate, session completion | D |
| O-08 | Nightly rollups | ARQ worker (`backend-architecture.md` §2.2) | D |
| O-09 | Deployment health | `/health/ready` + p95 budgets (§1.1 wahan) | D |
| O-10 | Content gaps dhoondhna | Coverage report: skills without activities, activities without `skill_id`, orphan graph nodes | D |
| O-11 | Speech phonetics ka drift | `kid_phonetics.json` hit-rate telemetry → low-confidence tokens ki weekly list | D |
| O-12 | Incident pe degrade karna | Ladder: LLM off → decoration off → voice off → read-only. Har rung pe app usable rehta hai | D |

**Ops automation: 12/12 = 100%.**

### 7.8 Total

| Surface | Steps | Automated | % |
|---|---|---|---|
| Child | 47 | 47 | **100%** |
| Parent — daily work | 10 | 10 | **100%** |
| Parent — control | 5 | 0 | **0% (by design)** |
| Ops & content | 12 | 12 | **100%** |
| **Total (excl. consent/control)** | **69** | **69** | **100%** |

---

## 8. Data Model — kya naya chahiye

`docs/backend-architecture.md` §3 mein 17 tables already specified hain, aur `upgrade-plan.md` W3
`daily_plans` (#18) jodta hai. Yeh doc **teen aur** jodta hai. Isse zyada nahi.

### 8.1 `lesson_states` (#19) — Conductor ka dil

```
id UUIDv7 PK
session_id        FK -> sessions (UNIQUE — ek session, ek state)
child_id          FK -> children
phase             TEXT  greet|set|i_do|say_it|we_do|you_do|check|branch|close
current_skill_id  TEXT
scaffold_level    SMALLINT  0..4
ladder_rung       SMALLINT  0..5
explanations_used TEXT[]                -- ek session mein rung dobara nahi
attempts_on_current SMALLINT
consecutive_correct SMALLINT
frustration_score NUMERIC(3,2)
modality          TEXT  tap|voice|trace
paused_for        TEXT NULL             -- 'doubt' | 'prerequisite'
resume_payload    JSONB NULL            -- exact activity index to come back to
last_input_at     TIMESTAMPTZ
idle_rung         SMALLINT  0..5
created_at, updated_at
INDEX (child_id, updated_at DESC)
```

`UNIQUE (session_id)` — ek session ke do states kabhi nahi. Isse concurrent tab ka poora
class of bugs khatam ho jaata hai.

### 8.2 `skill_graph` — table nahi, **file**

`backend/app/data/curriculum/skill_graph.json`. Authored, versioned, loader-validated.
Curriculum ki tarah — kyunki yeh curriculum **hai**, user data nahi. Isse table banane se
yeh review-able aur diff-able nahi rahega.

### 8.3 `analogies` — table nahi, **file**

`backend/app/data/curriculum/analogies.json`. Wahi wajah.

### 8.4 `learner_profiles` (#20)

OP-05 mein already specified hai. Yeh doc do column jodta hai:

```
engagement_by_hour  SMALLINT[24]   -- best-slot learning (§5.1 Addition B)
avg_engaged_minutes NUMERIC        -- attention window (§5.1 Addition C)
```

### 8.5 `revisit_queue` (#21)

```
child_id + skill_id  PK
reason        TEXT  end_kindly|spaced|weak|parent_flag
due_on        DATE
interval_days SMALLINT   -- 1, 3, 7, 21
attempts_since_queued SMALLINT
INDEX (child_id, due_on)
```

Plan engine (W3 S2) isko revise-block ka source banayega — aaj woh sirf R3 (weak skill) se
aata hai. Spaced retrieval (§2.5) ko ek durable queue chahiye.

**Total: 21 tables.** `backend-architecture.md` §0.3 ka "17 tables, every one earns its place"
wala anushasan maana ja raha hai — chaar naye, har ek ke saath wajah.

---

## 9. API — kya naya chahiye

Sab `/api/v1` ke neeche, `backend-architecture.md` §2.2 ke structure mein.

### 9.1 Conductor (naya router `api/v1/conductor.py`)

```
POST /conductor/{child_id}/open            -> ConductorDirective   (auto-open, plan se)
POST /conductor/sessions/{id}/input        -> ConductorDirective   (tap | voice | trace | idle | doubt)
GET  /conductor/sessions/{id}              -> ConductorDirective   (resume, refresh-safe)
POST /conductor/sessions/{id}/pause        -> ConductorDirective   (😴)
```

**Ek endpoint sab input handle karta hai.** Yeh jaanboojh kar hai: aaj `learning/answer`,
`practice/answer`, `agent/guide`, `companion/session/event` chaar alag jagah hain jo teen alag
tarah se decide karte hain. Ek hi jagah rakhne se teaching loop ek hi jagah rehti hai.

**`ConductorDirective` — ek hi response shape, har waqt:**

```json
{
  "session_id": "...",
  "phase": "we_do",
  "activity": { "...authored activity, answer key ke bina jab tak client ko na chahiye..." },
  "scaffold": { "level": 3, "point_at": ["visual-item-0"], "dim_others": true,
                "demo_tap": false, "options_shown": ["circle","square"] },
  "presentation": { "choices_shown": 2, "touch_target_px": 120, "text_density": "none",
                    "decoration": "off", "motion": "reduced", "narration_speed": 0.85 },
  "speech": { "text": "Dekho — yeh gol hai.", "language": "hi", "speak": true,
              "voice_speed": 0.85, "source": "llm|template" },
  "avatar": { "state": "encouraging", "animationEffect": "gentle_hint" },
  "visual_action": { "type": "highlight", "targets": ["visual-item-0"] },
  "next_input": { "expects": "tap", "timeout_ms": 12000, "on_timeout": "idle_rung_2" },
  "progress": { "shape": "bag", "filled": 3, "total": 6 },
  "auto_advance_in_ms": null,
  "close": null
}
```

`next_input.on_timeout` **isliye matter karta hai**: idle ladder ka faisla server ne pehle hi
le liya hai. Client ko sirf timer chalana hai aur bata dena hai. Client kuch decide nahi karta.

### 9.2 Plan (W3 se — yahan sirf reference)

```
GET   /plans/{child_id}/today
GET   /plans/{child_id}/history?days=30
POST  /plans/{child_id}/regenerate      (parent only, 1/day)
PATCH /plans/{child_id}/preferences
```

### 9.3 Parent

```
GET   /parents/digest/daily?child_id=
GET   /parents/report/weekly?child_id=
GET   /parents/activities/pending        (parent_activity cards)
POST  /parents/activities/{id}/complete
GET   /parents/suggestions               (class level, best slot — confirm karne ke liye)
POST  /parents/suggestions/{id}/accept
```

### 9.4 Kya deprecate hoga

| Aaj | Kal |
|---|---|
| `POST /learning/answer` | Conductor input ke andar. Route rahega, contract-tested, ek release ke liye. |
| `POST /practice/answer` | wahi |
| `POST /agent/guide` | Conductor ke andar. Standalone doubt-answering ke liye rahega. |
| `POST /companion/session/start` | `/conductor/{child_id}/open` |
| `POST /companion/session/event` | `/conductor/sessions/{id}/input` |
| `GET /health` (`{"mode":"prototype"}`) | `/health/live` + `/health/ready` |
| `POST /dev/seed/{child_id}` | **Non-production builds mein hi.** Aaj yeh `main.py` mein hamesha mounted hai. |

---
## 10. LLM Contract — model ko exactly kya milta hai aur kya nahi

### 10.1 Ek hi context builder

`backend/app/ai/context.py`. **Har** AI call isi se guzregi. Aaj `_payload_for_model()` sirf
guide agent mein hai; koi bhi naya call site use bypass kar sakta hai. Woh R6 ka structural hole hai.

**Model ko yeh milta hai:**

```json
{
  "event": "ANSWER_INCORRECT",
  "phase": "we_do",
  "decision": "RE_EXPLAIN",
  "ladder_rung": "L2",
  "scaffold_level": 3,
  "age_band": "nursery",
  "language": "hi",
  "skill_display_name": "गोल आकार",
  "activity_prompt": "Tap the circle.",
  "activity_hint": "Round, with no corners.",
  "options_shown": ["circle", "square"],
  "analogy_candidates": ["गेंद", "रोटी"],
  "attempts_on_current": 1,
  "allowed_ui_actions": ["highlight", "show_hint"],
  "allowed_ui_targets": ["question-area", "answer-options"],
  "allowed_visual_targets": ["visual-item-0", "visual-item-1"],
  "word_limit": 10,
  "already_said": ["Dekho — circle gol hota hai."]
}
```

**Model ko yeh kabhi nahi milta:**

| Kabhi nahi | Kyun |
|---|---|
| `correct_answer`, `accepted_answers` | R6 — warna star LLM ne diya |
| Bachche ka naam, DOB, koi PII | Privacy. `skill_display_name` kaafi hai. |
| Doosre bachchon ka data | — |
| Mastery numbers | Decision already ho chuka. Model ko sirf usko bolna hai. |
| Kya karna hai ka choice | `decision` aur `ladder_rung` **input hain, output nahi** |

### 10.2 Model output — sirf yeh 4 fields

```json
{ "message": "...", "avatar_state": "encouraging",
  "ui_action": {"type":"highlight","target":"answer-options"},
  "visual_action": {"type":"dim_others","targets":["visual-item-1"]} }
```

`strategy` field hata do — woh aaj model se aata hai, aur woh ek *decision* hai. Ab woh
server ka `decision` field hai. Yeh chhota sa change R1 ko structurally enforce karta hai.

### 10.3 Validation ladder (`ai/validate.py`) — har output pe

```
1. JSON parse                          -> fail: template
2. Pydantic schema                     -> fail: template
3. ui_action.type   in allowed         -> fail: template   (aaj already hai)
4. ui_action.target in allowed         -> fail: template   (aaj already hai)
5. visual_action    in allowed         -> fail: template   (aaj already hai)
6. word count <= word_limit            -> fail: truncate at word boundary
7. ANSWER LEAK: message correct_answer -> fail: template   ** NAYA **
   ya kisi accepted_answer ko contain
   nahi karta (normalised compare)
8. SHAME LEXICON: no wrong/bad/no/     -> fail: template   ** NAYA **
   failed/stupid/again? ke shaming forms
9. REPEAT GUARD: message `already_said` -> fail: agla ladder rung   ** NAYA **
   se >0.85 similar nahi
10. safe_text() (existing)              -> fail: FALLBACK
11. LANGUAGE: script matches            -> fail: template   ** NAYA **
    topic.language (hi -> Devanagari)
```

**Step 7 sabse zaroori hai.** Aaj answer-leak guard sirf *input* side pe hai
(`ANSWER_KEY_FIELDS` model ko nahi jaate). Par model **guess** kar sakta hai — options usko
dikhte hain. Ek 4-saal ka bachcha "answer kya hai?" poochhega, model "circle!" bol dega,
bachcha tap karega, deterministic scorer star de dega. Truth deterministic thi, par star LLM ne
dilaaya. Output-side check yeh band karta hai.

**Step 9 (Repeat Guard)** woh problem structurally khatam karta hai jiski aapne shikayat ki:
AI apni hi baat dohra raha hai. Agar naya message pichhle se 0.85+ similar hai, woh reject
hota hai aur **agla ladder rung** chalta hai — yaani ek alag *tarika*, alag *shabd* nahi.

### 10.4 Prompt library

`backend/app/ai/prompts/` — versioned `.txt`, ek per (decision × rung). Aaj poore prompts
Python constants hain (`SYSTEM_PROMPT`, `EARLY_MODE_SYSTEM_PROMPT`, `HINDI_SYSTEM_PROMPT`) —
jo achhe likhe hain, par unhe badalne ke liye deploy karna padta hai aur A/B nahi ho sakta.

```
prompts/
  base.v1.txt
  band_playgroup.v1.txt   band_nursery.v1.txt   band_lkg.v1.txt   band_ukg.v1.txt
  lang_hi.v1.txt
  decision_re_explain.v1.txt   decision_simplify.v1.txt   decision_advance.v1.txt
  rung_L1.v1.txt   rung_L2.v1.txt   rung_L4.v1.txt        # L3, L5 template-only
  parent_digest.v1.txt   parent_weekly.v1.txt   plan_copy.v1.txt
```

`prompt_version` har AI-generated string ke saath log hoga — taaki regression trace ho sake.

### 10.5 Budget & degradation

`backend-architecture.md` §1.4 ke budgets waise hi rahenge (12 calls/session, 200/child/day,
1200 token prompt, 300 token output). Conductor unke andar aise fit hota hai:

| Kab LLM call hoti hai | Typical/session |
|---|---|
| GREET continuity line | 1 |
| SET objective line | 1 |
| RE_EXPLAIN L1/L2/L4 | ≤ 4 |
| Doubt answer | ≤ 3 |
| Idle rung 3 | ≤ 2 |
| CLOSE recap | 1 |
| **Total** | **≈ 12** |

**Jahan LLM call *nahi* hoti:** first-try correct (`shouldCallAgent`), auto-advance,
L3/L5 rungs, idle rungs 1/2/4/5, poora branch engine, poora UI autopilot, plan generation,
mastery, unlock, certificate.

**Degrade ladder (O-12):**
```
budget khatam / circuit open  -> template voice, baaki sab identical
provider down                 -> wahi
TTS down                      -> text + icon, `early` mode strict simplify
STT down                      -> tap-only, saare spoken activities tap-fallback pe
DB down                       -> read-only, koi naya session nahi, saaf "thodi der mein aana"
```

Har rung pe **app usable rehti hai**. Yeh test hoga, assume nahi kiya jaayega:
`tests/e2e/test_full_lesson_llm_disabled.py` poora lesson `LLM_PROVIDER=none` pe chalata hai
aur assert karta hai ki har activity serve hui, har branch fire hua, aur session complete hua.

---

## 11. Phase Plan

Har phase ek gate pe rukega. **Ek session mein ek prompt. Kabhi do nahi.**
`upgrade-plan.md` Appendix ka same anushasan.

| Phase | Kya | Blocked by | Kyun is order mein |
|---|---|---|---|
| **P0** | Baseline audit refresh | — | `docs/backend-audit.md` 2026-08-13 ka hai; usse aage kaam hua hai |
| **P1** | Postgres + Alembic + repositories (OP-01) | P0 | Har cheez ko durable truth chahiye. `mock_storage.py` sab kuch block kar raha hai. |
| **P2** | Auth + consent (OP-02) + HttpOnly refresh cookie | P1 | `mock_auth.py` sha256 hai. Iske bina production illegal hai. |
| **P3** | Responsive mobile-first (W2) | — | P1/P2 se independent, parallel chal sakta hai |
| **P4** | Session engine server-authoritative + `sessions`/`attempts` | P1 | Conductor ko ek asli session row chahiye |
| **P5** | Mastery + recommendations R1–R7 (OP-05) | P4 | Branch engine mastery pe khada hai |
| **P6** | **Class Conductor** — state machine, branch engine, scaffolding | P5 | **Yeh doc ka core** |
| **P7** | **Explanation Ladder** + analogy bank + skill graph | P6 | Conductor ke branch ko rungs chahiye |
| **P8** | **UI Autopilot** + `presentation` block + `demo_tap` | P6, P3 | Conductor decide karta hai, UI obey karti hai |
| **P9** | Daily plan engine (W3) + `revisit_queue` + spaced retrieval | P5, P6 | Plan Conductor ko feed karta hai |
| **P10** | **Zero-Tap flow** — auto-open, auto-advance, graceful exit | P6, P8, P9 | Sab pieces chahiye |
| **P11** | Speech enhancer (0.30–0.80 band) + barge-in lock + modality switch | P6 | Conductor ke bina switch kahan jaayega |
| **P12** | Parent loop — digest, weekly, activity cards, suggestions | P5, P9 | Numbers pehle |
| **P13** | Web↔mobile parity (W4a–W4d) | P8 | Foundation pehle |
| **P14** | Ops — budget, circuit, golden transcripts, metrics, degrade ladder | P6 | Jo cheez maujood hai usi ko harden karo |

### Agent prompts

> Har prompt apne aap mein poora hai. Ek session mein ek.

**P6 — Class Conductor**

> Read `docs/AI-100-PERCENT-AUTOMATION.md` §3 and §8.1, plus `docs/backend-architecture.md` §2
> and §4. Backend Phase 5 has passed its gate, so `skill_mastery` and recommendation rules
> R1–R7 exist.
>
> Build the Class Conductor. Add one table, `lesson_states`, exactly as specified in §8.1 with
> `UNIQUE (session_id)`. Implement `services/conductor_service.py` as the state machine
> GREET → SET → I_DO → WE_DO → YOU_DO → CHECK → BRANCH → CLOSE, and
> `services/branch_engine.py` as a **pure function** `decide(BranchInput) -> BranchDecision`
> returning exactly one of ADVANCE, RE_EXPLAIN, SIMPLIFY, PREREQUISITE, SWITCH_MODALITY,
> END_KINDLY, evaluated in the priority order given in §3.4.
>
> `branch_engine.py` must not import anything from `app/ai/` — add
> `tests/contract/test_branch_is_llm_free.py` asserting that, by AST inspection of the module's
> imports, not by mocking. Implement scaffolding levels S0–S4 per §2.2, moving at most one step
> per outcome, initialised from the mastery band. Implement the WE_DO injection rule of §3.3:
> inject a guided pass only when `topic.lesson_flow == "sample"`; never for `"complete"`.
>
> Expose `POST /api/v1/conductor/{child_id}/open`, `POST /api/v1/conductor/sessions/{id}/input`,
> `GET /api/v1/conductor/sessions/{id}` and `POST /api/v1/conductor/sessions/{id}/pause`,
> all returning the single `ConductorDirective` shape from §9.1. Evaluate, update mastery and
> **commit before** any AI call, per `backend-architecture.md` §1.1.
>
> Test: every BranchInput combination in the §3.4 table produces the documented decision;
> the same input produces the same decision across 100 runs; a session resumed via GET returns
> the identical directive it was last issued; `attempts_on_current` never exceeds 4; and a full
> lesson completes with `LLM_PROVIDER=none`.

**P7 — Explanation Ladder**

> Read `docs/AI-100-PERCENT-AUTOMATION.md` §4 and §10. The Conductor exists and emits a
> `decision` and a `ladder_rung`.
>
> Implement `services/explanation_service.py` with the five rungs L1–L5 of §4.2. Rungs L3
> (Demonstrate) and L5 (Do together) must be **template-only and never LLM-worded**, because
> they legitimately need the answer key and §4.6 forbids that reaching a model. Enforce the
> rung policy of §4.2: `rung = min(L1 + attempts, L5)`, skip any rung already in
> `lesson_states.explanations_used`, and when all rungs are exhausted force the branch engine
> to END_KINDLY.
>
> Add `backend/app/data/curriculum/skill_graph.json` and `analogies.json`, and extend the
> existing curriculum loader so that startup fails fast — naming the offending file and field,
> exactly as it does today for activities — when a skill id is unknown, the graph has a cycle,
> graph depth exceeds 4, or an analogy list is missing a locale that its skill's subject
> declares.
>
> Add `app/ai/context.py` as the **single** context builder and route every AI call through it.
> Move the `ANSWER_KEY_FIELDS` stripping there from `guide_agent_service._payload_for_model()`.
> Add `app/ai/validate.py` implementing the full 11-step ladder in §10.3, including the three
> new steps: output-side answer-leak detection, shame lexicon, and the repeat guard at 0.85
> similarity which escalates to the next rung rather than returning a template.
>
> Test: a child answering wrong three times receives three **structurally different**
> explanations, asserted by rung id and by pairwise similarity below 0.85; no rung repeats
> within a session; a model output containing the correct answer is replaced by a template;
> a Hindi topic never produces a Latin-script explanation.

**P8 — UI Autopilot**

> Read `docs/AI-100-PERCENT-AUTOMATION.md` §6 and §9.1. W2 responsive work has landed.
>
> Add the `presentation` block to `ConductorDirective` and compute it server-side from the
> deterministic rules in §6.2. Enforce the two floors: `touch_target_px` may only ever be
> raised above the manifest band value, never lowered, and `choices_shown` never drops below 2.
> Remove every client-side decision about choice count and target size — `lib/experience.ts`
> keeps `FALLBACK_MODE` only for the pre-first-response moment, and `limitChoices()` becomes a
> renderer of a server-supplied list rather than a trimmer.
>
> Add one visual action type, `demo_tap`, to `APPROVED_VISUAL_ACTIONS` and implement it on web
> and mobile: it animates a tap on the correct option **without submitting it**. It is
> server-emitted only, at scaffold S4 and at idle rung 4, and it goes through the same
> `visual-item-` / `visual-example-` target allowlist as every other visual action.
>
> Implement Distraction Reduction Mode: when `presentation.decoration == "off"`, the
> `day-sky-backdrop` and all ambient animation are removed from the tree, not merely hidden.
>
> Test with Playwright at the seven W2 viewports: with `frustration >= 0.5` injected, exactly
> two options render at ≥ the band's touch target; after two sub-400ms mis-taps, targets grow
> and gaps widen; `demo_tap` never fires a submit; and `decoration: off` leaves zero
> decorative nodes in the DOM.

**P10 — Zero-Tap**

> Read `docs/AI-100-PERCENT-AUTOMATION.md` §5 and §7. The Conductor, the ladder, the autopilot
> and the plan engine all exist.
>
> Rebuild `/home` as the auto-open handshake of §5.2: a continuity greeting naming yesterday's
> topic from `learning_memory_service`, one large icon-only ▶ and one quieter 😴, and automatic
> lesson start at 5000 ms when the child does nothing. Never render a countdown, a timer, or
> any deadline. Do not auto-start for a guest, when no child is selected, on a rest day, or
> when today's plan is already complete.
>
> Remove the "next" control from every child-facing surface. After a correct answer the
> Conductor advances automatically 800 ms later — long enough for the celebration, short enough
> that the child never wonders whose turn it is. After a wrong answer it re-serves the same
> question with the next explanation rung. Neither transition may be initiated by the client.
>
> Implement the Graceful Exit Ladder of §3.6 and the idle ladder of §3.7, both driven by
> `next_input.on_timeout` values the server supplies; the client runs a timer and reports, it
> decides nothing. Replace the numeric `activity_index / activity_total` display with the
> non-numeric progress shape of C-21.
>
> Verify with an end-to-end test that a child can complete an entire scheduled session —
> greeting through recap, including one wrong-answer re-explain and one idle timeout — with
> **zero taps other than answer taps**, and that no screen in that flow contains text the child
> is required to read.

---

## 12. Kya jaanboojh kar manual rahega — aur kyun

Yeh section utna hi important hai jitna baaki doc. "100% automation" ka matlab
"insaan ko hata do" nahi hai.

| Manual rahega | Kyun |
|---|---|
| **Consent** (P-13) | DPDP Act 2023 aur COPPA dono verifiable parental consent maangte hain. Ise automate karna sirf galat nahi, gair-kanooni hai. |
| **Data delete** (P-14) | Wahi. Aur ek galti se hua auto-delete recoverable nahi hai. |
| **Daily goal, study days** (P-11, P-12) | Yeh parenting ke faisle hain, learning ke nahi. System suggest kar sakta hai; decide nahi. |
| **Class override** (P-07) | Ek bachche ko class badalna uski poori progress reset karta hai (`child_service._apply_class`). Yeh ek insaan ka faisla hai. System evidence deta hai. |
| **Curriculum authoring** | AI-generated content 2-saal ke bachche ko nahi dikhaya jaayega. Manifest + activity files insaan likhte hain, insaan review karte hain. Yeh product ki sabse badi safety property hai. |
| **Analogy bank aur skill graph** | Wahi wajah. Ek model "circle sikke jaisa hai" bol sakta hai ek aise bachche se jisne sikka dekha hi nahi. |
| **Safety lexicon** | Reviewed, versioned, tested. Model se generate nahi hoga. |
| **`parent_activity` completion** (P-06) | Nursery mein 14 aisi activities hain. Ball catch karna screen nahi sikha sakti. App parent ko card dikhata hai — aur **fake tap question nahi banata**. Yeh already sahi decision hai (`nursery.json` ka `delivery_legend` khud yeh kehta hai); ise mat todna. |

---

## 13. Definition of Done

### 13.1 Automation

- [ ] Ek bachcha poora scheduled session complete karta hai jismein **answer taps ke alawa
      zero taps** hain — E2E test se assert (§11 P10)
- [ ] Child surface pe kahin bhi aisa text nahi jo bachche ko *padhna zaroori* ho
- [ ] Har screen arrival pe khud bolta hai (R9)
- [ ] Har question se izzat ke saath nikalne ka raasta hai (R7) — koi dead end nahi
- [ ] Child surface pe koi "next" control nahi hai

### 13.2 Teaching quality

- [ ] Teen galat jawab = teen **structurally alag** explanations (rung id + <0.85 similarity)
- [ ] Ek session mein ek skill pe koi ladder rung dobara nahi chalta
- [ ] Har `lesson_flow: "sample"` topic pe WE_DO phase milta hai; `"complete"` pe kabhi nahi
- [ ] Scaffold ek waqt pe ek step move karta hai, kabhi do nahi
- [ ] `attempts_on_current` kabhi 4 se upar nahi
- [ ] Prerequisite micro-lesson lesson ko unmount kiye bina resume karta hai

### 13.3 LLM containment

- [ ] `branch_engine.py` `app/ai/` se kuch import nahi karta — AST test se
- [ ] Same `BranchInput` → same decision, 100 runs
- [ ] Poora lesson `LLM_PROVIDER=none` pe complete hota hai; sirf `speech.source` badalta hai
- [ ] Model output jismein correct answer hai → template se replace hota hai (output-side check)
- [ ] Model ko `correct_answer` / `accepted_answers` kabhi nahi jaate — har call site pe, `context.py` se
- [ ] Hindi topic kabhi Latin-script explanation nahi deta

### 13.4 Safety & privacy

- [ ] Shame lexicon har child-facing string pe chalta hai — LLM aur template dono pe
- [ ] Kahin bhi guilt copy nahi: missed day, broken streak, failed question
- [ ] Child surface pe koi countdown, timer, deadline nahi
- [ ] Consent record har child ke liye maujood hai, parent ne diya hua
- [ ] Bachche ka poora DOB store nahi hota — birth year + month hi (already sahi hai)
- [ ] Koi third-party ad ya behavioural-tracking SDK nahi (W4a rule)

### 13.5 Reliability

- [ ] Committed attempt kabhi nahi khota (durability 100%)
- [ ] Session refresh/re-login/navigation pe wahi directive resume karta hai
- [ ] Degrade ladder ke har rung pe app usable — har rung ka test hai
- [ ] p95 budgets `backend-architecture.md` §1.1 ke andar; conductor input (no LLM) ≤ 150 ms

### 13.6 Coverage

- [ ] §7 ki 47 child rows sab automated aur test-covered
- [ ] §7 ki 10 parent daily rows automated
- [ ] §7 ki 12 ops rows automated
- [ ] §12 ki manual rows **abhi bhi manual hain** — inhe automate karna regression hai, progress nahi

---

## 14. Risks

| Risk | Kitna bura | Kya karein |
|---|---|---|
| **Auto-open bachche ko chaunka deta hai** | Medium | 5s buffer, warm awaaz, 😴 hamesha maujood. Pehle 20 sessions ka opt-out rate dekho. |
| **Auto-advance bahut tez lagta hai** | High | 800 ms fixed nahi — band-wise (playgroup 1400 ms, ukg 600 ms). Metric: post-advance mis-tap rate. |
| **Branch engine over-tuned ho jaata hai** | Medium | Har threshold ek named constant, ek file mein, sab tested. Prompt nahi, number badalna. |
| **Ladder rung khatam ho jaate hain aur bachcha phir bhi stuck hai** | High | Yahi END_KINDLY ka pura maqsad hai. Alert: `END_KINDLY / session` > 0.3 = curriculum sequencing ka problem, teaching ka nahi. |
| **Skill graph galat hai** | High | Loader validation + curriculum author review. Galat prereq bachche ko aisi cheez pe bhejta hai jiski usse zaroorat nahi. |
| **Speech enhancer sahi jawab ko galat bana deta hai** | **Critical** | Enhancer ko **kabhi** correct answer nahi milega — `child_speech_service` ka docstring yeh already kehta hai aur woh bilkul sahi hai. Enhancer sirf visible options dekhta hai. |
| **AI budget lesson ke beech khatam** | Medium | Templates identical shape ke hain. Bachcha farq nahi bata paayega. Test karo. |
| **Parent ko lagta hai woh control mein nahi hai** | High | Digest har roz batata hai ki plan kaise bana. §12 ki manual controls kabhi na hatao. |
| **`mock_storage` P1 se aage bach jaata hai** | Critical | P1 ka gate: `grep -r mock_ backend/app` khaali ho. |
| **Doc aur code drift kar jaate hain** | Medium | §13 ke checkboxes CI mein test names hain, sirf prose nahi. |

---

## 15. Appendix — component-by-component verdict

Har file jo aaj repo mein hai, aur uska bhavishya.

### backend/app/services/

| File | LOC | Verdict |
|---|---|---|
| `activity_evaluators.py` | 173 | **KEEP AS-IS.** Yeh already production-grade hai. Pure functions, LLM zero, registry-based, loader-enforced. Isse mat chhedo. |
| `answer_normalization_service.py` | 286 | **KEEP.** Conductor ke saath reuse hoga. |
| `answer_resolution_service.py` | 266 | **KEEP.** |
| `child_speech_service.py` | 265 | **EXTEND.** Deterministic hissa sahi hai. `needs_enhancement` band (0.30–0.80) mein AI enhancer jodo — aur woh enhancer ko correct answer **kabhi nahi** milega. |
| `curriculum_service.py` | 701 | **EXTEND.** `skill_graph.json` + `analogies.json` loading + validation. Fail-fast pattern already sahi hai. |
| `guide_agent_service.py` | 924 | **SPLIT.** Sabse bada refactor. → `ai/context.py`, `ai/policy.py`, `ai/validate.py`, `ai/templates.py`, `ai/providers/groq.py`, `services/explanation_service.py`. Aaj ke fallback branches (counting co-count, trace watch-me) **ladder rungs ban jaate hain** — logic bacha rehta hai, jagah badalti hai. |
| `learning_service.py` | 468 | **REFACTOR.** Scoring/stars/unlock rakho (sahi hain). Attempt/feedback loop Conductor ko de do. |
| `practice_service.py` | 247 | **MERGE.** Practice bhi Conductor chalayega, `sessions.mode` alag ke saath. |
| `daily_recommendation_service.py` | 117 | **ABSORB into plan engine.** `next_topic()` ka manifest-order walk sahi hai — plan engine use lega. |
| `learning_memory_service.py` | 163 | **REPLACE.** Isme raw psycopg + threading lock + module-level `_session_fallback` dict hai. P1 mein SQLAlchemy repository ban jaayega. Iska *purpose* (continuity memory) GREET state ke liye zaroori hai. |
| `avatar_service.py` | 139 | **KEEP + EXTEND.** Praise pools ko growth-mindset lexicon (§2.6) ke against audit karo. |
| `content_generator.py` | 98 | **REPLACE.** `LLMContentGenerator` aaj `MockContentGenerator` se inherit karta hai aur kuch nahi karta — yeh prototype shortcut honestly marked hai. `ai/` package isse le lega. |
| `safety_service.py` | 37 | **REPLACE.** Keyword regex list. Comment khud kehta hai "replace with layered moderation before production." §10.3 ka 11-step ladder isse replace karta hai. **Do bugs verified hain:** (1) `\b(...|fat|...)\b` ki wajah se *"The fat cat sat on the mat."* block ho jaata hai — ek bilkul valid nursery phonics line; (2) 600 char se lambi string poori `FALLBACK` se replace ho jaati hai, truncate nahi hoti — yaani ek lambi story narration chup ho jaati hai. |
| `guided_navigation_service.py` | 38 | **MERGE into `ai/validate.py`.** Iska allowlist `guide_agent_service.APPROVED_GUIDE_TARGETS` se **alag** hai — do allowlists, do sach. Ek karo. |
| `child_service.py` | 238 | **REFACTOR to repository.** Class resolution logic sahi hai. |
| `history_service.py` | 39 | **REPLACE** — `attempts` table. |
| `certificate_service.py` | 11 | **EXTEND** — async render (ARQ), object storage. |
| `mock_storage.py` | 9 | **DELETE** (P1) |
| `mock_auth.py` | 71 | **DELETE** (P2) |

### backend/app/api/ · schemas/ · data/

| Path | Verdict |
|---|---|
| `api/companion.py` (112) | **REPLACE** → `/conductor/{child_id}/open` |
| `api/guide.py` (11) | **KEEP** doubt-answering ke liye; teaching Conductor mein |
| `api/learning.py` · `api/practice.py` | **KEEP one release**, contract-tested, phir Conductor |
| `api/dev.py` (14) | **GATE** — non-production builds mein hi mount ho |
| `api/speech.py` (77) | **EXTEND** — enhancer band |
| `schemas/guide.py` (134) | **EXTEND** → `ConductorDirective` |
| `schemas/curriculum.py` (145) | **KEEP.** Comments ke saath achha authored schema. `lesson_flow`, `delivery`, `language` sab pehle se sahi jagah pe hain. |
| `data/curriculum/manifest.json` (94 KB) | **EXTEND** — 4 experience modes (§2.4) |
| `data/curriculum/activities/*.json` (664 KB) | **KEEP.** Yeh product ki asli asset hai. |
| `data/speech/kid_phonetics.json` | **EXTEND** — Hindi coverage, telemetry-driven |
| `data/rewards.json` · `avatar_messages.json` | **KEEP + audit** growth-mindset ke against |

### frontend/

| Path | Verdict |
|---|---|
| `app/globals.css` (3029 lines) | **REPLACE** (W2). Ek hi breakpoint source, fluid clamp() tokens. |
| `app/home/page.tsx` + `HomeExperience.tsx` | **REBUILD** → auto-open handshake (§5.2) |
| `app/adventure/**` (3 routes) | **DEMOTE** — plan-driven flow ke baad browse-only. Delete mat karo; parent aur ukg ke liye kaam ke hain. |
| `app/practice/**` | **ABSORB** into conductor |
| `components/curriculum/ActivityView.tsx` (438) | **REFACTOR** → ek `ActivityRenderer` (W4b) |
| `components/learning/TraceCanvas.tsx` (713) | **KEEP.** Deterministic geometry. `strokeScoring` mobile se port. Kabhi LLM call nahi. |
| `components/avatar/**` (8 files) | **KEEP + EXTEND** — Pip Conductor ka chehra hai. `AVATAR_STATE_INDEX` ke 11 states kaafi hain. |
| `components/guide/VisualGuideRenderer.tsx` | **EXTEND** — `demo_tap` |
| `services/guide.ts` (256) | **SHRINK.** Isme ek poora client-side `localGuide()` fallback teaching engine hai — do sources of truth. Server-directive-only rakho, offline pe ek chhota static banner. |
| `services/companion.ts` | **REPLACE** — conductor client |
| `services/api.ts` (90) | **KEEP.** Stale-session recovery achha sochchaa hua hai. |
| `services/speech.ts` (514) | **EXTEND** — barge-in mutex (C-40) |
| `lib/experience.ts` | **KEEP shape, shrink role** — server ab `presentation` bhejta hai |
| `lib/responsive/**` | **EXTEND** (W2) |
| `app/sentence-coach` · `word-coach` | **KEEP** — web-only, parity one-directional (W4) |

### mobile/

| Path | Verdict |
|---|---|
| **Poora `mobile/`** | **UNMODIFIED.** `upgrade-plan.md` W4 ka rule: web catches up. `git diff --stat mobile/` khaali rahega. |
| `src/ai/guideEvents.ts` `shouldCallAgent()` | **PORT to web** — first-try correct pe zero LLM |
| `src/ai/GuideActionExecutor.ts` + `guideSchema.ts` | **PORT** — double-checked allowlist, exactly usi shape mein |
| `src/features/tracing/strokeScoring.ts` | **PORT as-is** — deterministic geometry |
| `src/features/guide/DoubtOverlay` + `useHandRaise` | **PORT** — §5.4 |
| `src/activities/ActivityRenderer.tsx` + 8 components | **PORT** (W4b) |
| `src/components/responsive/` · `src/theme/` | **PORT** (W2/W4a) |

### docs/

| File | Verdict |
|---|---|
| `backend-architecture.md` (1051) | **AUTHORITATIVE** for infra. Yeh doc conflict nahi karta. |
| `frontend-architecture.md` (890) | **AUTHORITATIVE** for FE structure |
| `upgrade-plan.md` (586) | **AUTHORITATIVE** for W1–W4 |
| `ops/OP-04-ai-navigation.md` | **AUTHORITATIVE** for idle ladder aur 7 design rules — yeh doc unhe implement karta hai |
| `ops/OP-05-ai-tracking.md` | **AUTHORITATIVE** for mastery constants aur plan |
| `TRACK-A-experience-first.md` | **SUPERSEDED by this doc's phase plan.** TRACK-A ne Postgres defer kiya tha; aap production maang rahe ho, toh P1 pehle hai. TRACK-A ka §2 rule ("backend single source of truth") **rehta hai** aur yeh doc use aur sakht karta hai. |
| `CLAUDE.md` (root) | **UPDATE** — "avoid adding production infrastructure" ab galat hai. §1 ke R1–R10 se replace karo. |

---

## 16. Aage kya karna hai

1. **§12 padho pehle.** Agar aap us list ki kisi cheez ko automate karna chahte ho, woh
   baat abhi karni chahiye — kyunki design uske around bana hai.
2. **P1 (Postgres) start karo.** `mock_storage.py` maujood rehte hue kuch bhi durable nahi ho
   sakta. Conductor ko `lesson_states` chahiye, aur usko ek asli DB chahiye.
3. **P6 ko pehla "AI" phase samjho, P0 nahi.** Infra ke bina Conductor ek prototype hai — aur
   aapke paas ek prototype already hai.
4. Har phase apna gate pass kare. **Ek session mein ek prompt.**

**Pehli line jo AI teacher bolega:**

> *"Namaste! Kal humne A seekha tha. Aaj B se milte hain — chalein?"*

Us ek line mein poora doc hai: continuity (`learning_memory`), plan (deterministic),
warmth (validated copy), aur bachche ki marzi (😴 hamesha maujood).

---

*Document ends. Grounded in a full read of `backend/` (21 service modules, 11 routers, 11 schema
modules, 758 KB authored curriculum), `frontend/` (19 routes, 33 components, 11 services),
`mobile/src` in full, and all 16 files in `docs/`.*
