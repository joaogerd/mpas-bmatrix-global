from mpas_workflow.wps import missing_surface_inventory_levels


INCOMPLETE_INVENTORY = """
PRES   TT        UU        VV        RH        HGT       PSFC      PMSL      SM000010  ST000010  SEAICE    LANDSEA   LANDN
-------------------------------------------------------------------------------
 850.0  X        X        X        X        X
 800.0  X        X        X        X        X
"""


COMPLETE_INVENTORY = """
PRES   TT        UU        VV        RH        HGT       PSFC      PMSL      SM000010  ST000010  SEAICE    LANDSEA   LANDN
-------------------------------------------------------------------------------
2013.0  O        O        O        O        O        O        X        O        O        O        O        O        O
2001.0  X        X        X        X        O        X        O        X        X        X        O        X        X
 850.0  X        X        X        X        X
"""


def test_missing_surface_inventory_levels_rejects_pressure_only_inventory():
    assert missing_surface_inventory_levels(INCOMPLETE_INVENTORY) == ["2013.0", "2001.0"]


def test_missing_surface_inventory_levels_accepts_gfs_surface_inventory():
    assert missing_surface_inventory_levels(COMPLETE_INVENTORY) == []
