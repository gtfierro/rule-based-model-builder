import sys
sys.path.append("../../")
from engine import _and_, tags, oneof, rules, JSONFileStream, drive

import brickschema
from brickschema.namespaces import BRICK, A
from rdflib import Namespace
import json

G = brickschema.Graph()
SODA = Namespace("urn:soda_hall#")
G.bind("soda", SODA)

point_types = {
    "alarm variable": BRICK.Alarm,
    "air volume": BRICK.Supply_Air_Flow_Sensor,
    "differential pressure status sensor": BRICK.Differential_Pressure_Sensor,
    "discharge air pressure sensor": BRICK.Discharge_Air_Static_Pressure_Sensor,
    "fan speed reset": BRICK.Speed_Reset_Command,
    "fan speed": BRICK.Speed_Command,
    "filtered air volume": BRICK.Discharge_Air_Flow_Sensor,
    "return air temp": BRICK.Return_Air_Temperature_Sensor,
    "start stop sensor": BRICK.Start_Stop_Command,
    "static pressure alarm": BRICK.Pressure_Alarm,
    "static pressure sensor": BRICK.Static_Pressure_Sensor,
    "static pressure setpoint": BRICK.Static_Pressure_Setpoint,
    "supply air temp": BRICK.Supply_Air_Temperature_Sensor,
    "supply air temp setpoint": BRICK.Supply_Air_Temperature_Setpoint,
    "status sensor": BRICK.Fan_Status,
    "smoke alarm": BRICK.Smoke_Detection_Alarm,
    "zone temp": BRICK.Zone_Air_Temperature_Sensor,
    "zone temp setpoint": BRICK.Zone_Air_Temperature_Setpoint,
}


#TODO: if tag is rawstring, treat as regex?
def tags(*tags):
    def _matches(func):
        def f(row):
            # match the tags
            for tag in tags:
                if tag not in row.keys():
                    return None
            return func(row)
        rules.append(f)
        return f
    return _matches

def oneof(*tags):
    s = set(tags)
    def _matches(func):
        def f(row):
            if len(set(row.keys()).intersection(s)) > 0:
                return func(row)
            return None
        rules.append(f)
        return f
    return _matches


def _and_(*_conds):
    def _matches(func):
        conds = []
        for _cond in _conds:
            cond = _cond[0](*_cond[1:])(lambda x: True)
            conds.append(cond)
        def f(row):
            for cond in conds:
                if cond(row) is None:
                    return None
            return func(row)
        if f is not None:
            rules.append(f)
        return f
    return _matches

        


@tags("site")
def add_site(row):
    sitename = row.get("site")
    G.add((SODA[sitename], A, BRICK.Site))

@tags("ahu")
def add_ahu(row):
    ahuname = row.get("ahu")
    G.add((SODA[ahuname], A, BRICK.AHU))

@tags("zone")
def add_zone_and_vav(row):
    zonename = row.get("zone")
    G.add((SODA[zonename], A, BRICK.HVAC_Zone))
    vavname = f"VAV_{zonename}"
    G.add((SODA[vavname], A, BRICK.VAV))
    G.add((SODA[vavname], BRICK.feeds, SODA[zonename]))

@tags("zone", "ahu")
def ahu_vav_topo(row):
    zonename = row.get("zone")
    ahuname = row.get("ahu")
    vavname = f"VAV_{zonename}"
    G.add((SODA[ahuname], BRICK.feeds, SODA[vavname]))

@_and_([tags, "ahu", "zone"], [oneof, *point_types.keys()])
def vav_points(row):
    zonename = row.get("zone")
    ahuname = row.get("ahu")
    vavname = f"VAV_{zonename}"
    G.add((SODA[ahuname], BRICK.feeds, SODA[vavname]))

    for tag, brickclass in point_types.items():
        if tag in row:
            sensor = row.get(tag)
            G.add((SODA[vavname + "_" + sensor], A, brickclass))
            G.add((SODA[vavname], BRICK.hasPoint, SODA[vavname + "_" + sensor]))
            break

@tags("zone", "ahu", "reheat valve position")
def vav_reheat(row):
    zonename = row.get("zone")
    pointname = row.get("reheat valve position")
    vavname = f"VAV_{zonename}"
    vlv = f"Reheat_Valve_{pointname}_{zonename}"
    G.add((SODA[vlv], A, BRICK.Reheat_Valve))
    G.add((SODA[vlv], BRICK.hasPoint, SODA[pointname]))
    G.add((SODA[vavname], BRICK.hasPart, SODA[vlv]))


@_and_([tags, "ahu", "exhaust fan"], [oneof, *point_types.keys()])
def ahu_ef(row):
    ahu = row.get("ahu")
    G.add((SODA[ahu], A, BRICK.AHU))

    ef = row.get("exhaust fan")
    G.add((SODA[ef], A, BRICK.Exhaust_Fan))
    G.add((SODA[ahu], BRICK.hasPart, SODA[ef]))

    for tag, brickclass in point_types.items():
        if tag in row:
            sensor = row.get(tag)
            G.add((SODA[ef + "_" + sensor], A, brickclass))
            G.add((SODA[ef], BRICK.hasPoint, SODA[ef + "_" + sensor]))
            break

@tags("ahu", "exhaust fan", "filtered air volume")
def ahu_ef_filter(row):
    ahu = row.get("ahu")
    G.add((SODA[ahu], A, BRICK.AHU))

    ef = row.get("exhaust fan")
    G.add((SODA[ef], A, BRICK.Exhaust_Fan))
    G.add((SODA[ahu], BRICK.hasPart, SODA[ef]))

    fil = ef + "_filter"
    G.add((SODA[fil], A, BRICK.Filter))
    G.add((SODA[ahu], BRICK.hasPart, SODA[fil]))
    G.add((SODA[ef], BRICK.feeds, SODA[fil]))

@oneof(*point_types.keys())
def define_point(row):
    for tag, brickclass in point_types.items():
        if tag in row:
            sensor = row.get(tag)
            G.add((SODA[sensor], A, brickclass))

@_and_([tags, "ahu", "supply fan"], [oneof, *point_types.keys()])
def ahu_sf(row):
    ahu = row.get("ahu")
    G.add((SODA[ahu], A, BRICK.AHU))

    ef = row.get("supply fan")
    G.add((SODA[ef], A, BRICK.Supply_Fan))
    G.add((SODA[ahu], BRICK.hasPart, SODA[ef]))

    for tag, brickclass in point_types.items():
        if tag in row:
            sensor = row.get(tag)
            G.add((SODA[ef + "_" + sensor], A, brickclass))
            G.add((SODA[ef], BRICK.hasPoint, SODA[ef + "_" + sensor]))
            break

@tags("ahu", "supply fan", "filtered air volume")
def ahu_ef_filter(row):
    ahu = row.get("ahu")
    G.add((SODA[ahu], A, BRICK.AHU))

    ef = row.get("supply fan")
    G.add((SODA[ef], A, BRICK.Supply_Fan))
    G.add((SODA[ahu], BRICK.hasPart, SODA[ef]))

    fil = ef + "_filter"
    G.add((SODA[fil], A, BRICK.Filter))
    G.add((SODA[ahu], BRICK.hasPart, SODA[fil]))
    G.add((SODA[ef], BRICK.feeds, SODA[fil]))

drive(JSONFileStream("rows.json"))

G.serialize("soda_hall.ttl", format="ttl")
