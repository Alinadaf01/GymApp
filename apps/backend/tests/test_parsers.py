"""Persian parser tests — spec §9.4 example and §25 voice scenarios A–F."""
import pytest

from app.parsers.dictionary import Entry, ExerciseDictionary
from app.parsers.numbers import words_to_digits
from app.parsers.nutrition import parse_nutrition
from app.parsers.supplements import parse_supplements
from app.parsers.workout import parse_workout

DICT = ExerciseDictionary([
    Entry("پرس بالا سینه دمبل", ("پرس بالاسینه دمبل",)),
    Entry("پرس سینه هالتر"),
    Entry("پرس سینه دستگاه"),
    Entry("قفسه سینه سیم‌کش", ("قفسه سیم‌کش",)),
    Entry("جلو بازو دمبل"),
    Entry("جلو بازو سیم‌کش"),
    Entry("اسکوات"),
    Entry("پرس پا"),
    Entry("لت سیم‌کش"),
    Entry("قایقی"),
])


@pytest.mark.parametrize("text,expected", [
    ("چهار ست پانزده تایی", "4 ست 15 تایی"),
    ("چار ست پونزده تایی", "4 ست 15 تایی"),
    ("بیست و پنج کیلو", "25 کیلو"),
    ("صد و بیست متر", "120 متر"),
    ("دو هزار و پانصد متر", "2500 متر"),
    ("یک و نیم دقیقه", "1.5 دقیقه"),
    ("نیم دقیقه", "0.5 دقیقه"),
    ("پانزده‌تایی", "15 تایی"),
    ("۴ ست ۱۵تایی", "4 ست 15 تایی"),
    ("هزار واحد", "1000 واحد"),
    ("نه، اشتباه شد", "نه، اشتباه شد"),  # «نه» = "no" is not a number
    ("نه ست", "9 ست"),
    ("ساعت نه شب", "ساعت 9 شب"),
    ("يک ست", "1 ست"),  # Arabic yeh normalized
])
def test_words_to_digits(text, expected):
    assert words_to_digits(text) == expected


def test_spec_example_9_4():
    r = parse_workout(
        "پرس بالا سینه دمبل چهار ست پانزده تایی، پرس سینه دستگاه سه ست دوازده تایی، استراحت بین ست‌ها یک دقیقه.",
        DICT, session_title="جلسه اول",
    )
    assert r.session_title == "جلسه اول"
    assert [(e.name, e.sets, e.reps, e.weight_value, e.rest_seconds) for e in r.exercises] == [
        ("پرس بالا سینه دمبل", 4, "15", None, None),
        ("پرس سینه دستگاه", 3, "12", None, None),
    ]
    assert r.session_notes == "استراحت بین ست‌ها ۱ دقیقه."
    assert all(e.matched and not e.warnings for e in r.exercises)


def test_scenario_a_clear_sentence():
    (e,) = parse_workout("پرس بالا سینه دمبل چهار ست پانزده تایی.", DICT).exercises
    assert (e.name, e.sets, e.reps) == ("پرس بالا سینه دمبل", 4, "15")


def test_scenario_b_multiple_exercises_in_order():
    r = parse_workout("پرس سینه دستگاه سه ست دوازده تایی، بعد قفسه سیم‌کش سه ست پانزده تایی.", DICT)
    assert [(e.name, e.sets, e.reps) for e in r.exercises] == [
        ("پرس سینه دستگاه", 3, "12"), ("قفسه سینه سیم‌کش", 3, "15")]


def test_scenario_b_without_punctuation():
    r = parse_workout("پرس سینه دستگاه سه ست دوازده تایی و قفسه سیم کش سه ست پانزده تایی", DICT)
    assert [e.name for e in r.exercises] == ["پرس سینه دستگاه", "قفسه سینه سیم‌کش"]


def test_scenario_c_weight_and_rest():
    (e,) = parse_workout("جلو بازو دمبل سه ست ده تایی با دمبل دوازده کیلویی، یک دقیقه استراحت.", DICT).exercises
    assert (e.sets, e.reps, e.weight_value, e.weight_unit, e.rest_seconds) == (3, "10", 12, "kg", 60)
    assert e.notes is None  # restated «با دمبل» is not noise in notes
    assert any("نسبت داده شد" in w for w in e.warnings)  # flagged for review


def test_scenario_d_incomplete_no_guessing():
    (e,) = parse_workout("اسکوات، چهار ست.", DICT).exercises
    assert (e.name, e.sets, e.reps) == ("اسکوات", 4, None)
    assert "تعداد تکرار گفته نشده" in e.warnings


def test_scenario_d_only_name():
    (e,) = parse_workout("اسکوات", DICT).exercises
    assert (e.sets, e.reps, e.weight_value, e.rest_seconds) == (None, None, None, None)


def test_scenario_e_unknown_name_kept():
    (e,) = parse_workout("پشت پا خوابیده دستگاه چهار ست دوازده تایی", DICT).exercises
    assert e.name == "پشت پا خوابیده دستگاه" and e.matched is False
    assert (e.sets, e.reps) == (4, "12")
    assert any("در فرهنگ لغت نیست" in w for w in e.warnings)


def test_close_name_is_suggested_not_replaced():
    (e,) = parse_workout("پرس کالا سینه دن بل چار ست پونزده تایی", DICT).exercises
    assert e.name == "پرس کالا سینه دن بل"  # raw kept
    assert e.suggestion == "پرس بالا سینه دمبل"
    assert (e.sets, e.reps) == (4, "15")


def test_ambiguous_numbers_are_not_assigned():
    (e,) = parse_workout("پرس سینه هالتر چهار پانزده", DICT).exercises
    assert (e.sets, e.reps) == (None, None)
    assert any("عدد بدون واحد" in w and "۴" in w and "۱۵" in w for w in e.warnings)


def test_raw_text_kept_for_debugging():
    (e,) = parse_workout("اسکوات چهار ست دوازده تایی", DICT).exercises
    assert e.raw_text == "اسکوات ۴ ست ۱۲ تایی"


@pytest.mark.parametrize("text,reps", [
    ("اسکوات چهار ست دوازده ده هشت تایی", "12-10-8"),
    ("اسکوات چهار ست ۱۲-۱۰-۸", "12-10-8"),
    ("اسکوات چهار ست هشت تا دوازده تکرار", "8-12"),
    ("اسکوات سه ست تا ناتوانی", "تا ناتوانی"),
])
def test_rep_schemes(text, reps):
    assert parse_workout(text, DICT).exercises[0].reps == reps


def test_supersets_and_notes():
    (e,) = parse_workout("اسکوات چهار ست دوازده تایی سوپرست با لانگز", DICT).exercises
    assert e.notes == "سوپرست با لانگز" and e.reps == "12"


def test_time_and_distance():
    r = parse_workout("دوچرخه ثابت بیست دقیقه، پیاده روی دو کیلومتر، پلانک سه ست سی ثانیه", DICT)
    bike, walk, plank = r.exercises
    assert (bike.execution_type, bike.duration_seconds) == ("time", 1200)
    assert (walk.execution_type, walk.distance_value, walk.distance_unit) == ("distance", 2, "km")
    assert (plank.sets, plank.duration_seconds, plank.reps) == (3, 30, None)


def test_rest_variants():
    r = parse_workout("اسکوات چهار ست ده تایی استراحت یک دقیقه و نیم، پرس پا سه ست دوازده تایی نود ثانیه استراحت", DICT)
    assert [e.rest_seconds for e in r.exercises] == [90, 90]


def test_weight_without_unit_is_flagged():
    (e,) = parse_workout("اسکوات چهار ست ده تایی وزنه بیست", DICT).exercises
    assert (e.weight_value, e.weight_unit) == (20, None)
    assert "واحد وزنه مشخص نیست" in e.warnings


def test_values_first_then_name():
    (e,) = parse_workout("چهار ست اسکوات دوازده تایی", DICT).exercises
    assert (e.name, e.sets, e.reps) == ("اسکوات", 4, "12")


def test_session_title_from_voice():
    r = parse_workout("جلسه دوم پا، اسکوات چهار ست ده تایی", DICT)
    assert r.session_title == "جلسه دوم: پا"
    assert [e.name for e in r.exercises] == ["اسکوات"]


def test_nothing_recognised():
    r = parse_workout("سلام، امروز چطوری", DICT)
    # Unknown words become an (unknown) exercise name rather than being dropped
    assert r.exercises and all(not e.matched for e in r.exercises)


def test_empty_text():
    r = parse_workout("", DICT)
    assert r.exercises == [] and r.warnings


# ---- nutrition -------------------------------------------------------------------


def test_nutrition_meals_times_and_content():
    r = parse_nutrition(
        "صبحانه ساعت هشت دو عدد تخم مرغ با نان سنگک، میان وعده ساعت ده و نیم یک عدد سیب، "
        "ناهار ساعت یک ظهر برنج و مرغ، شام ساعت نه شب سالاد")
    assert [(m.title, m.time_text, m.content) for m in r.meals] == [
        ("صبحانه", "۰۸:۰۰", "۲ عدد تخم مرغ با نان سنگک"),
        ("میان‌وعده", "۱۰:۳۰", "۱ عدد سیب"),
        ("ناهار", "۱۳:۰۰", "برنج و مرغ"),
        ("شام", "۲۱:۰۰", "سالاد"),
    ]


def test_nutrition_without_meal_names():
    r = parse_nutrition("روزی دو لیتر آب")
    assert len(r.meals) == 1 and r.meals[0].content == "روزی ۲ لیتر آب" and r.warnings


def test_nutrition_meal_without_time():
    (m,) = parse_nutrition("ناهار برنج و مرغ").meals
    assert m.time_text is None


# ---- supplements -----------------------------------------------------------------


def test_supplements_amount_and_timing_as_said():
    r = parse_supplements("ویتامین دی هزار واحد روزی یک بار بعد از ناهار، امگا سه دو عدد همراه شام، "
                          "کراتین پنج گرم بعد تمرین، منیزیم")
    assert [(x.name, x.amount_text, x.timing_text) for x in r.supplements] == [
        ("ویتامین دی", "۱۰۰۰ واحد", "روزی ۱ بار، بعد از ناهار"),
        ("امگا ۳", "۲ عدد", "همراه شام"),
        ("کراتین", "۵ گرم", "بعد تمرین"),
        ("منیزیم", None, None),  # nothing invented
    ]
    assert r.supplements[3].warnings == ["مقدار گفته نشده", "زمان مصرف گفته نشده"]


# --- First real voice on the server (Whisper spellings of spoken Persian) ---

REAL_DICT = ExerciseDictionary([
    Entry("پرس سینه هالتر", ("پرس سینه با هالتر",)),
    Entry("پرس سینه دمبل", ("پرس سینه با دمبل",)),
    Entry("جلو بازو چکشی", ("جلوبازو چکشی",)),
])


def test_first_real_voice_transcript():
    text = ("پرس سینه با حالتر، سست، دوازه تکرار، پرس سینه دنبل، چار ست، سیزه تکرار، "
            "جلو بازو چکوشی، چار ست، چارده تکرار")
    r = parse_workout(text, REAL_DICT)
    got = [(e.name, e.matched, e.sets, e.reps, e.warnings) for e in r.exercises]
    assert got == [
        ("پرس سینه هالتر", True, 3, "12", []),
        ("پرس سینه دمبل", True, 4, "13", []),
        ("جلو بازو چکشی", True, 4, "14", []),
    ]
    assert r.warnings == [] and r.session_notes is None


def test_second_real_voice_transcript():
    # Whisper split the numbers across words and put commas inside «چار، ست»
    text = ("پرس سینه حالتر، سست، دوزت ایکرار، پرس سینه دنبل، چار، ست، سیزهت ایکرار، "
            "جلو بازو چکوشی، چار، ست، چاردت ایکرار.")
    r = parse_workout(text, REAL_DICT)
    got = [(e.name, e.matched, e.sets, e.reps, e.warnings) for e in r.exercises]
    assert got == [
        ("پرس سینه هالتر", True, 3, "12", []),
        ("پرس سینه دمبل", True, 4, "13", []),
        ("جلو بازو چکشی", True, 4, "14", []),
    ]
    assert r.warnings == [] and r.session_notes is None


@pytest.mark.parametrize("text,expected", [
    ("چارد تکرار", "14 تکرار"),
    ("اسکوات تا ناتوانی", "اسکوات تا ناتوانی"),
    ("لت سیم‌کش تا خستگی", "لت سیم‌کش تا خستگی"),
    ("سه، تکرار", "3 تکرار"),
    ("سست دوازه تکرار", "3 ست 12 تکرار"),
    ("چهارست یازه تایی", "4 ست 11 تایی"),
    ("دوست پونزه تکرار", "2 ست 15 تکرار"),
    ("دوست 10 تایی", "2 ست 10 تایی"),
    ("با دوستم رفتم", "با دوستم رفتم"),     # not a number
    ("دوست داره", "دوست داره"),             # «دوست» without a count stays a word
    ("نشست", "نشست"),
])
def test_spoken_number_forms(text, expected):
    assert words_to_digits(text) == expected


def test_connector_ba_ignored_in_dictionary_match():
    r = parse_workout("پرس سینه با دمبل 4 ست 10 تایی", REAL_DICT)
    assert r.exercises[0].name == "پرس سینه دمبل" and r.exercises[0].matched


def test_spelling_fix_keeps_unknown_names_unguessed():
    r = parse_workout("زیر بغل دنبل 3 ست 12 تایی", REAL_DICT)
    ex = r.exercises[0]
    assert ex.name == "زیر بغل دمبل" and not ex.matched  # spelling fixed, name not replaced
