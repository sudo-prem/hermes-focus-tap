#!/usr/bin/env python3
"""Original deterministic focus planner; developed with Codex assistance.

Reads only supplied JSON. It neither imports assignment code nor accesses accounts,
network services, environment credentials or a user's calendar automatically.
"""

import argparse
from datetime import date, datetime, time, timedelta, timezone
import json
import re
import sys
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


UTC = timezone.utc
MAX_BYTES = 2 * 1024 * 1024


class InputError(ValueError):
    pass


def integer(value, field, lower, upper):
    if type(value) is not int or not lower <= value <= upper:
        raise InputError(f"{field} must be an integer between {lower} and {upper}.")
    return value


def text(value, field, limit):
    if not isinstance(value, str) or not value.strip() or len(value) > limit or any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise InputError(f"{field} must be nonempty printable text within its length bound.")
    return value


def strict_local(value, zone):
    local = value.replace(tzinfo=zone, fold=0)
    if local.utcoffset() != local.replace(fold=1).utcoffset():
        raise InputError("An ambiguous local time needs an explicit UTC offset.")
    if local.astimezone(UTC).astimezone(zone).replace(tzinfo=None) != value:
        raise InputError("A nonexistent local time cannot be planned.")
    return local.astimezone(UTC)


def wall(day, value, zone):
    if not isinstance(value, str) or not re.fullmatch(r"(?:[01][0-9]|2[0-3]):[0-5][0-9]", value):
        raise InputError("Work times and deadlines must use HH:MM.")
    return strict_local(datetime.combine(day, time.fromisoformat(value)), zone)


def event_time(value, zone):
    if not isinstance(value, dict) or not isinstance(value.get("dateTime"), str):
        raise InputError("A timed event needs dateTime start and end objects.")
    try:
        result = datetime.fromisoformat(value["dateTime"])
        if result.tzinfo is None:
            return strict_local(result, ZoneInfo(value.get("timeZone") or str(zone)))
        return result.astimezone(UTC)
    except (ValueError, TypeError, ZoneInfoNotFoundError):
        raise InputError("Event dateTime/timeZone could not be verified; provide an explicit offset.") from None


def busy_intervals(events, zone, left, right, buffer_minutes):
    blocked = []
    buffer = timedelta(minutes=buffer_minutes)
    for event in events:
        if not isinstance(event, dict):
            raise InputError("Each event must be an object.")
        if "busy" in event and type(event["busy"]) is not bool:
            raise InputError("Event busy must be a boolean.")
        if event.get("busy") is False or event.get("status") == "cancelled" or event.get("transparency") == "transparent":
            continue
        start, end = event.get("start"), event.get("end")
        if not isinstance(start, dict) or not isinstance(end, dict):
            raise InputError("Every busy event needs start and end objects.")
        if any("date" in point and "dateTime" in point for point in (start, end)):
            raise InputError("An event time must use date or dateTime, not both.")
        if "date" in start or "date" in end:
            try:
                first, last = date.fromisoformat(start["date"]), date.fromisoformat(end["date"])
                beginning = datetime.combine(first, time.min, tzinfo=zone).astimezone(UTC)
                ending = datetime.combine(last, time.min, tzinfo=zone).astimezone(UTC)
            except (ValueError, KeyError, TypeError):
                raise InputError("All-day events need valid, exclusive start/end dates.") from None
        else:
            beginning, ending = event_time(start, zone), event_time(end, zone)
        if ending <= beginning:
            raise InputError("Event end must follow start.")
        beginning, ending = max(left, beginning - buffer), min(right, ending + buffer)
        if beginning < ending:
            blocked.append((beginning, ending))
    merged = []
    for beginning, ending in sorted(blocked):
        if merged and beginning <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(ending, merged[-1][1]))
        else:
            merged.append((beginning, ending))
    free, cursor = [], left
    for beginning, ending in merged:
        if cursor < beginning:
            free.append((cursor, beginning))
        cursor = max(cursor, ending)
    if cursor < right:
        free.append((cursor, right))
    return free


def interval(left, right, zone):
    return {"start": left.astimezone(zone).isoformat(timespec="seconds"),
            "end": right.astimezone(zone).isoformat(timespec="seconds"),
            "minutes": int((right - left).total_seconds() // 60)}


def plan(document):
    allowed = {"date", "timezone", "complete", "work_start", "work_end", "buffer_minutes", "focus_minutes", "events", "tasks"}
    if not isinstance(document, dict) or set(document) - allowed:
        raise InputError("Use an input object with only the documented fields.")
    try:
        day = date.fromisoformat(document["date"])
        zone = ZoneInfo(document["timezone"])
    except (ValueError, KeyError, TypeError, ZoneInfoNotFoundError):
        raise InputError("Provide a valid planning date and IANA timezone.") from None
    left = wall(day, document.get("work_start", "09:00"), zone)
    right = wall(day, document.get("work_end", "17:00"), zone)
    if right <= left:
        raise InputError("The work window must end later on the same day.")
    buffer = integer(document.get("buffer_minutes", 10), "buffer_minutes", 0, 60)
    focus = integer(document.get("focus_minutes", 25), "focus_minutes", 5, 120)
    events, tasks = document.get("events"), document.get("tasks")
    if not isinstance(events, list) or len(events) > 200 or not isinstance(tasks, list) or len(tasks) > 50:
        raise InputError("Supply at most 200 events and 50 tasks as arrays.")
    parsed, seen = [], set()
    for index, task in enumerate(tasks):
        if not isinstance(task, dict) or set(task) - {"id", "title", "minutes", "priority", "splittable", "deadline", "min_chunk_minutes"}:
            raise InputError("Each task must use only the documented task fields.")
        ident = text(task.get("id"), "task id", 80)
        if ident in seen:
            raise InputError("Task IDs must be unique.")
        seen.add(ident)
        minutes = integer(task.get("minutes"), "task minutes", 5, 480)
        priority = integer(task.get("priority", 3), "priority", 1, 5)
        split = task.get("splittable", False)
        minimum = integer(task.get("min_chunk_minutes", min(15, minutes, focus)), "min_chunk_minutes", 5, minutes)
        if type(split) is not bool or split and minimum > focus:
            raise InputError("Use a boolean splittable flag and a minimum chunk no larger than focus_minutes.")
        parsed.append({"id": ident, "title": text(task.get("title", ident), "task title", 120),
                       "minutes": minutes, "priority": priority, "splittable": split, "minimum": minimum,
                       "deadline": wall(day, task["deadline"], zone) if "deadline" in task else right, "index": index})
    if "complete" in document and type(document["complete"]) is not bool:
        raise InputError("complete must be a boolean.")
    result = {"date": day.isoformat(), "timezone": str(zone), "buffer_minutes": buffer, "focus_minutes": focus,
              "work_window": interval(left, right, zone), "blocks": [], "tasks": [],
              "assumptions": ["Priority 1 first; ties use deadline then input order.",
                              "The supplied event list is the only calendar evidence; proposals do not create events."]}
    if document.get("complete") is not True:
        result.update(status="needs_complete_calendar", tasks=[{"id": task["id"], "remaining_minutes": task["minutes"]} for task in parsed])
        return result
    free = busy_intervals(events, zone, left, right, buffer)
    result["available_before_planning"] = [interval(beginning, ending, zone) for beginning, ending in free]
    for task in sorted(parsed, key=lambda task: (task["priority"], task["deadline"], task["index"])):
        remaining = task["minutes"]
        for index in range(len(free)):
            beginning, ending = free[index]
            while remaining:
                capacity = int((min(ending, task["deadline"]) - beginning).total_seconds() // 60)
                if not task["splittable"]:
                    take = remaining if capacity >= remaining else 0
                else:
                    take = min(remaining, focus, capacity)
                    if 0 < remaining - take < task["minimum"]:
                        take -= task["minimum"] - (remaining - take)
                    if take < task["minimum"]:
                        take = 0
                if take <= 0:
                    break
                finish = beginning + timedelta(minutes=take)
                result["blocks"].append({"task_id": task["id"], "title": task["title"], **interval(beginning, finish, zone)})
                remaining -= take
                beginning = finish
                free[index] = (beginning, ending)
        result["tasks"].append({"id": task["id"], "requested_minutes": task["minutes"], "scheduled_minutes": task["minutes"] - remaining,
                                "remaining_minutes": remaining, "status": "planned" if remaining == 0 else "partial" if remaining < task["minutes"] else "unplaced"})
    result["blocks"].sort(key=lambda block: (datetime.fromisoformat(block["start"]).astimezone(UTC), block["task_id"]))
    result["remaining_intervals"] = [interval(beginning, ending, zone) for beginning, ending in free if beginning < ending]
    result["status"] = "planned" if all(task["remaining_minutes"] == 0 for task in result["tasks"]) else "partially_planned"
    return result


def main():
    parser = argparse.ArgumentParser(description="Propose focus blocks from supplied JSON; no account access or event writes.")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    try:
        raw = sys.stdin.buffer.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise InputError("Input exceeds the 2 MiB bound.")
        try:
            document = json.loads(raw)
        except (ValueError, UnicodeError):
            raise InputError("Input must be valid JSON.") from None
        print(json.dumps(plan(document), indent=2 if args.pretty else None, ensure_ascii=True))
        return 0
    except InputError as error:
        print(json.dumps({"status": "invalid_input", "error": str(error), "blocks": []}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
