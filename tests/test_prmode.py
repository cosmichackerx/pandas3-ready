import subprocess

import pytest

from pandas3_ready.cli import main

GIT = ["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid"]
OLD = "import pandas as pd\ndf = pd.DataFrame({'a': [1.0, None]})\ndf['a'].fillna(0, inplace=True)\n"


def git(cwd, *a):
    subprocess.run([*GIT, *a], cwd=cwd, check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path):
    git(tmp_path, "init", "-q", "-b", "main")
    (tmp_path / "job.py").write_text(OLD)
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-q", "-m", "base")
    return tmp_path


def test_existing_findings_are_not_new(repo, capsys):
    assert main([str(repo), "--base", "HEAD", "--fail-on", "warning"]) == 0
    assert "introduced since HEAD" in capsys.readouterr().out


def test_new_finding_fails_and_old_one_stays_hidden(repo, capsys):
    with open(repo / "job.py", "a") as fh:
        fh.write("df['a'][0] = 5\n")
    git(repo, "commit", "-q", "-am", "pr")
    rc = main([str(repo), "--base", "HEAD~1", "-f", "json", "--fail-on", "warning"])
    out = capsys.readouterr().out
    assert rc == 1 and "chained-assignment" in out and "chained-inplace" not in out


def test_moved_line_is_not_new(repo):
    (repo / "job.py").write_text("\n\n# note\n" + OLD)
    git(repo, "commit", "-q", "-am", "move")
    assert main([str(repo), "--base", "HEAD~1", "--fail-on", "warning"]) == 0


def test_notebook_findings_are_compared_too(repo, capsys):
    nb = '{"cells":[{"cell_type":"code","metadata":{},"outputs":[],"execution_count":null,"source":["import pandas as pd\\n","df = pd.DataFrame({\'a\': [1]})\\n","df[\'a\'][0] = 2\\n"]}],"metadata":{},"nbformat":4,"nbformat_minor":5}'
    (repo / "n.ipynb").write_text(nb)
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "nb")
    assert main([str(repo), "--base", "HEAD~1", "--fail-on", "warning"]) == 1
    assert "n.ipynb" in capsys.readouterr().out


def test_unknown_base_is_a_usage_error(repo):
    assert main([str(repo), "--base", "no-such-rev"]) == 2
