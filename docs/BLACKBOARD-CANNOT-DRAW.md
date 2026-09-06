# What the blackboard cannot draw

Every subject, every class, generated from the syllabus in
`backend/app/data/curriculum/` against `app/playground/visuals.py`.

A card gets a picture when its **answer** names one of the things the app is
allowed to draw, and failing that when the level's **title** does. Anything
else leaves the board empty except for the level's name in the corner.

## What it can draw - the whole vocabulary

- **Any letter, in any script** - `letter:A`, `letter:अ`, `letter:क`. It is
  written as a wipe, so a glyph the app has never seen still appears.
- **Any number** up to three digits, and **counting** 1-10 as that many rings.
- **Five shapes**: circle, square, triangle, rectangle, star.
- **Ten colours**: red, blue, yellow, green, orange, purple, pink, brown,
  black, white (and grey).

That is the whole of it. `visuals.parse` refuses every other kind on purpose -
a picture named wrongly is worse than none - so what follows is not a handful
of missing drawings, it is every concept outside those five kinds.

## The important part: most of these are not missing artwork

The tables mark what the client already holds for each one:

- **chalk** - `frontend/components/blackboard/chalkArt.ts` already has
  hand-written stroke coordinates for it. The board could draw it today; the
  server is simply not allowed to name it.
- **emoji** - `frontend/lib/visualIcon.ts` has a picture, but no chalk strokes.
- **none** - nothing anywhere. Most of these are not things at all: `in`,
  `open`, `first car`, `thank you`, `summer`, `full`, `behind`.

## Levels whose board is blank on every card (42)

Nothing on these levels is a letter, a number, a shape or a colour, so
there is nothing the board is allowed to draw. The child hears the lesson
and reads the question, and the board carries only the level's name.


### Play Group - English & Language Development

- **Pre-Writing Strokes** `pg_eng_strokes`
  - sleeping line *(chalk)*, standing line *(chalk)*
- **Listening & Speaking** `pg_eng_listening`
  - cat *(chalk)*, good morning *(none)*, thank you *(none)*
- **Rhymes & Stories** `pg_eng_rhymes`
  - cow *(emoji)*, duck *(chalk)*

### Play Group - Early Mathematics

- **Pre-Number Concepts** `pg_maths_prenumber`
  - elephant *(emoji)*, mouse *(none)*, rock *(emoji)*, three apples *(chalk)*, tree *(chalk)*
- **Positions** `pg_maths_positions`
  - first car *(chalk)*, in *(none)*, open *(none)*, up *(none)*
- **Matching & Sorting** `pg_maths_matching`
  - banana *(chalk)*, big ball *(chalk)*, cat *(chalk)*, tree *(chalk)*

### Play Group - General Awareness

- **Farm Animals: Cow, Dog, Cat** `pg_ga_animals_1` - 3 of 6 cards
  - cat *(chalk)*, cow *(emoji)*, dog *(chalk)*
- **Farm Animals: Horse, Goat, Sheep** `pg_ga_animals_2` - 3 of 6 cards
  - goat *(emoji)*, horse *(emoji)*, sheep *(emoji)*
- **Wild Animals: Lion, Tiger, Elephant** `pg_ga_animals_3` - 3 of 6 cards
  - elephant *(emoji)*, lion *(emoji)*, tiger *(emoji)*
- **Wild Animals: Monkey, Bear, Giraffe** `pg_ga_animals_4` - 3 of 6 cards
  - bear *(emoji)*, giraffe *(emoji)*, monkey *(emoji)*
- **Fruits: Apple, Banana, Mango** `pg_ga_fruits_1` - 3 of 6 cards
  - apple *(chalk)*, banana *(chalk)*, mango *(chalk)*
- **Vegetables: Potato, Tomato, Carrot** `pg_ga_vegetables_1` - 3 of 6 cards
  - carrot *(emoji)*, potato *(emoji)*, tomato *(emoji)*
- **Vegetables: Peas, Onion, Spinach** `pg_ga_vegetables_2` - 3 of 6 cards
  - onion *(emoji)*, peas *(emoji)*, spinach *(emoji)*
- **Transport: Car, Bus, Train** `pg_ga_transport_1` - 3 of 6 cards
  - bus *(chalk)*, car *(chalk)*, train *(emoji)*
- **Transport: Bicycle, Aeroplane, Boat** `pg_ga_transport_2` - 3 of 6 cards
  - aeroplane *(emoji)*, bicycle *(emoji)*, boat *(chalk)*
- **Weather** `pg_ga_weather` - 4 of 6 cards
  - cloudy *(chalk)*, rainy *(chalk)*, sunny *(chalk)*, windy *(emoji)*

### Nursery - Basic Mathematics

- **Positions** `nur_maths_positions`
  - ball *(chalk)*, behind *(none)*, below *(none)*, bird *(chalk)*, bottom *(none)*, boy *(emoji)*, cat *(chalk)*, fish *(chalk)*, house *(chalk)*, outside *(none)*
- **Size & Measurement** `nur_maths_size`
  - elephant *(emoji)*, empty *(none)*, feather *(emoji)*, flower *(chalk)*, full *(none)*, giraffe *(emoji)*, rabbit *(emoji)*, snake *(emoji)*, stone *(emoji)*, tree *(chalk)*

### Nursery - English

- **Pre-Writing Strokes** `nur_eng_strokes`
  - curve *(chalk)*, line *(chalk)*, zigzag *(chalk)*
- **Listening & Speaking** `nur_eng_listening`
  - eat *(emoji)*, good morning *(none)*, sleep *(emoji)*, sorry *(none)*, thank you *(none)*

### Nursery - General Awareness

- **About Myself** `nur_ga_myself`
  - bed *(emoji)*, cake *(emoji)*, ears *(emoji)*, eyes *(emoji)*, grandmother *(emoji)*, legs *(emoji)*, nose *(emoji)*, school *(chalk)*, tongue *(emoji)*
- **Good Habits & Manners** `nur_ga_habits`
  - apple *(chalk)*, candy *(emoji)*, dustbin *(emoji)*, please *(none)*, soap *(emoji)*, sorry *(none)*, thank you *(none)*, toothbrush *(emoji)*
- **People Who Help Us** `nur_ga_helpers` - 7 of 9 cards
  - doctor *(emoji)*, farmer *(emoji)*, hospital *(emoji)*, policeman *(emoji)*, postman *(emoji)*, school *(chalk)*, teacher *(emoji)*
- **Transport** `nur_ga_transport`
  - aeroplane *(emoji)*, ambulance *(emoji)*, boat *(chalk)*, bus *(chalk)*, cycle *(emoji)*, helicopter *(emoji)*, ship *(chalk)*, station *(emoji)*, train *(emoji)*
- **Animals** `nur_ga_animals` - 9 of 10 cards
  - cat *(chalk)*, cow *(emoji)*, crow *(emoji)*, dog *(chalk)*, elephant *(emoji)*, fish *(chalk)*, lion *(emoji)*, parrot *(chalk)*, turtle *(emoji)*
- **Seasons & Festivals** `nur_ga_seasons`
  - colours *(emoji)*, diya *(chalk)*, gift *(emoji)*, kite *(chalk)*, rainbow *(emoji)*, rainy *(chalk)*, sun *(chalk)*, sweater *(emoji)*

### Nursery - Environmental Science

- **Living & Non-Living** `nur_evs_living` - 6 of 7 cards
  - bird *(chalk)*, dog *(chalk)*, plant *(chalk)*, rabbit *(emoji)*, stone *(emoji)*, tree *(chalk)*
- **Plants Around Us** `nur_evs_plants`
  - flower *(chalk)*, leaf *(chalk)*, mango *(chalk)*, root *(emoji)*, seed *(emoji)*, water *(emoji)*
- **Air, Water and the Sun** `nur_evs_air_water_sun` - 4 of 7 cards
  - air *(emoji)*, moon *(chalk)*, sun *(chalk)*, water *(emoji)*

### Nursery - Art, Music & Motor Skills

- **Fine Motor Skills** `nur_art_fine`
  - crayon *(emoji)*, glue *(emoji)*, pencil *(emoji)*
- **Music & Movement** `nur_art_music` - 4 of 5 cards
  - clap *(emoji)*, drum *(chalk)*, hands *(emoji)*, toes *(emoji)*

### LKG - Basic Mathematics

- **Size** `lkg_maths_size`
  - balloon *(chalk)*, building tall *(emoji)*, road wide *(emoji)*, snake long *(emoji)*

### LKG - General Awareness

- **People Who Help Us** `lkg_ga_helpers`
  - carpenter *(emoji)*, doctor *(emoji)*, plough *(emoji)*, policeman *(emoji)*
- **Seasons** `lkg_ga_seasons`
  - raincoat *(chalk)*, summer *(none)*, winter *(none)*
- **Animals** `lkg_ga_animals`
  - dog *(chalk)*, goat *(emoji)*, nest *(emoji)*, tiger *(emoji)*, turtle *(emoji)*

### LKG - Environmental Science

- **Living & Non-Living** `lkg_evs_living`
  - ball *(chalk)*, tree *(chalk)*
- **Traffic Rules & Body Parts** `lkg_evs_traffic`
  - get ready *(none)*, hands *(emoji)*, zebra crossing *(emoji)*

### LKG - Art & Writing

- **Pre-Writing Strokes** `lkg_art_strokes`
  - Left Slanting Line *(chalk)*, Right Slanting Line *(chalk)*, Sleeping Line *(chalk)*, Standing Line *(chalk)*

### UKG - English Language

- **Early Grammar** `ukg_eng_grammar`
  - an *(none)*, children *(emoji)*, in *(none)*, on *(none)*, these *(none)*, under *(none)*

### UKG - Environmental Science (EVS)

- **Pollution & Traffic Rules** `ukg_evs_pollution`
  - no *(none)*, smoke *(emoji)*, sound *(none)*, tree *(chalk)*

### UKG - General Awareness

- **Transport** `ukg_ga_transport`
  - ambulance *(emoji)*, fire engine *(emoji)*, ship *(chalk)*, truck *(emoji)*
- **Animals** `ukg_ga_animals`
  - calf *(emoji)*, hen *(chalk)*, kitten *(chalk)*, lion *(emoji)*, puppy *(chalk)*, sheep *(emoji)*

## Levels where some cards draw and some do not (43)

The level's title names something drawable, so a picture does go up - but
these particular questions ask about something else, and on those cards it
is the wrong picture or none.


### Play Group - Early Mathematics

- **Colours** `pg_maths_colours` - 1 of 6 cards
  - apple *(chalk)*

### Nursery - Basic Mathematics

- **Shapes** `nur_maths_shapes` - 2 of 10 cards
  - ball *(chalk)*, oval *(chalk)*
- **Colours** `nur_maths_colours` - 1 of 12 cards
  - apple *(chalk)*
- **Comparing** `nur_maths_comparing` - 4 of 9 cards
  - = *(none)*, apple *(chalk)*, ball *(chalk)*, duck *(chalk)*
- **Classify & Sort** `nur_maths_classify` - 5 of 9 cards
  - banana *(chalk)*, bus *(chalk)*, car *(chalk)*, dog *(chalk)*, tomato *(emoji)*

### Nursery - English

- **Letters Aa Bb** `nur_eng_letters_ab` - 2 of 6 cards
  - apple *(chalk)*, ball *(chalk)*
- **Letters Cc Dd** `nur_eng_letters_cd` - 2 of 6 cards
  - cat *(chalk)*, dog *(chalk)*
- **Letters Ee Ff** `nur_eng_letters_ef` - 2 of 6 cards
  - egg *(chalk)*, fish *(chalk)*
- **Letters Gg Hh** `nur_eng_letters_gh` - 2 of 6 cards
  - goat *(emoji)*, hat *(emoji)*
- **Letters Ii Jj** `nur_eng_letters_ij` - 2 of 6 cards
  - icecream *(chalk)*, jug *(emoji)*
- **Letters Kk Ll** `nur_eng_letters_kl` - 2 of 6 cards
  - kite *(chalk)*, lion *(emoji)*
- **Letters Mm Nn** `nur_eng_letters_mn` - 2 of 6 cards
  - monkey *(emoji)*, nest *(emoji)*
- **Letters Oo Pp** `nur_eng_letters_op` - 2 of 6 cards
  - orangefruit *(emoji)*, parrot *(chalk)*
- **Letters Qq Rr** `nur_eng_letters_qr` - 2 of 6 cards
  - queen *(emoji)*, rabbit *(emoji)*
- **Letters Ss Tt** `nur_eng_letters_st` - 2 of 6 cards
  - sun *(chalk)*, tree *(chalk)*
- **Letters Uu Vv** `nur_eng_letters_uv` - 2 of 6 cards
  - umbrella *(chalk)*, van *(chalk)*
- **Letters Ww Xx** `nur_eng_letters_wx` - 2 of 6 cards
  - watch *(chalk)*, xylophone *(emoji)*
- **Letters Yy Zz** `nur_eng_letters_yz` - 2 of 6 cards
  - yak *(emoji)*, zebra *(emoji)*
- **Phonetics** `nur_eng_phonetics` - 8 of 10 cards
  - ball *(chalk)*, cat *(chalk)*, dog *(chalk)*, doll *(emoji)*, fish *(chalk)*, hat *(emoji)*, monkey *(emoji)*, sun *(chalk)*
- **Rhymes & Stories** `nur_eng_rhymes` - 5 of 7 cards
  - crow *(emoji)*, moon *(chalk)*, sky *(emoji)*, stone *(emoji)*, water *(emoji)*

### Nursery - General Awareness

- **Safety** `nur_ga_safety` - 5 of 8 cards
  - helmet *(emoji)*, knife *(emoji)*, mother *(emoji)*, stove *(emoji)*, swing *(emoji)*

### LKG - Basic Mathematics

- **Shapes** `lkg_maths_shapes` - 1 of 5 cards
  - door *(chalk)*
- **Comparing** `lkg_maths_comparing` - 2 of 5 cards
  - no *(none)*, yes *(none)*
- **Positions** `lkg_maths_positions` - 4 of 5 cards
  - dog *(chalk)*, doll *(emoji)*, left *(none)*, outside *(none)*
- **Classify** `lkg_maths_classify` - 1 of 4 cards
  - the two cats *(chalk)*

### LKG - English

- **Phonetics** `lkg_eng_phonetics` - 5 of 6 cards
  - an *(none)*, boxes *(none)*, cats *(chalk)*, this *(none)*, those *(none)*

### LKG - General Awareness

- **About Myself** `lkg_ga_myself` - 4 of 5 cards
  - cake *(emoji)*, grandfather *(emoji)*, legs *(emoji)*, schoolbag *(chalk)*
- **Safety** `lkg_ga_safety` - 2 of 4 cards
  - footpath *(emoji)*, no *(none)*
- **Transport** `lkg_ga_transport` - 3 of 4 cards
  - bus *(chalk)*, helicopter *(emoji)*, train *(emoji)*

### LKG - Environmental Science

- **Good Habits & Manners** `lkg_evs_habits` - 2 of 3 cards
  - please *(none)*, put it in the dustbin *(emoji)*

### UKG - English Language

- **Letters & Sounds** `ukg_eng_letters` - 2 of 4 cards
  - cat *(chalk)*, zip *(emoji)*
- **Words & Rhyming** `ukg_eng_words` - 2 of 5 cards
  - big *(none)*, dog *(chalk)*
- **Reading & Conversation** `ukg_eng_reading` - 2 of 4 cards
  - big dog *(chalk)*, sun *(chalk)*
- **Activities** `ukg_eng_methods` - 2 of 3 cards
  - on the mat *(emoji)*, the cat sat on the mat *(chalk)*

### UKG - Mathematics

- **Pre-Maths Concepts** `ukg_maths_premaths` - 5 of 6 cards
  - book thick *(chalk)*, bottle half *(chalk)*, last child *(emoji)*, oval *(chalk)*, right *(none)*
- **Addition & Subtraction** `ukg_maths_addsub` - 3 of 9 cards
  - < *(none)*, = *(none)*, > *(none)*
- **Shapes** `ukg_maths_shapes` - 4 of 5 cards
  - diamond *(chalk)*, egg *(chalk)*, oval *(chalk)*, semicircle *(emoji)*
- **Money & Time** `ukg_maths_money_time` - 2 of 6 cards
  - Tuesday *(none)*, night *(chalk)*

### UKG - General Awareness

- **Myself** `ukg_ga_myself` - 4 of 5 cards
  - joint *(none)*, rainy *(chalk)*, skin *(emoji)*, tongue *(emoji)*

### UKG - Rhymes

- **Counting Rhymes** `ukg_rhymes_counting` - 2 of 3 cards
  - camel *(emoji)*, we count back down *(none)*
- **Rhymes About Me** `ukg_rhymes_me` - 1 of 2 cards
  - eyes *(emoji)*
- **Nature Rhymes** `ukg_rhymes_nature` - 2 of 3 cards
  - on the sea *(none)*, they sing *(emoji)*
- **Colour & Fun Rhymes** `ukg_rhymes_fun` - 1 of 3 cards
  - he laughs *(none)*

## Every answer with no picture behind it (199)

The number is how many cards ask for it, across all four classes.

### chalk (59)

apple (7), ball (6), balloon (1), banana (5), big ball (1), big dog (1), bird (2), boat (3), book thick (1), bottle half (1), bus (5), car (3), cat (9), cats (1), cloudy (1), curve (1), diamond (1), diya (1), dog (9), door (1), drum (2), duck (2), egg (2), first car (1), fish (4), flower (2), hen (1), house (1), icecream (1), kite (2), kitten (1), leaf (1), left slanting line (1), line (1), mango (3), moon (2), night (1), oval (3), parrot (2), plant (2), puppy (1), raincoat (1), rainy (4), right slanting line (1), school (2), schoolbag (1), ship (2), sleeping line (2), standing line (2), sun (6), sunny (2), the cat sat on the mat (1), the two cats (1), three apples (1), tree (7), umbrella (1), van (1), watch (1), zigzag (1)

### emoji (102)

aeroplane (3), air (2), ambulance (2), bear (2), bed (1), bicycle (2), boy (1), building tall (1), cake (2), calf (1), camel (1), candy (1), carpenter (1), carrot (2), children (1), clap (1), colours (1), cow (6), crayon (1), crow (3), cycle (1), doctor (3), doll (2), dustbin (1), ears (1), eat (1), elephant (5), eyes (2), farmer (2), feather (1), fire engine (1), footpath (1), gift (1), giraffe (3), glue (1), goat (4), grandfather (1), grandmother (1), hands (2), hat (2), helicopter (2), helmet (1), horse (2), hospital (1), jug (1), knife (1), last child (1), legs (2), lion (5), monkey (4), mother (1), nest (2), nose (1), on the mat (1), onion (2), orangefruit (1), peas (2), pencil (1), plough (1), policeman (2), postman (1), potato (2), put it in the dustbin (1), queen (1), rabbit (3), rainbow (1), road wide (1), rock (1), root (1), seed (1), semicircle (1), sheep (3), skin (1), sky (1), sleep (1), smoke (1), snake (1), snake long (1), soap (1), spinach (2), station (1), stone (3), stove (1), sweater (1), swing (1), teacher (1), they sing (1), tiger (3), toes (1), tomato (3), tongue (2), toothbrush (1), train (4), truck (1), turtle (2), water (4), windy (1), xylophone (1), yak (1), zebra (1), zebra crossing (1), zip (1)

### none (38)

< (1), = (3), > (1), an (2), behind (1), below (1), big (1), bottom (1), boxes (1), empty (1), full (1), get ready (1), good morning (2), he laughs (1), in (2), joint (1), left (1), mouse (1), no (4), on (1), on the sea (1), open (1), outside (2), please (2), right (1), sorry (2), sound (1), summer (1), thank you (3), these (1), this (1), those (1), tuesday (1), under (1), up (1), we count back down (1), winter (1), yes (1)

