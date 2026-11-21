"""The focus trip behind the automation sensors (v2.28.0)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from custom_components.ns_reisadvies._focus import (
    FOCUS_FAVOURITE,
    FOCUS_NEXT,
    departure_facts,
    disruption_events,
    focus_trip,
    journey_events,
    live_facts,
    trip_identity,
    trip_window,
)

NOW = datetime(2026, 11, 21, 8, 0, tzinfo=timezone.utc)


def _at(minutes: int) -> str:
    return (NOW + timedelta(minutes=minutes)).isoformat()


def _trip(ctx: str, dep: int, arr: int, *, number: str = "1537",
          track: str = "3", planned_track: str = "3", delay: int = 0,
          status: str = "NORMAL", legs: int = 1) -> dict:
    first = {
        "product": {"number": number, "shortCategoryName": "IC",
                    "displayName": "NS Intercity", "operatorName": "NS"},
        "direction": "Deventer",
        "origin": {"name": "Hilversum", "uicCode": "8400320",
                   "plannedDateTime": _at(dep), "actualDateTime": _at(dep + delay),
                   "plannedTrack": planned_track, "actualTrack": track},
        "destination": {"name": "Amersfoort Centraal", "uicCode": "8400055",
                        "plannedDateTime": _at(arr), "actualDateTime": _at(arr + delay)},
        "crowdForecast": "MEDIUM",
        "composition": {"numberOfParts": 7, "numberOfSeats": 471, "trainType": "ICM"},
    }
    all_legs = [first]
    if legs > 1:
        all_legs.append({"product": {}, "origin": {}, "destination": {}})  # a walk
        all_legs.append({
            "product": {"number": "637", "shortCategoryName": "IC"},
            "origin": {"name": "Amersfoort Centraal", "plannedDateTime": _at(arr + 3)},
            "destination": {"name": "Zwolle", "plannedDateTime": _at(arr + 38),
                            "actualDateTime": _at(arr + 38)},
        })
    return {"ctxRecon": ctx, "status": status, "legs": all_legs,
            "plannedDurationInMinutes": arr - dep}


# --------------------------------------------------------------------
# which trip
# --------------------------------------------------------------------

def test_without_a_favourite_the_next_departure_is_the_focus() -> None:
    trips = [_trip("gone", -10, 5), _trip("next", 4, 20), _trip("later", 34, 50)]
    trip, why = focus_trip(trips, [], NOW)
    assert trip["ctxRecon"] == "next" and why == FOCUS_NEXT


def test_a_favourite_wins_and_one_under_way_wins_over_one_to_come() -> None:
    trips = [_trip("next", 4, 20), _trip("fav-later", 34, 50), _trip("fav-now", -5, 15)]
    trip, why = focus_trip(trips, ["fav-later", "fav-now"], NOW)
    assert trip["ctxRecon"] == "fav-now" and why == FOCUS_FAVOURITE
    trip, _ = focus_trip(trips, ["fav-later"], NOW)
    assert trip["ctxRecon"] == "fav-later"


def test_a_finished_favourite_gives_way() -> None:
    trips = [_trip("fav-done", -60, -20), _trip("next", 4, 20)]
    trip, why = focus_trip(trips, ["fav-done"], NOW)
    assert trip["ctxRecon"] == "next" and why == FOCUS_NEXT


def test_a_cancelled_next_train_is_still_the_focus() -> None:
    """"My train is cancelled" is exactly what an automation is for."""
    trips = [_trip("next", 4, 20, status="CANCELLED"), _trip("later", 34, 50)]
    trip, _ = focus_trip(trips, None, NOW)
    assert trip["ctxRecon"] == "next"


def test_nothing_left_means_no_focus() -> None:
    assert focus_trip([_trip("gone", -10, 5)], [], NOW) == (None, None)
    assert focus_trip(None, None, NOW) == (None, None)
    assert focus_trip(["nope", {"legs": []}], [], NOW) == (None, None)


def test_a_trip_is_recognised_on_the_next_refresh() -> None:
    assert trip_identity(_trip("CTX", 4, 20)) == "CTX"
    bare = _trip("", 4, 20)
    bare.pop("ctxRecon")
    assert trip_identity(bare) == f"1537@{_at(4)}"
    assert trip_identity(None) is None
    assert trip_identity({"legs": []}) is None
    assert trip_identity({"legs": [{"product": {"number": "1"}, "origin": {}}]}) is None
    assert trip_window({"legs": []}) == (None, None)


# --------------------------------------------------------------------
# departure facts
# --------------------------------------------------------------------

def test_departure_facts_read_like_the_departure_board() -> None:
    facts = departure_facts(_trip("CTX", 12, 30, delay=4, track="5", planned_track="3",
                                  legs=3), NOW)
    assert facts["train"] == "IC 1537" and facts["train_type"] == "NS Intercity"
    assert facts["departure"] == NOW + timedelta(minutes=16)
    assert facts["planned_departure"] == NOW + timedelta(minutes=12)
    assert facts["departure_delay"] == 4
    assert facts["minutes_to_departure"] == 16
    assert facts["platform"] == "5" and facts["planned_platform"] == "3"
    assert facts["platform_changed"] is True
    assert facts["cancelled"] is False
    # Arrival is the end of the whole journey, past the transfer.
    assert facts["destination"] == "Zwolle"
    assert facts["arrival"] == NOW + timedelta(minutes=68)
    # The live map follows the first train, so its own stretch matters.
    assert facts["leg_origin"] == "Hilversum"
    assert facts["leg_destination"] == "Amersfoort Centraal"
    assert facts["transfers"] == 1
    assert facts["crowd"] == "medium"
    assert facts["carriages"] == 7 and facts["seats"] == 471
    assert facts["rolling_stock"] == "ICM"
    assert facts["travel_time"] == 18


def test_departure_facts_never_count_down_below_zero() -> None:
    facts = departure_facts(_trip("CTX", -3, 15), NOW)
    assert facts["minutes_to_departure"] == 0


def test_departure_facts_flag_a_cancellation_either_way() -> None:
    assert departure_facts(_trip("C", 4, 20, status="CANCELLED"), NOW)["cancelled"]
    leg_cancelled = _trip("C", 4, 20)
    leg_cancelled["legs"][0]["cancelled"] = True
    assert departure_facts(leg_cancelled, NOW)["cancelled"]


def test_departure_facts_without_times_leave_the_times_out() -> None:
    trip = _trip("C", 4, 20)
    trip["legs"][0]["origin"] = {"name": "Hilversum"}
    facts = departure_facts(trip, NOW)
    assert facts["departure"] is None and facts["minutes_to_departure"] is None
    assert facts["departure_delay"] == 0


def test_live_facts_past_the_traveller_s_stop_have_nothing_left() -> None:
    # Beyond Amersfoort, towards Deventer.
    live = live_facts(STOPS, {"lat": 52.2000, "lng": 5.7600, "speed": 120}, FACTS)
    assert live["progress"] == 100.0 and live["remaining_km"] == 0.0


def test_departure_facts_without_a_trip_are_empty() -> None:
    assert departure_facts(None, NOW) == {}
    assert departure_facts({"legs": [{"product": {}}]}, NOW) == {}


def test_transfers_are_counted_when_ns_does_not_say() -> None:
    trip = _trip("C", 4, 20, legs=3)
    trip["transfers"] = "nope"
    assert departure_facts(trip, NOW)["transfers"] == 1


# --------------------------------------------------------------------
# live facts
# --------------------------------------------------------------------

STOPS = [
    {"name": "Amsterdam Centraal", "uicCode": "8400058", "lat": 52.3789, "lng": 4.9003,
     "status": "ORIGIN"},
    {"name": "Weesp", "uicCode": "8400678", "lat": 52.3094, "lng": 5.0433, "status": "PASSING"},
    {"name": "Hilversum", "uicCode": "8400320", "lat": 52.2270, "lng": 5.1810,
     "status": "STOP"},
    {"name": "Baarn", "uicCode": "8400080", "lat": 52.2110, "lng": 5.2870,
     "status": "PASSING"},
    {"name": "Amersfoort Centraal", "uicCode": "8400055", "lat": 52.1533, "lng": 5.3736,
     "status": "STOP"},
    {"name": "Deventer", "uicCode": "8400173", "lat": 52.2572, "lng": 6.1606,
     "status": "DESTINATION"},
]

FACTS = {"leg_origin": "Hilversum", "leg_origin_uic": "8400320",
         "leg_destination": "Amersfoort Centraal", "leg_destination_uic": "8400055"}


def test_live_facts_between_stations() -> None:
    # Halfway between Hilversum and Baarn, at speed.
    fix = {"lat": 52.2190, "lng": 5.2340, "speed": 118.4, "heading": 101.6,
           "source": "ns-obis"}
    live = live_facts(STOPS, fix, FACTS)
    assert 2.0 < live["position_index"] < 3.0
    assert live["speed"] == 118.4 and live["heading"] == 102
    assert live["moving"] is True and live["at_station"] is False
    assert live["current_station"] is None
    # Baarn is passed through, so the next station is where it stops.
    assert live["next_station"] == "Amersfoort Centraal"
    assert 0 < live["progress"] < 50
    assert 0 < live["remaining_km"] < 20


def test_live_facts_standing_at_the_boarding_station() -> None:
    fix = {"lat": 52.2272, "lng": 5.1812, "speed": 0}
    live = live_facts(STOPS, fix, FACTS)
    assert live["current_station"] == "Hilversum"
    assert live["at_station"] is True and live["moving"] is False
    assert live["progress"] == 0.0
    assert live["next_station"] == "Amersfoort Centraal"


def test_live_facts_before_the_traveller_boards() -> None:
    """The train is still on its way to the platform: nothing done yet."""
    fix = {"lat": 52.3450, "lng": 4.9700, "speed": 90}
    live = live_facts(STOPS, fix, FACTS)
    assert live["position_index"] < 2
    assert live["progress"] == 0.0
    assert live["next_station"] == "Hilversum"


def test_a_fix_past_the_station_before_the_train_is_due_is_not_this_ride() -> None:
    """A train does not leave ten minutes early: that fix is another
    ride with the same number, or a stale one, and is not believed."""
    facts = {**FACTS, "departure": NOW + timedelta(minutes=10)}
    past_hilversum = {"lat": 52.2190, "lng": 5.2340, "speed": 118}
    assert live_facts(STOPS, past_hilversum, facts, NOW) == {}
    # On its way to the platform is fine, early or not...
    approaching = {"lat": 52.3450, "lng": 4.9700, "speed": 90}
    assert live_facts(STOPS, approaching, facts, NOW)["next_station"] == "Hilversum"
    # ...and once it is due, past the station is simply "departed".
    due = NOW + timedelta(minutes=9)
    assert live_facts(STOPS, past_hilversum, facts, due)["progress"] > 0


def test_racing_through_a_station_is_not_being_at_it() -> None:
    fix = {"lat": 52.3094, "lng": 5.0433, "speed": 130}
    live = live_facts(STOPS, fix, FACTS)
    assert live["current_station"] is None and live["at_station"] is False


def test_live_facts_need_a_fix_and_a_run() -> None:
    assert live_facts(STOPS, None, FACTS) == {}
    assert live_facts(STOPS[:1], {"lat": 52.0, "lng": 5.0}, FACTS) == {}
    # A fix far from the line belongs to another train.
    assert live_facts(STOPS, {"lat": 50.8, "lng": 4.3}, FACTS) == {}


def test_live_facts_without_a_known_stretch_leave_progress_out() -> None:
    live = live_facts(STOPS, {"lat": 52.2190, "lng": 5.2340, "speed": None},
                      {"leg_origin": "Utrecht Centraal", "leg_destination": "Zwolle"})
    assert live["progress"] is None and live["remaining_km"] is None
    assert live["speed"] is None and live["moving"] is False


def test_stations_are_found_by_name_where_there_is_no_code() -> None:
    live = live_facts(STOPS, {"lat": 52.2190, "lng": 5.2340, "speed": 100},
                      {"leg_origin": "hilversum", "leg_destination": "AMERSFOORT CENTRAAL"})
    assert live["boarding_index"] == 2 and live["alighting_index"] == 4


# --------------------------------------------------------------------
# events
# --------------------------------------------------------------------

def _facts(**changes) -> dict:
    facts = departure_facts(_trip("CTX", 12, 30), NOW)
    facts.update(changes)
    return facts


def test_a_platform_change_on_the_same_trip_is_news() -> None:
    events = journey_events(_facts(platform="3"), _facts(platform="5"), None, None,
                            set(), NOW)
    assert events == [("platform_changed", {
        "train": "IC 1537", "train_number": "1537", "origin": "Hilversum",
        "destination": "Amersfoort Centraal", "departure": _at(12),
        "platform": "5", "previous_platform": "3",
    })]


def test_a_different_trip_is_never_a_change() -> None:
    """The focus moving to the next train must not read as news."""
    other = _facts(identity="OTHER", platform="7", departure_delay=9, cancelled=True)
    assert journey_events(_facts(), other, None, None, set(), NOW) == []


def test_delay_and_cancellation_are_reported() -> None:
    events = journey_events(_facts(departure_delay=0), _facts(departure_delay=6,
                            cancelled=True), None, None, set(), NOW)
    kinds = [kind for kind, _ in events]
    assert kinds == ["delay_changed", "cancelled"]
    assert events[0][1]["delay"] == 6 and events[0][1]["previous_delay"] == 0


def test_departed_and_arrived_fire_once_from_the_clock() -> None:
    fired: set[str] = set()
    later = NOW + timedelta(minutes=31)
    first = journey_events(_facts(), _facts(), None, None, fired, later)
    assert [kind for kind, _ in first] == ["departed", "arrived"]
    assert journey_events(_facts(), _facts(), None, None, fired, later) == []


def test_departed_and_arrived_follow_the_train_where_it_is_known() -> None:
    fired: set[str] = set()
    # The clock says it has left, the train says it has not.
    standing = {"position_index": 2.0, "boarding_index": 2, "alighting_index": 4,
                "at_station": True}
    late = NOW + timedelta(minutes=14)
    assert journey_events(_facts(), _facts(), None, standing, fired, late) == []
    moving = {**standing, "position_index": 2.4, "at_station": False}
    assert [k for k, _ in journey_events(_facts(), _facts(), None, moving, fired,
                                         late)] == ["departed"]
    there = {**standing, "position_index": 4.0, "at_station": True}
    assert [k for k, _ in journey_events(_facts(), _facts(), None, there, fired,
                                         late)] == ["arrived"]


def test_a_cancelled_train_neither_leaves_nor_arrives() -> None:
    later = NOW + timedelta(minutes=40)
    events = journey_events(_facts(cancelled=True), _facts(cancelled=True), None, None,
                            set(), later)
    assert events == []


def test_no_focus_means_no_events() -> None:
    assert journey_events(None, None, None, None, set(), NOW) == []
    assert journey_events(None, {"identity": None}, None, None, set(), NOW) == []


def test_disruptions_starting_and_ending_are_reported() -> None:
    items = [{"id": "A", "type": "DISRUPTION", "title": "Weesp - Hilversum",
              "summary": "Wisselstoring", "extra_travel_time": "+15 min"}]
    assert disruption_events(None, items) == []
    started = disruption_events(set(), items)
    assert started == [("disruption_started", {
        "id": "A", "disruption_type": "DISRUPTION", "title": "Weesp - Hilversum",
        "summary": "Wisselstoring", "extra_travel_time": "+15 min",
    })]
    assert disruption_events({"A"}, items) == []
    assert disruption_events({"A", "B"}, items) == [("disruption_ended", {"id": "B"})]


# --------------------------------------------------------------------
# v2.28.0, second round: leaving, transfers, shorter trains, the train
# after and the last train
# --------------------------------------------------------------------

from custom_components.ns_reisadvies._focus import (  # noqa: E402
    following_trip,
    is_shorter,
    last_trip,
    summary,
    transfers_of,
)


def test_the_time_to_leave_follows_the_expected_departure() -> None:
    """Eight minutes to the station, a train that is four minutes late:
    leave twelve minutes before the planned time, not eight."""
    facts = departure_facts(_trip("C", 10, 30, delay=4), NOW, minutes_to_station=8)
    assert facts["leave_at"] == NOW + timedelta(minutes=6)
    assert facts["time_to_leave"] is False
    later = departure_facts(_trip("C", 10, 30, delay=4), NOW + timedelta(minutes=7),
                            minutes_to_station=8)
    assert later["time_to_leave"] is True
    gone = departure_facts(_trip("C", 10, 30, delay=4), NOW + timedelta(minutes=15),
                           minutes_to_station=8)
    assert gone["time_to_leave"] is False


def test_no_travel_time_means_no_leave_time() -> None:
    facts = departure_facts(_trip("C", 10, 30), NOW)
    assert facts["leave_at"] is None and facts["time_to_leave"] is False


def test_a_cancelled_train_is_never_time_to_leave() -> None:
    facts = departure_facts(_trip("C", 5, 30, status="CANCELLED"), NOW + timedelta(minutes=1),
                            minutes_to_station=8)
    assert facts["time_to_leave"] is False


def _with_transfer(first_arrives: int, second_leaves: int, *, planned_gap: int = 5,
                   cancelled: bool = False) -> dict:
    return {
        "ctxRecon": "T",
        "legs": [
            {"product": {"number": "1537", "shortCategoryName": "IC"},
             "origin": {"name": "Hilversum", "plannedDateTime": _at(0)},
             "destination": {"name": "Amersfoort Centraal", "plannedTrack": "1",
                             "plannedDateTime": _at(20),
                             "actualDateTime": _at(first_arrives)}},
            {"product": {"number": "637", "shortCategoryName": "IC"},
             "cancelled": cancelled,
             "origin": {"name": "Amersfoort Centraal", "plannedTrack": "2",
                        "actualTrack": "4",
                        "plannedDateTime": _at(20 + planned_gap),
                        "actualDateTime": _at(second_leaves)},
             "destination": {"name": "Zwolle", "plannedDateTime": _at(60)}},
        ],
    }


def test_a_transfer_with_room_is_not_at_risk() -> None:
    changes = transfers_of(_with_transfer(20, 25))
    assert changes == [{
        "station": "Amersfoort Centraal", "arrival_platform": "1",
        "departure_platform": "4", "margin": 5, "planned_margin": 5,
        "next_train": "IC 637", "at_risk": False,
    }]
    facts = departure_facts(_with_transfer(20, 25), NOW)
    assert facts["transfer_at_risk"] is False and facts["transfer_margin"] == 5
    assert facts["transfer_station"] == "Amersfoort Centraal"


def test_a_delay_that_eats_the_transfer_puts_it_at_risk() -> None:
    facts = departure_facts(_with_transfer(24, 25), NOW)
    assert facts["transfer_at_risk"] is True and facts["transfer_margin"] == 1
    # A connecting train that is cancelled is at risk however long the gap.
    assert departure_facts(_with_transfer(20, 25, cancelled=True), NOW)["transfer_at_risk"]


def test_a_direct_train_has_no_transfer() -> None:
    facts = departure_facts(_trip("C", 10, 30), NOW)
    assert facts["transfer_list"] == [] and facts["transfer_at_risk"] is False
    assert facts["transfer_margin"] is None and facts["transfer_station"] is None


def test_a_shorter_train_is_one_with_fewer_carriages_than_planned() -> None:
    assert is_shorter({"numberOfParts": 4, "plannedNumberOfParts": 8}) is True
    assert is_shorter({"numberOfParts": 8, "plannedNumberOfParts": 8}) is False
    assert is_shorter({"numberOfParts": 10, "plannedNumberOfParts": 8}) is False
    # Same carriages, fewer seats, and NS itself calls it significant.
    assert is_shorter({"numberOfParts": 6, "plannedNumberOfParts": 6, "numberOfSeats": 300,
                       "plannedNumberOfSeats": 450, "significantChange": True}) is True
    assert is_shorter({"numberOfParts": 6, "plannedNumberOfParts": 6, "numberOfSeats": 300,
                       "plannedNumberOfSeats": 450}) is False
    # Without both figures, nobody can say.
    assert is_shorter({"numberOfParts": 6}) is None
    assert is_shorter(None) is None


def test_departure_facts_carry_the_shorter_train() -> None:
    trip = _trip("C", 10, 30)
    trip["legs"][0]["composition"] = {"numberOfParts": 3, "plannedNumberOfParts": 7}
    facts = departure_facts(trip, NOW)
    assert facts["shorter_train"] is True
    assert facts["carriages"] == 3 and facts["planned_carriages"] == 7
    bare = _trip("C", 10, 30)
    bare["legs"][0].pop("composition")
    assert departure_facts(bare, NOW)["shorter_train"] is None


def test_the_arrival_platform_is_where_you_get_off() -> None:
    trip = _trip("C", 10, 30)
    trip["legs"][0]["destination"].update({"plannedTrack": "5", "actualTrack": "6"})
    facts = departure_facts(trip, NOW)
    assert facts["arrival_platform"] == "6" and facts["planned_arrival_platform"] == "5"
    assert facts["arrival_platform_changed"] is True


def test_the_train_after_is_the_next_one_that_runs() -> None:
    trips = [_trip("A", 5, 20), _trip("B", 35, 50, status="CANCELLED"),
             _trip("C", 65, 80), _trip("D", 95, 110), "nope"]
    focus = departure_facts(trips[0], NOW)
    assert following_trip(trips, focus)["ctxRecon"] == "C"
    assert following_trip(trips, {}) is None
    last = departure_facts(trips[3], NOW)
    assert following_trip(trips, last) is None


def test_the_last_train_is_the_last_that_leaves_before_the_day_ends() -> None:
    ends = NOW + timedelta(minutes=100)
    trips = [_trip("A", 5, 20), _trip("B", 65, 80), _trip("C", 95, 110, status="CANCELLED"),
             _trip("D", 125, 140), "nope", {"legs": []}]
    assert last_trip(trips, ends)["ctxRecon"] == "B"
    assert last_trip([], ends) is None


def test_a_summary_carries_just_enough() -> None:
    facts = summary(_trip("A", 5, 20, delay=2, track="7"), NOW)
    assert facts["train"] == "IC 1537" and facts["platform"] == "7"
    assert facts["departure_delay"] == 2
    assert set(facts) == {"departure", "planned_departure", "arrival", "train",
                          "train_number", "platform", "departure_delay", "transfers",
                          "travel_time", "cancelled"}
    assert summary(None, NOW) == {}
