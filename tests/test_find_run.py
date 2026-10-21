import json

from scripts import find_run


def test_finds_runs_by_prefix_in_every_checkout(tmp_path):
    main, worktree = tmp_path / "main", tmp_path / "worktree"
    (main / "dist/bedrock-tests/ab12aaaa").mkdir(parents=True)
    (main / "dist/bedrock-tests/cd34aaaa").mkdir(parents=True)
    report = worktree / "dist/bedrock-tests/ab12bbbb/report.json"
    report.parent.mkdir(parents=True)
    report.write_text(json.dumps({"mode": "scenarios", "status": "passed"}))
    assert list(find_run.find_runs("ab12", [main, worktree, tmp_path / "removed"])) == [
        (main / "dist/bedrock-tests/ab12aaaa", {}),
        (worktree / "dist/bedrock-tests/ab12bbbb", {"mode": "scenarios", "status": "passed"}),
    ]
    assert list(find_run.find_runs("[a", [main])) == []
