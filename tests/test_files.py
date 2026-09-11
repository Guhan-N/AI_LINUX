import tempfile
from pathlib import Path
from linagent.tools.files.manager import (
    read_file,
    write_file,
    append_file,
    search_files_by_name,
    search_text_in_files,
)

def test_file_operations():
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "sub" / "hello.txt"
        
        # Write
        w_res = write_file(str(test_file), "Line 1: Hello LinAgent\n")
        assert w_res.success is True
        assert test_file.exists()

        # Append
        a_res = append_file(str(test_file), "Line 2: Linux Automation\n")
        assert a_res.success is True

        # Read
        r_res = read_file(str(test_file))
        assert r_res.success is True
        assert "Hello LinAgent" in r_res.output
        assert "Linux Automation" in r_res.output

        # Search by name
        s_res = search_files_by_name(tmpdir, "*.txt")
        assert s_res.success is True
        assert "hello.txt" in s_res.output

        # Search text
        t_res = search_text_in_files(tmpdir, "Automation")
        assert t_res.success is True
        assert "Line 2: Linux Automation" in t_res.output
