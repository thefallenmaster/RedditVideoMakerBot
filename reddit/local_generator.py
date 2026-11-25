import json
import random
from os.path import exists
from pathlib import Path

from utils import settings
from utils.console import print_step, print_substep
from utils.posttextparser import posttextparser
from utils.subreddit import _contains_blocked_words
from utils.voice import sanitize_text

CUSTOM_POSTS_PATH = Path("video_creation/data/custom_posts.json")

# Grounded, conversational Reddit-style threads and replies written to avoid stiff AI phrasing.
_LOCAL_THREADS = [
    {
        "id": "loc_001",
        "subreddit": "AskReddit",
        "title": "What's a weirdly specific rule your workplace had because of one single incident?",
        "author": "forklift_philosopher",
        "upvotes": 4820,
        "selftext": (
            "At my old warehouse job there was a laminated sign above the breakroom sink that said "
            "'NO ROTISSERIE CHICKENS IN THE DISHWASHER'. Nobody ever explained it to new hires, "
            "you just had to earn the lore after six months."
        ),
        "comments": [
            {
                "id": "loc_001_c1",
                "author": "mildly_caffeinated",
                "score": 1940,
                "age": "7h ago",
                "body": "We weren't allowed to keep personal toasters at our desks after Greg tried to melt cheese on a sideways bagel and set off the sprinkler on floor four.",
            },
            {
                "id": "loc_001_c2",
                "author": "tuesday_regrets",
                "score": 1120,
                "age": "6h ago",
                "body": "Sign on the office printer: 'Do not scan your face with the lid open, HR gets every PDF.' Apparently somebody forgot it auto-emailed the front desk.",
            },
            {
                "id": "loc_001_c3",
                "author": "soggy_taco_99",
                "score": 845,
                "age": "5h ago",
                "body": "Not allowed to bring glitter to a hardware store anymore. One guy put it inside a ceiling fan display box as a prank and we were still sweeping it up two years later.",
            },
            {
                "id": "loc_001_c4",
                "author": "parking_lot_crow",
                "score": 612,
                "age": "4h ago",
                "body": "My high school banned bringing full 2-liter sodas because two sophomores kept trading Mentos like contraband behind the bleachers.",
            },
            {
                "id": "loc_001_c5",
                "author": "nightshift_dave",
                "score": 430,
                "age": "3h ago",
                "body": "We had a rule against microwaving foil-wrapped burritos, which should be obvious, yet somehow became a 20-minute safety slideshow.",
            },
        ],
    },
    {
        "id": "loc_002",
        "subreddit": "AskReddit",
        "title": "What's something cheap that immediately made your daily life way better?",
        "author": "boulder_hiker_co",
        "upvotes": 6310,
        "selftext": (
            "Bought a six-dollar magnetic key hook that sticks right onto the metal frame of my front door. "
            "Haven't torn apart my couch looking for car keys in eight months."
        ),
        "comments": [
            {
                "id": "loc_002_c1",
                "author": "just_a_tired_dad",
                "score": 2840,
                "age": "8h ago",
                "body": "A ten-foot braided phone charger. Being able to roll over in bed without unplugging my phone felt like upgrading to first class.",
            },
            {
                "id": "loc_002_c2",
                "author": "oatmeal_enjoyer",
                "score": 1650,
                "age": "7h ago",
                "body": "Silicone drain hair catcher for the shower. Costs four bucks and saved me from ever having to pull a swamp monster out of the pipe again.",
            },
            {
                "id": "loc_002_c3",
                "author": "half_asleep_dev",
                "score": 980,
                "age": "6h ago",
                "body": "A cheap electric kettle. I don't even drink tea that often, just having boiling water in ninety seconds for ramen or pasta is huge.",
            },
            {
                "id": "loc_002_c4",
                "author": "leftover_pasta",
                "score": 710,
                "age": "4h ago",
                "body": "Microfiber cloths in bulk. Paper towels started feeling weirdly expensive once I realized two damp cloths clean basically the whole kitchen.",
            },
            {
                "id": "loc_002_c5",
                "author": "couch_mechanic",
                "score": 495,
                "age": "2h ago",
                "body": "Adhesive cable clips for the side of my nightstand. No more fishing around on the floor in the dark at 1am.",
            },
        ],
    },
    {
        "id": "loc_003",
        "subreddit": "AskReddit",
        "title": "Night shift workers, what is the strangest completely harmless thing you've seen on shift?",
        "author": "wafflehouse_owl",
        "upvotes": 5490,
        "selftext": (
            "Used to stock shelves at a 24-hour grocery store from midnight to 8am. "
            "Around 3:15 every Thursday a guy in full cycling gear would walk in, buy one single yam, "
            "nod politely at the cashier, and ride off into the fog."
        ),
        "comments": [
            {
                "id": "loc_003_c1",
                "author": "hotel_desk_ghoul",
                "score": 2310,
                "age": "9h ago",
                "body": "Worked front desk at a roadside hotel. A wedding guest came down at 3am in a tuxedo, asked for three spoons, sat in the lobby eating a whole tub of dry oats with tap water, and went back upstairs.",
            },
            {
                "id": "loc_003_c2",
                "author": "diesel_coffee",
                "score": 1540,
                "age": "8h ago",
                "body": "Security at an office park. Caught a raccoon using the motion-sensor automatic doors just to walk in, stare at the vending machine lights, and walk back out.",
            },
            {
                "id": "loc_003_c3",
                "author": "er_scribe_77",
                "score": 1090,
                "age": "6h ago",
                "body": "Hospital overnight shift. Two paramedics spent twenty minutes in the ambulance bay quietly arguing over which dinosaur could beat a gorilla in a basketball game.",
            },
            {
                "id": "loc_003_c4",
                "author": "graveyard_baker",
                "score": 680,
                "age": "5h ago",
                "body": "At a 24-hour diner, a guy came in at 4am wearing slippers, ordered six sides of toast, buttered none of them, stacked them in a pyramid, left a twenty, and vanished.",
            },
            {
                "id": "loc_003_c5",
                "author": "late_bus_home",
                "score": 410,
                "age": "3h ago",
                "body": "Saw an older guy walking his pet duck on a tiny harness past the gas station at 2am. Duck was wearing little blue boots. Honestly made my whole week.",
            },
        ],
    },
    {
        "id": "loc_004",
        "subreddit": "tifu",
        "title": "TIFU by trying to sound polite on a work call and accidentally inventing a fake relative",
        "author": "throwaway_84920",
        "upvotes": 7120,
        "selftext": (
            "On Monday morning my manager asked why I missed the Friday afternoon wrap-up. "
            "The truth was I fell asleep on my couch at 4:10pm after eating two bowls of cereal. "
            "Instead my brain panicked and said I had to pick up my uncle from the train station. "
            "Now everyone keeps asking how Uncle Arthur liked visiting town and I have to invent a whole backstory for a man who lives in my head."
        ),
        "comments": [
            {
                "id": "loc_004_c1",
                "author": "spreadsheet_monk",
                "score": 3120,
                "age": "10h ago",
                "body": "Tell them Arthur went back home early because he hates humidity. Close the lore before someone invites him to the company picnic.",
            },
            {
                "id": "loc_004_c2",
                "author": "burnt_croissant",
                "score": 1870,
                "age": "8h ago",
                "body": "I once told a coworker I had a twin sister just to avoid admitting I didn't recognize her at Target. Four years later I'm still sending updates about 'Rachel' in Portland.",
            },
            {
                "id": "loc_004_c3",
                "author": "cold_brew_iv",
                "score": 940,
                "age": "6h ago",
                "body": "The funniest part is nobody would have cared if you just said you had a stomachache, yet panic brain always reaches for Victorian train station drama.",
            },
            {
                "id": "loc_004_c4",
                "author": "quiet_commute",
                "score": 590,
                "age": "4h ago",
                "body": "Wait until someone asks what Arthur does for a living. Keep your answer boring, like he repairs commercial ice machines or sells gravel.",
            },
        ],
    },
    {
        "id": "loc_005",
        "subreddit": "AskReddit",
        "title": "What's a completely useless skill you accidentally got really good at?",
        "author": "pm_me_cold_coffee",
        "upvotes": 4210,
        "selftext": (
            "From working retail for three years I can tell within five grams whether a soda can is "
            "full, half empty, or just has two sips left at the bottom before I even look inside."
        ),
        "comments": [
            {
                "id": "loc_005_c1",
                "author": "laundry_folder",
                "score": 1760,
                "age": "8h ago",
                "body": "I can guess the exact microwave time needed for any leftover without checking the wattage. Cold center in lasagna hasn't happened to me since 2019.",
            },
            {
                "id": "loc_005_c2",
                "author": "suburb_raccoon",
                "score": 1240,
                "age": "7h ago",
                "body": "Used to work at a deli counter. I can eyeball exactly half a pound of sliced turkey on the first grab almost every single time.",
            },
            {
                "id": "loc_005_c3",
                "author": "vinyl_static",
                "score": 890,
                "age": "5h ago",
                "body": "I can catch falling kitchen items with the top of my foot before they hit the tile. Doesn't help when it's a knife though, had to unlearn that fast.",
            },
            {
                "id": "loc_005_c4",
                "author": "train_window_seat",
                "score": 520,
                "age": "3h ago",
                "body": "Growing up with creaky hardwood floors means I can walk through a dark house at 2am in complete silence like a ninja with mild back pain.",
            },
        ],
    },
    {
        "id": "loc_006",
        "subreddit": "confession",
        "title": "I've been 'fixing' my dad's slow Wi-Fi for three years by just rebooting the router and pretending to type commands",
        "author": "router_whisperer",
        "upvotes": 8340,
        "selftext": (
            "Every time I visit my parents, my dad hands me his tablet and says the internet is acting up again. "
            "The first time I actually checked his channels and DNS. Now I just unplug the router for thirty seconds, "
            "open Terminal on my laptop, run ping google.com so green text scrolls by, and tell him I cleared the packet backlog. "
            "He thinks I'm basically a network wizard and makes me steak every time I drive over."
        ),
        "comments": [
            {
                "id": "loc_006_c1",
                "author": "sysadmin_burnout",
                "score": 3910,
                "age": "11h ago",
                "body": "Half of actual IT is rebooting things with confidence while looking mildly concerned at a terminal window. You're doing real enterprise work.",
            },
            {
                "id": "loc_006_c2",
                "author": "cable_drawer",
                "score": 2140,
                "age": "9h ago",
                "body": "Put the router on a cheap smart outlet that reboots itself at 4am every Sunday and watch him think you permanently cured Comcast.",
            },
            {
                "id": "loc_006_c3",
                "author": "mint_tea_mug",
                "score": 1120,
                "age": "7h ago",
                "body": "Honestly this is wholesome. You get steak, he feels taken care of, and the Wi-Fi actually works afterwards. Everybody wins.",
            },
            {
                "id": "loc_006_c4",
                "author": "old_thinkpad",
                "score": 640,
                "age": "4h ago",
                "body": "My mom thinks pressing F5 is a secret technician shortcut because I never explained what refresh does.",
            },
        ],
    },
    {
        "id": "loc_007",
        "subreddit": "AskReddit",
        "title": "What's a tiny childhood misunderstanding that took you way too long to figure out?",
        "author": "cereal_at_midnight",
        "upvotes": 5870,
        "selftext": (
            "Until I was fourteen I genuinely thought 'drinking and driving' meant ANY drink, "
            "so I used to panic whenever my mom took a sip of iced coffee at a red light."
        ),
        "comments": [
            {
                "id": "loc_007_c1",
                "author": "paperback_spine",
                "score": 2650,
                "age": "9h ago",
                "body": "Thought 'euthanasia' was 'youth in Asia' until high school biology. Could not figure out why the news was so stressed about teenagers in Japan.",
            },
            {
                "id": "loc_007_c2",
                "author": "rusty_bicycle",
                "score": 1820,
                "age": "8h ago",
                "body": "When restaurants said 'kids eat free on Tuesdays' I assumed it meant kids were allowed to eat without using utensils.",
            },
            {
                "id": "loc_007_c3",
                "author": "rainy_sidewalk",
                "score": 1190,
                "age": "6h ago",
                "body": "I thought the little red triangle hazard button in my dad's car was an eject seat button. Refused to sit near the center console for six years.",
            },
            {
                "id": "loc_007_c4",
                "author": "lemon_seltzer",
                "score": 730,
                "age": "5h ago",
                "body": "Thought 'for sale' and 'for sail' were different, so I wondered why so many houses on land were secretly boats.",
            },
        ],
    },
    {
        "id": "loc_008",
        "subreddit": "pettyrevenge",
        "title": "Roommate kept eating my labeled meal prep, so I switched my lunches to ghost-pepper chicken for a week",
        "author": "tupperware_warden",
        "upvotes": 6940,
        "selftext": (
            "My roommate ate my chicken and rice three Mondays in a row and always blamed 'sleepwalking' or said he thought it was communal. "
            "So I packed decoy lunches with extra habanero and ghost pepper sauce while keeping my real lunch at work. "
            "Came home Tuesday to find him sitting on the kitchen floor holding a carton of milk like a trophy. "
            "He never touched my shelf again."
        ),
        "comments": [
            {
                "id": "loc_008_c1",
                "author": "spicy_noodle_club",
                "score": 2480,
                "age": "10h ago",
                "body": "Notice how people who 'sleepwalk' into your food never accidentally eat plain celery or canned sardines.",
            },
            {
                "id": "loc_008_c2",
                "author": "fridge_diplomat",
                "score": 1590,
                "age": "8h ago",
                "body": "Did he even try to complain, or did he have to suffer in silence because admitting it burned meant admitting he stole it?",
            },
            {
                "id": "loc_008_c3",
                "author": "garlic_butter_toast",
                "score": 920,
                "age": "6h ago",
                "body": "Had a coworker like this. Put blue food coloring in my ranch dressing once and watched his face turn pale across the breakroom.",
            },
            {
                "id": "loc_008_c4",
                "author": "shared_apartment_blues",
                "score": 540,
                "age": "3h ago",
                "body": "Nothing cures 'I thought it was communal' faster than unexpected Scoville units.",
            },
        ],
    },
    {
        "id": "loc_009",
        "subreddit": "AskReddit",
        "title": "What's a movie or show detail you didn't notice until a rewatch years later?",
        "author": "late_night_crt",
        "upvotes": 4560,
        "selftext": (
            "Rewatched Toy Story as an adult and realized Woody isn't just jealous of Buzz — "
            "every toy in that room is genuinely terrified of getting replaced and thrown in a yard sale box."
        ),
        "comments": [
            {
                "id": "loc_009_c1",
                "author": "popcorn_kernel",
                "score": 1980,
                "age": "8h ago",
                "body": "In Home Alone, Kevin's dad accidentally throws Kevin's plane ticket into the trash while wiping up spilled milk, which is why the headcount at the door was off.",
            },
            {
                "id": "loc_009_c2",
                "author": "dvd_menu_loop",
                "score": 1340,
                "age": "7h ago",
                "body": "In Monsters Inc, Randall is testing his camouflage against different wallpapers during the opening montage and fails every time.",
            },
            {
                "id": "loc_009_c3",
                "author": "blanket_fort_ceo",
                "score": 815,
                "age": "5h ago",
                "body": "Rewatching The Truman Show as an adult makes it way sadder when you notice his wife literally holds groceries toward hidden cameras like commercials.",
            },
            {
                "id": "loc_009_c4",
                "author": "matinee_ticket",
                "score": 470,
                "age": "3h ago",
                "body": "In Shrek, Lord Farquaad literally turns down the music and closes the door on his mirror right before checking out Fiona in bed. Went right over my head at age nine.",
            },
        ],
    },
    {
        "id": "loc_010",
        "subreddit": "AskReddit",
        "title": "What's the most memorable thing a total stranger did that they probably forgot five minutes later?",
        "author": "bus_stop_umbrella",
        "upvotes": 7890,
        "selftext": (
            "Dropped my whole bag of groceries in the pouring rain outside a pharmacy when the paper handle ripped. "
            "A guy waiting at the crosswalk sprinted over with two reusable bags from his backpack, helped me pack everything, and left before I even got his name."
        ),
        "comments": [
            {
                "id": "loc_010_c1",
                "author": "honda_civic_08",
                "score": 3340,
                "age": "11h ago",
                "body": "My old car stalled at a busy intersection in winter. Four guys jumped out of a pickup truck behind me, pushed me into a parking lot in twenty seconds, and yelled 'have a good Tuesday' as they drove off.",
            },
            {
                "id": "loc_010_c2",
                "author": "airport_gate_b4",
                "score": 2190,
                "age": "9h ago",
                "body": "Was crying quietly on a subway after getting laid off. An older woman handed me a pack of tissues and two butterscotch candies without saying a word, then got off at the next stop.",
            },
            {
                "id": "loc_010_c3",
                "author": "grocery_aisle_7",
                "score": 1410,
                "age": "7h ago",
                "body": "Card declined for eight dollars of baby formula because my bank froze a transfer. Guy behind me tapped his card before I could even pull out cash and told the cashier to ring it together.",
            },
            {
                "id": "loc_010_c4",
                "author": "parallel_parker",
                "score": 780,
                "age": "4h ago",
                "body": "Failed to parallel park twice with a line of cars watching. A teenager on the sidewalk stood behind my bumper and guided me in like an air traffic controller, then gave me a fist bump.",
            },
        ],
    },
    {
        "id": "loc_011",
        "subreddit": "CasualConversation",
        "title": "Tried making homemade bread for the first time and ended up creating a very heavy doorstop",
        "author": "yeast_was_expired",
        "upvotes": 3620,
        "selftext": (
            "Thought baking sourdough looked relaxing on YouTube. Three hours later I pulled something out of the oven "
            "that sounded like knocking on oak flooring when I tapped the crust. Still ate half of it with butter because I'm stubborn."
        ),
        "comments": [
            {
                "id": "loc_011_c1",
                "author": "cast_iron_skillet",
                "score": 1420,
                "age": "7h ago",
                "body": "Slice it thin, toast it twice, and call it rustic garlic croutons. Nobody has to know your yeast gave up halfway through.",
            },
            {
                "id": "loc_011_c2",
                "author": "flour_on_shoes",
                "score": 890,
                "age": "6h ago",
                "body": "My first loaf came out shaped like a deflated football and weighed four pounds. My dog wouldn't even chew the crust.",
            },
            {
                "id": "loc_011_c3",
                "author": "butter_knife_bandit",
                "score": 610,
                "age": "4h ago",
                "body": "Honestly warm bad bread with salted butter still beats store-bought sandwich bread eight days a week.",
            },
            {
                "id": "loc_011_c4",
                "author": "timer_went_off",
                "score": 380,
                "age": "2h ago",
                "body": "Check the expiration date on the yeast packet next time. Learned that after baking what was basically a warm warm-brick.",
            },
        ],
    },
    {
        "id": "loc_012",
        "subreddit": "AskReddit",
        "title": "What's an unwritten social rule everyone silently agrees on without ever talking about it?",
        "author": "elevator_corner",
        "upvotes": 6740,
        "selftext": (
            "If two strangers almost walk into each other in a hallway and both dodge the same direction twice, "
            "one of you has to say 'ope, sorry' or make a tiny joke about dancing. Walking away silently feels illegal."
        ),
        "comments": [
            {
                "id": "loc_012_c1",
                "author": "gym_locker_14",
                "score": 2890,
                "age": "9h ago",
                "body": "If there are five open treadmills in an empty gym, you leave at least one empty machine between yourself and the other person.",
            },
            {
                "id": "loc_012_c2",
                "author": "check_please_88",
                "score": 1950,
                "age": "8h ago",
                "body": "When someone shows you a photo on their phone, you look ONLY at that photo. Swiping left or right without permission is basically breaking into their house.",
            },
            {
                "id": "loc_012_c3",
                "author": "crosswalk_jogger",
                "score": 1320,
                "age": "6h ago",
                "body": "Doing the little fake half-jog across the crosswalk when a car stops for you, even though your speed barely changes by two percent.",
            },
            {
                "id": "loc_012_c4",
                "author": "cart_return_hero",
                "score": 870,
                "age": "4h ago",
                "body": "If you're first in line at a red light, you can't sit there scrolling for three seconds after it turns green. Everybody behind you is silently judging.",
            },
        ],
    },
]


def _load_custom_posts() -> list:
    if not CUSTOM_POSTS_PATH.exists():
        return []
    try:
        data = json.loads(CUSTOM_POSTS_PATH.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return [p for p in data if isinstance(p, dict) and p.get("title")]
    except Exception:
        pass
    return []


def _load_done_ids() -> set:
    videos_path = Path("video_creation/data/videos.json")
    if not videos_path.exists():
        videos_path.parent.mkdir(parents=True, exist_ok=True)
        videos_path.write_text("[]", encoding="utf-8")
        return set()
    try:
        return {
            v.get("id")
            for v in json.loads(videos_path.read_text(encoding="utf-8"))
            if isinstance(v, dict)
        }
    except Exception:
        return set()


def get_local_thread(POST_ID: str = None) -> dict:
    """Selects a realistic local story + comments without touching Reddit or external APIs."""
    print_step("Generating local story & comments...")
    pool = _load_custom_posts() + list(_LOCAL_THREADS)

    requested_sub = str(settings.config["reddit"]["thread"].get("subreddit") or "").strip().lower()
    if requested_sub.startswith("r/"):
        requested_sub = requested_sub[2:]

    done_ids = _load_done_ids()
    storymode = bool(settings.config["settings"]["storymode"])
    max_story_len = int(settings.config["settings"].get("storymode_max_length") or 2000)

    def _eligible(item: dict) -> bool:
        text_blob = f"{item.get('title', '')} {item.get('selftext', '')}"
        if _contains_blocked_words(text_blob):
            return False
        if storymode:
            selftext = item.get("selftext", "") or ""
            if len(selftext) < 30 or len(selftext) > max_story_len:
                return False
        return True

    selected = None
    if POST_ID:
        selected = next((t for t in pool if t.get("id") == POST_ID), None)

    if selected is None:
        undone = [t for t in pool if t.get("id") not in done_ids and _eligible(t)]
        if requested_sub:
            sub_matches = [t for t in undone if t.get("subreddit", "").lower() == requested_sub]
            if sub_matches:
                undone = sub_matches
        if undone:
            selected = random.choice(undone)
        else:
            eligible_all = [t for t in pool if _eligible(t)] or pool
            selected = random.choice(eligible_all)

    sub_name = selected.get("subreddit") or requested_sub or "AskReddit"
    thread_id = selected.get("id") or f"loc_{random.randint(1000, 9999)}"
    title = selected["title"]
    selftext = selected.get("selftext", "") or ""

    print_substep(f"Subreddit style: r/{sub_name}", style="bold blue")
    print_substep(f"Video will be: {title} :thumbsup:", style="bold green")

    content = {
        "is_local": True,
        "subreddit": sub_name,
        "thread_url": f"local://{sub_name}/{thread_id}",
        "thread_title": title,
        "thread_id": thread_id,
        "thread_author": selected.get("author", "anonymous_poster"),
        "thread_upvotes": selected.get("upvotes", 2500),
        "is_nsfw": bool(selected.get("is_nsfw", False)),
        "comments": [],
    }

    if storymode:
        if settings.config["settings"]["storymodemethod"] == 1:
            content["thread_post"] = posttextparser(selftext)
        else:
            content["thread_post"] = selftext
    else:
        content["thread_post"] = selftext
        max_len = int(settings.config["reddit"]["thread"]["max_comment_length"])
        min_len = int(settings.config["reddit"]["thread"]["min_comment_length"])

        # Include the OP story first (when present) so videos feature both the story and comments
        if selftext and len(selftext.strip()) >= min_len:
            story_id = f"{thread_id}_story"
            content["comments"].append(
                {
                    "comment_body": selftext.strip(),
                    "comment_url": f"local://{sub_name}/{thread_id}/{story_id}",
                    "comment_id": story_id,
                    "comment_author": content["thread_author"],
                    "comment_score": content["thread_upvotes"],
                    "comment_age": "OP • 9h ago",
                    "is_op": True,
                }
            )

        raw_comments = list(selected.get("comments", []))
        # Keep top comment first most of the time, shuffle remaining for natural variety
        if len(raw_comments) > 1:
            head = raw_comments[:1]
            tail = raw_comments[1:]
            random.shuffle(tail)
            raw_comments = head + tail

        for idx, c in enumerate(raw_comments):
            body = (c.get("body") or "").strip()
            if not body or _contains_blocked_words(body):
                continue
            sanitised = sanitize_text(body)
            if not sanitised or sanitised == " ":
                continue
            if min_len <= len(body) <= max_len:
                cid = c.get("id") or f"{thread_id}_c{idx}"
                content["comments"].append(
                    {
                        "comment_body": body,
                        "comment_url": f"local://{sub_name}/{thread_id}/{cid}",
                        "comment_id": cid,
                        "comment_author": c.get("author", f"redditor_{random.randint(10, 99)}"),
                        "comment_score": c.get("score", random.randint(120, 2400)),
                        "comment_age": c.get("age", f"{random.randint(1, 11)}h ago"),
                    }
                )

    print_substep(
        f"Prepared local post with {len(content['comments'])} comments.",
        style="bold green",
    )
    return content
