u=(units_of(2) or [None])[0]
mo=S(lambda: u.model)
P("MID 0x%x uid=%s pos=%r" % (S(lambda: id(mo)) or 0, S(lambda: u.uid), S(lambda: u.world_position)))
