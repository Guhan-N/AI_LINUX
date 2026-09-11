import tempfile
from pathlib import Path
from linagent.tools.memory.store import MemoryStore

def test_memory_store_and_recall():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_file = Path(tmpdir) / "test_memory.db"
        store = MemoryStore(db_path=str(db_file))

        # Store facts
        id1 = store.store("shell_preference", "User prefers zsh with starship prompt", category="preference")
        assert id1 > 0

        id2 = store.store("backup_script", "/var/scripts/backup.sh runs at 3am", category="context")
        assert id2 > 0

        # Store solution
        id3 = store.store(
            "nginx 502 bad gateway",
            "Check if php-fpm or gunicorn is running: systemctl status gunicorn",
            category="solution",
        )
        assert id3 > 0

        # Search
        results = store.search("starship")
        assert len(results) > 0
        assert "zsh" in results[0]["content"]

        # Search solution
        sol = store.search("nginx 502")
        assert len(sol) > 0
        assert "php-fpm" in sol[0]["content"]

        # List all
        all_mems = store.list_all()
        assert len(all_mems) == 3

        # Delete
        deleted = store.delete("shell_preference", "preference")
        assert deleted is True
        assert len(store.list_all()) == 2
