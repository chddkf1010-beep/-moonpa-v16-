"""Immutable portrait bindings for the shipped default seed-16 founding roster.

Portrait names/roles are checked to prevent attaching a face to a different
person after world generation rules change. Other seeds retain role art.
"""
FOUNDER_16 = {
    640: ("차자찬", 5),
    641: ("서문매휘", 4),
    642: ("표담별", 3),
    643: ("구은휘", 5),
    644: ("설민현", 4),
    645: ("마린온", 4),
    646: ("송하아", 3),
    647: ("문운희", 4),
    648: ("정준운", 5),
    649: ("정서아", 1),
    650: ("천소준", 0),
    651: ("표영현", 1),
    652: ("구희온", 1),
    653: ("안현수", 5),
    654: ("설경천", 5),
    655: ("독고정담", 0),
    656: ("조운별", 2),
    657: ("윤매진", 3),
    658: ("최희화", 5),
    659: ("정윤아", 0),
}


def assign_default_founder_portrait(seed, fighter):
    if seed != 16:
        return False
    identity = FOUNDER_16.get(fighter.fid)
    if identity != (fighter.name, fighter.role):
        return False
    # This property belongs to the Fighter, never the Guild.
    fighter.portrait_key = f"founders/seed16_{fighter.fid}.webp"
    return True


def portrait_asset(fighter):
    return f"assets/portraits/{fighter.portrait_key}" if fighter.portrait_key else ""
