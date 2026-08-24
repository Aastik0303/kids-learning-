# TEACHING LOOP — Aapka Flow, Poora Design

### "A kya hai" se lekar "A aa gaya" tak — end to end

**Repo:** `D:\testcase` · **Version:** 1.0 · 2026-08-19
**Companions:** `docs/AI-100-PERCENT-AUTOMATION.md` · `docs/AI-ARCHITECTURE-DECISIONS.md` · `docs/AGENT-FLOW.md`
**Visual:** `docs/teaching-loop-visual.html` — isi doc ka diagram

---

## 0. Aapka flow, mere shabdon mein

Aapne jo bataya, main use exactly aise samjha hoon. Agar kahin galat samjha hoon, wahi
theek karna sabse pehle:

```
 1.  Bachcha web app mein enter karta hai
 2.  AI uska pichhla data padhta hai (kal kya kiya, kya aata hai, kya nahi)
 3.  AI aaj ka schedule banata hai
 4.  AI schedule ke hisaab se class KHUD kholta hai
 5.  Class start hoti hai — teacher padhana shuru karta hai
 6.  Bachche ko "A" nahi pata
 7.  AI teacher use batata hai ki A kya hai          ← EXPLAIN
 8.  Phir poochta hai                                 ← ASK
 9.  Bachcha jawab deta hai                           ← RESPONSE
10.  AI response ke basis pe DECIDE karta hai:
        sahi hai  → aage badho
        galat hai → story ya example do, phir dobara poochho
11.  Jab tak sahi response nahi aata, aage nahi badhna
12.  Har class ke syllabus ke hisaab se hardness alag — upar ki class, zyada mushkil
```

**Point 1–10 aur 12 pe main poori tarah aapke saath hoon.** Woh design ban chuka hai
(§2, §3, §4, §6).

**Point 11 pe ek problem hai — aur woh opinion nahi, aapke apne data se nikli hai.**
Woh §1 hai. Usse padh lijiye, phir baaki doc.

---

## Contents

| § | Section |
|---|---|
| 1 | **"Jab tak sahi na kare" — ek zaroori sudhaar** (data ke saath) |
| 2 | **The Concept Loop** — aapka loop, formalized |
| 3 | **9 Teaching Strategies** — "story ya example" ka poora set |
| 4 | **Difficulty Engine** — class ke hisaab se hardness, 6 dials |
| 5 | **Reinforcement Learning — HAAN**, par kaunsa (RLHF nahi) |
| 6 | **End-to-end workflow** — aapke 12 steps → system events |
| 7 | **11 Enhancements** — jo maine add kiye |
| 8 | Data model |
| 9 | Build order |

---

## 1. "Jab tak sahi response na de, move mat karo" — ek zaroori sudhaar

### 1.1 Aapka irada 100% sahi hai

> *"Bachcha A seekhe bina aage na jaaye."*

Yeh **mastery-based progression** hai, aur yeh sahi pedagogy hai. Time-based progression
(ghanta khatam, agla topic) hi wo cheez hai jisse school system fail karta hai. Aap sahi
soch rahe ho.

### 1.2 Par mechanism tootа hua hai — aur proof aapke apne content mein hai

Maine aapki chaaron activity files padhi. Yeh numbers hain:

| Class | Activities | Options per question |
|---|---|---|
| `playgroup` | 311 | **hamesha 2** (146/146) |
| `nursery` | 503 | **3** (251), 2 (25) |
| `lkg` | 98 | 2 (62), 3 (27) |
| `ukg` | 118 | 2 (67), 3 (28) |

Ab "jab tak sahi na kare, move mat karo" ka matlab dekhiye — **ek aisa bachcha jisko
kuch nahi aata, sirf random tap kar raha hai:**

| Options | 1 try | 2 tries | 3 tries | 4 tries | Unlimited |
|---|---|---|---|---|---|
| **2** (playgroup — sab) | 50% | 75% | **87.5%** | 93.8% | **100%** |
| **3** (nursery — zyadatar) | 33% | 55.6% | **70.4%** | 80.2% | **100%** |

> **"Jab tak sahi na kare" wala loop hamesha khatam hota hai — chahe bachche ne kuch bhi
> na seekha ho.** Woh sikke ke uchhalne pe khatam hota hai, seekhne pe nahi.
>
> Playgroup mein toh 3 try mein 87.5% bachche "pass" ho jaayenge bina A jaane.

Aur ek doosri baat, jo isse bhi zaroori hai:

> Ek 3-saal ka bachcha jo 3 baar fail ho chuka hai, **jaanboojh kar random tap karna
> shuru kar deta hai** — sirf loop se nikalne ke liye. Toh aap sirf galat data nahi le
> rahe. Aap use sikha rahe ho ki **seekhna ek aisi cheez hai jisse bhaagna hota hai.**

### 1.3 Sudhaar — do alag gates

Aapka irada poora zinda rehta hai. Bas gate ki jagah badalti hai:

| | **SITTING GATE** ❌ | **CONCEPT GATE** ✅ |
|---|---|---|
| Rule | "Is sawaal se tab tak mat hato jab tak sahi na ho" | "Is concept ko tab tak *seekha hua* mat maano jab tak sach mein na aa jaaye" |
| Kahan lagta hai | Ek baithak, ek sawaal | Poore curriculum ki progression |
| Khatam kab hota hai | Coin flip pe | Mastery pe |
| Bachche ka anubhav | Phansa hua | Aage badhta hua, par A wapas aata rehta hai |
| Aapka irada poora? | — | **Haan — poora** |

**Concept Gate ka matlab practically:**

```
Ek session mein:  A pe max 4 attempts. Uske baad A ko PARK kar do.
                  Bachcha kuch aur karta hai — mood bacha rehta hai.

A ka kya hua:     A "seekha hua" NAHI mark hua. Woh revisit_queue mein hai.
                  KAL A phir aayega — sabse pehle.
                  Aur agle din bhi, jab tak sach mein na aa jaaye.

Aage kya locked:  Jo bhi A pe depend karta hai, woh locked hai.
                  skill_graph.json ke edges se.
                  Bachcha "Apple" nahi padh sakta jab tak A nahi aata.
                  ← YAHI aapka "move nahi karoge" hai, sahi jagah pe.
```

**Farq ek line mein:** *baithak* aage badhti hai, *curriculum* nahi.

### 1.4 "Seekha hua" ka matlab kya — aur ek lucky tap kyun kaafi nahi

Agar A ko "aa gaya" mark karne ke liye ek sahi jawab kaafi ho, toh playgroup mein
**50% bachche pehli koshish mein hi "seekh" jaayenge** — bina kuch jaane.

Aapke `docs/ops/OP-05-ai-tracking.md` mein pehle se **sahi formula** likha hai, aur usmein
yeh problem already hal hai:

```python
def outcome(attempt_index, is_correct):
    if not is_correct:      return 0.0
    if attempt_index == 1:  return 1.0     # pehli koshish mein — YEH aata hai
    if attempt_index == 2:  return 0.6     # soch ke nikala
    return 0.3                             # aakhir mein kar liya

mastered = effective >= 0.75 and attempts_total >= 4
```

**Dekhiye yeh kya karta hai:** 4th try pe mila hua sahi jawab sirf **0.3** deta hai.
Isliye grind karke mastery nahi milti. Mastery **pehli koshish** ke sahi jawab se milti hai,
aur woh bhi **4 baar, alag-alag activities pe.**

Random tap se yeh milne ka chance:

| Options | 4 consecutive first-try correct, sirf luck se |
|---|---|
| 2 | **6.25%** |
| 3 | **1.2%** |

**Yeh acceptable hai. Aur yeh spec aapke paas pehle se hai** — bas use aaj implement nahi
kiya gaya. Concept Gate isi formula pe khada hoga.

### 1.5 Toh aapka rule, final shape mein

> **"Jab tak A sach mein na aa jaaye, A se aage nahi badhenge."**
>
> - A ki mastery `< 0.75` → A pe depend karne wala kuch bhi unlock nahi hoga
> - A **har din** wapas aayega, session ki shuruaat mein
> - Ek baithak mein A pe **max 4 attempts** — phir A park, kuch aur karo
> - A ka status: *"abhi seekh rahe hain"* — **kabhi "fail" nahi**
> - 3 din se A atka hai → parent ko real-world activity card
>   (`parent_activity` type aapke content mein pehle se hai)

Aapko jo chahiye tha, woh mila. Bachcha bhi bacha.

---

## 2. The Concept Loop — aapka loop, formalized

Yeh **§0 ke steps 6–11** ka exact design hai.

```
                      ┌─────────────────────────────┐
                      │  CONCEPT ENTER: "A"         │
                      │  skill_id = "letter_A"      │
                      └──────────────┬──────────────┘
                                     ▼
              ┌──────────────────────────────────────────┐
              │  PRE-CHECK   (naya — Enhancement E1)     │
              │  • prerequisite aata hai?  nahi → prereq │
              │  • kya A pehle se aata hai? → skip       │
              │    (aane wali cheez padhana time waste)  │
              └──────────────┬───────────────────────────┘
                             ▼
         ┌───────────────────────────────────────────────┐
    ┌───►│  TEACH        strategy S(n) chuni gayi        │  ← AGENT/RL
    │    │  n=1 pe hamesha TELL + SHOW (pehla exposure)  │
    │    └───────────────────┬───────────────────────────┘
    │                        ▼
    │    ┌───────────────────────────────────────────────┐
    │    │  ASK          ek check question                │
    │    │  difficulty engine se chuna (§4)               │
    │    └───────────────────┬───────────────────────────┘
    │                        ▼
    │    ┌───────────────────────────────────────────────┐
    │    │  LISTEN       tap / voice / trace              │
    │    │  voice → deterministic clean                   │
    │    └───────────────────┬───────────────────────────┘
    │                        ▼
    │    ┌───────────────────────────────────────────────┐
    │    │  JUDGE        activity_evaluators  [D]         │
    │    │  ← YAHI SACH HAI. Koi agent nahi. Koi RL nahi. │
    │    └───────────────────┬───────────────────────────┘
    │                        ▼
    │    ┌───────────────────────────────────────────────┐
    │    │  RECORD       attempt + mastery EWMA + COMMIT  │
    │    └───────────────────┬───────────────────────────┘
    │                        ▼
    │              ┌─────────────────────┐
    │              │      SAHI?          │
    │              └──┬───────────────┬──┘
    │            HAAN │               │ NAHI
    │                 ▼               ▼
    │   ┌──────────────────────┐  ┌────────────────────────────┐
    │   │ CONCEPT GATE  (§1.4) │  │ attempts < 4 ?             │
    │   │ mastery>=0.75 AND    │  └───┬────────────────────┬───┘
    │   │ attempts>=4 ?        │  HAAN│                    │NAHI
    │   └──┬────────────────┬──┘      ▼                    ▼
    │ HAAN │                │NAHI  ┌──────────────┐  ┌──────────────┐
    │      ▼                │      │ NEXT STRATEGY│  │ PARK         │
    │  ┌─────────┐          │      │ S(n+1) chuno │  │ revisit_queue│
    │  │ MASTERED│          │      │ ← AGENT/RL   │  │ due = kal    │
    │  │ agla    │          │      │ dohrayi nahi │  │ warm exit    │
    │  │ concept │          │      └──────┬───────┘  │ koi shame    │
    │  └─────────┘          │             │          │   nahi       │
    │                       │             │          └──────┬───────┘
    │       ┌───────────────┘             │                 │
    │       ▼                             │                 ▼
    │  ┌──────────────────┐               │          ┌──────────────┐
    └──┤ EASY WIN         │◄──────────────┘          │ KAL A PHIR   │
       │ ek aur form,     │                          │ AAYEGA       │
       │ thodi mushkil    │                          │ (A locked    │
       │ (§4 dials)       │                          │  rahega)     │
       └──────────────────┘                          └──────────────┘
```

**Teen cheezein jo is loop mein zaroori hain:**

1. **JUDGE hamesha deterministic hai.** `activity_evaluators.py` — 37 registered types,
   pure functions. Agent aur RL dono is box ko chhoote bhi nahi.
2. **Strategy chunna agent/RL ka kaam hai.** Yeh woh 14 faisle mein se ek hai jo aapne
   agents ko diye (`AGENT-FLOW.md` §1).
3. **Ek strategy dobara nahi chalti** ek concept ke ek session mein. Warna wahi
   "AI apni baat dohra raha hai" wali problem wapas aa jaati hai.

---

## 3. 9 Teaching Strategies — "story ya example" ka poora set

Aapne kaha: *"pehle A explain karte ho, phir poochte ho, phir galat hone par story ya
example dete ho."* Bilkul sahi. Maine usko poora set banaya hai — kyunki ek concept ko
sirf 2 tarah se samjhana kaafi nahi.

| # | Strategy | Kya hota hai | "A" ka example | Rung |
|---|---|---|---|---|
| **S1** | **TELL** | Seedha bata do. Koi sawaal nahi. | "Yeh A hai. A." | L1 |
| **S2** | **SHOW** | Dikhao — A pulse kare, ungli uska shape banaye | A chamakta hai, ungli ↗↘— banati hai | L1 |
| **S3** | **EXAMPLE** | Bachche ki duniya se ek cheez | "A se Apple 🍎. A se Aam 🥭." | L2 |
| **S4** | **STORY** | Ek chhoti kahani (aapne yeh maanga) | "Ek Apple tha jise apna naam bhool gaya. Usne A dhoondha — do khadi lakeeren aur ek patti beech mein!" | L2 |
| **S5** | **CONTRAST** | Sahi vs galat, saath mein | "Yeh A hai ✅. Yeh B hai ❌. A ki patti beech mein hai." | L4 |
| **S6** | **DO-TOGETHER** | Haath pakad ke — `demo_tap`, saath trace | Pip A pe tap karta hai (submit nahi), phir bachcha | L5 |
| **S7** | **SENSE-SWITCH** | Indriya badlo — dekha? ab chhuo. suna? ab bolo. | Tap fail hua → ab A trace karo ungli se | L3 |
| **S8** | **PREREQUISITE** | Peeche jao — neev kamzor hai | A se pehle "khadi lakeer" seekho | — |
| **S9** | **PARK** | Aaj bas. Kal phir. Koi shame nahi. | "A thoda shaitan hai! Kal pakdenge use 😊" | — |

### 3.1 Pehla exposure hamesha fixed hai

Jab bachche ne A **kabhi nahi dekha**, strategy chunne ka koi matlab nahi. Woh hamesha:

```
S1 TELL  →  S2 SHOW  →  S3 ASK
```

**RL yahan kuch nahi chunta.** Kuch chunne layak hai hi nahi — bachche ke paas koi
misconception nahi hai jise theek karna ho. RL tab shuru hota hai jab **pehli galti** hoti hai.

### 3.2 STORY — ise theek se karna zaroori hai

Aapne story specifically maangi, aur woh sahi maang hai — 2-6 saal ke bachche kahani se
sabse achha seekhte hain. Par:

| Galat tareeka | Sahi tareeka |
|---|---|
| LLM live kahani banaye | **Authored story bank**, `stories.json`, per skill |
| Kahani lambi ho | **≤ 3 vaakya**, `early` mode mein ≤ 25 shabd |
| Kahani sirf mazedaar ho | Kahani mein **concept ka distinguishing feature** hona chahiye |
| Har baar nayi kahani | Ek kahani jo **dohrayi** jaaye woh yaad rehti hai |

```json
// backend/app/data/curriculum/stories.json
{
  "letter_A": {
    "en": [{
      "id": 0,
      "text": "An apple forgot its name. It looked and looked — then it found A! Two legs standing, and a belt in the middle.",
      "feature": "crossbar",
      "bands": ["nursery", "lkg", "ukg"],
      "words": 28
    }],
    "hi": [{
      "id": 0,
      "text": "एक सेब अपना नाम भूल गया। उसने ढूँढा — मिल गया अ! देखो, अ से सेब।",
      "feature": "name_sound",
      "bands": ["nursery", "lkg", "ukg"]
    }]
  }
}
```

`feature` field sabse zaroori hai — kahani ko **kuch sikhana** chahiye, sirf entertain nahi
karna chahiye. Yeh field author ko majboor karti hai ki woh soche kahani kis cheez ko
distinguish kar rahi hai.

> **Playgroup (2–3 saal) mein STORY nahi chalti.** Un bachchon ka narrative comprehension
> abhi nahi bana. Unke liye S1/S2/S6/S7 hain — batao, dikhao, saath karo, chhuo.
> Yeh `bands` field se enforce hoga.

### 3.3 Strategy ka repeat ban

```
lesson_states.strategies_used = ["S1","S2","S4"]

RULE: ek concept ke ek session mein koi strategy dobara nahi
RULE: saari legal strategies khatam → S9 PARK (force)
RULE: playgroup mein S4/S5 legal hi nahi hain
```

---
## 4. Difficulty Engine — class ke hisaab se hardness

> Aapne kaha: *"har class ke bacche ke syllabus ke hisaab se AI alag tarah kaam karegi,
> uska hardness utna jyada hoga."*

### 4.1 Achhi khabar — aapne yeh aadha bana rakha hai

Maine chaaron activity files ka `difficulty` field ginaa. Gradient **pehle se authored hai**:

| Class | Age | very_easy | easy | medium | hard | Activities |
|---|---|---|---|---|---|---|
| `playgroup` | 2–3 | **173** (56%) | 138 (44%) | 0 | 0 | 311 |
| `nursery` | 3–4 | 131 (26%) | **372** (74%) | 0 | 0 | 503 |
| `lkg` | 4–5 | 16 (16%) | **43** (44%) | 36 (37%) | 3 (3%) | 98 |
| `ukg` | 5–6 | 5 (4%) | 39 (33%) | **62** (53%) | 12 (10%) | 118 |

Yeh ek saaf ladder hai. Kisi ne yeh sochkar likha hai. **Engine isko use karega, isse
replace nahi karega.**

Ek gap jo dikha: **`lkg` ke paas sirf 98 activities hain, `nursery` ke 503.** Ek poora saal
ka content 98 activities mein nahi aata. Yeh content gap hai, code ka issue nahi — par
plan engine ise mahsoos karega. Isliye §7 mein content-gap detector hai.

### 4.2 Par `difficulty` ek label hai, dial nahi

`"difficulty": "easy"` batata hai ki ek activity kitni mushkil hai. Woh yeh nahi batata
ki usse **kaise mushkil banaya jaaye** ek aise bachche ke liye jo aage nikal raha hai,
ya **kaise aasan** kiya jaaye jo atka hua hai.

Uske liye 6 dials chahiye. Yeh sab **runtime pe** move karte hain, content badle bina:

| Dial | Aasan ⟵ | ⟶ Mushkil | Kahan se |
|---|---|---|---|
| **H1 Distractors** | 2 options | 3 → 4 options | `presentation.choices_shown` |
| **H2 Similarity** | door (circle vs star) | paas (circle vs oval, b vs d) | distractor selection |
| **H3 Scaffold** | S4 (dikha ke bolo) | S0 (chup) | `scaffold_level` |
| **H4 Modality** | pehchano (tap) | yaad karo (bolo) → banao (likho) | `modality` |
| **H5 Delay** | turant | usi session | kal | 7 din | `revisit_queue.interval_days` |
| **H6 Support** | narration + hint + visual | sirf prompt | `presentation` |

**H2 sabse zyada under-rated hai.** "Circle tap karo" jab options `[circle, star]` hain —
woh aasan hai. Wahi sawaal `[circle, oval]` ke saath ek asli discrimination task hai.
**Ek hi authored activity, do bilkul alag difficulty levels** — sirf distractor badalne se.
Yeh muft difficulty range hai jo aaj use nahi ho rahi.

### 4.3 Per-class hardness envelope

Har class ka ek **window** hai. Difficulty us window ke andar move karti hai — bahar kabhi nahi.

```
                H1        H2          H3       H4              H5          H6
                choices   similarity  scaffold modality        delay       support

playgroup 2-3   2         far only    S4–S2    tap only        same-session full only
nursery   3-4   2–3       far–mid     S4–S1    tap, voice opt  next-day    full–partial
lkg       4-5   2–4       far–near    S3–S0    tap, voice      7-day       partial–min
ukg       5-6   3–4       near ok     S2–S0    tap,voice,trace 21-day      minimal
```

**Chaar hard floors jo class kabhi cross nahi karti:**

1. `playgroup` mein spoken answer kabhi mandatory nahi (H4 lock)
2. `playgroup`/`nursery` mein near-similar distractors kabhi nahi (H2 lock) — un umron mein
   perceptual discrimination abhi ban rahi hai; oval-vs-circle ek **development** issue hai,
   knowledge issue nahi
3. `playgroup` mein next-day se lambi delay nahi (H5 lock)
4. Touch target manifest floor se neeche kabhi nahi (96px early / 64px standard)

### 4.4 Runtime pe difficulty kaise move karti hai

```python
# services/difficulty_engine.py — DETERMINISTIC, agent nahi

def next_difficulty(state, outcome, class_envelope) -> Difficulty:
    d = state.difficulty

    if outcome.correct and outcome.attempt == 1:
        if state.consecutive_first_try >= 2:
            d = d.step_up(class_envelope)      # ek dial, ek step
    elif not outcome.correct:
        d = d.step_down(class_envelope)        # turant, ek dial

    return d.clamp(class_envelope)             # window ke andar hamesha
```

**Step-up ka order matter karta hai** (aasan → mushkil banane ke liye kaunsa dial pehle):

```
H3 scaffold hatao  →  H6 support hatao  →  H2 similarity badhao
   →  H1 options badhao  →  H4 modality badhao  →  H5 delay badhao
```

**Step-down ka order ulta hai** — aur yeh ulta hona zaroori hai:

```
H2 similarity ghatao  →  H1 options ghatao  →  H6 support badhao
   →  H3 scaffold badhao  →  ... (H4/H5 kabhi nahi girte session ke andar)
```

Kyun ulta: jab bachcha atka hai, sabse pehle **task ko aasan karo** (kam confusing options),
uske baad **madad badhao**. Ulta karne se aap ek confusing task pe zyada madad de rahe hote
ho — jo kaam nahi karta.

### 4.5 Syllabus-aware, sirf age-aware nahi

Aapne "syllabus ke hisaab se" kaha, aur woh age se alag baat hai. Ek hi bachcha alag
subjects mein alag jagah hota hai:

```
Aditi, nursery (3.5 saal)
  ├── nur_maths   : counting mastered 0.82  → H1=3, H2=mid, H3=S1   (mushkil)
  ├── nur_english : letters weak     0.31  → H1=2, H2=far, H3=S4   (aasan)
  └── nur_hindi   : abhi shuru        —    → H1=2, H2=far, H3=S4, H4=tap-only
```

**Difficulty per (child × skill) hai, per child nahi.** Yeh `skill_mastery` table se
naturally nikalta hai — bas engine ko usse padhna hai, class label se nahi.

---

## 5. Reinforcement Learning — **HAAN**, par kaunsa

> Aapne poochha: *"iske liye RLHF ya kisi reinforcement algo ka use kar skte ho?"*

**Reinforcement learning: HAAN. RLHF: nahi.** Yeh do alag cheezein hain, aur farq
samajhna zaroori hai — kyunki aapka loop **sach mein** ek RL problem hai.

### 5.1 Farq

| | **RLHF** | **RL over teaching strategies** |
|---|---|---|
| Kya seekhta hai | LLM ke **weights** | Ek **policy table** — kaunsi strategy kab |
| Data | 10,000+ human-ranked pairs | Aapke apne attempt logs |
| Action space | Infinite (koi bhi text) | **9 strategies** (§3) |
| Kya invent kar sakta hai | Kuch bhi — unsafe bhi | **Kuch nahi** — sirf chunta hai |
| Infra | GPU cluster, apne weights serve karo | Ek Postgres table |
| Reward hack | **"Bachche ko answer bata do"** | Namumkin — text generate hi nahi karta |
| Rollback | Redeploy weights | Ek row |
| Audit | Namumkin | "S4 chuna kyunki Q=0.71 sabse ooncha tha" |
| Kab kaam karega | 12–18 mahine | **~2 hafte** |

**Aapka loop ek textbook MDP hai:**

```
State   s = (bachche ki abhi ki haalat is concept pe)
Action  a = 9 teaching strategies mein se ek
Reward  r = bachche ne seekha ya nahi
Episode  = ek concept, pehle exposure se mastery tak
```

Yeh RL hai. Bas isme LLM ke weights nahi badalte — **teaching policy** badalti hai.
Aur wahi cheez hai jise aap sach mein optimize karna chahte ho.

### 5.2 State, Action, Reward

**State** — jaanboojh kar chhota:

```python
s = (
  skill_type,        # 4: symbolic | quantity | perceptual | motor
  attempt_index,     # 4: 1 | 2 | 3 | 4
  last_strategy,     # 9
  mastery_band,      # 3: weak | learning | mastered
  fatigue_band,      # 2: fresh | tired
)
# 4 × 4 × 9 × 3 × 2 = 864 states × 9 actions = 7,776 Q-values
```

**Action** — §3 ki 9 strategies. **Sirf woh jo envelope-legal hain**
(playgroup mein S4/S5 nahi, dohrayi hui strategies nahi).

**Reward** — aur yahan ek trap hai jise dekhna zaroori hai:

```python
r =  +1.0   agar is strategy ke turant baad pehli koshish mein sahi
     +0.5   agar doosri koshish mein sahi
     -0.15  har extra attempt pe          ← BACHCHE KI SABR KI KEEMAT
     -0.60  agar concept PARK pe khatam
     +0.80  agar KAL yaad tha             ← nightly credit assignment
     -1.00  agar envelope ne veto kiya
```

> **`-0.15` per-attempt penalty sabse zaroori line hai.**
>
> Uske bina RL "efficiently padhana" nahi seekhega — woh "ragadna" seekhega. Kyunki
> agar sirf "aakhir mein sahi hua" ka reward hai, toh 8 baar try karna 2 baar try karne
> jitna hi achha hai. Penalty se policy seekhti hai ki **kam steps mein sikhana** behtar hai.
>
> Aur `+0.80` next-day retention **sabse asli signal hai**. Ek strategy jo aaj turant kaam
> karti hai par kal bhula di jaati hai, woh achhi teaching nahi hai. Yeh reward usse pakadta hai.

### 5.3 Chaar stages — aur data kitna chahiye

RL ko din 1 se mat chalao. Ek warm start ke saath badhao:

```
┌─────────────────────────────────────────────────────────────────────┐
│ STAGE 0 — HEURISTIC LADDER            ← DIN 1. Yahi ship karo.      │
│   S1→S2→ASK→ S3 → S4 → S5 → S6 → S7 → PARK                          │
│   Fixed order. Deterministic. Yeh aapki BASELINE hai.               │
│   Data chahiye: 0                                                    │
├─────────────────────────────────────────────────────────────────────┤
│ STAGE 1 — CONTEXTUAL BANDIT                        ← ~2 hafte       │
│   Context COARSE rakho: (attempt_index × skill_type) = 16            │
│   16 contexts × 9 arms = 144 cells, ~30 pulls each                   │
│   Data chahiye: ~4,300 teaching events                               │
│     100-child pilot pe: ~14 din                                      │
│     6k DAU pe:          ~6 ghante                                    │
│   Thompson sampling. Nightly update. Kill switch.                    │
├─────────────────────────────────────────────────────────────────────┤
│ STAGE 2 — CONTEXT REFINEMENT                       ← ~2 mahine      │
│   Jis bucket mein 200+ pulls ho gaye, use split karo                 │
│   (age_band, phir mastery_band, phir fatigue)                        │
│   Sirf wahan split karo jahan data hai. Poora space kabhi nahi.      │
├─────────────────────────────────────────────────────────────────────┤
│ STAGE 3 — TABULAR Q-LEARNING                       ← ~4-6 mahine    │
│   Poora 864-state space. γ=0.9. Episode = concept.                   │
│   AB delayed reward kaam karta hai: ek strategy jo AGLI strategy ko  │
│   kaam karne deti hai, use credit milta hai.                         │
│   Data chahiye: ~78,000 events (6k DAU pe ~5 din, par pehle          │
│   Stage 1-2 se seekha hua chahiye)                                   │
│   Warm start: Q ko heuristic ladder se initialise karo               │
└─────────────────────────────────────────────────────────────────────┘

   RLHF / DPO: is list mein nahi hai. Stage 3 saturate hone ke baad socho.
```

### 5.4 Warm start — yeh optional nahi hai

```python
# Din 1 pe Q table random NAHI hai. Woh heuristic ladder hai.
for s in states:
    for a in actions:
        Q[s][a] = 0.5 if a == heuristic_ladder(s) else 0.0
```

> **Aap kabhi ek randomly-initialised policy bachchon pe nahi chalayenge.**
> Din 1 pe RL ka behaviour = heuristic ka behaviour. RL sirf **wahan se sudhaar** karta hai.
> Iska matlab worst case = aapki baseline, aur behtar hone ki gunjaish upar hai.

### 5.5 Exploration — bachchon pe, isliye sambhal ke

```python
ε = 0.10                      # 10% turns pe explore
ε = 0.0  agar:
    attempt_index >= 3        # atka hua bachcha experiment ki jagah nahi hai
    frustration >= 0.5        # pareshaan bachche pe kabhi nahi
    pehla exposure            # tab TELL+SHOW hi hai, chunne ko kuch nahi
    class == playgroup        # 2-3 saal pe koi exploration nahi

explore hamesha SIRF envelope-legal actions mein se
```

**Yeh rules hi RL ko bachchon ke liye safe banate hain.** Explore tab jab bachcha
comfortable hai. Jab woh struggle kar raha hai, best-known action chalao.

### 5.6 Poora RL flow

```
  ONLINE (har wrong answer pe)
  ┌──────────────────────────────────────────────────────────┐
  │  state s banao (trusted server state se)                  │
  │       ▼                                                   │
  │  legal actions nikalo (envelope + class + used-list)      │
  │       ▼                                                   │
  │  ε-greedy / Thompson → action a                           │
  │       ▼                                                   │
  │  a = strategy. AGENT usko SHABD deta hai (LLM)            │
  │       ▼                                                   │
  │  envelope validate → render                               │
  │       ▼                                                   │
  │  (s, a, r_immediate) transitions table mein LIKHO         │
  └──────────────────────────────────────────────────────────┘

  NIGHTLY (ARQ worker)
  ┌──────────────────────────────────────────────────────────┐
  │  1. kal ke transitions padho                              │
  │  2. next-day retention reward jodo (+0.80)                │
  │     ← isi liye nightly hai. Yeh signal 24 ghante lagta hai│
  │  3. Q / Beta posteriors update karo                        │
  │  4. offline eval: nayi policy vs purani, replay pe        │
  │  5. sudhaar hua → promote. nahi → purani rakho.           │
  └──────────────────────────────────────────────────────────┘
```

**Update kabhi real-time nahi.** Do wajah: (a) next-day reward available hi nahi hota,
(b) ek bachche ka jawab doosre bachche ka content turant badal de — woh debug karna
namumkin ho jaata hai.

### 5.7 Do metrics jo saath padhni hain

| Metric | Achha |
|---|---|
| **Attempts-to-mastery** | Kam |
| **Next-day retention** | Zyada |
| PARK rate | Kam |
| Strategy diversity | Collapse na ho — ek strategy 60%+ le rahi hai toh shak karo |
| `answer_leak` veto rate | **~0** |

> **Trap:** RL `attempts-to-mastery` ko "jeet" sakta hai un strategies ko chunkar jo
> answer ke sabse paas hain (S6 DO-TOGETHER hamesha). Turant kaam karega, kal bhula
> diya jaayega. **Isliye next-day retention reward mein hai, sirf dashboard pe nahi.**

---

## 6. End-to-end workflow — aapke 12 steps → system

```
════════════════════════════════════════════════════════════════════════════
  A.  ENTRY                                            [aapka step 1]
════════════════════════════════════════════════════════════════════════════
  Bachcha app kholta hai
  → GET /api/v1/conductor/{child_id}/open
  → auth + owned_child check                                          [D]

════════════════════════════════════════════════════════════════════════════
  B.  PICHHLA DATA PADHO                               [aapka step 2]
════════════════════════════════════════════════════════════════════════════
  → skill_mastery         (kya aata hai, kya nahi — EWMA + decay)     [D]
  → revisit_queue         (kya due hai — PARK kiye hue concepts)      [D]
  → learner_profile       (kitni der baithta hai, kis waqt achha)     [D]
  → yesterday's plan      (kya adhoora chhoota)                       [D]
  → learning_memory       ("kal humne kya kiya tha")                  [D]

════════════════════════════════════════════════════════════════════════════
  C.  AAJ KA SCHEDULE BANAO                            [aapka step 3]
════════════════════════════════════════════════════════════════════════════
  ╔═══ PLANNER AGENT ═══════════════════════════════════════════════╗
  ║  6 read-only tools · max 8 steps · 8s deadline                  ║
  ║  Decide: kaunse concepts, kis order, kitni der                  ║
  ║  PRIORITY jo prompt mein hard hai:                              ║
  ║    1. revisit_queue due (kal ka PARK kiya A — SABSE PEHLE)      ║
  ║    2. spaced retrieval due (1/3/7/21 din)                       ║
  ║    3. current topic continue                                    ║
  ║    4. naya concept                                              ║
  ╚═════════════════════════════════════════════════════════════════╝
                              ▼
  ENVELOPE: sirf unlocked+available · plan_days · time fit · freeze   [D]
                              ▼
  INSERT daily_plans  UNIQUE(child_id, plan_date)                     [D]

════════════════════════════════════════════════════════════════════════════
  D.  CLASS KHUD KHOLO                                 [aapke steps 4-5]
════════════════════════════════════════════════════════════════════════════
  GREET: "Namaste Aditi! Kal A thoda shaitan tha. Aaj pakdenge use!" [H]
  ▶ (bada, icon-only)     😴 (chhota)
  5 second → koi tap nahi → CLASS KHUD KHULTI HAI                     [D]
  ← koi navigation nahi. koi menu nahi. koi padhne wali cheez nahi.

════════════════════════════════════════════════════════════════════════════
  E.  CONCEPT LOOP: "A"                                [aapke steps 6-11]
════════════════════════════════════════════════════════════════════════════

  PRE-CHECK    prereq aata hai? A pehle se aata hai?                  [D]
       ▼
  TEACH        S1 TELL   "Yeh A hai."                            [H]  ← pehla
  TEACH        S2 SHOW   A chamakta hai, ungli shape banati hai  [D]     exposure
       ▼                                                                 fixed
  ASK          difficulty engine se question (§4)                 [D]
       ▼
  LISTEN       tap / voice / trace                                 [D]
  JUDGE        activity_evaluators                                 [D] ← SACH
  RECORD       attempt + mastery EWMA + COMMIT                     [D]
       ▼
  ┌── SAHI ─────────────────────────────────────────────────────┐
  │  CONCEPT GATE: mastery>=0.75 AND attempts>=4 ?               │
  │     HAAN → A ho gaya. Agla concept. A ke aage wale unlock.   │
  │     NAHI → ek aur form, thodi mushkil (H-dials +1). Loop.    │
  └──────────────────────────────────────────────────────────────┘
  ┌── GALAT ────────────────────────────────────────────────────┐
  │  attempts < 4 ?                                              │
  │     ▼ HAAN                                                   │
  │  ┌────────────────────────────────────────────────┐          │
  │  │ INSTANT ACK (0 ms): "Hmm, saath dekhte hain..." │  [D]     │
  │  └────────────────────────────────────────────────┘          │
  │  ╔═══ RL: kaunsi strategy? ══════════════════════╗           │
  │  ║  legal actions (envelope + class + used)      ║  [RL]      │
  │  ║  → S4 STORY chuni                             ║           │
  │  ╚═══════════════════════════════════════════════╝           │
  │  ╔═══ TEACHER AGENT: usko shabd do ══════════════╗  [H]      │
  │  ║  story bank se, bachche ki bhasha mein         ║           │
  │  ╚═══════════════════════════════════════════════╝           │
  │  ENVELOPE: answer-leak · shame · repeat · script  [D]         │
  │  DIFFICULTY: step down (H2 → H1 → H6 → H3)        [D]         │
  │       ▼  loop wapas ASK pe                                    │
  │                                                               │
  │     ▼ NAHI (attempts == 4)                                    │
  │  PARK: revisit_queue(due=kal) · A LOCKED rehta hai            │
  │        "A thoda shaitan hai! Kal pakdenge 😊"      [H]        │
  │        koi shame · koi fail · koi score gira nahi             │
  └──────────────────────────────────────────────────────────────┘

════════════════════════════════════════════════════════════════════════════
  F.  AGLA CONCEPT / CLASS CLOSE
════════════════════════════════════════════════════════════════════════════
  plan mein aur item? → LessonAssignment → E pe wapas
  nahi → RECAP (mastery deltas se) [D] + celebrate [D] + "kal milte hain"
       → AUR KUCH NAHI. koi "ek aur?" nahi.

════════════════════════════════════════════════════════════════════════════
  G.  NIGHTLY
════════════════════════════════════════════════════════════════════════════
  next-day retention reward jodo → Q/bandit update → offline eval        [D]
  revisit_queue schedule (1/3/7/21) · parent digest · content gaps       [D]
  3 din se atka concept → parent ko real-world activity card             [D]

════════════════════════════════════════════════════════════════════════════
  H.  KAL                                              [aapka step 11 ka jawab]
════════════════════════════════════════════════════════════════════════════
  Planner: revisit_queue priority 1 → A SABSE PEHLE aayega
  Naye strategy set ke saath (jo kal use hui thi woh reset)
  Aur tab tak, jab tak A sach mein na aa jaaye.
       ← YAHI aapka "jab tak sahi na kare move nahi karoge" hai
```

---
## 7. Enhancements — jo maine add kiye

> Aapne kaha *"ise enhance karne ke liye jo add karna chahte ho kar do."* Yeh 11 hain,
> impact ke order mein. Har ek ke saath wajah — kyunki ek enhancement jiski wajah na ho
> woh sirf scope hai.

### E1 · Pre-Check — padhane se pehle poochho ki aata toh nahi
**Problem:** aaj system har concept ko zero se padhata hai. Ek bachcha jisko A pehle se
aata hai (ghar pe, TV se, bade bhai se) woh 4 activity baith ke A sunta hai. Bore ho jaata
hai, aur woh time kisi aur concept ka tha.

**Solution:** concept enter pe ek single check question, S0 scaffold pe. Sahi first-try →
mastery 0.30 se shuru, teaching skip, seedha practice pe. Galat → normal loop.

**Kyun matter karta hai:** 2–6 saal ke bachchon mein prior knowledge ka variance bahut
zyada hota hai. Yeh session ka 20–30% time bacha leta hai.

---

### E2 · Success = 2 sahi, alag-alag form mein (§1.4 ka enforcement)
**Problem:** playgroup ke saare questions 2-option hain. Ek sahi jawab = 50% coin flip.

**Solution:** ek concept "aa gaya" tab, jab **do alag activities** pe first-try correct ho —
alag distractor set ke saath. Aur mastery formula (OP-05) 4 attempts maangta hai.

**Kyun matter karta hai:** iske bina aapka poora mastery data shor hai, aur RL us shor pe
train hoga. **Yeh doc ka sabse zaroori technical fix hai.**

---

### E3 · Sense-Switch (S7) — indriya badlo, shabd nahi
**Problem:** agar bachche ne A ko *dekh ke* nahi pehchana, use A ko *aur dikhana* aksar kaam
nahi karta. Problem visual channel mein hai.

**Solution:** do visual failures ke baad modality badlo — sunao (A ki dhwani), chhuao
(A trace karo), karwao (haath se A banao). Aapke content mein `trace`, `voice_repeat`,
`repeat_letter` types **pehle se hain** — bas woh alag activities ki tarah serve hote hain,
ek hi concept ke alag raaste ki tarah nahi.

**Kyun matter karta hai:** 2–6 saal mein multi-sensory learning sabse strong evidence wali
cheez hai. Aur yeh **zero naya content** maangta hai.

---

### E4 · Sibling-Concept Contrast — b vs d, circle vs oval, 6 vs 9
**Problem:** alag-alag padhaye gaye concepts confuse hote hain. Bachcha A akela pehchan
leta hai, par A aur B saath mein aayein toh atak jaata hai. Yeh **discrimination** failure
hai, recognition failure nahi — aur dono ka ilaaj alag hai.

**Solution:** `skill_graph.json` mein ek naya edge type — `confusable_with`. Jab dono skills
`learning` band mein hon, ek contrast activity chalao jo dono saath dikhaye.

```json
"letter_b": { "requires": ["letter_a"], "confusable_with": ["letter_d", "letter_p"] }
```

**Kyun matter karta hai:** b/d confusion, 6/9 confusion, circle/oval — yeh early literacy
aur numeracy ki sabse common atak hain, aur inhe alag-alag padhane se woh theek nahi hoti.

---

### E5 · Fatigue Gate — thakan aur na-samajh alag cheezein hain
**Problem:** ek bachcha jo 10 minute baad fail kar raha hai, woh concept nahi samjha —
ya woh thak gaya hai? Aaj system dono ko ek jaisa treat karta hai, aur "thaka hua" ko
"weak skill" mark kar deta hai. Woh data hamesha ke liye galat hai.

**Solution:** `fatigue_band` compute karo (session minutes + accuracy trend + latency trend).
`tired` state mein:
- Mastery update ka weight **aadha** (thaka hua performance mastery ka sabooot nahi hai)
- PARK jaldi
- Naya concept shuru mat karo — sirf practice

**Kyun matter karta hai:** iske bina aapka mastery data har session ke aakhir mein
systematically corrupt hota hai.

---

### E6 · Story Bank with `feature` field (§3.2)
**Problem:** kahani entertain kar sakti hai bina sikhaye.

**Solution:** har authored story ko ek `feature` declare karna padta hai — woh distinguishing
cheez jo kahani sikha rahi hai (`crossbar` for A, `tail` for Q). Author ko sochna padta hai.

**Kyun matter karta hai:** yeh ek chhota schema constraint hai jo content quality ko
structurally upar le jaata hai.

---

### E7 · Misconception Taxonomy
**Problem:** aaj "galat jawab" ek bit hai. Par *kaunsa* galat jawab sab kuch batata hai —
`circle` ki jagah `square` tapping = corners vs round confusion. `circle` ki jagah `oval` =
subtle perceptual discrimination. Bilkul alag ilaaj.

**Solution:** Teacher Agent har wrong answer pe ek `diagnosis` code deta hai. Aggregate hota hai.

**Kyun matter karta hai:** *"37% nursery bachche `corners_vs_round` pe atakte hain"* ek
**curriculum insight** hai. Aap us activity ko dobara likh sakte ho. Yeh data aaj exist hi nahi karta.

---

### E8 · Parent Bridge for stuck concepts
**Problem:** kuch cheezein screen sikha hi nahi sakti. Ek bachcha jo 3 din se "bada/chhota"
pe atka hai, use asli cheezein chahiye jo woh haath se pakde.

**Solution:** 3 din stuck → parent ko ek real-world activity card. **Aapke content mein
`parent_activity` type pehle se hai** (nursery mein 14, ukg mein 5), aur `delivery_legend`
mein saaf likha hai ki app ise fake tap question nahi banata. Us mechanism ko stuck-concept
trigger se jodo.

**Kyun matter karta hai:** yeh aapka sabse strong parent-engagement moment hai, aur infra
pehle se hai.

---

### E9 · Concept Ledger — do alag din, do sahi jawab
**Problem:** ek session mein 4 sahi jawab "seekha hua" nahi hai. Woh "aaj yaad tha" hai.

**Solution:** `concept_ledger` — ek concept `mastered` tab hota hai jab **do alag calendar
dinon** pe first-try correct mile. Ek din mein kabhi nahi.

**Kyun matter karta hai:** yeh short-term recall aur asli seekhne ka farq hai. Aur yeh
E2 ke saath milkar aapke "jab tak sach mein na aa jaaye" ko sach mein enforce karta hai.

---

### E10 · Content Gap Detector
**Problem:** maine gina — `lkg` ke paas **98 activities** hain, `nursery` ke **503**.
Ek poora academic saal 98 activities mein nahi aata. Plan engine ise mahsoos karega
(repeat hone lagega), par koi alert nahi hoga.

**Solution:** nightly report — per class: activities/topic, skills without enough practice
variety, topics with `available: false`, aur skill_graph ke orphan nodes.

**Kyun matter karta hai:** ek AI teacher itni hi achhi hai jitna uska content. Yeh aapko
batata hai ki agla content kahan likhna hai.

---

### E11 · Golden Child Simulator
**Problem:** aap teaching loop ko asli bachchon pe test nahi kar sakte har deploy pe.

**Solution:** 12 synthetic learner profiles (fast/slow, visual/auditory, guesser,
perfectionist, quitter, prior-knowledge, tired…). CI mein poora concept loop chalao.
Assert: koi profile 4 attempts cross na kare, koi profile 20 turn mein mastery pe na
pahunche bina, PARK rate ranges mein rahe.

**Kyun matter karta hai:** yeh aapko har prompt aur policy change pe regression signal deta
hai, bina asli bachchon ko test group banaye. **RL ship karne ke liye yeh lagbhag zaroori hai.**

---

## 8. Data model

`AI-100-PERCENT-AUTOMATION.md` §8 aur `AGENT-FLOW.md` §7 ke upar:

### `concept_ledger` (naya) — E2 + E9
```sql
child_id + skill_id           PRIMARY KEY
state          TEXT     -- unseen | teaching | practising | mastered | parked
first_seen_at  TIMESTAMPTZ
correct_forms  TEXT[]   -- distinct activity_ids jahan first-try correct hua
correct_days   DATE[]   -- distinct calendar days       ← E9
attempts_total SMALLINT
parked_count   SMALLINT
last_strategy  TEXT
stuck_days     SMALLINT -- 3 pe parent bridge trigger   ← E8
INDEX (child_id, state)
```

**`correct_forms` aur `correct_days` do arrays hain jo poore mastery sawaal ko hal karte hain:**
`mastered` tab jab `len(distinct correct_forms) >= 2` **aur** `len(correct_days) >= 2`
**aur** `effective_mastery >= 0.75`.

### `rl_policy` (naya) — §5
```sql
state_key    TEXT   -- "symbolic|2|S3|learning|fresh"
action       TEXT   -- S1..S9
q_value      NUMERIC
alpha, beta  NUMERIC  -- bandit stage
visits       INTEGER
updated_at   TIMESTAMPTZ
PRIMARY KEY (state_key, action)
```

### `rl_transitions` (naya) — nightly credit assignment
```sql
id, child_id, skill_id, episode_id
state_key, action
reward_immediate  NUMERIC
reward_delayed    NUMERIC NULL   -- kal bhara jaata hai (retention)
next_state_key    TEXT
created_at
INDEX (created_at) · INDEX (episode_id)
```

### Naye content files
```
backend/app/data/curriculum/
  ├── skill_graph.json    requires · confusable_with (E4) · depth <= 4
  ├── analogies.json      per skill, per language, per band
  └── stories.json        per skill, feature field mandatory (E6)
```

Teeno **curriculum loader ke fail-fast validation** se guzrenge — bilkul waise hi jaise
aaj `activity_evaluators.is_registered()` unknown activity type ko startup pe reject karta hai.

---

## 9. Build order

| # | Kya | Kyun is order mein |
|---|---|---|
| 1 | Postgres + repositories (OP-01) | `mock_storage.py` ke rehte hue kuch durable nahi |
| 2 | Auth + consent (OP-02) | `mock_auth.py` sha256 hai |
| 3 | `concept_ledger` + mastery (OP-05 formula) | **§1 ka fix. Sab isi pe khada hai.** |
| 4 | Concept Loop state machine (§2) | Dhaancha |
| 5 | Heuristic strategy ladder (RL Stage 0) | **Baseline. RL se pehle, hamesha.** |
| 6 | `skill_graph` + `stories` + `analogies` + loader | Strategies ko content chahiye |
| 7 | Difficulty Engine — 6 dials (§4) | Aapka "hardness" requirement |
| 8 | Envelope (26 rules) | **Agents/RL se pehle** |
| 9 | Teacher Agent — strategy ko shabd deta hai | Yahan LLM aata hai |
| 10 | Planner Agent | Din mein ek baar, kam risk |
| 11 | E1, E2, E5 (pre-check, 2-form, fatigue) | Data quality — RL se pehle |
| 12 | E11 Golden Child Simulator | **RL se pehle. Iske bina regression blind hai.** |
| 13 | **RL Stage 1 — bandit**, 10% traffic | ~2 hafte data |
| 14 | E3, E4, E6, E7 (sense-switch, contrast, story, diagnosis) | Action space badhao |
| 15 | RL Stage 2 — context refinement | ~2 mahine |
| 16 | E8, E10 (parent bridge, content gaps) | — |
| 17 | RL Stage 3 — tabular Q | ~4-6 mahine |

**#3, #5, #8, #12 sab RL (#13) se pehle hain.** Yeh sequencing hi poore doc ka nateeja hai:

> Ek RL policy utni hi achhi hai jitna uska **reward signal**.
> Agar mastery ek coin flip se mil jaati hai (§1.2), toh RL coin flip optimize karega.
> **Pehle measurement theek karo. Phir optimize karo.**

---

## 10. Ek nazar mein

```
  AAPKA FLOW                          SYSTEM

  bachcha enter                   →   auth + owned_child            [D]
  pichhla data                    →   mastery · revisit · profile   [D]
  aaj ka schedule                 →   PLANNER AGENT + envelope      [A]
  class khud khule                →   auto-open, 5s, ▶/😴           [D]
  teacher padhata hai             →   S1 TELL + S2 SHOW             [H]
  poochta hai                     →   difficulty engine se question [D]
  response leta hai               →   activity_evaluators           [D] ← SACH
  decide karta hai                →   CONCEPT GATE + RL strategy    [D+RL]
  galat → story/example           →   S3..S7, dohrayi nahi          [RL+H]
  jab tak sahi na ho              →   CONCEPT GATE (baithak nahi)   [D]
  class ke hisaab se hardness     →   6 dials, per-class envelope   [D]
  RL                              →   bandit → Q-learning, NOT RLHF [RL]

  [D] deterministic   [A] agent   [H] agent likhta, envelope checkti   [RL] policy
```

**Teen line mein:**

> 1. **Aapka loop bilkul sahi hai** — teach → ask → judge → decide → re-teach. Woh
>    §2 mein poora design ho chuka hai, 9 strategies ke saath jisme aapki STORY bhi hai.
> 2. **"Jab tak sahi na kare" ko concept pe lagao, baithak pe nahi.** Aapke playgroup
>    ke saare sawaal 2-option hain — 3 try mein 87.5% bachche luck se "pass" ho jaayenge.
>    Concept Gate aapka irada poora rakhta hai aur bachche ko phansata nahi.
> 3. **RL — haan. RLHF — nahi.** Aapka loop ek asli MDP hai: 9 actions, chhota state
>    space, ek Postgres table. **~2 hafte mein kaam karta hai**, RLHF ke 12–18 mahine ke
>    against. Aur woh answer leak kar hi nahi sakta, kyunki woh text likhta hi nahi.

---

*Visual: `docs/teaching-loop-visual.html` — yeh poora flow ek page pe.*
