from __future__ import annotations

import pytest
from pytest import param

import ibis.expr.types as ir
from ibis.backends.conftest import TEST_TABLES
from ibis.backends.tests.errors import PyDruidProgrammingError


def test_backend_name(backend):
    # backend is the TestConf for the backend
    assert backend.api.name == backend.name()


@pytest.mark.notyet(["druid"], raises=PyDruidProgrammingError)
@pytest.mark.notyet(["athena"], raises=NotImplementedError)
def test_version(backend):
    assert isinstance(backend.api.version, str)


# 1. `current_catalog` returns '.', but isn't listed in list_catalogs()
@pytest.mark.never(
    [
        "polars",
        "clickhouse",
        "sqlite",
        "exasol",
        "druid",
        "oracle",
        "bigquery",
        "mysql",
        "impala",
        "flink",
    ],
    reason="backend does not support catalogs",
    raises=AttributeError,
)
@pytest.mark.xfail_version(pyspark=["pyspark<3.4"])
def test_catalog_consistency(backend, con):
    catalogs = con.list_catalogs()
    assert isinstance(catalogs, list)
    assert len(catalogs) >= 1
    assert all(isinstance(catalog, str) for catalog in catalogs)

    # every backend has a different set of catalogs, not testing the
    # exact names for now
    current_catalog = con.current_catalog
    assert isinstance(current_catalog, str)
    if (name := backend.name()) in "snowflake":
        assert current_catalog.upper() in catalogs
    elif name == "athena":
        assert current_catalog.lower() in list(map(str.lower, catalogs))
    else:
        assert current_catalog in catalogs


def test_list_tables(con):
    tables = con.list_tables()
    assert isinstance(tables, list)
    # only table that is guaranteed to be in all backends
    key = "functional_alltypes"
    assert key in tables or key.upper() in tables
    assert all(isinstance(table, str) for table in tables)


def test_tables_accessor_mapping(con):
    if con.name == "snowflake":
        pytest.skip("snowflake sometimes counts more tables than are around")

    name = "functional_alltypes"

    assert isinstance(con.tables[name], ir.Table)

    with pytest.raises(KeyError, match="doesnt_exist"):
        con.tables["doesnt_exist"]

    # temporary might pop into existence in parallel test runs, in between the
    # first `list_tables` call and the second, so we check that there's a
    # non-empty intersection
    assert TEST_TABLES.keys() & set(map(str.lower, con.list_tables()))
    assert TEST_TABLES.keys() & set(map(str.lower, con.tables))


def test_tables_accessor_getattr(con):
    name = "functional_alltypes"
    assert isinstance(getattr(con.tables, name), ir.Table)

    with pytest.raises(AttributeError, match="doesnt_exist"):
        con.tables.doesnt_exist  # noqa: B018

    # Underscore/double-underscore attributes are never available, since many
    # python apis expect checking for the absence of these to be cheap.
    with pytest.raises(AttributeError, match="_private_attr"):
        con.tables._private_attr  # noqa: B018


def test_tables_accessor_tab_completion(con):
    name = "functional_alltypes"
    attrs = dir(con.tables)
    assert name in attrs
    assert "keys" in attrs  # type methods also present

    keys = con.tables._ipython_key_completions_()
    assert name in keys


def test_tables_accessor_repr(con):
    name = "functional_alltypes"
    result = repr(con.tables)
    assert f"- {name}" in result


@pytest.mark.parametrize(
    "expr_fn",
    [
        param(lambda t: t.limit(5).limit(10), id="small_big"),
        param(lambda t: t.limit(10).limit(5), id="big_small"),
    ],
)
def test_limit_chain(alltypes, expr_fn):
    expr = expr_fn(alltypes)
    result = expr.execute()
    assert len(result) == 5


@pytest.mark.parametrize(
    "expr_fn",
    [
        param(lambda t: t, id="alltypes table"),
        param(lambda t: t.join(t.view(), [("id", "int_col")]), id="self join"),
    ],
)
def test_unbind(alltypes, expr_fn):
    expr = expr_fn(alltypes)
    assert expr.unbind() != expr
    assert expr.unbind().schema() == expr.schema()

    assert "Unbound" not in repr(expr)
    assert "Unbound" in repr(expr.unbind())


def test_get_backend(con, alltypes):
    assert alltypes.get_backend() is con
    assert alltypes.id.min().get_backend() is con
