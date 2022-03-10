import textwrap
import uuid

from pytest import fixture, raises

from cfgy import *


@configclass
class InputTable:
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
    input_table_one: list = RequireA(InputTable)


CONFIG_1 = """---
chunk_training_mode: training
household_sample_size: 1
input_table_list:
- tablename: Table1
  filename: File1
- tablename: Table2
  index_col: Index2
...
"""

CONFIG_2 = """---
household_sample_size: 2
input_table_list:
- tablename: Table3
...
"""

CONFIG_3 = """---
household_sample_size: 2
input_table_list:
- tablename: Table3
...
"""


@fixture
def yaml_files(tmp_path):
    d = tmp_path / "cfgy-test"
    d.mkdir()
    (d / "config-1.yaml").write_text(CONFIG_1)
    (d / "config-2.yaml").write_text(CONFIG_2)
    return d


def dump(pth, content):
    filename = str(uuid.uuid4())[:12] + ".yaml"
    out = pth / filename
    out.write_text(textwrap.dedent(content))
    return out


def test_one_file(tmp_path):
    f1 = dump(
        tmp_path,
        """
    tablename: MyTablename
    filename: MyFilename
    rename_columns:
        aa: bb
        zz: yy
    keep_columns:
      - bb
      - yy
    """,
    )
    i = InputTable.initialize(f1)
    assert isinstance(i, InputTable)
    assert i.tablename == "MyTablename"
    assert i.filename == "MyFilename"
    assert i.rename_columns == {"aa": "bb", "zz": "yy"}
    assert i.keep_columns == {"bb", "yy"}
    assert i.index_col is None
    assert InputTable.tablename.__doc__ == "Name of table"


def test_missing_required_value(tmp_path):
    f1 = dump(
        tmp_path,
        """
    filename: MyFilename
    rename_columns:
        aa: bb
        zz: yy
    keep_columns:
      - bb
      - yy
    """,
    )
    with raises(ValueError, match="'tablename' is required"):
        InputTable.initialize(f1)


def test_not_a_string(tmp_path):
    f1 = dump(
        tmp_path,
        """
    tablename: 123
    filename: MyFilename
    rename_columns:
        aa: bb
        zz: yy
    keep_columns:
      - bb
      - yy
    """,
    )
    with raises(TypeError, match="'tablename' values must be of type str"):
        InputTable.initialize(f1)


def test_bad_mapping_values(tmp_path):
    f1 = dump(
        tmp_path,
        """
    tablename: MyTable
    filename: MyFilename
    rename_columns:
        aa: 123
        zz: yy
    keep_columns:
      - bb
      - yy
    """,
    )
    with raises(TypeError, match="values for 'rename_columns' have to be str"):
        InputTable.initialize(f1)


def test_bad_mapping_keys(tmp_path):
    f1 = dump(
        tmp_path,
        """
    tablename: MyTable
    filename: MyFilename
    rename_columns:
        aa: bb
        123: yy
    keep_columns:
      - bb
      - yy
    """,
    )
    with raises(TypeError, match="items for 'rename_columns' have to be str"):
        InputTable.initialize(f1)


def test_overload(tmp_path):
    f1 = dump(
        tmp_path,
        """
    tablename: MyTablename
    filename: MyFilename
    rename_columns:
        aa: bb
        zz: yy
    keep_columns:
      - bb
      - yy
    """,
    )
    f2 = dump(
        tmp_path,
        """
    filename: MyFilenameOverloaded
    rename_columns:
        aa: gg
        cc: ff
    keep_columns:
      - gg
      - yy
    """,
    )
    i = InputTable.initialize(f1)
    i.overload(f2)
    assert isinstance(i, InputTable)
    assert i.tablename == "MyTablename"
    assert i.filename == "MyFilenameOverloaded"
    assert i.rename_columns == {"aa": "gg", "zz": "yy", "cc": "ff"}
    assert i.keep_columns == {"bb", "yy", "gg"}
    assert i.index_col is None


def test_underload(tmp_path):
    f1 = dump(
        tmp_path,
        """
    tablename: MyTablename
    filename: MyFilename
    rename_columns:
        aa: bb
        zz: yy
    keep_columns:
      - bb
      - yy
    """,
    )
    f2 = dump(
        tmp_path,
        """
    filename: MyFilenameOverloaded
    index_col: IndexCol
    rename_columns:
        aa: gg
        cc: ff
    keep_columns:
      - gg
      - yy
    """,
    )
    i = InputTable.initialize(f1)
    i.underload(f2)
    assert isinstance(i, InputTable)
    assert i.tablename == "MyTablename"
    assert i.filename == "MyFilename"
    assert i.rename_columns == {"aa": "bb", "zz": "yy"}
    assert i.keep_columns == {"bb", "yy"}
    assert i.index_col == "IndexCol"
