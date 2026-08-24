# SAKSHAM IQ — Production Workflow

### v2.0 · Do track, teen gates, aur teen cheezein jo v1.0 mein galat thi

**Repo:** `D:\testcase` — `backend/` (FastAPI) · `frontend/` (Next.js) · `mobile/` (Expo RN)
**Version:** 2.0 · 2026-08-23 (v1.0 supersede karta hai — §1 padho)
**Companions:** `AI-100-PERCENT-AUTOMATION.md` (kya banana hai) · `AGENT-FLOW.md` §12 (build order) ·
`AI-ARCHITECTURE-DECISIONS.md` §3 (RLHF kyun reject hua) · `TEACHING-GRAPH-SPEC.md` (nodes/edges)

> Yeh doc *kis order mein, kis gate ke saath, kis scale pe* — woh batata hai.
> **v1.0 mein teen structural galtiyaan thi.** §1 unhe naam se likhta hai, kyunki
> ek plan jo apni galti chhupata hai, plan nahi — marketing hai.

**Doc bhasha:** Hinglish prose, English technical terms/tables.

---

## Contents

| § | Section | Kya milega |
|---|---|---|
| 1 | **v1.0 ki teen galtiyaan** | Shadow mode · gate ka sample size · variant bank |
| 2 | Do numbers jo poora plan badalte hain | 48% · 80% — measured, guessed nahi |
| 3 | Aaj ka scorecard | ~15%, aur kyun |
| 4 | Core insight | RL ko agent ka intezaar nahi karna |
| 5 | Phase 0 — Foundation | F0 variant bank · F1 cutover · F2 auth · F3 metrics |
| 6 | Phase 1 — Do track | Track A (agent) · Track B (RL) |
| 7 | **Scale ladder** | Kis DAU pe kaunsa gate lagta hai |
| 8 | Rollout, rollback, kill switch | Ek variable at a time |
| 9 | Cost model | Per child per day, 6k DAU pe |
| 10 | Privacy — jo v1.0 mein tha hi nahi | Child speech third-party pe |
| 11 | Team shape | "Parallel" ka matlab ≥2 log |
| 12 | Har hafte kya dekhna hai | Do jodi numbers |
| 13 | Agent prompts | Ek session mein ek |
| 14 | Definition of done | CI test names |
| 15 | Sunset criteria | Agent gate kabhi pass na ho toh? |

---

## 1. v1.0 ki teen galtiyaan

### G1 — "Shadow mode mein Q-values bharte rahenge" — **yeh galat hai**

v1.0 ne kaha tha: policy shadow mode mein 2 hafte chalegi aur Q-table bharta rahega bina kisi
bachche ko chhue. **Aisa hota hi nahi.**

Shadow mode mein policy action `A` chunti hai, par chalta ladder ka action `L` hai. Reward `L`
ke outcome se aata hai. Ab do hi raaste hain, aur dono mein Q-table policy ke apne chunav ke
baare mein kuch nahi seekhta:

| Agar episode mein likha | Nateeja |
|---|---|
| `action = A` (policy ka chunav) | **Mislabeled data.** Reward `L` ka hai, label `A` ka. Yeh no-data se *badtar* hai — policy galat cheez confidently seekh legi |
| `action = L` (jo asli mein chala) | Valid off-policy data, par sirf un actions ke baare mein jo ladder khud leta hai. Jo action ladder kabhi nahi leta, uska Q-value hamesha prior pe atka rahega |

**Sahi baat:** shadow mode **plumbing validate karta hai, policy train nahi karta.** Episode
mein `L` likho (off-policy, ladder = behaviour policy), aur saath mein `policy_choice` column
mein `A` bhi log karo — sirf yeh dekhne ke liye ki policy ladder se kitna alag soch rahi hai.
Policy apne chunav ke baare mein tabhi seekhna shuru karegi jab woh 10% live traffic pe apna
action actually chalayegi.

**Iska plan pe asar:** shadow mode ki value "training" nahi, "divergence measurement" hai. 2
hafte kaafi hain, par expectation badal gayi.

### G2 — Ship gate chhote scale pe **compute hi nahi ho sakta**

`AGENT-FLOW.md` §11.4 kehta hai "attempts-to-correct ≥10% behtar". v1.0 ne isko bina soche
copy kar liya. Statistically yeh kya maangta hai:

```
baseline attempts-to-correct ≈ 2.5, sd ≈ 1.5
10% relative improvement    = 0.25 absolute
Cohen's d                    = 0.25 / 1.5 ≈ 0.167
n per arm (80% power, α=.05) ≈ 16 / d²   ≈ 575 episodes
child-level clustering (ICC ~0.2, ~30 episodes/child) → design effect ≈ 6.8
                             ≈ 3,900 episodes per arm
                             ≈ 130 children per arm
```

| Scale | 4 hafte mein 10% arm | Gate compute ho sakta hai? |
|---|---|---|
| 50 children (pilot) | ~5 children, ~1,400 episodes | ❌ **Nahi.** Effectively n=5 |
| 500 children | ~50 children, ~14,000 episodes | ⚠️ Marginal |
| 6,000 DAU (target) | ~600 children, ~170,000 episodes | ✅ Haan |

**Sahi baat:** gate scale-dependent hai. §7 mein teen alag gates hain — pilot, growth, scale.
Pilot pe "≥10% behtar" maangna matlab hamesha fail hona, aur phir gate ko ignore karna seekh
jaana — jo gate na hone se badtar hai.

### G3 — Variant bank ko optional maan liya — **woh hard blocker hai**

v1.0 ne retention probe ko step B1 rakha aur variant bank ka zikr hi nahi kiya. Par probe ka
poora point hi "alag form mein poocho" hai. §2 ke numbers batate hain ki curriculum mein woh
alag form hai hi nahi.

**Sahi baat:** variant bank ab **F0** hai — Phase 0 ka pehla kaam, B1 se pehle.

---

## 2. Do numbers jo poora plan badalte hain

Curriculum ko scan karke nikale, andaaze nahi:

```
1,030 activities · 579 distinct skill_id

skills with exactly ONE activity      : 276  (48%)
skills with only ONE activity TYPE    : 464  (80%)
```

**Iske teen seedhe nateeje:**

1. **48% skills kabhi "mastered" nahi ho sakte the.** P1 ka gate `MIN_DISTINCT_FORMS = 2`
   maangta tha. Jis skill ke paas ek hi activity hai, uske paas do form aa hi nahi sakte — toh
   bachcha chahe kitna bhi sahi kare, skill locked, aur uspe depend karne wale saare topics
   permanently locked. **Yeh P1 mein maine daala hua live bug tha; fix ho chuka hai**
   (`forms_available` column + `required_forms()`: jahan do form hain wahan do maango, jahan
   ek hai wahan ek).
2. **80% skills pe retention probe transfer test kar hi nahi sakta** — same form dobara
   poochna recall test karta hai, transfer nahi. `REWARD_TRANSFER_BONUS` un skills pe kabhi
   nahi milega, aur reward signal ka aadha hissa gayab.
3. **Isliye F0 = variant bank.** Har skill ke liye kam se kam ek doosra form — authored ya
   content studio se generated. Iske bina B (RL track) ka reward aadha-adhoora hai.

---

## 3. Aaj ka scorecard

`AGENT-FLOW.md` §12 ki 14-step list mein **step 1 poora**, baaki 13 baaki.

| Cheez | Status |
|---|---|
| Postgres schema + Alembic + repositories | ✅ `app/db/` — 22 tests green |
| Mastery gate | ✅ fixed (§2.1) — single-form skills ab masterable |
| Q-learning tables + retention reward | ✅ likhe hain, **koi episode likh nahi raha** |
| Guide ka LLM call (T2/T3/T7) | ✅ live, Groq |
| Services (`child_service`, `learning_service`, `mock_auth`, …) | ❌ `mock_storage` pe |
| Variant bank (second form per skill) | ❌ **80% missing** |
| Branch engine · Envelope · Agent runtime | ❌ scaffold zip mein |
| Teacher Agent · Planner Agent · policy selector | ❌ |
| Metrics / holdout / cost monitor | ❌ |

**AI automation ~15%.**

---

## 4. Core insight — RL ko agent ka intezaar nahi karna

> **Policy sirf chunti hai ki kaunsi strategy chale (S1–S9).
> Usko *bolna* `_question_teaching_message()` already deterministically jaanta hai.**

Isliye Q-learning envelope (#6) aur Teacher Agent (#8) se pehle ship ho sakta hai, aur us waqt
bachche tak koi naya LLM-authored text nahi jaa raha — sirf strategy ka chunav badla hai.

**Par G1 ke baad ek caveat:** policy ko *seekhne* ke liye apna action actually chalana padega.
Isliye RL ka "safe" hissa shadow mode nahi, balki yeh hai ki uska output deterministic wording
se hokar guzarta hai. Blast radius chhota hai, **zero nahi.**

---

## 5. Phase 0 — Foundation

| # | Kaam | Effort | Blocker for |
|---|---|---|---|
| **F0** | **Variant bank** — har skill ka doosra form | L | B1, B2, B3 (poora RL track) |
| **F1** | Services → Postgres cutover | M | Sab kuch |
| **F2** | Auth + consent (argon2, HttpOnly cookie, `consent_granted_at`) | M | Live jaana |
| **F3** | Metrics table + rollup + `/ops/metrics` | S | Dono gates |

### F0 — Variant bank (naya, v1.0 mein nahi tha)

464 skills ke paas ek hi activity-type hai. Har ek ke liye ek doosra form chahiye jo *wahi
skill* test kare, *alag tareeke* se:

| Skill ka form 1 | Form 2 kaisa ho |
|---|---|
| `select_letter` — "अ pe tap karo" | `repeat_letter` — "अ bolo" |
| `multiple_choice` — "kaunsa circle hai?" | `identify_in_scene` — tasveer mein dhoondo |
| `trace` — line follow karo | `select_letter` — jo abhi banaya usko pehchaano |

Do raaste, aur dono chal sakte hain:

- **Authored** — sahi, dheema, ~460 activities likhni padengi
- **Content studio (LangGraph, offline)** — `AGENT-FLOW.md` #14. Yahi LangGraph ka *sabse
  accha* use case hai: offline, batch, human review ke saath, aur bachche ke saamne live nahi

> **Recommendation:** pehle 100 highest-traffic skills authored karo (2 hafte), baaki content
> studio se — human review ke saath. RL track 100 skills pe shuru ho sakta hai.

### F1 — Services cutover

| Service | Kis repository pe | Order |
|---|---|---|
| `history_service.py` | `truth.record_attempt` | 1 (sabse chhota, cutover pattern yahin banega) |
| `certificate_service.py` | `models.Certificate` | 2 |
| `child_service.py` | `learners.*` | 3 |
| `practice_service.py` | `truth.record_attempt` | 4 |
| `learning_service.py` | `truth.save_lesson_state` + `record_attempt` | 5 (sabse bada) |
| `mock_auth.py` | `learners.*` | 6 (F2 ke saath) |
| `learning_memory_service.py` | **delete** — `topic_memories` ki jagah `attempts` | 7 |

> Ek-ek cut, har cut ke baad poora suite (aaj 210 green). Sab ek saath = kaunsa toota, pata
> nahi chalega.

### F3 — Metrics ⚠️ **F1/F2 ke saath hi, baad mein nahi**

Gates 4 hafte ka data maangte hain. Baad mein banaoge toh rollout se pehle ka data gayab, aur
gate pass karne ke liye dobara 4 hafte.

Din 1 se: `attempts_to_correct` · `answer_leak_veto_rate` · `retention_7day` ·
`pending_episodes` · `p95_latency` · `end_kindly_rate` · `safety_incidents` ·
`ai_cost_usd_per_child_day` · `policy_ladder_divergence` (G1 ke liye naya).

---

## 6. Phase 1 — Do track

```
          ┌──────────────── TRACK A · Agent ─────────────────┐
F0,F1 ────┤ A1 branch engine → A2 envelope → A3 runtime      │───┐
F2,F3     │ → A4 Teacher Agent (shadow: latency+veto check)  │   │
          └─────────────────────────────────────────────────┘   │
                                                                ├─→ MERGE
          ┌──────────────── TRACK B · RL ───────────────────┐   │
          │ B1 probe injection → B2 seed priors             │   │
          │ → B3 selector → B4 shadow (divergence only, G1) │───┘
          └─────────────────────────────────────────────────┘
```

### Track A

| # | Kaam | Kyun is order mein |
|---|---|---|
| A1 | Deterministic branch engine | Agent ka fallback **aur** baseline. Iske bina holdout comparison possible hi nahi |
| A2 | Envelope — 26 rules, `answer_leak` detector | Agent se pehle. Unguarded output = bachche ko galat jawab |
| A3 | Agent runtime — bounded loop, 2.5 s deadline, 1 retry, budget | Dono agents ka common |
| A4 | Teacher Agent shadow — **latency aur veto rate measure karne ke liye**, training ke liye nahi | 2 hafte |

### Track B

| # | Kaam | Kyun is order mein |
|---|---|---|
| B1 | Probe injection — due probes daily plan mein, **alag form mein** (F0 chahiye) | Iske bina reward hamesha NULL |
| B2 | Q-table ko ladder priors se seed | Cold start: day-one worst case = aaj ka behaviour |
| B3 | Selector — ε-greedy + hard constraints + bandit→Q staging | Constraints learnable **nahi** |
| B4 | Shadow — `policy_ladder_divergence` measure | G1: yahan training nahi hoti |

**Cold-start priors (B2)**

| Rung | Standard | Early mode |
|---|---|---|
| 0 | S1_TELL, S2_SHOW | S1_TELL, S2_SHOW |
| 2 | S3_EXAMPLE, S5_CONTRAST | S1_TELL, S2_SHOW |
| 3 | S4_STORY, S6_DO_TOGETHER, S7_SENSE_SWITCH | S2_SHOW, S6_DO_TOGETHER |
| ≥4 | S9_PARK (forced) | S9_PARK (forced) |

**Staging (B3):** `visits < 50 → γ = 0` (pure contextual bandit) · `visits ≥ 50 → γ = 0.85`.
Ek function, ek `if`. Do alag system mat banao.

**Teen hard constraints — Q-value se nahi aa sakte:**

1. Rung ≥ 4 pe sirf `S9_PARK`
2. Rung < 4 pe `S9_PARK` menu par nahi — warna policy seekh legi ki mushkil bachche ko jaldi
   park karna "sasta" hai
3. Spent strategy aur early-mode ka illegal set menu se bahar

**State:** `experience_mode(2) × mastery_bucket(4) × rung(5) × spent_count(4)` = 160 states ×
9 actions ≈ 1,440 cells. Ek insaan poori table padh, diff kar, revert kar sakta hai.

---

## 7. Scale ladder — kis DAU pe kaunsa gate

G2 ka jawab. **Gate scale ke saath badalta hai, warna aap gate ko ignore karna seekh jaoge.**

### Gate P — Pilot (< 200 children)

Statistical power hai hi nahi. Toh **safety + qualitative**, efficacy nahi:

- [ ] 4 hafte zero safety incident (shame, PII, off-curriculum)
- [ ] `answer_leak_veto_rate` < 0.5%
- [ ] p95 latency budget mein
- [ ] **100 golden transcripts par manual review** — do teachers, blind, "yeh bachcha padha ya sirf jawab tak pahuncha?"
- [ ] `attempts_to_correct` **kharaab nahi hua** (non-inferiority, superiority nahi)
- [ ] `pending_episodes` drain ho raha hai

### Gate G — Growth (200–2,000 children)

Gate P ka sab kuch, plus:

- [ ] `attempts_to_correct` non-inferior, 95% CI ki lower bound > −5%
- [ ] `retention_7day` non-inferior
- [ ] Cost per child per day budget mein (§9)

### Gate S — Scale (> 2,000 children) = `AGENT-FLOW.md` §11.4 ka original gate

- [ ] `attempts_to_correct` ≥10% behtar, **statistically significant**, ≥130 children per arm
- [ ] `end_kindly_rate` nahi badha
- [ ] `answer_leak_veto_rate` < 0.5% **aur** trend flat/neeche
- [ ] `retention_7day` barabar ya behtar
- [ ] p95 budget mein · 4 hafte zero safety incident

> **Holdout assignment sticky per child hona chahiye, per session nahi.** Warna (a) experiment
> contaminated, aur (b) ek hi bachche ko alag-alag din alag teacher milega — jo child
> experience ke liye bhi kharaab hai. `hash(child_id + experiment_salt) % 100`.

---

## 8. Rollout, rollback, kill switch

### Order — ek time pe ek variable

| Step | Kya | Gate |
|---|---|---|
| 1 | B → 10% (policy live, deterministic wording) | §7 ka current-scale gate |
| 2 | B → 50% → 100% | p95 + safety re-check |
| 3 | A → 10% (Teacher Agent live, policy ke chune strategy ko word karta hai) | §7 |
| 4 | A → 50% → 100% | p95 + safety re-check |
| 5 | Planner Agent → 10% → 100% | §7 |

> **Dono track ek saath 10% pe kabhi nahi.** Retention gira toh attribute nahi kar paoge.

### Rollback — v1.0 mein tha hi nahi

Har rollout step ke saath yeh teen cheezein ready honi chahiye, **pehle se test ki hui**:

| Level | Kya | Kitni der |
|---|---|---|
| **L1 — Feature flag** | `POLICY_TRAFFIC_PCT=0` / `AGENT_TRAFFIC_PCT=0`, restart ke bina | < 60 s |
| **L2 — Q-table revert** | Har raat `policy_q_values` ka snapshot; `q_table_restore <date>` | < 10 min |
| **L3 — Prompt pin** | Prompt version pinned aur DB mein versioned; pichhle version pe pin | < 10 min |

**Kill switch trigger — automatic, insaan ke faisle ka intezaar nahi:**

- `answer_leak_veto_rate` > 2% kisi bhi rolling hour mein → L1
- p95 latency > 2× budget, 15 min tak → L1
- Koi bhi confirmed safety incident → L1, turant

---

## 9. Cost model — v1.0 mein nahi tha

`backend-architecture.md` §1.4 ke budgets: **12 LLM calls/session, 200/child/day**.

```
Groq llama-3.1-8b-instant, guide turn:
  input  ≈ 1,400 tokens (system + overlays + payload)
  output ≈    90 tokens

per turn      ≈ 1,490 tokens
per session   ≈ 12 turns  ≈  17,900 tokens
per child/day ≈ 1.5 sessions ≈ 27,000 tokens

6,000 DAU     ≈ 162M tokens/day  ≈  4.9B tokens/month
```

**Isse teen cheezein nikalti hain:**

1. **Prompt caching zaroori hai, optional nahi.** `CORE_SYSTEM_PROMPT` ~800 tokens ka hai aur
   har turn bhejta hai — total ka ~54%. Cache karo toh input cost aadhe se kam.
2. **Per-child/day hard cap enforce karo**, warna ek stuck bachcha (repair ladder loop) poore
   din ka budget kha sakta hai. Park-at-4 pehle se yeh rok raha hai — **iski value cost mein
   bhi hai, sirf pedagogy mein nahi.**
3. **`ai_cost_usd_per_child_day` ko F3 metrics mein daalo.** Gate mein nahi, par weekly review
   mein — kyunki agent 10% se 100% pe jaane ka matlab cost 10× hai.

---

## 10. Privacy — v1.0 mein bilkul nahi tha

Yeh sabse badi missing cheez thi. Consent ke aage kuch nahi likha tha.

| Sawaal | Aaj | Kya chahiye |
|---|---|---|
| **Bachche ki awaaz ka transcript third-party (Groq) pe jaata hai?** | Haan — `feature` field mein child speech hoti hai | Transcript se PII strip karo; bachche ka naam prompt mein kabhi nahi (aaj `child_id` jaata hai, naam nahi — verify karo) |
| Data retention | Koi policy nahi | `attempts` 24 mahine, `policy_episodes` 12 mahine, raw transcripts **0 din** (store hi mat karo) |
| DPDP right to erasure | Koi raasta nahi | `DELETE /children/{id}` → cascade already schema mein hai; endpoint aur audit log chahiye |
| Groq ka data retention | Verify nahi kiya | **Ship se pehle DPA check karo.** Agar zero-retention nahi hai, self-hosted model ya alag vendor |
| `policy_q_values` mein PII? | Nahi — state key mein sirf band/bucket/rung | ✅ by design. Isse aisa hi rakho |

> **Yeh F2 ka hissa hai, baad ka kaam nahi.** Bina iske "production" kehna galat hai.

---

## 11. Team shape — "parallel" ka matlab

v1.0 ne do parallel track dikhaye bina yeh bataye ki parallel chalane ke liye **do log** chahiye.

| Team | Track A + B parallel? | Realistic timeline |
|---|---|---|
| 1 dev | ❌ Nahi — sequential | F0 se Gate P tak ~16–20 hafte |
| 2 devs | ✅ Haan (ek per track) | ~10–12 hafte |
| 3 devs + 1 content | ✅ Haan, F0 bhi parallel | ~8 hafte |

**Agar ek hi dev hai:** Track B pehle poora karo, phir Track A. Wajah §4 — RL ka blast radius
chhota hai, aur woh pehle live jaake seekhna shuru kar dega jabki aap Track A bana rahe ho.

---

## 12. Har hafte kya dekhna hai

| Jodi | Kya batati hai |
|---|---|
| `attempts_to_correct` **+** `answer_leak_veto_rate` | Attempts gir rahe **aur** vetoes badh rahe = system padha nahi raha, **cheat kar raha hai** |
| `pending_episodes` **+** `retention_7day` | Pending badh raha = probes puche nahi ja rahe. Policy **bina error diye** seekhna band kar chuki hai |
| `policy_ladder_divergence` **+** `end_kindly_rate` | Divergence high aur park rate bhi high = policy ladder se alag ja rahi hai aur natija kharaab hai |
| `ai_cost_usd_per_child_day` **+** traffic % | 10% → 100% ka matlab 10× cost. Surprise nahi hona chahiye |

---

## 13. Agent prompts — ek session mein ek

**F0 — variant bank (pehle 100 skills)**

> Read `docs/PRODUCTION-WORKFLOW.md` §2 and §5 F0. For the 100 highest-traffic skills that
> currently have a single activity type, author one second-form activity each that tests the
> same `skill_id` through a different `type`. Do not change any existing activity. Add a test
> asserting those 100 skills now report `forms_available >= 2`.

**F1 — services cutover (ek service)**

> Read `CLAUDE.md` and `backend/app/db/repositories/`. Cut `history_service.py` from
> `mock_storage.mock_activity_attempts` to `truth.record_attempt`, that service only. Keep the
> suite green; add tests for the durable path. Do not touch any other service this session.

**F3 — metrics**

> Read §5 F3 and §12. Add a `metrics` table, a rollup job for the nine series named there, and
> a read-only `/ops/metrics` endpoint. No dashboard UI this session — the series must exist
> before anything rolls out; the chart can wait.

**B1 — probe injection**

> Read §6 Track B and `backend/app/db/repositories/policy.py`. Make `due_probes()` feed the
> daily plan: a due probe becomes a question posed in a *different* form from the teaching
> question (F0 supplies it), and answering it calls `settle_probe()`. Add a test that
> `pending_episodes` drains, and one that a probe is never posed in the same form.

**B3 — selector**

> Read §6 Track B and `backend/app/policy/actions.py`. Add `app/policy/state.py` and
> `app/policy/selector.py` (ε-greedy over `legal_actions`, bandit→Q staging at 50 visits). The
> three hard constraints must be unlearnable — add a test that no sequence of rewards makes the
> policy park below rung 4.

**B4 — shadow mode**

> Read §1 G1 carefully. In shadow mode the episode records the action the ladder *actually*
> took, plus a `policy_choice` column for what the policy would have chosen. Do not label
> episodes with the policy's choice — that is mislabeled data and worse than none. Emit
> `policy_ladder_divergence`.

**A2 — envelope**

> Unpack `saksham-langchain-agents.zip`'s `app/agents/envelope.py` and wire it to the current
> schemas. All 26 rules, `answer_leak` detector reporting to F3's series. Contract test: no
> agent output reaches a child without passing the envelope.

---

## 14. Definition of done — CI test names

| Test | Asserts |
|---|---|
| `test_no_service_imports_mock_storage` | F1 poora — AST walk, mocks nahi |
| `test_every_skill_has_a_second_form` | F0 poora (ya explicit allowlist) |
| `test_consent_is_never_granted_by_automation` | `grant_consent` sirf parent route se reachable |
| `test_no_child_name_reaches_the_model` | §10 — prompt payload mein naam nahi |
| `test_truth_node_isolation` | Evaluator kisi LLM tak nahi pahunchta, kisi import path se |
| `test_every_agent_has_a_deterministic_fallback` | Har agent node ka `on_fail` edge deterministic pe |
| `test_shadow_episodes_record_the_executed_action` | G1 — mislabeled data nahi |
| `test_pending_episodes_drain` | Probes puche jaate hain, reward settle hota hai |
| `test_policy_cannot_learn_to_park_early` | Constraints unlearnable |
| `test_a_single_form_skill_can_still_be_mastered` | ✅ **green** — §2.1 ka fix |
| `test_leaking_the_answer_is_paid_less_than_teaching_it` | ✅ **green** — reward boundary |

---

## 15. Sunset criteria — agar gate kabhi pass na ho

v1.0 ne yeh socha hi nahi tha. Har experiment ka ek end hona chahiye, warna woh hamesha
"agle hafte" chalta rehta hai.

| Kitne baad | Faisla |
|---|---|
| **12 hafte** Teacher Agent 10% pe, gate fail | Agent band. Deterministic ladder + policy hi production hai. Cost bachega, latency behtar hogi |
| **12 hafte** policy 10% pe, gate fail | Priors pe wapas (= aaj ka ladder), exploration off. Q-table data ke liye chalta rahe |
| `answer_leak_veto_rate` 2 hafte tak > 1% | Agent band jab tak envelope theek na ho — traffic ghatana nahi, band karna |

**Yeh failure nahi hai.** Deterministic ladder + retention-based policy apne aap mein ek accha
product hai. LLM agent us par ek improvement hai — agar improvement measure na ho, toh woh
improvement hai hi nahi, sirf cost hai.

---

## 16. Ek line mein: kya pehle

**F0 (variant bank) → F3 (metrics) → B1 (probe injection).**

F0 ke bina reward ka aadha hissa unearnable hai. F3 ke bina koi gate compute nahi hoga.
B1 ke bina policy chup-chaap kabhi nahi seekhegi.

---

Saksham IQ · Production Workflow v2.0 · 2026-08-23
v1.0 supersede — §1 mein teen corrections
Build order: `AGENT-FLOW.md` §12 · Original gate: `AGENT-FLOW.md` §11.4 (ab §7 ka Gate S)
