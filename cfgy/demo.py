from cfgy import *


@configclass
class InputTable:
    """
    Settings for an individual input table.
    """

    tablename: str = RequireString(default=NODEFAULT, doc="Name of table")
    filename: str = RequireString()
    index_col: str = RequireString()
    rename_columns: dict = RequireDictOfStrTo(str)
    keep_columns: list = RequireSetOf(str)


@configclass
class OverallSettings:
    chunk_training_mode: str = Enumerated.Lowercase(
        ["disabled", "training", "production", "adaptive"]
    )
    household_sample_size: int = RequireInteger.NonNegative(
        doc="The number of households to sample."
    )
    chunk_size: int = RequireInteger.NonNegative()
    num_processes: int = RequireInteger.NonNegative()
    input_table_list: list = RequireListOf(InputTable)
    input_table_one: InputTable = RequireA(InputTable)
