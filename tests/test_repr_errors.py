"""Tests for __repr__, __str__, and error handling."""

import pytest
from sqlink import Query, F, Raw, Func, Case
from sqlink.expressions import Condition, And, Or, Not, Between, In, IsNull


class TestQueryRepr:
    def test_repr_select(self):
        q = Query("users").select("*")
        r = repr(q)
        assert "Query(" in r
        assert "SELECT" in r

    def test_repr_with_params(self):
        q = Query("users").select("*").where(F("id") == 1)
        r = repr(q)
        assert "params=" in r
        assert "[1]" in r

    def test_repr_no_params(self):
        q = Query("users").select("*")
        r = repr(q)
        assert "params" not in r

    def test_str_select(self):
        q = Query("users").select("*")
        assert "SELECT" in str(q)

    def test_str_insert(self):
        q = Query("users").insert("name").values({"name": "John"})
        assert "INSERT" in str(q)

    def test_str_update(self):
        q = Query("users").update(name="John")
        assert "UPDATE" in str(q)

    def test_str_delete(self):
        q = Query("users").delete()
        assert "DELETE" in str(q)


class TestExprRepr:
    def test_f_repr(self):
        assert "F(" in repr(F("name"))

    def test_raw_repr(self):
        assert "Raw(" in repr(Raw("COUNT(*)"))

    def test_condition_repr(self):
        c = Condition("age", ">", 18)
        assert "Condition(" in repr(c)

    def test_and_repr(self):
        e = (F("a") > 1) & (F("b") < 10)
        assert "And(" in repr(e)

    def test_or_repr(self):
        e = (F("a") > 1) | (F("b") < 10)
        assert "Or(" in repr(e)

    def test_not_repr(self):
        e = ~(F("a") > 1)
        assert "Not(" in repr(e)

    def test_between_repr(self):
        b = Between("age", 18, 65)
        assert "Between(" in repr(b)

    def test_in_repr(self):
        i = In("id", [1, 2, 3])
        assert "In(" in repr(i)

    def test_is_null_repr(self):
        n = IsNull("email")
        assert "IsNull(" in repr(n)

    def test_func_repr(self):
        f = Func("COUNT", "*")
        assert "Func(" in repr(f)

    def test_case_repr(self):
        c = Case().when(F("a") > 1, "yes")
        assert "Case(" in repr(c)


class TestErrorHandling:
    def test_unknown_query_type(self):
        q = Query("users")
        q._type = "MERGE"
        with pytest.raises(ValueError, match="Unknown query type"):
            q.build()

    def test_insert_empty_values(self):
        """Building INSERT with no values should still produce SQL."""
        q = Query("users").insert("name")
        # This will produce invalid SQL but shouldn't crash
        sql, params = q.build()
        assert "INSERT" in sql

    def test_query_without_table(self):
        """SELECT without table (for expressions like SELECT 1)."""
        sql, params = Query().select(Raw("1 + 1")).build()
        assert "SELECT 1 + 1" in sql

    def test_update_no_where_warning(self):
        """UPDATE without WHERE is valid but dangerous."""
        sql, params = Query("users").update(active=False).build()
        assert "WHERE" not in sql
        assert "UPDATE" in sql

    def test_delete_no_where(self):
        """DELETE without WHERE is valid but dangerous."""
        sql, params = Query("users").delete().build()
        assert "WHERE" not in sql
        assert "DELETE" in sql
