# Curriculum Inventory — every component the four classes teach

What this file is: a **reading** of the curriculum data, on one page, so you can
see what a child in each class actually meets — which letters, which numbers,
which animals, fruits, vegetables, colours, shapes, vehicles and Hindi letters.

It is **not** a source of truth and nothing reads it. The truth is three files,
and if this page and they disagree, they are right:

| What | File |
|---|---|
| Taxonomy — class → subject → topic → subtopic | [`backend/app/data/curriculum/manifest.json`](../backend/app/data/curriculum/manifest.json) |
| Questions, answers, options, hints, pictures | [`backend/app/data/curriculum/activities/{playgroup,nursery,lkg,ukg}.json`](../backend/app/data/curriculum/activities/) |
| Prerequisites between skills | [`backend/app/data/curriculum/skill_graph.json`](../backend/app/data/curriculum/skill_graph.json) |

The AI Teacher's explanation passages are separate again, in
[`backend/app/data/playground/teacher_notes.md`](../backend/app/data/playground/teacher_notes.md).

---

## 1. The four classes at a glance

| Class | id | Age | Mode | Subjects | Topics (levels) | Subtopics | Activities |
|---|---|---|---|---|---|---|---|
| Play Group | `playgroup` | 2–3 | `early` | 3 | 58 | 297 | 421 |
| Nursery | `nursery` | 3–4 | `early` | 6 | 52 | 152 | 585 |
| LKG | `lkg` | 4–5 | `standard` | 5 | 23 | 103 | 98 |
| UKG | `ukg` | 5–6 | `standard` | 6 | 23 | 93 | 118 |
| **Total** | | | | **20** | **156** | **645** | **1222** |

A **topic is one level and one stage of a day** — the schedule gives every
subject exactly one level per day, so a Play Group child's day is 3 stages and a
Nursery child's is 6. The subject and topic counts are asserted in
[`backend/tests/test_curriculum.py`](../backend/tests/test_curriculum.py), so
they cannot drift from the manifest without a test failing.

> Note: `backend/app/data/curriculum/README.md` still prints Play Group as
> 24 topics / 88 subtopics. That is stale — it predates the split into one level
> per letter and one per number. The test and the manifest say 58.

### Subjects per class

| Class | Subjects (topic count) |
|---|---|
| Play Group | `pg_english` English & Language (29) · `pg_maths` Early Mathematics (15) · `pg_ga` General Awareness (14) |
| Nursery | `nur_maths` Basic Mathematics (11) · `nur_english` English (17) · `nur_ga` General Awareness (7) · `nur_evs` Environmental Science (3) · `nur_art` Art, Music & Motor Skills (4) · `nur_hindi` Hindi, oral (10) |
| LKG | `lkg_maths` Basic Mathematics (9) · `lkg_english` English (3) · `lkg_ga` General Awareness (6) · `lkg_evs` Environmental Science (3) · `lkg_art` Art & Writing (2) |
| UKG | `ukg_english` English Language (5) · `ukg_maths` Mathematics (6) · `ukg_evs` EVS (2) · `ukg_ga` General Awareness (3) · `ukg_language` Language, Hindi (3) · `ukg_rhymes` Rhymes (4) |

Play Group also carries four `removed_subjects` in the manifest — `pg_motor`,
`pg_social`, `pg_creative`, `pg_life`. They are recorded, not taught.

---

## 2. Alphabets

### English — Play Group: 26 levels, one letter each

`pg_english_letters_a` … `pg_english_letters_z`. Every level is six subtopics:
Meet the letter · its sound · the picture word · Draw · Say · Match.

| | | | | | |
|---|---|---|---|---|---|
| A — apple 🍎 | B — ball ⚽ | C — cat 🐱 | D — dog 🐶 | E — egg 🥚 | F — fish 🐟 |
| G — goat 🐐 | H — hat 🎩 | I — ice cream 🍨 | J — jug 🫗 | K — kite 🪁 | L — lion 🦁 |
| M — mango 🥭 | N — nest | O — orange 🍊 | P — parrot 🦜 | Q — queen 👸 | R — rabbit 🐰 |
| S — sun ☀️ | T — tree 🌳 | U — umbrella ☂️ | V — van 🚐 | W — watch ⌚ | X — xylophone 🎼 |
| Y — yak 🐃 | Z — zebra 🦓 | | | | |

### English — Nursery: 13 levels, two letters each (capital + small)

`nur_eng_letters_ab` … `nur_eng_letters_yz` — Aa Bb · Cc Dd · Ee Ff · Gg Hh ·
Ii Jj · Kk Ll · Mm Nn · Oo Pp · Qq Rr · Ss Tt · Uu Vv · Ww Xx · Yy Zz.

The same picture words as Play Group with **one difference: M is monkey 🐒, not
mango.** The subject also holds `nur_eng_strokes` (pre-writing),
`nur_eng_phonetics`, `nur_eng_listening` and `nur_eng_rhymes`.

### English — LKG and UKG

LKG has three topics rather than twenty-six: `lkg_eng_capitals` (A–Z as one
level), `lkg_eng_smalls` (a–z, and the vowels a e i o u), `lkg_eng_phonetics`
(a/an, this/that/these/those, plurals — cats, boxes). UKG's `ukg_eng_letters` is
vowels and sounds, and `ukg_eng_words` is CVC word families — bat, mat, rat,
cup, pot, hen, big, dog.

### Hindi — Nursery (oral only, 9 letter levels)

| Level | Letters | Words |
|---|---|---|
| `nur_hindi_swar_a_aa` | अ आ | अनार (`anar`) · आम (`aam`) |
| `nur_hindi_swar_i_ii` | इ ई | इमली (`imli`) · ईख (`eekh`) |
| `nur_hindi_swar_u_uu` | उ ऊ | उल्लू (`ullu`) · ऊन (`oon`) |
| `nur_hindi_swar_e_ai` | ए ऐ | एड़ी · ऐनक (`ainak`) |
| `nur_hindi_swar_o_au` | ओ औ | ओखली · औरत |
| `nur_hindi_swar_am_ah` | अं अः | अंगूर · नमः |
| `nur_hindi_vyanjan_ka_kha` | क ख | कबूतर · खरगोश |
| `nur_hindi_vyanjan_ga_gha` | ग घ | गमला (`gamla`) · घड़ी |
| `nur_hindi_vyanjan_nga` | ङ | पतंग |

Plus `nur_hindi_maukhik` — the oral work: rhymes, Hindi names for fruits,
animals and family members, and नमस्ते / धन्यवाद.

### Hindi — UKG (3 topics, with writing)

`ukg_lang_swar` (स्वर अ–अः) · `ukg_lang_vyanjan` (व्यंजन क–ज्ञ) ·
`ukg_lang_matra` (मात्राएँ — का, कि, मा, नाक, काम).

> **A picture token is Roman; the spoken word is Devanagari.** The data writes
> `anar`, `aam`, `imli` as asset names, and the guide says "अनार", never "anar".
> See `explain.spoken_form()` and `frontend/lib/visualIcon.ts`.

---

## 3. Numbers

| Class | What is taught | Where |
|---|---|---|
| Play Group | **1–10, one level per number** (`pg_maths_number_1` … `_10`), each with meet it, what it means, count it, write it, say it, match it. Plus pre-number concepts — big/small, heavy/light, tall/short | `pg_maths` |
| Nursery | **1–10 in four levels** — 1 2 3 · 4 5 · 6 7 8 · 9 10 — plus 0, comparing (more/less/equal, `=`), and pre-number readiness (the missing number, order) | `nur_maths` |
| LKG | Count to 3 · to 5 · to 10, with **ten-frames** and groups; "are there enough", fewer/more; money (₹1 and ₹5 coins) | `lkg_maths` |
| UKG | **Numbers 1–200**, number names (twelve, thirteen, thirty), backward counting, skip counting by 2 and 5, addition and subtraction to 9, comparison signs `< = >`, money (₹2, ₹5), time (o'clock, days of the week) | `ukg_maths` |

Counting pictures are drawn out of things — apple, balloon, candy, duck, fish,
bird, star, leaf, coin, mangoes, peas. A counting picture shows at most **10**
(`visuals.MAX_COUNT`), which is both the top of the notes and the most a small
child takes in at a glance.

---

## 4. Colours

**The app's whole colour vocabulary** (`visuals.COLOURS`, and `chalkArt.ts` has
a swatch for each): red · blue · yellow · green · orange · purple · pink ·
brown · black · white — plus `grey`, which exists in the art only.

| Class | Colours taught | Levels |
|---|---|---|
| Play Group | red, yellow, blue, green in Maths — then in General Awareness over three levels: **red, blue, yellow** / **green, orange, purple** / **pink, black, white** | `pg_maths_colours`, `pg_ga_colors_1..3` |
| Nursery | **all ten** — red, yellow, blue, green, orange, purple, brown, pink, black, white — plus naming and sorting | `nur_maths_colours` |
| LKG | colour is used for sorting rather than taught as a topic of its own — red/blue/yellow/green circles and squares | `lkg_maths_classify` |
| UKG | **shades and mixing** — light blue / dark blue, light green / dark green; red + yellow = orange, red + white = pink, blue + red = purple | `ukg_maths_colours` |

The everyday examples the data uses: red → apple 🍎, tomato 🍅 · yellow →
banana 🍌, sun ☀️ · blue → water 💧 · green → leaf 🍃, tree 🌳 · orange →
carrot 🥕 · purple → grapes 🍇 · black → crow, night · white → milk 🥛 · pink →
flower 🌸.

---

## 5. Shapes

| Class | Shapes | Level |
|---|---|---|
| Play Group | **circle, square, triangle** (3) | `pg_maths_shapes` |
| Nursery | **circle, square, triangle, rectangle, oval, star** (6), plus shapes in objects — ball, book, hat | `nur_maths_shapes` |
| LKG | circle, triangle, square vs rectangle, shapes in objects — door, plate | `lkg_maths_shapes` |
| UKG | **oval, diamond, semicircle**, and counting corners and sides | `ukg_maths_shapes` |

Pre-writing strokes are a family of their own and the blackboard treats them as
shapes: standing line, sleeping line, slanting line (left and right), curve (up
and down), zigzag, joining dots. Taught in `pg_eng_strokes`, `nur_eng_strokes`,
`nur_art_fine` and `lkg_art_strokes`.

---

## 6. Animals

| Class | Animals | Where |
|---|---|---|
| **Play Group** | Farm: **cow, dog, cat, horse, goat, sheep** · Wild: **lion, tiger, elephant, monkey, bear, giraffe** — four levels of three | `pg_ga_animals_1..4` |
| Nursery | cat, cow, crow, dog, duck, elephant, fish, goat, hen, lion, parrot, rabbit, tiger, turtle, zebra — with their sounds and homes | `nur_ga_animals` |
| LKG | dog, goat, tiger, turtle, cow, elephant, lion, camel — and their **homes**: nest, kennel | `lkg_ga_animals` |
| UKG | **the babies**: calf, kitten, puppy, cub, chick — with hen, sheep, horse, lion, tiger | `ukg_ga_animals` |

Animals also arrive through the alphabet (cat, dog, fish, goat, lion, monkey,
parrot, rabbit, yak, zebra), through Hindi (कबूतर pigeon, खरगोश rabbit, उल्लू
owl), through counting (ducks, birds, fish) and through EVS living/non-living
(bird, dog, rabbit).

---

## 7. Fruits and vegetables

**Fruits — Play Group, two levels of three:** apple, banana, mango
(`pg_ga_fruits_1`) · orange, grapes, watermelon (`pg_ga_fruits_2`).

**Vegetables — Play Group, two levels of three:** potato, tomato, carrot
(`pg_ga_vegetables_1`) · peas, onion, spinach (`pg_ga_vegetables_2`).

No other class has a dedicated fruit or vegetable topic. They keep appearing as
examples instead: apple (A, red, counting, good habits), banana (yellow,
sorting), mango (M in Play Group, आम in Hindi, plants), grapes (purple, अंगूर),
tomato (red), carrot (orange), peas (a UKG counting rhyme), cherry (a UKG nature
rhyme).

> Data note: the orange **fruit** is the token `orangefruit`, because `orange`
> is already the colour. Both are drawable.

---

## 8. Transport

| Class | Vehicles |
|---|---|
| Play Group | **car, bus, train** (`pg_ga_transport_1`) · **bicycle, aeroplane, boat** (`pg_ga_transport_2`) |
| Nursery | aeroplane, ambulance, auto, boat, bus, car, cycle, helicopter, rocket, ship, train — and where they go: station, hospital, park | `nur_ga_transport` |
| LKG | bus, cycle, helicopter, train — counting their wheels | `lkg_ga_transport` |
| UKG | ambulance, fire engine, ship, truck, taxi, aeroplane, bus — **which one you call for what** | `ukg_ga_transport` |

---

## 9. Everything else, by class

**Play Group** — Weather: sunny, rainy, cloudy, windy. Positions: in/out,
up/down, open/closed, first/second. Matching and sorting. Listening and
speaking, rhymes and stories.

**Nursery** — About Myself (body parts: eyes, ears, nose, tongue, legs, hands,
feet, mouth; family: mother, father, sister, grandmother; places: home, school,
market). Good habits (soap, toothbrush, dustbin, please, sorry, thank you).
Safety (helmet, knife, stove, swing, and the traffic light's red/yellow/green).
People who help us (doctor, farmer, teacher, policeman, postman, with their
tools — stethoscope, plough). Seasons and festivals (rainbow, kite, diya,
sweater, gift). EVS: living vs non-living, plants (root, seed, leaf, flower),
air, water, sun, moon. Art: fine motor (crayon, pencil, glue, brush, clay),
gross motor (hop, jump, run), music (drum, clap, hands, toes), show and tell.

**LKG** — About Myself (family including grandfather and uncle; schoolbag).
Safety (footpath, matches, a grown-up). People who help us, plus carpenter.
Seasons (summer/winter, raincoat, sweater, cap). EVS: good habits,
living/non-living, traffic rules (zebra crossing, traffic light) and body parts.
Maths also carries positions (inside/outside, left/right, top/middle/bottom),
classifying by colour and shape, size (tall/short, long/short, wide/narrow) and
money.

**UKG** — Myself (the five senses, skin, joint family vs small family). EVS:
pollution (smoke, sound, river, trees) and traffic rules; our community (post
office, street, basket). Grammar: a/an, this/these/those, in/on/under, plurals.
Reading and conversation. **Rhymes are a subject of their own** — counting
(Rabbits Rabbits, The Peapod, Indian Song), about me (All About Me, Little Me),
nature (The Cherry Tree, This Is the Sun, Thank You God), colour and fun
(Colours of the Rainbow, My Balloon, The Clown).

---

## 10. What the blackboard can actually draw

A picture only appears if the token has real stroke coordinates in
[`frontend/components/blackboard/chalkArt.ts`](../frontend/components/blackboard/chalkArt.ts).
A token with no strokes draws **nothing** rather than a near-miss — the rule
that exists because अनार was once drawn as an apple. The server's closed list of
nameable things is `visuals.THINGS`, and
[`backend/tests/test_playground_teacher.py`](../backend/tests/test_playground_teacher.py)
reads the TypeScript and fails if a name in `THINGS` has no drawing behind it.

**Animals:** bear, bird, buffalo, bull, bunny, calf, camel, cat, chick,
cockerel, cow, crow, cub, dog, donkey, duck, elephant, fish, frog, giraffe,
goat, hen, horse, kitten, lion, monkey, mouse, owl, ox, parrot, peacock, pig,
pony, puppy, rabbit, rat, rooster, serpent, sheep, snake, tiger, tortoise,
turtle, ullu, yak, zebra

**Food and plants:** aam, apple, apples, banana, bread, egg, flower, ice_cream,
icecream, kamal, leaf, leaves, lotus, mango, mangoes, plant, seb, tree

**Things:** bag, ball, balloon, balloons, boat, book, books, bottle, box, bus,
candle, car, clock, cloud, cone, cricketball, cup, dholak, diya, door, drum,
football, glass, home, house, hut, jeep, kite, lamp, moon, mug, notebook,
patang, raincoat, school, schoolbag, ship, tabla, taxi, umbrella, van, watch

**Weather and time:** cloudy, day, night, rain, rainy, sun, sunny

**Shapes:** circle, semicircle, oval, square, rectangle, triangle, diamond,
heart, star, round

**Strokes:** line, standing_line, sleeping_line, slanting_line, left_slant,
right_slant, up_curve, down_curve, curve, zigzag

**Colours:** red, blue, yellow, green, orange, purple, pink, brown, black,
white, grey

Two rules worth remembering before you add anything here. A model may **never**
name a thing — `visuals.parse` refuses `thing:`, and the only producers are
`visuals.for_card` (out of the answer a person wrote in the syllabus) and
`visuals.from_concept` (out of a level's own title). And a child's progress is
keyed by topic id, so **reordering the manifest is safe and renaming a topic id
is not** — a renamed id is dropped from the child's board by
`child_service._forget_departed_topics`.
