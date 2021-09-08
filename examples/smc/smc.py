import sys
sys.path.append("../../")

from engine import _and_, tags, oneof, rules, fixedpoint, CSVFileStream, drive
import csv
import brickschema
from brickschema.namespaces import BRICK, A, RDFS
from rdflib import Namespace, Literal
import json

G = brickschema.Graph()
SMC = Namespace("urn:smc#")
G.bind("smc", SMC)

point_types = {
    "ActFlow": BRICK.Supply_Air_Flow_Sensor,
    "DischargeTemp": BRICK.Discharge_Air_Temperature_Sensor,
    "MaxFlowHeatSP": BRICK.Air_Flow_Setpoint,
    "Reheat": BRICK.Heating_Command,
    "SpaceTemp": BRICK.Zone_Air_Temperature_Sensor,
    "SuppliedFanSpeedAHU1": BRICK.Speed_Command,
    "SuppliedFanSpeedAHU2": BRICK.Speed_Command,
    "OutsideTempAHU1": BRICK.Outside_Air_Temperature_Sensor,
    "OutsideTempAHU2": BRICK.Outside_Air_Temperature_Sensor,
    "SuppliedTempAHU1": BRICK.Supply_Air_Temperature_Sensor,
    "SuppliedTempAHU2": BRICK.Supply_Air_Temperature_Sensor,
    "boiler_flow": BRICK.Hot_Water_Supply_Flow_Sensor,
    "boiler_gas": BRICK.Gas_Sensor, # TODO
    "boiler_returnTemp": BRICK.Return_Water_Temperature_Sensor,
    "boiler_suppliedTemp": BRICK.Hot_Water_Supply_Temperature_Sensor,
}

@tags("AHU")
def add_ahu(row):
    ahu_name = row.get("AHU")
    G.add((SMC[ahu_name], A, BRICK.AHU))
    G.add((SMC[ahu_name], RDFS.label, Literal(row.get("AHU"))))

@_and_([tags, "AHU", "uuid"], [oneof, *["SuppliedFanSpeedAHU1", "SuppliedFanSpeedAHU2"]])
def add_ahu_sf(row):
    sf_name = "SupplyFan_" + row.get("AHU")
    G.add((SMC[sf_name], A, BRICK.Supply_Fan))
    G.add((SMC[sf_name], BRICK.isPartOf, SMC[row.get("AHU")]))
    if "SuppliedFanSpeedAHU1" in row:
        G.add((SMC[row.get("SuppliedFanSpeedAHU1")], BRICK.isPointOf, SMC[row.get("AHU")]))
    if "SuppliedFanSpeedAHU2" in row:
        G.add((SMC[row.get("SuppliedFanSpeedAHU2")], BRICK.isPointOf, SMC[row.get("AHU")]))

@_and_([tags, "AHU", "uuid"], [oneof, *point_types.keys()])
def ahu_points(row):
    ahu_name = row.get('AHU')
    for cls, brickclass in point_types.items():
        if cls in row:
            point = row.get(cls)
            G.add((SMC[point], A, brickclass))
            G.add((SMC[point], BRICK.timeseries, [
                (BRICK.hasTimeseriesId, Literal(row.get("uuid")))
            ]))
            G.add((SMC[ahu_name], BRICK.hasPoint, SMC[point]))

@tags("VAV")
def add_vav(row):
    vav_name = "VAV_" + row.get("VAV")
    zone_name = "Zone_" + row.get("VAV")
    G.add((SMC[vav_name], A, BRICK.VAV))
    G.add((SMC[vav_name], RDFS.label, Literal(row.get("VAV"))))
    G.add((SMC[zone_name], A, BRICK.HVAC_Zone))
    G.add((SMC[vav_name], BRICK.feeds, SMC[zone_name]))

@tags("VAV", "SpaceTemp")
def add_vav(row):
    vav_name = "VAV_" + row.get("VAV")
    zone_name = "Zone_" + row.get("VAV")
    G.add((SMC[zone_name], BRICK.hasPoint, SMC[row.get("SpaceTemp")]))

@tags("VAV", "Reheat")
def add_vav(row):
    vav_name = "VAV_" + row.get("VAV")
    G.add((SMC[vav_name], A, BRICK.RVAV))
    coil = "ReheatCoil_" + row.get("VAV")
    G.add((SMC[coil], A, BRICK.Reheat_Coil))
    G.add((SMC[vav_name], BRICK.hasPart, SMC[coil]))

@_and_([tags, "VAV", "uuid"], [oneof, *point_types.keys()])
def vav_points(row):
    vav_name = f"VAV_{row.get('VAV')}"
    for cls, brickclass in point_types.items():
        if cls in row:
            point = row.get(cls)
            G.add((SMC[point], A, brickclass))
            G.add((SMC[point], BRICK.timeseries, [
                (BRICK.hasTimeseriesId, Literal(row.get("uuid")))
            ]))
            G.add((SMC[vav_name], BRICK.hasPoint, SMC[point]))

@_and_([tags, "boiler", "uuid"], [oneof, *point_types.keys()])
@fixedpoint("G")
def add_boiler(row):
    boiler = row.get("boiler")
    G.add((SMC[boiler], A, BRICK.Boiler))
    for cls, brickclass in point_types.items():
        if cls in row:
            point = row.get(cls)
            G.add((SMC[point], A, brickclass))
            G.add((SMC[point], BRICK.timeseries, [
                (BRICK.hasTimeseriesId, Literal(row.get("uuid")))
            ]))
            G.add((SMC[boiler], BRICK.hasPoint, SMC[point]))
    G.update("""INSERT { ?boiler brick:feeds ?thing }
               WHERE {
                ?boiler a brick:Boiler .
                { ?thing a brick:Reheat_Coil } 
                UNION
                { ?thing a brick:AHU } 
               }""")

@tags("AHU")
@fixedpoint("G")
def ahu_feeds(row):
    print("ROW", row)
    ahu = row.get("AHU")
    idnum = ahu[-1]
    vavs = G.subjects(predicate=A, object=BRICK.VAV)
    for vav in vavs:
        label = list(G.objects(subject=vav, predicate=RDFS.label))[0]
        if label.startswith(idnum):
            G.add((SMC[ahu], BRICK.feeds, vav))

class SMCStream(CSVFileStream):
    def next(self):
        row = next(self.rdr)
        row[row.pop('equipment_type')] = row.pop('equipment_ID')
        row[row.pop('variable_type')] = row.pop('variable_name')
        return row

drive(SMCStream("metadata.csv"))
G.serialize("smc.ttl", format="ttl")
