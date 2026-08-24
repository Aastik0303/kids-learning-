# LangChain Implementation — Saksham IQ Agents

**Status:** working code, 10/10 contract tests passing against real
`langchain-core 1.6.0` · `langchain-groq 1.1.3` · `langgraph 1.2.11`
**Version:** 1.0 · 2026-08-19
**Companion:** `docs/TEACHING-GRAPH-SPEC.md` (node ids here map 1:1 onto §4)

---

## 0. Aapne LangChain maanga — yeh raha, chalta hua

Pichhle doc mein maine kaha tha "plain Python se shuru karo". Aapka call hai, aur
LangChain use ho raha hai — **par do constraints code mein hi enforce kiye hain**,
kyunki woh do cheezein tootne se bachche ka data corrupt hota hai:

1. **`compile()` bina checkpointer ke** — warna lesson state do jagah ho jaata hai
2. **Truth path LangChain import nahi karta** — aur uska ek AST test hai jo CI mein fail hoga

Baaki sab LangChain hai: `ChatGroq`, `@tool`, `bind_tools`,
`with_structured_output`, `StateGraph`.

---

## 1. Files

```
backend/
├── requirements-ai.txt              pinned, aur kya NAHI install karna
├── app/agents/
│   ├── llm.py                       ChatGroq wiring — ek jagah
│   ├── schemas.py                   AgentDecision · PlanProposal
│   ├── envelope.py                  26 rules — DETERMINISTIC, agent nahi
│   ├── runner.py                    deadline · budget · fallback edge
│   ├── teacher/
│   │   ├── tools.py                 6 read-only tools · answer key strip
│   │   ├── agent.py                 LangGraph StateGraph, TA.01–TA.07
│   │   └── prompts/base.v1.txt + band_{playgroup,nursery,lkg,ukg}.v1.txt
│   └── planner/
│       ├── agent.py                 5 tools · 8 steps · structured output
│       └── prompts/planner.v1.txt
└── tests/contract/test_agent_boundaries.py     ← 10 tests, sab pass
```

---

## 2. Graph — jo actually compile hua

`TEACHER_GRAPH.get_graph()` se nikala hua, invent nahi kiya:

```
NODES: TA.01  TA.02  TA.04  TA.05  TA.06  TA.07

__start__ -> TA.01
TA.01     -> TA.02
TA.02     -> TA.04     [tool]
TA.02     -> TA.06     [final]
TA.04     -> TA.05     [run]
TA.04     -> TA.07     [abort]
TA.05     -> TA.02
TA.06     -> TA.02     [retry]
TA.06     -> TA.07     [abort]
TA.06     -> __end__   [ok]
TA.07     -> __end__

checkpointer: None
```

Spec ke `TA.03 route_action` aur `TA.08 emit_decision` yahan alag node nahi hain —
LangGraph mein woh conditional-edge function aur `END` hain. Yeh sahi mapping hai,
gaayab nahi hue.

---

## 3. Do constraints — aur unka enforcement

### 3.1 Checkpointer band

```python
return g.compile()          # ← NO checkpointer
```

Ek turn ka agent loop **stateless** hai: state Postgres se aati hai, decision
Postgres mein jaata hai. `PostgresSaver` lagane ka matlab lesson state ka doosra
store — aur do sources of truth wahi bug hai jo aap client se hata rahe ho
(`TRACK-A` §2). Test:

```python
def test_teacher_graph_compiles_without_checkpointer():
    assert getattr(TEACHER_GRAPH, "checkpointer", None) in (None, False)
```

### 3.2 Truth path LangChain-free

```python
TRUTH_MODULES = ["services/activity_evaluators.py", "services/branch_engine.py",
                 "services/mastery_service.py", "agents/envelope.py"]

def test_truth_path_never_imports_langchain(rel):
    leaked = _imports(APP / rel) & {"langchain", "langchain_core",
                                    "langchain_groq", "langgraph"}
    assert not leaked
```

Correctness, mastery, branch engine aur envelope **LangChain uninstall karke bhi
chalne chahiye**. Agar inme se kisi mein LLM import aa gaya, toh "model kabhi star
decide nahi karta" wali guarantee chupke se khatam ho chuki hai.

---

## 4. Sabse zaroori design line

```python
# teacher/agent.py — build_context docstring
# The model is told WHAT WAS DECIDED and asked to SAY IT.
# It is never asked what to do.
```

`decision` aur `rung` model ke **input** hain, output nahi. Yeh ek inversion hai
jo "LLM kabhi source of truth nahi" ko *aspiration* se *structure* bana deta hai.

---

## 5. Answer key — do taraf se band

**Input side** (`teacher/tools.py`):
```python
ANSWER_KEY_FIELDS = ("correct_answer", "accepted_answers", "accept")

def _strip_answer_key(activity: dict) -> dict:
    return {k: v for k, v in activity.items() if k not in ANSWER_KEY_FIELDS}
```

**Output side** (`envelope.py`) — kyunki model options dekh ke **guess** kar sakta hai:
```python
def _leaks_answer(message, turn) -> bool:
    said = normalize_answer(message, kind)
    return any(k and normalize_answer(k, kind) in said for k in keys)
```

Wahi normaliser jo grader use karta hai — toh `GOL`, `gol.` aur `गोल` sab barabar
compare hote hain. Test pass:

```
input : "It is the circle! Tap circle."
veto  : answer_leak
output: "Chalo saath dekhte hain."
```

Aur ek chhoti par zaroori baat: **tools turn ko `_TURN` module state se padhte hain,
tool argument se nahi.** LangChain mein tool args model-controlled hote hain — agar
`child_id` ek argument hota, model kisi doosre bachche ka turn maang sakta tha.

---

## 6. Envelope kabhi bhi agent ko override kar sakti hai

Test se, real output:

```
agent   : decision=RE_EXPLAIN  "Let us try once more!"   (attempts=4)
envelope: veto=attempt_cap → OVERRIDE
final   : decision=END_KINDLY  "Yeh thoda mushkil tha! Kal phir milte hain."
```

Agent kitna bhi convinced ho ki ek aur try se ho jaayega — **4 pe cap hai**. Ek
teen-saal ka bachcha jo paanch baar fail hua hai, yeh seekh raha hai ki seekhna
bura lagta hai.

---

## 7. Fallback — har agent call ke saath

`runner.py` woh jagah hai jahan spec ka "har agent node ki ek `on_fail` edge hoti
hai" rehta hai:

```python
if turn["ai_calls_used"] >= SESSION_AI_BUDGET:      return _fallback(turn, "budget")
except asyncio.TimeoutError:                        return _fallback(turn, "timeout")
except Exception:                                   return _fallback(turn, "error")
if decision is None:                                return _fallback(turn, "aborted")
```

Aur `_fallback` **`deterministic_repair()`** call karta hai — heuristic ladder jo
agent se **pehle** banti hai. Woh teen kaam karti hai: fallback, floor, aur
**baseline** jiske against agent naapa jaayega.

`agent_source` (`"agent"` / `"deterministic_fallback"`) lesson row pe likha jaata
hai — timeouts aapko **muft mein ek control group** de dete hain, bina alag A/B
framework banaye.

---

## 8. Smoke run — poora loop, fake model ke saath

```
node calls : ['model_step', 'model_step', 'structured']
decision   : RE_EXPLAIN | S5_CONTRAST L4 variant 2
diagnosis  : misconception:corners_vs_round
message    : Yeh gol hai, koi kona nahi. Isme kone hain.
vetoes     : none
target px  : 96 | choices: 2
```

Tool call → model step → structured output → envelope. Presentation nursery ke
floor (96 px) pe clamp, choices 2.

---

## 9. Test results

```
$ pytest tests/contract/test_agent_boundaries.py -q
..........                                                     [100%]
10 passed in 0.37s
```

| Test | Kya rokta hai |
|---|---|
| `test_truth_path_never_imports_langchain` × 4 | LLM ka truth path mein ghusna |
| `test_agents_have_no_write_tools` | agent ka DB corrupt karna |
| `test_answer_key_never_leaves_tools` | R6, input side |
| `test_answer_leak_is_replaced` | R6, output side |
| `test_teacher_graph_compiles_without_checkpointer` | do sources of truth |
| `test_every_agent_call_site_has_a_fallback` | bina fallback wala agent |
| `test_attempt_cap_is_unreachable_past_four` | bachche ka phansna |

---

## 10. Kya install NAHI kiya, aur kyun

| Package | Kyun nahi |
|---|---|
| `langchain` (umbrella) | chains, retrievers, loaders — ek bhi use nahi hota. `core` + `groq` kaafi hai. |
| `langchain-community` | wahi, aur bada surface |
| `langchain-openai` | ek provider. Doosra add karna ek faisla hai, default nahi. |
| `faiss` / `chroma` / `pgvector` | child path pe vector search nahi. Curriculum primary key se aata hai. |
| `PostgresSaver` | §3.1 |

---

## 11. Agla step

1. `deterministic_repair()` ko poora likho (`services/branch_engine.py` mein abhi
   ek chalta hua ladder stub hai) — **agent se pehle**, kyunki woh uska floor hai
2. `variant_bank.py` ko `analogies.json` / `stories.json` se jodo — abhi `[]` lautata hai
3. `envelope.py` mein baaki rules bharo (abhi 14 hain, spec mein 26)
4. `metrics.py` ko asli Prometheus counters se replace karo — veto rate hi aapka
   prompt-quality signal hai
5. `GROQ_API_KEY` set karke ek asli lesson chalao, `LLM_PROVIDER=none` pe bhi chala ke dekho

---

*Companions: `docs/TEACHING-GRAPH-SPEC.md` · `docs/AGENT-FLOW.md` ·
`docs/TEACHING-LOOP-WORKFLOW.md` · `docs/AI-ARCHITECTURE-DECISIONS.md`
(§4 ka LangGraph verdict ab is implementation se supersede hota hai).*
