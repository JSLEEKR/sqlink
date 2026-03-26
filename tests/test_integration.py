"""Integration tests — end-to-end scenarios."""

import json
import os
import tempfile
import pytest
from sqlink.cli import main


class TestAnalyzeIntegration:
    def test_analyze_with_index_suggestions(self):
        result = main(["analyze", "--suggest-indexes", "--no-color",
                       "SELECT * FROM users WHERE email = 'test@test.com'"])
        assert result in (0, 1)

    def test_analyze_with_rewrites(self):
        result = main(["analyze", "--suggest-rewrites", "--no-color",
                       "SELECT * FROM users"])
        assert result in (0, 1)

    def test_analyze_with_complexity(self):
        result = main(["analyze", "--complexity", "--no-color",
                       "SELECT * FROM a JOIN b ON a.id = b.a_id WHERE a.x = 1"])
        assert result in (0, 1)

    def test_analyze_with_patterns(self):
        result = main(["analyze", "--patterns", "--no-color",
                       "SELECT COUNT(*) FROM users WHERE email = 'x'"])
        assert result in (0, 1)

    def test_analyze_all_features_json(self, capsys):
        result = main(["analyze", "--format", "json",
                       "--suggest-indexes", "--suggest-rewrites",
                       "--complexity", "--patterns",
                       "SELECT * FROM users WHERE email = 'test@test.com'"])
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert "score" in data
        assert "index_suggestions" in data
        assert "rewrites" in data
        assert "complexity" in data
        assert "patterns" in data

    def test_analyze_clean_query(self, capsys):
        result = main(["analyze", "--format", "json",
                       "SELECT id, name FROM users WHERE id = 1 LIMIT 1"])
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["score"] >= 80


class TestBatchIntegration:
    def test_batch_with_n_plus_one(self, capsys):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".sql", delete=False) as f:
            f.write("""
SELECT * FROM orders WHERE user_id = 1;
SELECT * FROM orders WHERE user_id = 2;
SELECT * FROM orders WHERE user_id = 3;
SELECT * FROM orders WHERE user_id = 4;
            """)
            f.flush()
            result = main(["batch", f.name, "--format", "json"])
        os.unlink(f.name)
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["query_count"] == 4
        # Should detect N+1
        all_findings = []
        for r in data["results"]:
            all_findings.extend(r["findings"])
        rule_ids = [f["rule_id"] for f in all_findings]
        assert "NP001" in rule_ids

    def test_batch_mixed_queries(self, capsys):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".sql", delete=False) as f:
            f.write("""
SELECT id FROM users WHERE id = 1 LIMIT 1;
UPDATE users SET name = 'x';
SELECT * FROM a, b;
DELETE FROM logs;
            """)
            f.flush()
            result = main(["batch", f.name, "--format", "json"])
        os.unlink(f.name)
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["query_count"] == 4
        assert data["total_findings"] > 0


class TestFingerprintIntegration:
    def test_fingerprint_command(self, capsys):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".sql", delete=False) as f:
            f.write("""
SELECT * FROM users WHERE id = 1;
SELECT * FROM users WHERE id = 2;
SELECT * FROM users WHERE id = 3;
SELECT * FROM orders WHERE id = 1;
            """)
            f.flush()
            result = main(["fingerprint", f.name])
        os.unlink(f.name)
        assert result == 0

    def test_fingerprint_json(self, capsys):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".sql", delete=False) as f:
            f.write("SELECT * FROM t WHERE id = 1; SELECT * FROM t WHERE id = 2;")
            f.flush()
            result = main(["fingerprint", f.name, "--format", "json"])
        os.unlink(f.name)
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert len(data) >= 1
        assert data[0]["count"] >= 2

    def test_fingerprint_no_duplicates(self, capsys):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".sql", delete=False) as f:
            f.write("SELECT 1; DELETE FROM t;")
            f.flush()
            result = main(["fingerprint", f.name])
        os.unlink(f.name)
        assert result == 0


class TestPatternsIntegration:
    def test_patterns_command(self):
        result = main(["patterns"])
        assert result == 0

    def test_rules_command(self):
        result = main(["rules"])
        assert result == 0


class TestEndToEnd:
    def test_complex_real_world_query(self, capsys):
        sql = """
        SELECT u.id, u.name, COUNT(o.id) as order_count,
               SUM(o.total) as total_spent
        FROM users u
        LEFT JOIN orders o ON u.id = o.user_id
        LEFT JOIN order_items oi ON o.id = oi.order_id
        WHERE u.status = 'active'
        AND u.created_at > '2024-01-01'
        GROUP BY u.id, u.name
        HAVING COUNT(o.id) > 5
        ORDER BY total_spent DESC
        LIMIT 100
        """
        result = main(["analyze", "--format", "json",
                       "--suggest-indexes", "--complexity", sql])
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert "score" in data
        assert "complexity" in data
        assert data["complexity"]["level"] in ("medium", "high", "very high")

    def test_problematic_query(self, capsys):
        sql = "SELECT * FROM users, orders WHERE UPPER(users.name) LIKE '%test%' AND orders.total != 0"
        result = main(["analyze", "--format", "json", sql])
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["score"] < 70  # Should have many findings
        assert data["summary"]["total"] >= 3
