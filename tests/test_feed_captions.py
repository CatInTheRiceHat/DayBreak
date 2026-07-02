from core.feed_captions import (
    build_display_channel,
    build_display_hashtags,
    build_display_title,
    build_short_description,
)


def test_short_description_removes_urls_promos_and_excess_hashtags():
    raw = """
    A quiet city guide with three tiny stops for your next weekend walk.
    Subscribe for more travel ideas!
    Watch the full map here: https://example.com/map
    #travel #city #weekend #guide #vlog
    """

    caption = build_short_description(raw)

    assert "http" not in caption
    assert "Subscribe" not in caption
    assert caption.count("#") <= 2
    assert caption.startswith("A quiet city guide")


def test_short_description_truncates_at_word_boundary_with_ellipsis():
    raw = (
        "This thoughtful explainer follows the strange history of a small online "
        "trend and why it keeps resurfacing across different communities today."
    )

    caption = build_short_description(raw, max_chars=90)

    assert caption.endswith("...")
    assert len(caption) <= 90
    assert not caption.endswith(" communities...")


def test_display_title_removes_hashtags_and_truncates():
    raw = (
        "A very long city walk through hidden streets and tiny food stalls "
        "with a careful local guide showing every stop on the route "
        "#travel #city #weekend #guide #vlog #wander"
    )

    title = build_display_title(raw, max_chars=72)

    assert "#" not in title
    assert title.endswith("...")
    assert len(title) <= 72


def test_display_channel_truncates_cleanly():
    channel = build_display_channel("An Extremely Long Creator Channel Name For Travel Vlogs", max_chars=30)

    assert channel.endswith("...")
    assert len(channel) <= 30


def test_display_hashtags_caps_to_three_unique_tags():
    tags = build_display_hashtags(
        "Cozy frog vlog #Frogs #TinyPets #Frogs",
        "More notes #CuteAnimals #Pets #Vlog #Extra",
    )

    assert tags == ["#Frogs", "#TinyPets", "#CuteAnimals"]
