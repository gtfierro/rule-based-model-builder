import sys
sys.path.append("../../")
from engine import  tags,  values, fixedpoint, CSVFileStream, drive
import brickschema
from brickschema.namespaces import BRICK, A, RDFS, UNIT
from rdflib import Namespace, Literal

# TODO: process the components tab
# TODO: use https://github.com/IfcOpenShell/IfcOpenShell/blob/v0.7.0/src/ifccobie/cobie.py  (ignore the Writer)

G = brickschema.Graph()
EX = Namespace("ex:")
G.bind("ex", EX)

IFC = Namespace("ifc:")
G.bind("ifc", IFC)

# defaults
units = {
    "area": UNIT.M2,
    "linear": UNIT.M
}

unit_lookup = {
    "square meters": UNIT.M2,
    "square feet": UNIT.FT2,
    "millimeters": UNIT.MilliM,
    "meters": UNIT.M,
    "feet": UNIT.FT,
}

zone_category_lookup = {
    "Occupancy": BRICK.Zone,
}

@values({"Category": "Level", "ModelObject": "IfcBuildingStorey"})
def add_floors(row):
    floor_id = EX[row["ModelID"]]
    G.add((floor_id, RDFS.label, Literal(row["Name"])))
    G.add((floor_id, A, BRICK.Floor))
    G.add((floor_id, BRICK.elevation, [
        (BRICK.value, Literal(float(row["Elevation"]))),
        (BRICK.unit, units["linear"]),
    ]))
                        
@tags("AreaUnits", "LinearUnits")
def add_units(row):
    if row["AreaUnits"] in unit_lookup:
        units["area"] = unit_lookup[row["AreaUnits"]]
    else:
        print(f"Unknown area unit: {row['AreaUnits']}; defaulting to square meters")
    if row["LinearUnits"] in unit_lookup:
        units["linear"] = unit_lookup[row["LinearUnits"]]
    else:
        print(f"Unknown linear unit: {row['LinearUnits']}; defaulting to meters")

@tags("ProjectName", "Name")
def add_building(row):
    building_id = EX[row["ModelBuildingID"]]
    G.add((building_id, RDFS.label, Literal(row["Name"])))
    G.add((building_id, BRICK.IFCRepresentation, [(IFC.identifier, Literal(row["ModelBuildingID"]))]))
    G.add((building_id, A, BRICK.Building))

@tags("ProjectName", "Name")
@fixedpoint("G")
def add_building_floors(row):
    building_id = EX[row["ModelBuildingID"]]
    G.update(f"""INSERT {{ <{building_id}> brick:hasPart ?floor }}
                WHERE {{ ?floor a brick:Floor }}""")

@tags("LevelName", "ModelID", "AreaGross", "AreaNet")
def add_rooms(row):
    room_id = EX[row["ModelID"]]
    G.add((room_id, BRICK.IFCRepresentation, [(IFC.identifier, Literal(row["ModelID"]))]))
    G.add((room_id, RDFS.label, Literal(row["Name"])))
    G.add((room_id, RDFS.label, Literal(row["Description"])))
    G.add((room_id, A, BRICK.Space))
    if row["AreaGross"] != "NULL":
        G.add((room_id, BRICK.grossArea, [
            (BRICK.value, Literal(float(row["AreaGross"]))),
            (BRICK.unit, units["area"]),
        ]))
    if row["AreaNet"] != "NULL":
        G.add((room_id, BRICK.netArea, [
            (BRICK.value, Literal(float(row["AreaNet"]))),
            (BRICK.unit, units["area"]),
        ]))
    G.update(f"""INSERT {{ <{room_id}> brick:isPartOf ?floor }}
                WHERE {{ ?floor a brick:Floor . 
                        ?floor rdfs:label "{row['LevelName']}" }}""")

@tags("SpaceName", "ModelID", "Category")
def add_zones(row):
    zone_id = EX[row["ModelID"]]
    G.add((zone_id, BRICK.IFCRepresentation, [(IFC.identifier, Literal(row["ModelID"]))]))
    G.add((zone_id, RDFS.label, Literal(row["Name"])))
    G.add((zone_id, A, zone_category_lookup[row["Category"]]))
    G.update(f"""INSERT {{ <{zone_id}> brick:hasPart ?room }}
                WHERE {{ ?room a brick:Room . 
                        ?room rdfs:label "{row['SpaceName']}" }}""")

drive(CSVFileStream("facility.csv"),
      CSVFileStream("floor.csv"),
      CSVFileStream("room.csv"),
      CSVFileStream("zone.csv"))
valid, _, report = G.validate()
if not valid:
    print(report)
G.serialize("brick-ifc-example.ttl", format="turtle")
